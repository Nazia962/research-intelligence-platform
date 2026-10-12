"""Getting readable text for a paper: open-access PDFs, publisher pages, and
PDFs uploaded by the user. Everything successful is cached."""
import hashlib
import io
import ipaddress
import re
import socket
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

from . import db
from .config import CONTACT_EMAIL
from .paper_model import new_paper

MAX_BYTES = 15 * 1024 * 1024
MAX_TEXT = 60000
MIN_USEFUL_CHARS = 500
TIMEOUT = 20
FETCH_OK_SECONDS = 7 * 86400
FETCH_FAIL_SECONDS = 900
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120 Safari/537.36"),
    "Accept": "text/html,application/pdf,*/*",
}


# ---------------------------------------------------------------- helpers
def clean_text(text):
    text = str(text or "").replace("\x00", "")
    text = re.sub(r"-\n(?=[a-z])", "", text)          # join hyphenated line breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_safe_url(url):
    """Refuse non-http(s) URLs and anything that resolves to a private address."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        for info in socket.getaddrinfo(parsed.hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        return True
    except (OSError, ValueError):
        return False


def extract_pdf_text(data, max_pages=40):
    """Text of the first pages of a PDF. Returns '' for scanned/encrypted files."""
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        parts = []
        for i, page in enumerate(reader.pages):
            if i >= max_pages:
                break
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        return clean_text("\n".join(parts))[:MAX_TEXT]
    except Exception:
        return ""


def extract_abstract_from_text(text):
    """Best-effort pull of a clearly labelled abstract out of page/PDF text."""
    if not text:
        return ""
    flat = re.sub(r"\s+", " ", str(text)).strip()
    patterns = [
        r"(?i)\babstract\b\s*[:.\-—]?\s*(.{100,4000}?)(?=\b(?:keywords?|key words|index terms|introduction|1\.? introduction|background)\b)",
        r"(?i)\babstract\b\s*[:.\-—]?\s*(.{150,2500})",
    ]
    for pattern in patterns:
        m = re.search(pattern, flat)
        if m and len(m.group(1).strip()) >= 100:
            return m.group(1).strip(" .:-")[:3500]
    return ""


def _download(url):
    with requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True) as r:
        r.raise_for_status()
        ctype = r.headers.get("Content-Type", "").lower()
        buf = bytearray()
        for chunk in r.iter_content(65536):
            buf.extend(chunk)
            if len(buf) > MAX_BYTES:
                raise ValueError("file is larger than 15 MB")
        return bytes(buf), ctype


def fetch_paper_content(url):
    """Download one URL (PDF or web page) and return its readable text.

    Returns {"success": bool, "text": str, "message": str}.
    """
    if not url:
        return {"success": False, "text": "", "message": "No paper URL available."}
    if not _is_safe_url(url):
        return {"success": False, "text": "", "message": "That link cannot be fetched safely."}
    try:
        data, ctype = _download(url)
        if "pdf" in ctype or data[:5] == b"%PDF-":
            text = extract_pdf_text(data)
        else:
            soup = BeautifulSoup(data.decode("utf-8", errors="ignore"), "html.parser")
            for el in soup(["script", "style", "nav", "footer", "header", "form", "noscript"]):
                el.decompose()
            text = clean_text(soup.get_text(separator=" ", strip=True))[:MAX_TEXT]
        if len(text) < MIN_USEFUL_CHARS:
            return {"success": False, "text": "", "message": "No readable paper text (it may be behind a paywall)."}
        return {"success": True, "text": text, "message": "Paper text retrieved."}
    except requests.HTTPError as exc:
        status = getattr(exc.response, "status_code", None)
        if status == 403:
            message = "Publisher blocked automated full-text access (HTTP 403). Try an open-access repository copy or use the available abstract."
        elif status == 429:
            message = "The source rate-limited this request. Please retry later or use the available abstract."
        else:
            message = f"Paper source returned HTTP {status or 'error'}. Try an open-access copy or use the available abstract."
        return {"success": False, "text": "", "message": message}
    except Exception as exc:
        return {"success": False, "text": "", "message": f"Could not retrieve the paper: {str(exc)[:150]}"}


def _unpaywall_pdf(doi):
    """Find a legitimate open-access PDF/landing page for a DOI."""
    if not (doi and CONTACT_EMAIL):
        return ""
    doi = str(doi).strip()
    doi = re.sub(r"^https?://doi\.org/", "", doi, flags=re.I)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.I)
    try:
        endpoint = f"https://api.unpaywall.org/v2/{quote(doi, safe='/')}"
        r = requests.get(endpoint, params={"email": CONTACT_EMAIL}, headers=HEADERS, timeout=8)
        if not r.ok:
            return ""
        payload = r.json()
        locations = payload.get("oa_locations") or []
        best = payload.get("best_oa_location") or {}
        ordered = ([best] if best else []) + locations
        seen = set()
        for location in ordered:
            candidate = location.get("url_for_pdf") or location.get("url") or ""
            if candidate and candidate not in seen:
                seen.add(candidate)
                return candidate
    except (requests.RequestException, ValueError, TypeError):
        pass
    return ""


def get_full_text(paper):
    """Best available full text for a paper.

    Order: PDF the user uploaded -> cached copy -> open-access PDF -> Unpaywall ->
    arXiv PDF -> publisher page.  Returns {"success","text","source","message"}.
    """
    key = paper.get("key", "")
    stored = db.fulltext_get(key) if key else ""
    if stored:
        return {"success": True, "text": stored, "source": "uploaded PDF", "message": "Using the PDF text you provided."}
    cached = db.cache_get(f"fetch:{key}", max_age=FETCH_OK_SECONDS)
    if cached and cached.get("success"):
        return cached
    failed = db.cache_get(f"fetch:{key}", max_age=FETCH_FAIL_SECONDS)
    if failed and not failed.get("success"):
        return failed

    candidates = []
    if paper.get("pdf_url"):
        candidates.append(("open-access PDF", paper["pdf_url"]))
    if paper.get("arxiv_id"):
        candidates.append(("arXiv PDF", f"https://arxiv.org/pdf/{paper['arxiv_id']}"))
    up = _unpaywall_pdf(paper.get("doi"))
    if up:
        candidates.append(("Unpaywall open-access copy", up))
    if paper.get("url"):
        candidates.append(("publisher page", paper["url"]))

    seen, last_msg = set(), "No accessible full text link was found."
    for label, url in candidates:
        if url in seen:
            continue
        seen.add(url)
        res = fetch_paper_content(url)
        if res["success"]:
            out = {"success": True, "text": res["text"], "source": label, "message": f"Text retrieved from the {label}."}
            db.cache_set(f"fetch:{key}", out)
            return out
        last_msg = res["message"]
    out = {
        "success": False,
        "text": "",
        "source": "",
        "message": (
            "Full text could not be retrieved from the available links. "
            "The publisher may restrict automated access. Try an open-access copy "
            "or analyze the available title and abstract."
        ),
    }
    if key:
        db.cache_set(f"fetch:{key}", out)
    return out


# ------------------------------------------------------------ PDF uploads
def attach_pdf_to_paper(paper, data):
    """Store text from a user-supplied PDF for an existing paper."""
    text = extract_pdf_text(data)
    if len(text) < MIN_USEFUL_CHARS:
        return False, "No selectable text found. Scanned PDFs need OCR, which is not supported yet."
    db.fulltext_set(paper["key"], text)
    return True, f"PDF read successfully ({len(text):,} characters)."


def make_uploaded_paper(filename, data):
    """Build a paper record from a standalone uploaded PDF."""
    from pypdf import PdfReader
    text = extract_pdf_text(data)
    if len(text) < MIN_USEFUL_CHARS:
        return None, "No selectable text found. Scanned PDFs need OCR, which is not supported yet."
    title, authors = "", []
    try:
        meta = PdfReader(io.BytesIO(data)).metadata
        if meta:
            title = (meta.title or "").strip()
            authors = [a.strip() for a in re.split(r"[;,]| and ", meta.author or "") if a.strip()]
    except Exception:
        pass
    if len(title) < 8:
        first = next((ln.strip() for ln in text.splitlines() if 12 <= len(ln.strip()) <= 200), "")
        title = first or re.sub(r"\.pdf$", "", filename or "Uploaded paper", flags=re.I)
    paper = new_paper(
        title=title, authors=authors, venue="Uploaded PDF", abstract=extract_abstract_from_text(text),
        source="upload", type="article", key=hashlib.sha1(data).hexdigest()[:12])
    paper["uploaded"] = True
    db.fulltext_set(paper["key"], text)
    return paper, f"PDF read successfully ({len(text):,} characters)."
