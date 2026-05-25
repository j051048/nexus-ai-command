"""Production proof fixtures.

These tests are designed to be useful in two modes:
- default CI/local mode: deterministic offline contracts that always run;
- real proof mode: set RUN_REAL_PRODUCTION_PROOF=1 plus Supabase/LLM env vars.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def real_proof_enabled() -> bool:
    return os.getenv("RUN_REAL_PRODUCTION_PROOF") == "1"


def require_real_proof(reason: str):
    if not real_proof_enabled():
        pytest.skip(f"{reason}; set RUN_REAL_PRODUCTION_PROOF=1 to enable.")


@pytest.fixture
def golden_flows():
    return load_fixture("golden_business_flows.json")


@pytest.fixture
def intent_baseline():
    return load_fixture("intent_baseline.json")


@pytest.fixture
def llm_replay_cassette():
    return load_fixture("llm_replay_cassette.json")
