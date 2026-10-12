"""Free paper sources, searched in parallel, merged and de-duplicated.

OpenAlex, Semantic Scholar, arXiv, Crossref and Europe PMC need no API key.
Google Scholar (SerpApi) is added only if SERPAPI_KEY is set.
"""
import hashlib
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from . import db
from .config import CONTACT_EMAIL, OPENALEX_API_KEY, S2_API_KEY, SERPAPI_KEY
from .paper_model import (SOURCE_LABELS, clean_doi, new_paper, norm_title, safe_url, strip_tags)
from .serpapi_service import search_scholar_papers

TIMEOUT = 12
CACHE_SECONDS = 6 * 3600
UA = "ResearchIntelligencePlatform/1.0" + (f" (mailto:{CONTACT_EMAIL})" if CONTACT_EMAIL else "")

FREE_SOURCES = ["openalex", "semantic_scholar", "arxiv", "crossref", "europepmc"]


def available_sources():
    return FREE_SOURCES + (["google_scholar"] if SERPAPI_KEY else [])


def _get(url, params=None, headers=None, as_json=True, retries=1):
    h = {"User-Agent": UA, "Accept": "application/json" if as_json else "*/*"}
    h.update(headers or {})
    for attempt in range(retries + 1):
        r = requests.get(url, params=params, headers=h, timeout=TIMEOUT)
        if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
            time.sleep(1.5 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json() if as_json else r.text


def _inverted_to_text(inv):
    if not inv:
        return ""
    positions = {}
    for word, idxs in inv.items():
        for i in idxs:
            positions[i] = word
    return " ".join(positions[i] for i in sorted(positions))


# ---------------------------------------------------------------- OpenAlex
def parse_openalex(data):
    out = []
    for w in data.get("results", []) or []:
        loc = w.get("primary_location") or {}
        best = w.get("best_oa_location") or {}
        venue = ((loc.get("source") or {}).get("display_name")) or ""
        pdf = safe_url(best.get("pdf_url") or loc.get("pdf_url"))
        url = safe_url(loc.get("landing_page_url") or best.get("landing_page_url") or w.get("doi") or w.get("id"))
        wtype = w.get("type") or "article"
        ptype = {"review": "review", "preprint": "preprint"}.get(wtype, "article" if wtype in ("article", "book-chapter") else "other")
        out.append(new_paper(
            title=w.get("title") or w.get("display_name") or "", year=w.get("publication_year"),
            authors=[(a.get("author") or {}).get("display_name", "") for a in w.get("authorships", []) or []],
            venue=venue, doi=w.get("doi") or "", url=url, pdf_url=pdf,
            abstract=_inverted_to_text(w.get("abstract_inverted_index")),
            citations=w.get("cited_by_count"), is_oa=bool((w.get("open_access") or {}).get("is_oa")),
            type=ptype, source="openalex"))
    return out


def search_openalex(query, limit=25):
    params = {
        "search": query, "per-page": limit,
        "select": "id,doi,title,display_name,publication_year,cited_by_count,type,open_access,"
                  "primary_location,best_oa_location,authorships,abstract_inverted_index",
    }
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY
    elif CONTACT_EMAIL:
        params["mailto"] = CONTACT_EMAIL
    return parse_openalex(_get("https://api.openalex.org/works", params))


# --------------------------------------------------------- Semantic Scholar
def parse_semantic_scholar(data):
    out = []
    for p in data.get("data", []) or []:
        ext = p.get("externalIds") or {}
        types = p.get("publicationTypes") or []
        venue = p.get("venue") or ""
        ptype = "review" if "Review" in types else ("preprint" if venue.lower() == "arxiv" or (ext.get("ArXiv") and not venue) else "article")
        pdf = safe_url((p.get("openAccessPdf") or {}).get("url"))
        out.append(new_paper(
            title=p.get("title") or "", year=p.get("year"),
            authors=[a.get("name", "") for a in p.get("authors", []) or []],
            venue=venue, doi=ext.get("DOI") or "", url=safe_url(p.get("url")), pdf_url=pdf,
            abstract=p.get("abstract") or "", citations=p.get("citationCount"),
            is_oa=bool(p.get("isOpenAccess") or pdf), type=ptype, source="semantic_scholar",
            arxiv_id=ext.get("ArXiv") or ""))
    return out


def search_semantic_scholar(query, limit=25):
    params = {"query": query, "limit": limit,
              "fields": "title,abstract,year,venue,citationCount,authors,externalIds,openAccessPdf,url,publicationTypes,isOpenAccess"}
    headers = {"x-api-key": S2_API_KEY} if S2_API_KEY else {}
    return parse_semantic_scholar(_get("https://api.semanticscholar.org/graph/v1/paper/search", params, headers, retries=2))


# --------------------------------------------------------------------- arXiv
def parse_arxiv(xml_text):
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    out = []
    root = ET.fromstring(xml_text)
    for e in root.findall("a:entry", ns):
        id_url = e.findtext("a:id", "", ns)
        pdf = ""
        for link in e.findall("a:link", ns):
            if link.get("title") == "pdf":
                pdf = safe_url((link.get("href") or "").replace("http://", "https://"))
        journal = " ".join(e.findtext("x:journal_ref", "", ns).split())
        out.append(new_paper(
            title=e.findtext("a:title", "", ns), abstract=e.findtext("a:summary", "", ns),
            authors=[a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)],
            year=e.findtext("a:published", "", ns)[:4] or None, venue=journal or "arXiv preprint",
            doi=e.findtext("x:doi", "", ns), url=safe_url(id_url.replace("http://", "https://")),
            pdf_url=pdf, is_oa=True, type="preprint", source="arxiv",
            arxiv_id=id_url.split("/abs/")[-1] if "/abs/" in id_url else ""))
    return out


