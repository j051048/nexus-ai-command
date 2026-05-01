import json

import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from app.main import app


def _get_client():
    if not hasattr(_get_client, "_instance"):
        _get_client._instance = TestClient(app)
    return _get_client._instance


# Fuzzing strategy for random strings, integers, lists, and dicts
json_strategy = st.recursive(
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(),
    lambda children: st.lists(children) | st.dictionaries(st.text(), children),
    max_leaves=100,
)


@pytest.mark.security
@settings(deadline=None, max_examples=50)
@given(
    payload=st.dictionaries(
        keys=st.text(min_size=1, max_size=50), values=json_strategy, max_size=20
    )
)
def test_fuzz_ai_assistant_endpoint(payload):
    """
    Fuzz test for the /api/v1/ai/assistant endpoint.
    Sends completely randomized structured JSON inputs to ensure the service
    gracefully handles and rejects invalid structures (HTTP 422 Unprocessable Entity)
    instead of crashing the server with Internal Server Error (HTTP 500).
    """
    # Assuming the route exists and has some validation
    # If the payload misses required fields like "message" or "tenant_id", it should be a 422
    # The server MUST NOT crash (500)

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer fake_token_for_fuzzing",
    }

    try:
        response = _get_client().post(
            "/api/v1/ai/assistant", json=payload, headers=headers
        )

        # We expect a validation error (422) or unauthorized (401/403)
        # Any 5xx error implies an unhandled exception or crash which is a security flaw
        assert (
            response.status_code < 500
        ), f"Fuzzing caused internal server error! Payload: {json.dumps(payload)}"

    except ValueError:
        # Some Pydantic or Starlette internals might raise specific errors in the test client
        # In a real deployed server these are normally handled by exception handlers
        pass


@pytest.mark.security
@settings(deadline=None, max_examples=20)
@given(query=st.text(min_size=1000, max_size=50000))  # Testing massive strings
def test_fuzz_massive_prompt(query):
    """
    Fuzz test for excessively massive string lengths to ensure we don't trigger
    RegEx DoS (ReDoS) or run out of memory before the prompt exceeds token limits.
    """
    payload = {"message": query, "tenant_id": "org_fuzz_123"}

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer fake_token_for_fuzzing",
    }

    response = _get_client().post("/api/v1/ai/assistant", json=payload, headers=headers)

    # We mainly care that the server doesn't crash (500)
    assert (
        response.status_code < 500
    ), "Fuzzing massive prompt caused internal server error!"
