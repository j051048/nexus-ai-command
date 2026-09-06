"""Atomic persistence boundary for a completed artifact package."""

from typing import Any


async def persist_artifact_package(
    db: Any,
    *,
    artifact: dict,
    version: dict,
    links: list[dict],
    result: dict,
    job_id: str | None = None,
    lease_token: str | None = None,
) -> None:
    if bool(job_id) != bool(lease_token):
        raise ValueError("Job persistence requires both job ID and lease token")
    await db.rpc(
        "persist_artifact_package",
        {
            "p_organization_id": artifact["organization_id"],
            "p_user_id": artifact["created_by"],
            "p_artifact": artifact,
            "p_version": version,
            "p_links": links,
            "p_result": result,
            "p_job_id": job_id,
            "p_lease_token": lease_token,
        },
    ).execute()
