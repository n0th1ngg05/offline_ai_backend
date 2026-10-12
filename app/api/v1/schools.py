"""
Schools Management router (/api/v1/school, /api/v1/school/{id}/class-section,
/api/v1/school/export).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_admin_user_id, get_current_user_id
from app.core.database import get_async_db
from app.core.response import success_response
from app.schemas.school import (
    SchoolClassSectionPatchRequest,
    SchoolCreateRequest,
    SchoolUpdateRequest,
)
from app.services import school_service

router = APIRouter(tags=["schools"])


@router.get("/school")
@router.get("/schools")
async def list_schools(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=500),
    search: str | None = Query(None, max_length=100),
    status: str | None = Query(None, pattern=r"^(?i)(active|inactive|deleted)$"),
    state_id: uuid.UUID | None = Query(None),
    district_id: uuid.UUID | None = Query(None),
    ulb_id: uuid.UUID | None = Query(None),
    ward_id: uuid.UUID | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await school_service.list_schools(
        db,
        page=page,
        limit=limit,
        search=search,
        status=status,
        state_id=state_id,
        district_id=district_id,
        ulb_id=ulb_id,
        ward_id=ward_id,
    )
    return success_response(message="Schools fetched successfully.", data=data)


@router.get("/school/export")
@router.get("/schools/export")
async def export_schools(
    search: str | None = Query(None, max_length=100),
    status: str | None = Query(None, pattern=r"^(?i)(active|inactive|deleted)$"),
    state_id: uuid.UUID | None = Query(None),
    district_id: uuid.UUID | None = Query(None),
    ulb_id: uuid.UUID | None = Query(None),
    ward_id: uuid.UUID | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    csv_text = await school_service.export_schools_csv(
        db,
        search=search,
        status=status,
        state_id=state_id,
        district_id=district_id,
        ulb_id=ulb_id,
        ward_id=ward_id,
    )
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="schools_export.csv"'},
    )


@router.get("/school/{school_id}")
@router.get("/schools/{school_id}")
async def get_school(
    school_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await school_service.get_school(db, school_id)
    return success_response(message="School fetched successfully.", data=data)


@router.post("/school", status_code=status.HTTP_201_CREATED)
@router.post("/schools", status_code=status.HTTP_201_CREATED)
async def create_school(
    payload: SchoolCreateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await school_service.create_school(db, payload)
    return success_response(
        message="School created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/school/{school_id}")
@router.patch("/schools/{school_id}")
async def update_school(
    school_id: uuid.UUID,
    payload: SchoolUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await school_service.update_school(db, school_id, payload)
    return success_response(message="School updated successfully.", data=data)


@router.delete("/school/{school_id}")
@router.delete("/schools/{school_id}")
async def delete_school(
    school_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await school_service.delete_school(db, school_id)
    return success_response(message="School deleted successfully.")


@router.get("/school/{school_id}/class-section")
@router.get("/schools/{school_id}/class-section")
async def list_school_class_sections(
    school_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await school_service.list_school_class_sections(
        db, school_id, page=page, limit=limit, search=search
    )
    return success_response(message="School class-sections fetched successfully.", data=data)


@router.patch("/school/{school_id}/class-section/{item_id}")
@router.patch("/schools/{school_id}/class-section/{item_id}")
async def update_school_class_section(
    school_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: SchoolClassSectionPatchRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await school_service.update_school_class_section(db, school_id, item_id, payload)
    return success_response(message="School class-section updated successfully.", data=data)
