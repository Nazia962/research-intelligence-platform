"""AI layer with three protections against running out of free quota:

1. Every answer is cached (identical request = instant, costs nothing).
2. If one model is out of quota or missing, the next model/provider is tried
   (Gemini models first, then optional free Groq / OpenRouter keys).
3. If everything fails the caller still gets an offline, extractive result built
   directly from the paper text, so the app never shows an error wall.
"""
import hashlib
import json
import re
import time
from dataclasses import dataclass

import requests

from . import db
from .config import (GEMINI_API_KEY, GEMINI_MODELS, GROQ_API_KEY, GROQ_MODEL,
                     OPENROUTER_API_KEY, OPENROUTER_MODEL)

try:
    from google import genai
except Exception:  # package missing: other providers / offline fallback still work
    genai = None

CONTENT_LIMIT = 30000
SMALL_MODEL_LIMIT = 18000
NOT_AVAILABLE = "Not available from the provided research information."
COOLDOWN_SECONDS = 120


@dataclass
class AIResult:
    text: str
    source: str            # "live" | "cache" | "offline" | "limit"
    model: str = ""
    note: str = ""

    @property
    def ok(self):
        return self.source in ("live", "cache")


class AIError(Exception):
    def __init__(self, kind, message=""):
        super().__init__(f"{kind}: {message}" if message else kind)
        self.kind = kind   # quota | unavailable | notfound | auth | no_key | other


_client = None
_dead_models = set()
_cooldown = {}


# ------------------------------------------------------------- providers
def _gemini_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _classify(exc):
    t = str(exc).upper()
    if "429" in t or "RESOURCE_EXHAUSTED" in t or "QUOTA" in t:
        return "quota"
    if "404" in t or "NOT_FOUND" in t:
        return "notfound"
    if "401" in t or "403" in t or "API_KEY" in t or "PERMISSION" in t:
        return "auth"
    if any(x in t for x in ("503", "500", "UNAVAILABLE", "OVERLOADED", "HIGH DEMAND", "TIMEOUT", "TIMED OUT")):
        return "unavailable"
    return "other"


def _call_gemini(model, prompt):
    try:
        resp = _gemini_client().models.generate_content(model=model, contents=prompt)
    except Exception as exc:
        raise AIError(_classify(exc), str(exc)[:200])
    text = getattr(resp, "text", None)
    if not text:
        raise AIError("other", "empty response")
    return text


def _call_openai_compatible(url, key, model, prompt):
    try:
        r = requests.post(
            url, timeout=90,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "temperature": 0.3,
                  "messages": [{"role": "user", "content": prompt[:SMALL_MODEL_LIMIT]}]})
    except requests.RequestException as exc:
        raise AIError("unavailable", str(exc)[:200])
    if r.status_code == 429:
        raise AIError("quota", r.text[:200])
    if r.status_code == 404:
        raise AIError("notfound", r.text[:200])
    if r.status_code in (401, 403):
        raise AIError("auth", r.text[:200])
    if r.status_code >= 500:
        raise AIError("unavailable", r.text[:200])
    if not r.ok:
        raise AIError("other", r.text[:200])
    try:
        return r.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError):
        raise AIError("other", "unexpected response")


def _chain():
    chain = []
    if GEMINI_API_KEY and genai:
        chain += [("gemini", m) for m in GEMINI_MODELS]
    if GROQ_API_KEY:
        chain.append(("groq", GROQ_MODEL))
    if OPENROUTER_API_KEY:
        chain.append(("openrouter", OPENROUTER_MODEL))
    return chain


def ai_providers():
    """Human-readable list of configured providers (for the sidebar)."""
    names = []
    if GEMINI_API_KEY and genai:
        names.append(f"Gemini ({len(GEMINI_MODELS)} model{'s' if len(GEMINI_MODELS) != 1 else ''})")
    if GROQ_API_KEY:
        names.append("Groq")
    if OPENROUTER_API_KEY:
        names.append("OpenRouter")
    return names


