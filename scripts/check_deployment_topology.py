#!/usr/bin/env python3
"""Keep the four deployment surfaces honest and reproducible.

The repository ships a Vercel frontend config, a Zeabur PaaS manifest, a
single-host docker-compose file and Kubernetes manifests. That is acceptable as
long as (a) exactly one artifact definition per surface is used and (b) no
surface deploys a floating image tag, which would make rollback impossible.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
K8S = ROOT / "k8s"
TOPOLOGY_DOC = ROOT / "docs" / "adr" / "005-deployment-topology-authority.md"

SURFACES = ("vercel", "zeabur", "docker-compose", "k8s")


def check_k8s_images() -> list[str]:
    failures: list[str] = []
    for manifest in sorted(K8S.glob("*.yaml")):
        if manifest.name == "kustomization.yaml":
            continue
        text = manifest.read_text(encoding="utf-8")
        has_image = False
        for index, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith("image:"):
                continue
            has_image = True
            value = stripped.split("image:", 1)[1].strip().strip('"')
            if value.endswith(":latest") or ":" not in value:
                failures.append(
                    f"{manifest.name}:{index}: floating image reference '{value}' "
                    "(pin a version tag or digest)"
                )
        if has_image and "imagePullPolicy" not in text:
            failures.append(
                f"{manifest.name}: containers with an image must set imagePullPolicy"
            )
    return failures


def check_topology_doc() -> list[str]:
    if not TOPOLOGY_DOC.exists():
        return [f"missing {TOPOLOGY_DOC.relative_to(ROOT).as_posix()}"]
    content = TOPOLOGY_DOC.read_text(encoding="utf-8").lower()
    missing = [surface for surface in SURFACES if surface not in content]
    if missing:
        return [f"topology doc does not cover: {', '.join(missing)}"]
    return []


def check_compose_uses_shared_image() -> list[str]:
    compose = ROOT / "docker-compose.yml"
    if not compose.exists():
        return ["docker-compose.yml is missing"]
    text = compose.read_text(encoding="utf-8")
    if "dockerfile: Dockerfile" not in text:
        return ["docker-compose.yml must build from the shared root Dockerfile"]
    return []


def main() -> int:
    failures = check_k8s_images() + check_topology_doc() + check_compose_uses_shared_image()
    if failures:
        print("DEPLOYMENT_TOPOLOGY_GATE_FAIL")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("DEPLOYMENT_TOPOLOGY_GATE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
