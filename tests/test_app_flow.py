"""End-to-end UI walkthrough with Streamlit AppTest. Search and AI are faked (no network)."""
import pytest
from pathlib import Path
from streamlit.testing.v1 import AppTest

from services import ai_service, paper_service, sources
from services.paper_model import new_paper

ABS = "This paper studies explainable models for intrusion detection and reports results on a public benchmark dataset. " * 2


def _papers():
    return [new_paper(title=f"Explainable intrusion detection {i}", authors=["A. Author"], year=2020 + i, abstract=ABS,
                      doi=f"10.1/x{i}", citations=10 * i, sources=["openalex"], venue="Journal") for i in range(3)]


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    monkeypatch.setattr(sources, "search_all", lambda q, s=None, **k: {
        "papers": _papers(), "counts": {"openalex": 3}, "errors": {}, "query": q})
    monkeypatch.setattr(paper_service, "get_full_text", lambda p: {"success": False, "text": "", "source": "", "message": "No full text."})


def _app():
    at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=30)
    at.query_params["space"] = "testspace123"
    at.session_state["guest_mode"] = True          # skip the sign-in gate
    at.run()
    assert not at.exception, at.exception
    return at


def test_full_flow():
    at = _app()
    at.text_input(key="topic_input").set_value("intrusion detection").run()
    at.button(key="start_search").click().run()
    assert not at.exception and at.session_state["page"] == "results"
    # select two papers and compare
    keys = [k for k in at.session_state["paper_index"]]
    for k in keys[:2]:
        at.checkbox(key=f"sel_{k}").check().run()
    at.button(key="bulk_compare").click().run()
    assert at.session_state["page"] == "compare", [e.value for e in at.exception]
    at.button(key="run_compare").click().run()
    assert not at.exception and at.session_state["compare_out"] is not None
    # open a paper, analyse, find gaps
    at.session_state["selected_paper"] = _papers()[0]
    at.session_state["page"] = "analysis"
    at.run()
    k = _papers()[0]["key"]
    at.button(key=f"an_{k}").click().run()
    at.button(key=f"gp_{k}").click().run()
    assert not at.exception, at.exception
    assert set(at.session_state["ai_out"][k]) == {"analysis", "gaps"}
    # planner
    at.session_state["planner_ctx"] = {"papers": _papers()[:2], "gaps": "Gap: limited real-time evaluation."}
    at.session_state["page"] = "planner"
    at.run()
    at.button(key="run_plan").click().run()
    assert not at.exception and at.session_state["plan_out"] is not None


def test_other_pages_render():
    at = _app()
    for page in ("workspace", "planner", "discovery", "agent", "results", "compare", "analysis", "discovery"):
        at.session_state["page"] = page
        at.run()
        assert not at.exception, (page, at.exception)


def test_auth_roundtrip_and_hashing():
    from services import auth_service, db
    ok, res = auth_service.create_user("Asha Rao", "Asha@Example.com", "correct horse")
    assert ok and res["email"] == "asha@example.com"
    assert auth_service.authenticate("asha@example.com", "correct horse")[0]
    assert not auth_service.authenticate("asha@example.com", "wrong password")[0]
    assert not auth_service.create_user("Asha Rao", "asha@example.com", "another pass1")[0]       # duplicate
    assert not auth_service.create_user("A", "bad", "short")[0]
    import sqlite3
    from services import config
    row = sqlite3.connect(str(config.DB_PATH)).execute("select password_hash from users").fetchone()
    assert "correct horse" not in row[0] and len(row[0]) == 64


def test_signin_gate_shown_without_guest_and_guest_unlocks():
    at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=30)
    at.run()
    assert not at.exception and any("Continue as guest" in b.label for b in at.button)
    next(b for b in at.button if "Continue as guest" in b.label).click().run()
    assert not at.exception and at.session_state["page"] == "home"
