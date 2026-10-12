"""SerpApi-powered research discovery using the official SDK and Search Tools.

Search calls are intentionally explicit: Scholar for academic literature, web for
institutional/technical context, and News for recent reporting. No agent claims
that search results alone establish scientific validity or novelty.
"""
from __future__ import annotations

import hashlib
from typing import Any

from . import db
from .config import SERPAPI_KEY
from .serpapi_service import search_scholar_papers

CACHE_SECONDS = 6 * 3600


def _search_tool(kind: str, query: str) -> str:
    """Run a SerpApi Search Tools callable; fall back to SDK if unavailable."""
    if not SERPAPI_KEY:
        raise RuntimeError("Add SERPAPI_KEY to your .env file to use SerpApi discovery.")
    try:
        from serpapi_search_tools import news_search, web_search
        if kind == "news":
            tool = news_search(provider="function", api_key=SERPAPI_KEY, result_limit=8)
        else:
            tool = web_search(
                provider="function", api_key=SERPAPI_KEY, allowed_engines=["google"],
                default_engine="google", result_limit=8,
            )
        result = tool(query=query)
        return str(result or "No results returned.")
    except ImportError:
        # Still allow the app to work if a host skipped the optional package.
        import serpapi
        client = serpapi.Client(api_key=SERPAPI_KEY, timeout=20)
        engine = "google_news" if kind == "news" else "google"
        data = client.search({"engine": engine, "q": query, "num": 8})
        key = "news_results" if kind == "news" else "organic_results"
        rows = data.get(key, []) or []
        if not rows:
            return "No results returned."
        lines = []
        for row in rows[:8]:
            title = row.get("title", "Untitled result")
            link = row.get("link", "")
            snippet = row.get("snippet", "")
            date = row.get("date", "")
            lines.append(f"- **{title}**\n  {link}\n  {date}\n  {snippet}".strip())
        return "\n\n".join(lines)


def _cached(key: str, factory):
    cache_key = "research_radar:" + hashlib.sha256(key.encode("utf-8")).hexdigest()
    cached = db.cache_get(cache_key, max_age=CACHE_SECONDS)
    if cached is not None:
        return cached
    value = factory()
    db.cache_set(cache_key, value)
    return value


def search_web(query: str) -> str:
    query = (query or "").strip()
    if not query:
        return ""
    return _cached("web:" + query.lower(), lambda: _search_tool("web", query))


def search_news(query: str) -> str:
    query = (query or "").strip()
    if not query:
        return ""
    return _cached("news:" + query.lower(), lambda: _search_tool("news", query))


def search_scholar(query: str, limit: int = 8) -> list[dict[str, Any]]:
    return search_scholar_papers(query, limit=limit) if SERPAPI_KEY else []


def research_sweep(query: str) -> dict[str, Any]:
    """Run Scholar, web and news searches independently; one failure won't block others."""
    output: dict[str, Any] = {"scholar": [], "web": "", "news": "", "errors": {}}
    jobs = [
        ("scholar", lambda: search_scholar(query, 8)),
        ("web", lambda: search_web(query)),
        ("news", lambda: search_news(query)),
    ]
    for name, job in jobs:
        try:
            output[name] = job()
        except Exception as exc:
            output["errors"][name] = str(exc)[:240]
    return output
