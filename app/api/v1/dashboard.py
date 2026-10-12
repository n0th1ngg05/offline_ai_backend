"""
Dashboard Summary & Role Permissions Matrix router:
- GET /api/v1/dashboard/summary
- GET /api/v1/reports/summary
- GET /api/v1/role-permissions/matrix
- PATCH /api/v1/role-permissions/{role_id}
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_admin_user_id
from app.core.database import get_async_db
from app.core.response import success_response
from app.schemas.users import RolePermissionUpdateRequest
from app.services import dashboard_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary")
@router.get("/reports/summary")
async def get_summary(
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await dashboard_service.get_dashboard_summary(db)
    return success_response(message="Summary fetched successfully.", data=data)


@router.get("/role-permissions/matrix")
async def get_role_permissions_matrix(
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await dashboard_service.get_role_permissions_matrix(db)
    return success_response(message="Role permissions matrix fetched successfully.", data=data)


@router.patch("/role-permissions/{role_id}")
@router.put("/role-permissions/{role_id}")
async def update_role_permissions(
    role_id: str,
    payload: RolePermissionUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await dashboard_service.update_role_permissions(db, role_id, payload)
    return success_response(message="Role permissions updated successfully.", data=data)