def _run_provider(provider, model, prompt):
    if provider == "gemini":
        return _call_gemini(model, prompt)
    if provider == "groq":
        return _call_openai_compatible("https://api.groq.com/openai/v1/chat/completions", GROQ_API_KEY, model, prompt)
    return _call_openai_compatible("https://openrouter.ai/api/v1/chat/completions", OPENROUTER_API_KEY, model, prompt)


_discovered = None


def _discover_gemini_models():
    """Ask Google which text models this key can use (flash first). Used only when every configured model 404s."""
    global _discovered
    if _discovered is None:
        _discovered = []
        try:
            names = []
            for m in _gemini_client().models.list():
                actions = getattr(m, "supported_actions", None) or ["generateContent"]
                n = m.name.replace("models/", "")
                if "generateContent" in actions and "flash" in n and not any(x in n for x in ("image", "tts", "live", "audio", "embed", "thinking", "preview-")):
                    names.append(n)
            # newest/lightest-looking first: stable names before dated ones, shorter first
            _discovered = sorted(set(names), key=lambda n: (any(c.isdigit() for c in n.split("-")[-1]) and "-0" in n, len(n)))[:4]
        except Exception:
            _discovered = []
    return _discovered


def _generate_live(prompt, _retry=True):
    chain = _chain()
    if not chain:
        raise AIError("no_key", "No AI key configured")
    kinds = []
    for provider, model in chain:
        ident = f"{provider}:{model}"
        if ident in _dead_models:
            continue
        if _cooldown.get(ident, 0) > time.time():
            kinds.append("quota")
            continue
        for attempt in range(2):
            try:
                return _run_provider(provider, model, prompt), ident
            except AIError as exc:
                if exc.kind == "unavailable" and attempt == 0:
                    time.sleep(2)
                    continue
                if exc.kind == "notfound":
                    _dead_models.add(ident)
                elif exc.kind in ("quota", "unavailable"):
                    _cooldown[ident] = time.time() + COOLDOWN_SECONDS
                kinds.append(exc.kind)
                break
    if _retry and GEMINI_API_KEY and genai and kinds and all(k == "notfound" for k in kinds):
        extra = [m for m in _discover_gemini_models() if f"gemini:{m}" not in _dead_models]
        if extra:                                   # configured names are stale: switch to models this key really has
            GEMINI_MODELS[:] = extra
            return _generate_live(prompt, _retry=False)
    if "quota" in kinds:
        raise AIError("quota")
    raise AIError(kinds[-1] if kinds else "other")


def _friendly(err):
    return {
        "no_key": "No AI key is set. Add GEMINI_API_KEY to your .env file to enable AI analysis.",
        "quota": "The free AI quota is used up for now (it resets daily). Results you generate later are cached.",
        "auth": "The AI API key was rejected. Check the key in your .env file.",
        "unavailable": "The AI service is busy right now. Please try again in a minute.",
    }.get(err.kind, "The AI service returned an error. Please try again shortly.")


def generate(task, prompt, fallback_text="", live_allowed=True):
    """Cache -> live AI chain -> offline fallback. Never raises."""
    ck = f"ai:{task}:{hashlib.sha1(prompt.encode('utf-8')).hexdigest()}"
    cached = db.cache_get(ck)
    if cached:
        return AIResult(cached["text"], "cache", cached.get("model", ""))
    if not live_allowed:
        return AIResult(fallback_text, "limit")
    try:
        text, model = _generate_live(prompt)
    except AIError as exc:
        return AIResult(fallback_text, "offline", note=_friendly(exc))
    db.cache_set(ck, {"text": text, "model": model})
    return AIResult(text, "live", model)


# ------------------------------------------------------------ prompt parts
def norm_mode(mode):
    return "Beginner" if "beginner" in str(mode).lower() else "Technical"