def search_arxiv(query, limit=15):
    words = re.findall(r"[A-Za-z0-9\-]+", query)[:8]
    if not words:
        return []
    q = " AND ".join(f"all:{w}" for w in words)
    text = _get("https://export.arxiv.org/api/query",
                {"search_query": q, "start": 0, "max_results": limit, "sortBy": "relevance"}, as_json=False)
    return parse_arxiv(text)


# ------------------------------------------------------------------ Crossref
def parse_crossref(data):
    out = []
    for it in (data.get("message") or {}).get("items", []) or []:
        authors = [" ".join(x for x in (a.get("given"), a.get("family")) if x) for a in it.get("author", []) or []]
        parts = ((it.get("issued") or {}).get("date-parts") or [[None]])[0]
        ctype = it.get("type", "")
        ptype = "preprint" if ctype == "posted-content" else ("article" if ctype in ("journal-article", "proceedings-article", "book-chapter") else "other")
        out.append(new_paper(
            title=(it.get("title") or [""])[0], authors=authors, year=parts[0] if parts else None,
            venue=(it.get("container-title") or [""])[0], doi=it.get("DOI") or "",
            url=safe_url(it.get("URL")), abstract=it.get("abstract") or "",
            citations=it.get("is-referenced-by-count"), type=ptype, source="crossref"))
    return out


def search_crossref(query, limit=20):
    params = {"query": query, "rows": limit,
              "select": "DOI,title,author,issued,container-title,is-referenced-by-count,abstract,URL,type"}
    if CONTACT_EMAIL:
        params["mailto"] = CONTACT_EMAIL
    return parse_crossref(_get("https://api.crossref.org/works", params))


# ---------------------------------------------------------------- Europe PMC
def parse_europepmc(data):
    out = []
    for r in (data.get("resultList") or {}).get("result", []) or []:
        pdf = ""
        for u in (r.get("fullTextUrlList") or {}).get("fullTextUrl", []) or []:
            if str(u.get("documentStyle", "")).lower() == "pdf":
                pdf = safe_url(u.get("url"))
                break
        doi, pmid = r.get("doi") or "", r.get("pmid") or ""
        url = f"https://doi.org/{clean_doi(doi)}" if doi else (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "")
        pub_types = " ".join((r.get("pubTypeList") or {}).get("pubType", []) or []).lower()
        authors = [a.strip() for a in (r.get("authorString") or "").rstrip(".").split(",") if a.strip()]
        out.append(new_paper(
            title=r.get("title") or "", authors=authors, year=r.get("pubYear"),
            venue=r.get("journalTitle") or "", doi=doi, url=safe_url(url), pdf_url=pdf,
            abstract=r.get("abstractText") or "", citations=r.get("citedByCount"),
            is_oa=r.get("isOpenAccess") == "Y", type="review" if "review" in pub_types else "article",
            source="europepmc"))
    return out


