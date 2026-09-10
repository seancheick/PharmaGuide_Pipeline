"""The queue client and the database must agree, checked against the migrations.

A mock can be wrong in the same direction as the code that uses it. These
assertions read the shipped SQL, so a renamed parameter or a dropped function
fails here rather than at the first real run.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

APP_MIGRATIONS = Path("/Users/seancheick/PharmaGuide ai/supabase/migrations")
CLIENT = (
    Path(__file__).parents[1]
    / "submission_review/extraction/queue_client.py"
)


def _migrations() -> str:
    if not APP_MIGRATIONS.exists():
        pytest.skip("app repository not available")
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(APP_MIGRATIONS.glob("2026*.sql"))
    )


def _client() -> str:
    return CLIENT.read_text(encoding="utf-8")


#: Every RPC the worker calls, with the parameters it sends.
EXPECTED = {
    "claim_product_submission_extraction_jobs": {"p_limit"},
    "heartbeat_product_submission_extraction_job": {"p_job_id", "p_fencing_token"},
    "reserve_product_submission_extraction_budget": {"p_job_id", "p_fencing_token"},
    "product_submission_extraction_budget_state": set(),
    "product_submission_extraction_attempt_outcome": {"p_job_id", "p_fencing_token"},
    "complete_product_submission_extraction_job": {
        "p_job_id",
        "p_fencing_token",
        "p_outcome",
        "p_schema_version",
        "p_provider",
        "p_model",
        "p_prompt_version",
        "p_input_image_hashes",
        "p_draft_payload",
        "p_field_provenance",
        "p_usage",
        "p_error_code",
        "p_cost_microcents",
    },
}


def test_the_client_calls_only_functions_that_exist() -> None:
    sql = _migrations()
    called = set(re.findall(r'self\._rpc\(\s*"([a-z_]+)"', _client()))

    assert called, "the client must call the queue through named RPCs"
    for name in called:
        assert f"FUNCTION public.{name}(" in sql, f"{name} is not a shipped function"


def test_every_parameter_the_client_sends_is_a_real_parameter() -> None:
    sql = _migrations()
    client = _client()

    for name, parameters in EXPECTED.items():
        # The last CREATE wins, which is what a deployed chain ends up with.
        # REVOKE lines name the same function, so they must not be mistaken
        # for its definition.
        definitions = re.findall(
            rf"CREATE (?:OR REPLACE )?FUNCTION public\.{name}\((.*?)\)\s*RETURNS",
            sql,
            re.DOTALL,
        )
        assert definitions, f"{name} is missing"
        signature = definitions[-1]
        for parameter in parameters:
            assert parameter in signature, f"{name} has no {parameter}"
            assert f'"{parameter}"' in client, f"the client never sends {parameter}"


def test_the_client_never_reaches_for_a_service_key() -> None:
    client = _client()

    # A worker holding the service role could read every user's photographs.
    assert "SUPABASE_SECRET_KEY" in client, "the guard must name what it refuses"
    assert "service_role" not in client
    assert "SERVICE_ROLE" not in client.replace("SUPABASE_SERVICE_ROLE_KEY", "")


def test_every_called_function_is_actually_callable_by_the_worker() -> None:
    """A function the worker cannot execute is a deployment failure, not a typo.

    This caught the client calling the internal allowance function, which is
    revoked from every role and only reachable from inside a definer.
    """
    sql = _migrations()
    called = set(re.findall(r'self\._rpc\(\s*"([a-z_]+)"', _client()))

    for name in called:
        grants = re.findall(
            rf"GRANT EXECUTE ON FUNCTION public\.{name}\([^)]*\)\s*TO ([^;]+);", sql
        )
        assert grants, f"{name} is never granted to anyone"
        assert any("authenticated" in clause for clause in grants), (
            f"{name} is not callable by an authenticated worker"
        )


def test_worker_facing_functions_are_closed_to_anon_and_service_role() -> None:
    sql = _migrations()

    for name in EXPECTED:
        revokes = re.findall(
            rf"REVOKE ALL ON FUNCTION public\.{name}\([^)]*\)\s*FROM ([^;]+);", sql
        )
        assert revokes, f"{name} must revoke default access"
        assert any("anon" in clause and "service_role" in clause for clause in revokes), (
            f"{name} must be closed to anon and service_role"
        )


def test_the_client_reads_evidence_only_from_the_leased_paths() -> None:
    client = _client()

    # The database owns where a submission's bytes live; the client must not
    # rebuild that path from parts.
    assert "evidence_object_paths" in client
    assert "storage/v1/object" in client
    assert re.search(r'f"\{[^"]*\}/\{[^"]*submission_id[^"]*\}/', client) is None


#: Every column the client reads off a claimed row. The worker learns nothing
#: except through its lease, so anything absent here is a fact it cannot have.
CLAIM_COLUMNS = {
    "job_id",
    "submission_id",
    "evidence_revision",
    "job_key",
    "fencing_token",
    "attempts",
    "leased_until",
    "evidence_manifest",
    "evidence_object_paths",
    "configuration",
    "submission_gtin",
    "catalog_match",
}


def _latest_claim_return_columns() -> set[str]:
    """The columns the most recent definition of the claim actually returns."""
    sql = _migrations()
    # The function has been redefined more than once; only the last definition
    # is live, and rebuilding it from an older ancestor is how a column gets
    # silently dropped.
    definitions = list(re.finditer(
        r"FUNCTION public\.claim_product_submission_extraction_jobs\("
        r".*?RETURNS TABLE \((?P<columns>.*?)\)\s*LANGUAGE",
        sql, re.S,
    ))
    assert definitions, "the claim function is not defined in any migration"
    body = definitions[-1].group("columns")
    return {
        line.strip().split()[0]
        for line in body.split(",")
        if line.strip()
    }


def test_the_claim_returns_every_column_the_worker_reads() -> None:
    returned = _latest_claim_return_columns()

    missing = CLAIM_COLUMNS - returned
    assert not missing, (
        "the worker reads columns the claim does not return: "
        f"{sorted(missing)}"
    )


def test_the_claim_returns_nothing_the_worker_does_not_read() -> None:
    returned = _latest_claim_return_columns()

    # A claim is also a disclosure. Anything handed to the worker that it has
    # no use for is data leaving the database for no reason.
    extra = returned - CLAIM_COLUMNS
    assert not extra, f"the claim discloses unused columns: {sorted(extra)}"


def test_the_client_reads_the_identity_context_the_claim_now_carries() -> None:
    client = _client()

    # Deterministic checks can only compare a printed barcode against the
    # filing if the filing reaches the worker. It has exactly one route in.
    assert "submission_gtin" in client
    assert "catalog_match" in client
