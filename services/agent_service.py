"""Research agent: an LLM that decides which SerpApi tool to call, reads the returned results,
and writes an evidence brief that cites only what the tools returned.

Loop (max MAX_STEPS): the model replies with JSON {"tool": ..., "query": ...} or {"finish": true};
we run the tool through the official SerpApi SDK and feed the results back.  Works with any
provider in ai_service's chain (Gemini -> Groq -> OpenRouter).  With no AI available the same
tools still run (fixed plan) and an extractive digest is shown instead, labelled as such.
"""
import json
import re
from dataclasses import dataclass, field

from . import ai_service, serpapi_service as sp
from .serpapi_service import SerpError

MAX_STEPS = 5
TOOLS = {
    "search_scholar": ("Google Scholar: academic papers, with citation counts and links.", sp.search_scholar_evidence),
    "search_web": ("Google web search: official pages, datasets, code repositories, blogs, tutorials.", sp.search_web),
    "search_news": ("Google News: recent reporting and announcements about the topic.", sp.search_news),
    "search_patents": ("Google Patents: has this idea already been patented? Use for novelty checks on applied ideas.", sp.search_patents),
    "check_trend": ("Google Trends: is public interest in a SHORT topic phrase (1-4 words) rising or falling?", sp.search_trends),
}


@dataclass
class AgentRun:
    question: str
    steps: list = field(default_factory=list)      # {"tool","query","count","cached","error"}
    evidence: list = field(default_factory=list)   # normalised items from SerpApi
    answer: str = ""
    mode: str = "agent"                            # "agent" (LLM chose tools) | "fixed-plan" (no AI available)
    note: str = ""
    model: str = ""


def _tool_prompt(question, audience, history):
    tools = "\n".join(f"- {n}: {d}" for n, (d, _) in TOOLS.items())
    seen = "\n".join(f"[{i}] ({e['kind']}) {e['title']} | {e['source']} {e['date']} | {e['snippet'][:160]}"
                     for i, e in enumerate(history["evidence"], 1)) or "(nothing yet)"
    done = "\n".join(f"- {s['tool']}({s['query']!r}) -> {s['count']} results" + (f" ERROR {s['error']}" if s.get("error") else "")
                     for s in history["steps"]) or "(no searches yet)"
    return f"""You are a research agent helping {audience} investigate a research question using live search tools.
You may NOT answer from memory. Decide the next action.

QUESTION: {question}

TOOLS:
{tools}

SEARCHES DONE:
{done}

EVIDENCE SO FAR:
{seen}

Reply with ONLY one JSON object, no prose:
- to search: {{"tool": "search_scholar" | "search_web" | "search_news" | "search_patents" | "check_trend", "query": "<focused search query>"}}
- when you have enough evidence from at least two different tools (or tools keep failing): {{"finish": true}}
Do not repeat a search. Use at most {MAX_STEPS} searches."""


def _parse_action(text):
    m = re.search(r"\{.*\}", str(text or ""), flags=re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _run_tool(run, tool, query):
    step = {"tool": tool, "query": query, "count": 0, "cached": False, "error": ""}
    try:
        items, cached = TOOLS[tool][1](query)
        step.update(count=len(items), cached=cached)
        have = {e["url"] for e in run.evidence}
        run.evidence += [e for e in items if e["url"] not in have]
    except SerpError as exc:
        step["error"] = str(exc)
    run.steps.append(step)
    return step


def _brief_prompt(run, audience):
    ev = "\n".join(f"[{i}] ({e['kind']}) {e['title']} | {e['source']} | {e['date']}\n    {e['snippet']}\n    {e['url']}"
                   for i, e in enumerate(run.evidence[:30], 1))
    return f"""You are writing an evidence brief for {audience}.

QUESTION: {run.question}

Use ONLY the search results below. Cite sources as [n]. If the results do not support a point, say so.
Never invent papers, numbers, authors or URLs. Snippets are short, so do not claim more than they say.

RESULTS
{ev}

Write Markdown with exactly these sections:
## What the evidence says
(4-6 bullets, each ending with citations like [1][4])
## Recent developments, momentum and prior art
(news items, trend items and patent items only; say "None found." for any that are missing. Never call something novel just because no patent was found.)
## Open questions and possible research gaps
(3 bullets, framed as hypotheses to verify, with citations where relevant)
## Suggested next steps
(3 short bullets for a student)"""


def _digest(run):
    """Extractive fallback: list what the tools returned, without any AI interpretation."""
    lines = ["## Evidence found (no AI summary)", ""]
    for kind, title in (("paper", "Papers (Google Scholar)"), ("web", "Web sources"), ("news", "Recent news"),
                        ("patent", "Patents"), ("trend", "Search interest (Google Trends)")):
        rows = [(i, e) for i, e in enumerate(run.evidence, 1) if e["kind"] == kind]
        if rows:
            lines.append(f"**{title}**")
            lines += [f"- [{i}] {e['title']} ({e['source']}{', ' + str(e['date']) if e['date'] else ''})" for i, e in rows[:6]]
            lines.append("")
    return "\n".join(lines)


def fixed_plan(question):
    return [("search_scholar", question), ("search_web", question), ("search_news", question)]


def run_agent(question, mode="Beginner", live_allowed=True):
    """Never raises. Returns AgentRun."""
    run = AgentRun(question=question.strip())
    if not sp.configured():
        run.note = "SERPAPI_KEY is not set, so no live search can run. Add it to your .env file."
        return run
    audience = "a beginner student (plain language)" if mode == "Beginner" else "an advanced student or researcher (technical)"
    agent_ok = live_allowed and bool(ai_service._chain())
    if agent_ok:
        for _ in range(MAX_STEPS):
            try:
                text, model = ai_service._generate_live(_tool_prompt(run.question, audience, {"steps": run.steps, "evidence": run.evidence}))
            except ai_service.AIError as exc:
                run.note = ai_service._friendly(exc)
                agent_ok = False
                break
            run.model = model
            act = _parse_action(text)
            if not act or act.get("finish"):
                break
            tool, query = act.get("tool"), str(act.get("query") or "").strip()[:200]
            if tool not in TOOLS or not query or any(s["tool"] == tool and s["query"] == query for s in run.steps):
                break
            _run_tool(run, tool, query)
    if not agent_ok or not run.steps:           # AI missing / over quota / produced nothing usable
        run.mode = "fixed-plan"
        for tool, query in fixed_plan(run.question):
            if not any(s["tool"] == tool for s in run.steps):
                _run_tool(run, tool, query)
    if not run.evidence:
        run.note = run.note or "The searches returned no results."
        return run
    if run.mode == "agent" and live_allowed:
        res = ai_service.generate("agent", _brief_prompt(run, audience), _digest(run), True)
        run.answer, run.model = res.text, res.model or run.model
        if res.source in ("offline", "limit"):
            run.mode, run.note = "fixed-plan", res.note
    else:
        run.answer = _digest(run)
    return run