def search_europepmc(query, limit=20):
    params = {"query": query, "format": "json", "resultType": "core", "pageSize": limit}
    return parse_europepmc(_get("https://www.ebi.ac.uk/europepmc/webservices/rest/search", params))


SEARCHERS = {
    "openalex": search_openalex,
    "semantic_scholar": search_semantic_scholar,
    "arxiv": search_arxiv,
    "crossref": search_crossref,
    "europepmc": search_europepmc,
    "google_scholar": search_scholar_papers,
}


# --------------------------------------------------------------- merge logic
def _merge_into(base, other, src, score):
    if len(other["abstract"]) > len(base["abstract"]):
        base["abstract"] = other["abstract"]
    for field in ("pdf_url", "url", "venue", "doi", "arxiv_id"):
        if not base[field] and other[field]:
            base[field] = other[field]
    if base["year"] is None:
        base["year"] = other["year"]
    if len(other["authors"]) > len(base["authors"]):
        base["authors"] = other["authors"]
    if other["citations"] is not None:
        base["citations"] = max(base["citations"] or 0, other["citations"])
    base["is_oa"] = base["is_oa"] or other["is_oa"]
    if base["type"] in ("other", "article") and other["type"] in ("review", "preprint") and base["type"] != "review":
        base["type"] = other["type"]
    base["is_survey"] = base["is_survey"] or other["is_survey"]
    if src not in base["sources"]:
        base["sources"].append(src)
    base["score"] += score


def merge_results(results_by_source):
    """Reciprocal-rank fusion: papers found by several sources rise to the top."""
    merged, by_doi, by_title = [], {}, {}
    for src, papers in results_by_source.items():
        for rank, p in enumerate(papers):
            if not p["title"] or p["title"] == "Untitled paper":
                continue
            score = 1.0 / (60 + rank)
            tkey = norm_title(p["title"])
            hit = by_doi.get(p["doi"]) if p["doi"] else None
            hit = hit or by_title.get(tkey)
            if hit is None:
                p["score"] = score
                p["sources"] = [src]
                merged.append(p)
                if p["doi"]:
                    by_doi[p["doi"]] = p
                by_title[tkey] = p
            else:
                _merge_into(hit, p, src, score)
                if hit["doi"]:
                    by_doi[hit["doi"]] = hit
    from .paper_model import make_key
    for p in merged:
        p["key"] = make_key(p["doi"], p["title"])
    merged.sort(key=lambda p: p["score"], reverse=True)
    return merged


def search_all(query, sources=None, per_source=25):
    """Search every selected source in parallel. Never raises for one bad source."""
    query = (query or "").strip()
    sources = [s for s in (sources or available_sources()) if s in SEARCHERS]
    if not query or not sources:
        return {"query": query, "papers": [], "counts": {}, "errors": {}}
    ck = "search:" + hashlib.sha1(f"{query.lower()}|{','.join(sorted(sources))}|{per_source}".encode()).hexdigest()
    cached = db.cache_get(ck, max_age=CACHE_SECONDS)
    if cached:
        return cached
    results, errors = {}, {}
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        futures = {pool.submit(SEARCHERS[s], query, per_source): s for s in sources}
        for fut in as_completed(futures):
            s = futures[fut]
            try:
                results[s] = fut.result()
            except Exception as exc:  # one failing source must not break the search
                results[s], errors[s] = [], f"{type(exc).__name__}: {str(exc)[:160]}"
    out = {"query": query, "papers": merge_results(results),
           "counts": {s: len(results.get(s, [])) for s in sources}, "errors": errors}
    if out["papers"] and not errors:
        db.cache_set(ck, out)
    return out


def source_label(s):
    return SOURCE_LABELS.get(s, s)
