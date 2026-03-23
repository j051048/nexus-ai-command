"""证照管理 API 路由"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.certificate_service import certificate_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/certificates", tags=["Certificates"])


# ── Schemas ──


class CertificateCreate(BaseModel):
    name: str
    cert_type: str
    holder_type: str
    holder_id: str
    cert_no: str | None = None
    issue_date: str | None = None
    expire_date: str | None = None


class CertificateRenew(BaseModel):
    new_expire_date: str
    attachment_url: str | None = None


# ── Endpoints ──


@router.get("")
async def list_certificates(
    req: Request,
    cert_type: str = None,
    holder_type: str = None,
    status: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """查询证照列表"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        filters = {}
        if cert_type:
            filters["cert_type"] = cert_type
        if holder_type:
            filters["holder_type"] = holder_type
        if status:
            filters["status"] = status
        certs = await certificate_service.list_certificates(
            org_id=org_id,
            filters=filters if filters else None,
            db=db,
        )
        return api_success(data={"certificates": certs})
    except Exception as e:
        logger.error(f"Failed to list certificates: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "证书操作失败")


@router.post("")
async def create_certificate(
    body: CertificateCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建证照"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        data = body.model_dump(exclude_none=True)
        cert = await certificate_service.create_certificate(
            org_id=org_id,
            data=data,
            db=db,
        )
        return api_success(data={"certificate": cert}, message="证照创建成功")
    except Exception as e:
        logger.error(f"Failed to create certificate: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "证书操作失败")


@router.get("/expiring")
async def get_expiring_certs(
    req: Request,
    days: int = 30,
    user_id: str = Depends(get_current_user_id),
):
    """查询即将到期证照"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        db = getattr(req.state, "db", None)
        certs = await certificate_service.get_expiring_certs(
            org_id=org_id,
            days=days,
            db=db,
        )
        return api_success(data={"certificates": certs})
    except Exception as e:
        logger.error(f"Failed to get expiring certificates: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "证书操作失败")


@router.patch("/{cert_id}/renew")
async def renew_certificate(
    cert_id: str,
    body: CertificateRenew,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """续期证照"""
    try:
        db = getattr(req.state, "db", None)
        result = await certificate_service.renew_certificate(
            cert_id=cert_id,
            new_expire_date=body.new_expire_date,
            attachment_url=body.attachment_url,
            db=db,
        )
        return api_success(data={"certificate": result}, message="证照续期成功")
    except Exception as e:
        logger.error(f"Failed to renew certificate: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "证书操作失败")