def _audience(mode):
    if norm_mode(mode) == "Beginner":
        return ("a first-time student. Use plain language and short sentences, define every technical term "
                "the first time it appears, and use simple analogies where they help.")
    return ("a researcher. Use precise terminology and discuss methodology, validity, baselines, metrics "
            "and reproducibility.")


def _paper_block(paper, text, limit=CONTENT_LIMIT):
    authors = ", ".join(paper.get("authors", [])[:10]) or "Unknown"
    cites = paper.get("citations")
    lines = [
        f"Title: {paper.get('title', 'Unknown')}", f"Authors: {authors}",
        f"Year: {paper.get('year') or 'Unknown'}", f"Venue: {paper.get('venue') or 'Unknown'}",
        f"DOI/Link: {paper.get('doi') or paper.get('url') or 'Unknown'}",
        f"Citation count: {cites if cites is not None else 'Unknown'}",
        "", "Abstract / snippet:", paper.get("abstract") or "(none available)",
    ]
    if text:
        lines += ["", "Full text (retrieved, may be partial):", text[:limit]]
    else:
        lines += ["", "Full text: NOT AVAILABLE - only the abstract and metadata above can be used."]
    return "\n".join(lines)


RULES = f"""RULES
- Use ONLY the material under "PAPER MATERIAL". Never invent facts, numbers, datasets, methods or citations.
- If something is not in the material write exactly: "{NOT_AVAILABLE}"
- Mark each claim as (From paper) when the material states it or (Inference) when you are interpreting.
- If only the abstract is available, say so in the first section."""


# ---------------------------------------------------------- offline helpers
METHOD_RX = r"(we (propose|present|develop|use|apply|train|design|introduce)\b|this (paper|study|work|article) (propos|present|us|introduc)\w*|\bmethod|\bapproach|framework|architecture|algorithm)"
DATA_RX = r"(dataset|data set|corpus|benchmark|participants|samples|collected|records|images)"
RESULT_RX = r"(achiev\w*|outperform\w*|accuracy|precision|recall|\bf1\b|improv\w*|results (show|demonstrate|indicate)|we (find|found|show|observe)\b)"
LIMIT_RX = r"(limitation|limited|future (work|research|stud)\w*|however|challeng\w*|\bremain\w*|\block\w*|unexplored|further research|not (yet|been))"


def _sentences(text):
    flat = re.sub(r"\s+", " ", text or "")
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"(])", flat)
    return [s.strip() for s in parts if 40 <= len(s.strip()) <= 420]


def pick_sentences(text, pattern, n=3):
    rx, out, seen = re.compile(pattern, re.I), [], set()
    for s in _sentences(text):
        if rx.search(s) and s.lower() not in seen:
            out.append(s)
            seen.add(s.lower())
        if len(out) >= n:
            break
    return out


def _bullets(items):
    return "\n".join(f"- {s}" for s in items) if items else f"- {NOT_AVAILABLE}"


OFFLINE_BANNER = ("> **Extractive summary (no AI was used).** These sentences were pulled directly from the "
                  "paper text using simple rules, so they may miss context. Generate again later for a full AI analysis.\n")


def offline_analysis(paper, text=""):
    body = f"{paper.get('abstract', '')} {text[:CONTENT_LIMIT]}"
    meta = " | ".join(x for x in (str(paper.get("year") or ""), paper.get("venue") or "") if x)
    return "\n".join([
        OFFLINE_BANNER, "## Paper Overview", f"**{paper.get('title', '')}**" + (f" ({meta})" if meta else ""), "",
        paper.get("abstract") or NOT_AVAILABLE, "",
        "## Methodology", _bullets(pick_sentences(body, METHOD_RX)), "",
        "## Dataset / Data", _bullets(pick_sentences(body, DATA_RX, 2)), "",
        "## Results / Findings", _bullets(pick_sentences(body, RESULT_RX)), "",
        "## Limitations", _bullets(pick_sentences(body, LIMIT_RX)),
    ])


