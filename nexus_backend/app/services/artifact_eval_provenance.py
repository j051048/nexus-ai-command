"""Provenance of the recorded evidence behind artifact-quality claims.

The product states document-quality targets (一次通过率 >= 90%、平均分 >= 85).
Those numbers can be measured against two very different things:

* ``contract-fixture`` - recorded outputs that exercise the evaluator itself;
  they prove the contract works, not that a real model produces good documents;
* ``live-model`` - outputs produced by the real generation pipeline with real
  evidence documents, recorded with model id, latency and cost.

Only the second may be used to claim model quality. This module reads the
committed baseline so the SLO payload and the monthly report can say which one
they are standing on, instead of implying quality that was never measured.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: ``nexus_backend/evals/artifact_output_baseline.json`` - shipped with the app.
BASELINE_PATH = (
    Path(__file__).resolve().parents[2] / "evals" / "artifact_output_baseline.json"
)

LIVE_SOURCE = "live-model"
FIXTURE_SOURCE = "contract-fixture"


def load_artifact_eval_provenance(path: Path | None = None) -> dict[str, Any]:
    """Describe the recorded evidence; never raises on a missing baseline."""
    target = path or BASELINE_PATH
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("[ArtifactEval] baseline unreadable at %s: %s", target, exc)
        return {
            "available": False,
            "source": None,
            "claims_live_quality": False,
            "reason": "baseline_missing_or_invalid",
        }

    source = str(payload.get("source") or "").strip() or None
    return {
        "available": True,
        "source": source,
        "version": payload.get("version"),
        "recorded_at": payload.get("recorded_at"),
        "models": payload.get("models") or [],
        "pass_rate": payload.get("pass_rate"),
        "minimum_pass_rate": payload.get("minimum_pass_rate"),
        "cases": len(payload.get("cases") or {}),
        "evidence_documents": payload.get("evidence_document_ids") or [],
        "environment": payload.get("environment"),
        # The single field consumers must check before making quality claims.
        "claims_live_quality": source == LIVE_SOURCE,
    }
