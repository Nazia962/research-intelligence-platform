"""Optional Google Scholar search through SerpApi (free plan: 250 searches/month).
Results are cached so repeated searches do not use up your quota."""
import re

from . import db
from .config import SERPAPI_KEY
from .paper_model import new_paper, safe_url

CACHE_SECONDS = 24 * 3600


class SerpError(Exception):
    """Friendly, user-showable SerpApi failure."""


def configured():
    return bool(SERPAPI_KEY)


def _search(params):
    """One call through the official SDK (pip install serpapi). Raises SerpError with a readable message."""
    if not SERPAPI_KEY:
        raise SerpError("SERPAPI_KEY is not set. Add it to your .env file (free plan: 250 searches/month).")
    import serpapi
    try:
        client = serpapi.Client(api_key=SERPAPI_KEY, timeout=20)
        return client.search(params)
    except serpapi.TimeoutError:
        raise SerpError("SerpApi took too long to answer. Try again.")
    except serpapi.HTTPError as exc:
        code = getattr(exc, "status_code", None)
        if code == 401:
            raise SerpError("SerpApi rejected the API key. Check SERPAPI_KEY in .env.")
        if code == 429:
            raise SerpError("SerpApi rate limit or monthly search credits used up (free plan: 250/month, 50/hour).")
        raise SerpError(f"SerpApi error ({code}): {str(getattr(exc, 'error', exc))[:120]}")
    except serpapi.SerpApiError as exc:
        raise SerpError(f"SerpApi error: {str(exc)[:120]}")


def search_scholar(query):
    """Raw SerpApi Google Scholar response (kept for backwards compatibility)."""
    return _search({"engine": "google_scholar", "q": query, "num": 20})


def parse_scholar(results):
    papers = []
    for r in results or []:
        info = r.get("publication_info") or {}
        summary = info.get("summary", "") or ""
        parts = [x.strip() for x in summary.split(" - ")]
        authors = [a.get("name", "") for a in info.get("authors", []) if isinstance(a, dict)]
        if not authors and parts and parts[0]:
            authors = [x.strip(" .…") for x in parts[0].split(",") if x.strip(" .…")]
        venue = ""
        if len(parts) > 1:
            venue = re.sub(r",?\s*\b(19|20)\d{2}\b.*$", "", parts[1]).strip()
        year_match = re.search(r"\b(19|20)\d{2}\b", summary)
        pdf = ""
        for res in r.get("resources", []) or []:
            if str(res.get("file_format", "")).upper() == "PDF":
                pdf = safe_url(res.get("link"))
                break
        cited = ((r.get("inline_links") or {}).get("cited_by") or {}).get("total")
        papers.append(new_paper(
            title=r.get("title", ""), authors=authors,
            year=year_match.group(0) if year_match else None, venue=venue,
            url=safe_url(r.get("link")), pdf_url=pdf, abstract=r.get("snippet", ""),
            citations=cited, is_oa=bool(pdf), source="google_scholar",
        ))
    return papers


def search_scholar_papers(query, limit=20):
    """Normalised paper list from Google Scholar. Returns [] if no key is set."""
    if not SERPAPI_KEY:
        return []
    cache_key = f"serpapi:{query.lower().strip()}"
    cached = db.cache_get(cache_key, max_age=CACHE_SECONDS)
    if cached is not None:
        return cached[:limit]
    try:
        raw = search_scholar(query)
    except SerpError as exc:
        raise RuntimeError(str(exc))
    papers = parse_scholar(list(raw.get("organic_results", [])))
    db.cache_set(cache_key, papers)
    return papers[:limit]


# ------------------------------------------------ web + news evidence (SerpApi)
def _evidence(kind, title, url, source, snippet="", date=""):
    return {"kind": kind, "title": " ".join(str(title or "").split())[:200], "url": safe_url(url),
            "source": str(source or "")[:80], "snippet": " ".join(str(snippet or "").split())[:400], "date": str(date or "")[:40]}


def parse_web(results):
    out = []
    for r in results or []:
        ev = _evidence("web", r.get("title"), r.get("link"), r.get("displayed_link") or r.get("source"), r.get("snippet"), r.get("date"))
        if ev["title"] and ev["url"]:
            out.append(ev)
    return out