def offline_gaps(paper, text=""):
    body = f"{paper.get('abstract', '')} {text[:CONTENT_LIMIT]}"
    limits = pick_sentences(body, LIMIT_RX, 5)
    ideas = "\n".join(f"- Investigate: *{s}*" for s in limits[:3]) or f"- {NOT_AVAILABLE}"
    return "\n".join([
        OFFLINE_BANNER, "## Explicit Limitations / Future Work Mentioned", _bullets(limits), "",
        "## Starting Points for Research Directions", ideas, "",
        "_These are statements the paper itself makes. Check the literature before treating any of them as a real gap._",
    ])


def offline_comparison(papers, texts=None):
    texts = texts or {}
    rows = []
    for p in papers:
        body = f"{p.get('abstract', '')} {texts.get(p['key'], '')[:6000]}"
        first = lambda rx: (pick_sentences(body, rx, 1) or [NOT_AVAILABLE])[0]
        sents = _sentences(p.get("abstract", ""))
        rows.append({"paper": p["title"][:80], "problem": sents[0] if sents else NOT_AVAILABLE,
                     "method": first(METHOD_RX), "dataset": first(DATA_RX),
                     "results": first(RESULT_RX), "limitations": first(LIMIT_RX)})
    return json.dumps({"papers": rows, "common_themes": "AI is unavailable, so no synthesis was generated.",
                       "key_differences": "Compare the extracted sentences in the table above.",
                       "opportunity": "Try again later for an AI-written synthesis."})


def _roadmap_rows(weeks):
    phases = [("Literature review and problem definition", .15), ("Reproduce a baseline", .20),
              ("Design and build your improvement", .30), ("Experiments and evaluation", .20),
              ("Report, paper and presentation", .15)]
    rows, prev = [], 0.0
    for name, frac in phases:
        a = int(weeks * prev) + 1
        b = max(a, round(weeks * (prev + frac)))
        rows.append(f"| {a}-{b} | {name} | Written notes / working result |")
        prev += frac
    return rows


def offline_plan(papers, params):
    weeks = int(params.get("weeks", 12))
    titles = "\n".join(f"- {p['title']}" for p in papers[:6]) or "- (no papers selected)"
    return "\n".join([
        "> **Template plan (no AI was used).** Generate again later for ideas tailored to your papers.\n",
        "## Papers this plan is based on", titles, "",
        "## Week-by-Week Roadmap", "| Week | Goal | Deliverable |", "|---|---|---|", *_roadmap_rows(weeks), "",
        "## Next Step", "Pick one limitation or future-work statement from the papers above and turn it into a single research question.",
    ])


# ------------------------------------------------------------- public tasks
def analyze_paper(paper, mode, paper_content="", live_allowed=True):
    last = ("## Beginner Explanation\nExplain the whole paper simply, step by step.\n\n## Key Terms\nDefine 4-6 technical terms used in the paper."
            if norm_mode(mode) == "Beginner" else
            "## Technical Analysis\nCritically assess the methodology, evaluation design, baselines and threats to validity.")
    prompt = f"""You are a research intelligence assistant. Write for {_audience(mode)}

{RULES}

Return Markdown with exactly these sections:
## Paper Overview
## Key Takeaways
(3-5 bullets)
## Research Problem
## Methodology
## Dataset / Data
## Results / Findings
## Limitations
## Research Opportunities
{last}

PAPER MATERIAL
{_paper_block(paper, paper_content)}"""
    return generate("analysis", prompt, offline_analysis(paper, paper_content), live_allowed)


def detect_research_gaps(paper, mode, paper_content="", live_allowed=True):
    prompt = f"""You are a research intelligence assistant helping identify research gaps. Write for {_audience(mode)}

{RULES}
- Never claim something is definitely a gap. Say "appears to be" and give a confidence (Low / Medium / High).
- For every Evidence line quote a short phrase (max 25 words) from the material in quotation marks, or write "(Inference)".

Return Markdown with exactly these sections:
## Research Scope
## Explicit Limitations
## Potential Research Gaps
(for each: ### Gap, **Why it matters**, **Evidence**, **Confidence**)
## Unanswered Research Questions
## Suggested Research Directions
(for each: ### Research Idea, **What to investigate**, **Difficulty** (Beginner / Intermediate / Advanced))
## Best Project Idea
## Novelty Check
(3-5 search queries the user should run to confirm each gap is not already filled)

PAPER MATERIAL
{_paper_block(paper, paper_content)}"""
    return generate("gaps", prompt, offline_gaps(paper, paper_content), live_allowed)


