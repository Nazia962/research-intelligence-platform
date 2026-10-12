"""Live smoke test: calls each real service once and prints PASS/FAIL. Never prints your keys.

Run from the project folder (with your .env filled in):   python scripts/smoke_test.py
Uses a throw-away database so cached answers cannot hide a failure. Uses about 5 SerpApi credits.
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "smoke.db")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import ai_service, config, serpapi_service as sp, sources  # noqa: E402

Q = "explainable AI intrusion detection"
results = []


def check(name, fn):
    try:
        out = fn()
        results.append((name, True, out))
    except Exception as exc:                                    # report, never crash
        results.append((name, False, f"{type(exc).__name__}: {str(exc)[:900]}"))


def serp(fn, q=Q):
    def run():
        items, _ = fn(q)
        assert items, "0 results"
        return f"{len(items)} results, e.g. {items[0]['title'][:60]!r} -> {items[0]['url'][:50]}"
    return run


print(f"SERPAPI_KEY set: {bool(config.SERPAPI_KEY)} | GEMINI_API_KEY set: {bool(config.GEMINI_API_KEY)}\n")
check("SerpApi: Google Scholar", serp(sp.search_scholar_evidence))
check("SerpApi: Google Search", serp(sp.search_web))
check("SerpApi: Google News", serp(sp.search_news))
check("SerpApi: Google Patents", serp(sp.search_patents))
check("SerpApi: Google Trends", serp(sp.search_trends, "explainable AI"))


def free_sources():
    out = sources.search_all(Q, [s for s in sources.FREE_SOURCES], per_source=5)
    ok = {s: n for s, n in out["counts"].items() if n}
    assert ok, f"no source answered: {out['errors']}"
    return f"{len(out['papers'])} merged papers; answered: {ok}; failed: {list(out['errors'])}"


check("Free paper sources (OpenAlex, S2, arXiv, Crossref, Europe PMC)", free_sources)


def gemini():
    """Try every configured model separately so you can see exactly which one fails and why."""
    notes, worked = [], None
    for provider, model in ai_service._chain():
        try:
            text = ai_service._run_provider(provider, model, "Reply with exactly the word: ready")
            notes.append(f"OK    {provider}:{model} -> {text.strip()[:20]!r}")
            worked = worked or f"{provider}:{model}"
        except ai_service.AIError as exc:
            notes.append(f"FAIL  {provider}:{model} -> {str(exc)[:160]}")
    if not worked:
        try:                                            # same path the app uses, including automatic model discovery
            text, model = ai_service._generate_live("Reply with exactly the word: ready")
            notes.append(f"OK    app auto-picked a working model: {model} -> {text.strip()[:20]!r}")
            worked = model
        except ai_service.AIError as exc:
            notes.append(f"FAIL  automatic model discovery -> {exc}")
    if config.GEMINI_API_KEY and ai_service.genai:
        try:
            names = [m.name.replace("models/", "") for m in ai_service._gemini_client().models.list()
                     if "flash" in m.name and "generateContent" in (getattr(m, "supported_actions", None) or ["generateContent"])]
            notes.append("Gemini models your key can see (flash): " + ", ".join(sorted(names)[:15]))
        except Exception as exc:
            notes.append(f"Could not list Gemini models: {type(exc).__name__}: {str(exc)[:120]}")
    detail = "\n      ".join(notes) or "no AI provider configured"
    if not worked:
        raise RuntimeError("no model answered.\n      " + detail)
    return detail


check("AI model (Gemini/Groq/OpenRouter)", gemini)


def agent():
    from services import agent_service
    run = agent_service.run_agent(Q, "Technical")
    assert run.evidence, run.note or "no evidence"
    return f"mode={run.mode}, steps={[s['tool'] for s in run.steps]}, {len(run.evidence)} sources, brief {len(run.answer)} chars"


check("Research agent end-to-end", agent)

print()
for name, ok, info in results:
    print(("PASS  " if ok else "FAIL  ") + name + "\n      " + info)
bad = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f"; fix these first: {bad}" if bad else ". Live integration works."))
sys.exit(1 if bad else 0)