def parse_news(results):
    out = []
    for r in results or []:
        src = r.get("source")
        src = src.get("name") if isinstance(src, dict) else src
        ev = _evidence("news", r.get("title"), r.get("link"), src, r.get("snippet"), r.get("date"))
        if ev["title"] and ev["url"]:
            out.append(ev)
    return out


def _cached_search(kind, query, params, key_field, parser, limit):
    ck = f"serpapi:{kind}:{query.lower().strip()}"
    cached = db.cache_get(ck, max_age=CACHE_SECONDS)
    if cached is not None:
        return cached[:limit], True
    raw = _search(params)
    items = parser(list(raw.get(key_field, []) or []))
    db.cache_set(ck, items)
    return items[:limit], False


def search_web(query, limit=8):
    """Google web results via SerpApi -> (items, from_cache). Items carry title, url, source, snippet, date."""
    return _cached_search("web", query, {"engine": "google", "q": query, "num": 10, "hl": "en"},
                          "organic_results", parse_web, limit)


def search_news(query, limit=8):
    """Recent Google News results via SerpApi -> (items, from_cache)."""
    return _cached_search("news", query, {"engine": "google_news", "q": query, "hl": "en"},
                          "news_results", parse_news, limit)


def search_scholar_evidence(query, limit=8):
    """Scholar hits in the same evidence format (used by the agent) -> (items, from_cache)."""
    ck = f"serpapi:{query.lower().strip()}"
    from_cache = db.cache_get(ck, max_age=CACHE_SECONDS) is not None
    try:
        papers = search_scholar_papers(query, limit)
    except RuntimeError as exc:
        raise SerpError(str(exc))
    return [_evidence("paper", p["title"], p.get("url") or p.get("pdf_url"), p.get("venue") or "Google Scholar",
                      p.get("abstract"), p.get("year") or "") for p in papers if p.get("title")], from_cache


# ------------------------------------------- patents (novelty) and trends (momentum)
def parse_patents(results):
    out = []
    for r in results or []:
        who = r.get("assignee") or r.get("inventor") or "Google Patents"
        ev = _evidence("patent", r.get("title"), r.get("patent_link"), who, r.get("snippet"),
                       r.get("filing_date") or r.get("publication_date"))
        if ev["title"] and ev["url"]:
            out.append(ev)
    return out


def search_patents(query, limit=6):
    """Google Patents via SerpApi: has anyone already patented this idea? -> (items, from_cache)."""
    return _cached_search("patents", query, {"engine": "google_patents", "q": query, "num": 10},
                          "organic_results", parse_patents, limit)


def parse_trends(raw, query):
    """Turn a TIMESERIES response into ONE evidence item with a computed, clearly-derived summary."""
    from urllib.parse import quote_plus
    rows = ((raw.get("interest_over_time") or {}).get("timeline_data")) or []
    vals = []
    for row in rows:
        v = (row.get("values") or [{}])[0].get("extracted_value")
        if isinstance(v, (int, float)):
            vals.append(v)
    if len(vals) < 6:
        return []
    third = max(1, len(vals) // 3)
    first, last = sum(vals[:third]) / third, sum(vals[-third:]) / third
    trend = "rising" if last > first * 1.15 else "falling" if last < first * 0.85 else "roughly flat"
    snippet = (f"Google Trends search interest (0-100) over the last 5 years: average {first:.0f} in the first third vs "
               f"{last:.0f} in the last third, so interest is {trend}. Computed from SerpApi data; it measures search interest, not research quality.")
    return [_evidence("trend", f"Google Trends: interest in '{query}'", f"https://trends.google.com/trends/explore?q={quote_plus(query)}&date=today%205-y",
                      "Google Trends", snippet, "last 5 years")]


def search_trends(query, limit=1):
    ck = f"serpapi:trends:{query.lower().strip()}"
    cached = db.cache_get(ck, max_age=CACHE_SECONDS)
    if cached is not None:
        return cached[:limit], True
    items = parse_trends(_search({"engine": "google_trends", "q": query[:100], "data_type": "TIMESERIES", "date": "today 5-y"}), query)
    db.cache_set(ck, items)
    return items[:limit], False
