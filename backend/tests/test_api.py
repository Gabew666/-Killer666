from datetime import timedelta

from fastapi.testclient import TestClient

from app.main import create_app


def test_api_seed_state_and_explainable_plan(settings, now):
    app = create_app(settings)
    app.state.clock = lambda: now
    with TestClient(app) as client:
        assert client.get("/health").json()["database"] == "ok"
        subjects = client.get("/subjects").json()
        assert subjects[0]["name"] == "IA Simbólica"
        assert len(client.get(f"/subjects/{subjects[0]['id']}/concepts").json()) == 30
        states = client.get("/student/state").json()
        assert len(states) == 30
        assert all(s["mastery"] is None and s["status"] == "NOT_DIAGNOSED"
                   and s["mastery_interpretation"] == "NOT_DIAGNOSED"
                   and s["low_evidence"] and s["evidence_count"] == 0 for s in states)
        before = states
        response = client.post("/sessions/plan", json={"student_id": 1, "available_minutes": 40})
        assert response.status_code == 200
        plan = response.json()
        assert 0 < plan["planned_minutes"] <= 36
        assert len(plan["ranking"]) == 30
        assert all(r["reason"] and r["components"] for r in plan["ranking"])
        assert all(a["mode"] == "diagnostic" for a in plan["activities"])
        assert all(a["activity_type"] != "EXPLANATION" for a in plan["activities"])
        assert any(a["decision_after"] for a in plan["activities"])
        assert "answer_spec" not in response.text and "correct_index" not in response.text
        assert client.get("/student/state").json() == before
        assert len(client.get("/assessments").json()[0]["concept_weights"]) == 7


def test_invalid_requests_and_missing_entities(settings):
    with TestClient(create_app(settings)) as client:
        for minutes in [0, -1, 9, 241, 1.5, True, "40"]:
            response = client.post("/sessions/plan", json={"available_minutes": minutes})
            assert response.status_code == 422
        assert client.post("/sessions/plan", json={"student_id": 999, "available_minutes": 40}).status_code == 422
        assert client.get("/student/state?student_id=999").status_code == 404
        assert client.get("/subjects/999/concepts").status_code == 404


def test_server_restart_preserves_seed_without_duplicates(settings, now):
    for _ in range(2):
        app = create_app(settings)
        app.state.clock = lambda: now
        with TestClient(app) as client:
            assert len(client.get("/subjects/1/concepts").json()) == 30
            assert len(client.get("/assessments").json()) == 1
