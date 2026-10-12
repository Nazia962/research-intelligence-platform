"""One common shape for a paper, whichever source it came from."""
import hashlib
import re

SOURCE_LABELS = {
    "openalex": "OpenAlex",
    "semantic_scholar": "Semantic Scholar",
    "arxiv": "arXiv",
    "crossref": "Crossref",
    "europepmc": "Europe PMC",
    "google_scholar": "Google Scholar",
    "upload": "Uploaded PDF",
}

SURVEY_RE = re.compile(
    r"\b(survey|review|overview|systematic|state[- ]of[- ]the[- ]art|tutorial|taxonomy|roadmap)\b", re.I)
TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(text):
    text = TAG_RE.sub(" ", str(text or ""))
    return re.sub(r"\s+", " ", text).strip()


def norm_title(title):
    return re.sub(r"[^a-z0-9]+", " ", str(title or "").lower()).strip()


def clean_doi(doi):
    doi = str(doi or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi


def make_key(doi, title):
    basis = clean_doi(doi) or norm_title(title)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def new_paper(**kw):
    p = {
        "key": "", "title": "", "authors": [], "year": None, "venue": "", "doi": "",
        "url": "", "pdf_url": "", "abstract": "", "citations": None, "is_oa": False,
        "type": "article", "source": "", "sources": [], "score": 0.0, "arxiv_id": "",
        "uploaded": False,
    }
    p.update({k: v for k, v in kw.items() if v is not None})
    p["title"] = re.sub(r"\s+", " ", strip_tags(p["title"])) or "Untitled paper"
    p["doi"] = clean_doi(p["doi"])
    p["abstract"] = strip_tags(p["abstract"])
    p["authors"] = [a.strip() for a in p["authors"] if a and a.strip()]
    if p["year"] is not None:
        try:
            p["year"] = int(p["year"])
        except (TypeError, ValueError):
            p["year"] = None
    if p["citations"] is not None:
        try:
            p["citations"] = int(p["citations"])
        except (TypeError, ValueError):
            p["citations"] = None
    if not p["sources"] and p["source"]:
        p["sources"] = [p["source"]]
    p["is_survey"] = p["type"] == "review" or bool(SURVEY_RE.search(p["title"]))
    p["key"] = p["key"] or make_key(p["doi"], p["title"])
    return p


def safe_url(url):
    url = str(url or "").strip()
    return url if url.lower().startswith(("http://", "https://")) else ""


def publication_text(p):
    bits = [x for x in (p.get("venue"), str(p["year"]) if p.get("year") else "") if x]
    return " · ".join(bits) if bits else "Publication details not available"


def authors_text(p, limit=6):
    names = p.get("authors") or []
    if not names:
        return "Authors not listed"
    text = ", ".join(names[:limit])
    return text + (f" +{len(names) - limit} more" if len(names) > limit else "")
