"""Exercise the deployer's real-HTTP probe, including its refusal to touch an open session."""

from patient_web.acceptance import run_probe
from test_events import server


def test_acceptance_probe_verifies_demo_receipt_and_retry():
    with server() as (client, sid, manager):
        client.post(f"/ui/v1/sessions/{sid}/finish", json={"request_id":"finish"})
        report = run_probe(str(client.base_url).rstrip("/"), "demo", timeout_s=3)
        assert report["verdict"] == "PASS_DEMO_TEXT_DELIVERY"
        assert report["turn_result"]["delivery_receipt"]["model_called"] is False
        assert "snapshot_recovers_same_single_publication_without_browser_ack" in report["checks"]
        assert len(manager.conversations) == 2


def test_acceptance_probe_preserves_existing_open_consultation():
    with server() as (client, sid, manager):
        report = run_probe(str(client.base_url).rstrip("/"), "demo", timeout_s=3)
        assert report["verdict"] == "FAILED"
        assert report["failure"]["message"] == "no_existing_open_consultation"
        assert len(manager.conversations) == 1
        assert client.get(f"/ui/v1/sessions/{sid}").json()["closed"] is False


def test_acceptance_probe_does_not_mislabel_demo_as_native_validation():
    with server() as (client, sid, manager):
        report = run_probe(str(client.base_url).rstrip("/"), "native", timeout_s=3)
        assert report["verdict"] == "FAILED"
        assert report["failure"]["message"] == "explicit_backend_matches"
        assert len(manager.conversations) == 1


def test_acceptance_probe_includes_frozen_chief_evaluation_when_requested():
    with server() as (client, sid, manager):
        client.post(f"/ui/v1/sessions/{sid}/finish", json={"request_id":"finish"})
        report = run_probe(str(client.base_url).rstrip("/"), "demo", timeout_s=3, include_evaluation=True)
        assert report["verdict"] == "PASS_DEMO_TEXT_DELIVERY"
        assert report["evaluation"]["rule_score"]["score"] == 10
        assert "evaluation_identity_schema_and_digest_valid" in report["checks"]
        assert "evaluation_stable_after_repeated_finish_and_query" in report["checks"]

