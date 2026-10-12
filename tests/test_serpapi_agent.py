"""SerpApi web/news parsing, error mapping, and the agent loop (SerpApi + AI are faked; no network)."""
import json

import pytest

from services import agent_service, ai_service, serpapi_service as sp

WEB = [{"title": "XAI for IDS", "link": "https://example.org/a", "displayed_link": "example.org", "snippet": "A survey."},
       {"title": "no link"}]
NEWS = [{"title": "New IDS model", "link": "https://news.example/b", "source": {"name": "TechNews"}, "date": "2 days ago"}]


class FakeClient:
    calls = []

    def __init__(self, **kw):
        pass

    def search(self, params):
        FakeClient.calls.append(params["engine"])
        data = {"google": {"organic_results": WEB}, "google_news": {"news_results": NEWS},
                "google_scholar": {"organic_results": [{"title": "Scholar paper", "link": "https://s.org/p",
                                                        "publication_info": {"summary": "A Author - Journal, 2021 - pub"},
                                                        "snippet": "abs"}]}}
        return data[params["engine"]]


@pytest.fixture
def serp(monkeypatch):
    import serpapi
    FakeClient.calls = []
    monkeypatch.setattr(sp, "SERPAPI_KEY", "test-key")
    monkeypatch.setattr(serpapi, "Client", FakeClient)
    return FakeClient


def test_parsers_drop_items_without_links():
    assert [e["title"] for e in sp.parse_web(WEB)] == ["XAI for IDS"]
    n = sp.parse_news(NEWS)[0]
    assert n["source"] == "TechNews" and n["kind"] == "news" and n["date"] == "2 days ago"


def test_web_search_caches(serp):
    items, cached = sp.search_web("xai ids")
    assert len(items) == 1 and cached is False
    items, cached = sp.search_web("xai ids")
    assert cached is True and serp.calls == ["google"]


def test_missing_key_and_http_errors(monkeypatch):
    monkeypatch.setattr(sp, "SERPAPI_KEY", "")
    with pytest.raises(sp.SerpError):
        sp.search_web("q")
    import serpapi

    class Boom:
        def __init__(self, **kw): pass
        def search(self, p):
            exc = serpapi.HTTPError.__new__(serpapi.HTTPError)
            exc.status_code, exc.error = 429, "limit"
            raise exc
    monkeypatch.setattr(sp, "SERPAPI_KEY", "k")
    monkeypatch.setattr(serpapi, "Client", Boom)
    with pytest.raises(sp.SerpError, match="credits"):
        sp.search_web("q2")


def test_agent_uses_tool_results_in_next_prompt_and_brief(serp, monkeypatch):
    seen = []
    script = iter([{"tool": "search_scholar", "query": "xai ids"}, {"tool": "search_news", "query": "xai ids news"}, {"finish": True}])

    def fake_live(prompt):
        seen.append(prompt)
        return json.dumps(next(script)), "gemini:fake"
    monkeypatch.setattr(ai_service, "_generate_live", fake_live)
    monkeypatch.setattr(ai_service, "_chain", lambda: [("gemini", "fake")])
    monkeypatch.setattr(ai_service, "generate", lambda task, prompt, fb, live: ai_service.AIResult("Brief [1][2]", "live", "gemini:fake"))
    run = agent_service.run_agent("xai ids question", "Technical")
    assert run.mode == "agent" and [s["tool"] for s in run.steps] == ["search_scholar", "search_news"]
    assert "Scholar paper" in seen[1] and "Scholar paper" in seen[2]          # step-1 results were shown to the model
    assert {e["kind"] for e in run.evidence} == {"paper", "news"} and run.answer == "Brief [1][2]"
    assert serp.calls == ["google_scholar", "google_news"]


def test_agent_without_ai_runs_fixed_plan_and_is_extractive(serp, monkeypatch):
    monkeypatch.setattr(ai_service, "_chain", lambda: [])
    run = agent_service.run_agent("some research question", "Beginner")
    assert run.mode == "fixed-plan" and len(run.steps) == 3 and "no AI summary" in run.answer
    assert all(e["url"].startswith("https://") for e in run.evidence)


def test_agent_without_serpapi_key(monkeypatch):
    monkeypatch.setattr(sp, "SERPAPI_KEY", "")
    run = agent_service.run_agent("a question here")
    assert not run.evidence and "SERPAPI_KEY" in run.note


def test_agent_survives_tool_error(serp, monkeypatch):
    monkeypatch.setattr(ai_service, "_chain", lambda: [])
    monkeypatch.setattr(sp, "search_news", lambda q, limit=8: (_ for _ in ()).throw(sp.SerpError("down")))
    monkeypatch.setitem(agent_service.TOOLS, "search_news", ("n", sp.search_news))
    run = agent_service.run_agent("another question")
    assert any(s["error"] == "down" for s in run.steps) and run.evidence


def test_parse_patents_uses_patent_link():
    items = sp.parse_patents([{"title": "IDS method", "patent_link": "https://patents.google.com/patent/US1", "assignee": "Acme",
                               "snippet": "s", "filing_date": "2020-01-01"}, {"title": "no link"}])
    assert len(items) == 1 and items[0]["kind"] == "patent" and items[0]["source"] == "Acme"


def test_parse_trends_summarises_direction_and_skips_thin_data():
    rows = [{"date": str(i), "values": [{"query": "q", "extracted_value": v}]} for i, v in enumerate([10, 10, 12, 30, 40, 50, 60, 70, 80])]
    ev = sp.parse_trends({"interest_over_time": {"timeline_data": rows}}, "xai")[0]
    assert ev["kind"] == "trend" and "rising" in ev["snippet"] and ev["url"].startswith("https://trends.google.com/")
    assert sp.parse_trends({"interest_over_time": {"timeline_data": rows[:3]}}, "xai") == []


def test_agent_can_call_patents_and_trend(serp, monkeypatch):
    monkeypatch.setattr(sp, "search_patents", lambda q, limit=6: ([{"kind": "patent", "title": "P", "url": "https://p/1", "source": "A", "snippet": "", "date": ""}], False))
    monkeypatch.setitem(agent_service.TOOLS, "search_patents", ("p", sp.search_patents))
    script = iter([{"tool": "search_patents", "query": "xai ids"}, {"finish": True}])
    monkeypatch.setattr(ai_service, "_generate_live", lambda prompt: (json.dumps(next(script)), "m"))
    monkeypatch.setattr(ai_service, "_chain", lambda: [("gemini", "m")])
    monkeypatch.setattr(ai_service, "generate", lambda t, p, f, l: ai_service.AIResult("Brief", "live", "m"))
    run = agent_service.run_agent("xai ids question", "Technical")
    assert [s["tool"] for s in run.steps] == ["search_patents"] and run.evidence[0]["kind"] == "patent"