COMPARE_KEYS = ("problem", "method", "dataset", "results", "limitations")


def compare_papers(papers, texts, mode, live_allowed=True):
    budget = max(1500, 24000 // max(1, len(papers)))
    blocks = "\n\n".join(f"=== PAPER {i} ===\n{_paper_block(p, texts.get(p['key'], ''), budget)}"
                         for i, p in enumerate(papers, 1))
    prompt = f"""You are a research intelligence assistant comparing {len(papers)} papers for {_audience(mode)}

{RULES}
- Keep every field under 40 words.
- Return ONLY valid JSON, with no markdown fences, in exactly this shape and with papers in the same order:
{{"papers":[{{"paper":"<short title>","problem":"","method":"","dataset":"","results":"","limitations":""}}],
 "common_themes":"","key_differences":"","opportunity":""}}

PAPER MATERIAL
{blocks}"""
    return generate("compare", prompt, offline_comparison(papers, texts), live_allowed)


def parse_comparison(text):
    """Tolerant JSON parse of a comparison answer. Returns dict or None."""
    s = re.sub(r"^```(?:json)?|```$", "", str(text or "").strip(), flags=re.M).strip()
    start, end = s.find("{"), s.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(s[start:end + 1])
    except ValueError:
        return None
    rows = data.get("papers")
    if not isinstance(rows, list) or not rows:
        return None
    clean = []
    for r in rows:
        if isinstance(r, dict):
            row = {"paper": str(r.get("paper", "")) or "Paper"}
            row.update({k: str(r.get(k, "")) or NOT_AVAILABLE for k in COMPARE_KEYS})
            clean.append(row)
    return {"papers": clean, **{k: str(data.get(k, "")) for k in ("common_themes", "key_differences", "opportunity")}} if clean else None


def plan_project(papers, gaps_text, params, mode, live_allowed=True):
    weeks = int(params.get("weeks", 12))
    context = "\n\n".join(
        f"[{i}] {p['title']} ({p.get('year') or 'n.d.'})\n{(p.get('abstract') or '(no abstract)')[:900]}"
        for i, p in enumerate(papers[:6], 1))
    gaps = (gaps_text or "")[:6000]
    prompt = f"""You are a research mentor helping a student turn research gaps into a project that can actually be finished. Write for {_audience(mode)}

{RULES}
- Base the project ideas ONLY on the papers and gap notes below.
- Any dataset, library or tool you suggest must be a well-known, publicly available resource; add "(verify availability)" after it.
- Be realistic for: {params.get('project_type', 'Final-year project')}, {weeks} weeks, team of {params.get('team', 1)}, skill level {params.get('level', 'Beginner')}, constraints: {params.get('constraints') or 'none stated'}.

Return Markdown with exactly these sections:
## Project Ideas
(3 ideas; for each: ### Title, **Objective**, **Why it is a gap** (cite the paper numbers), **Approach**, **Data**, **Tools**, **Difficulty**, **Expected outcome**)
## Recommended Project
(choose one and justify it)
## Week-by-Week Roadmap
(a Markdown table with columns Week | Goal | Deliverable covering all {weeks} weeks)
## Evaluation Plan
## Risks and Fallbacks
## Novelty Check
(search queries to confirm the idea is not already done)
## How to Present It
(outline for a viva or short paper)

PAPER MATERIAL
{context}

GAP NOTES
{gaps or '(none provided - identify gaps from the papers yourself and label them as Inference)'}"""
    return generate("plan", prompt, offline_plan(papers, params), live_allowed)