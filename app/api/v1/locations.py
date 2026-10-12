"""
Location Hierarchy router:
- /api/v1/state & /api/v1/academics/states
- /api/v1/district & /api/v1/academics/districts
- /api/v1/ulb & /api/v1/academics/ulbs
- /api/v1/ward & /api/v1/academics/wards
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_admin_user_id, get_current_user_id
from app.core.database import get_async_db
from app.core.response import success_response
from app.schemas.academics import (
    DistrictCreateRequest,
    DistrictUpdateRequest,
    StateCreateRequest,
    StateUpdateRequest,
    UlbCreateRequest,
    UlbUpdateRequest,
    WardCreateRequest,
    WardUpdateRequest,
)
from app.services import location_service

router = APIRouter(tags=["locations"])


# ==============================================================================
# States (/state and /academics/states)
# ==============================================================================

@router.get("/state")
@router.get("/academics/states")
async def list_states(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = Query(None),
    status: str | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await location_service.list_states(
        db, page=page, limit=limit, search=search, status=status
    )
    return success_response(message="States fetched successfully.", data=data)


@router.get("/state/{state_id}")
@router.get("/academics/states/{state_id}")
async def get_state(
    state_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await location_service.get_state(db, state_id)
    return success_response(message="State fetched successfully.", data=data)


@router.post("/state", status_code=status.HTTP_201_CREATED)
@router.post("/academics/states", status_code=status.HTTP_201_CREATED)
async def create_state(
    payload: StateCreateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await location_service.create_state(db, payload)
    return success_response(
        message="State created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/state/{state_id}")
@router.patch("/academics/states/{state_id}")
async def update_state(
    state_id: uuid.UUID,
    payload: StateUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await location_service.update_state(db, state_id, payload)
    return success_response(message="State updated successfully.", data=data)


@router.delete("/state/{state_id}")
@router.delete("/academics/states/{state_id}")
async def delete_state(
    state_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await location_service.delete_state(db, state_id)
    return success_response(message="State deleted successfully.")


# ==============================================================================
# Districts (/district and /academics/districts)
# ==============================================================================

@router.get("/district")
@router.get("/academics/districts")
async def list_districts(
    state_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = Query(None),
    status: str | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await location_service.list_districts(
        db, state_id=state_id, page=page, limit=limit, search=search, status=status
    )
    return success_response(message="Districts fetched successfully.", data=data)


@router.get("/district/{district_id}")
@router.get("/academics/districts/{district_id}")
async def get_district(
    district_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await location_service.get_district(db, district_id)
    return success_response(message="District fetched successfully.", data=data)


@router.post("/district", status_code=status.HTTP_201_CREATED)
@router.post("/academics/districts", status_code=status.HTTP_201_CREATED)
async def create_district(
    payload: DistrictCreateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await location_service.create_district(db, payload)
    return success_response(
        message="District created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/district/{district_id}")
@router.patch("/academics/districts/{district_id}")
async def update_district(
    district_id: uuid.UUID,
    payload: DistrictUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await location_service.update_district(db, district_id, payload)
    return success_response(message="District updated successfully.", data=data)


@router.delete("/district/{district_id}")
@router.delete("/academics/districts/{district_id}")
async def delete_district(
    district_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await location_service.delete_district(db, district_id)
    return success_response(message="District deleted successfully.")


# ==============================================================================
# ULBs (/ulb and /academics/ulbs)
# ==============================================================================

@router.get("/ulb")
@router.get("/academics/ulbs")
async def list_ulbs(
    district_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = Query(None),
    status: str | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await location_service.list_ulbs(
        db, district_id=district_id, page=page, limit=limit, search=search, status=status
    )
    return success_response(message="ULBs fetched successfully.", data=data)


@router.get("/ulb/{ulb_id}")
@router.get("/academics/ulbs/{ulb_id}")
async def get_ulb(
    ulb_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await location_service.get_ulb(db, ulb_id)
    return success_response(message="ULB fetched successfully.", data=data)


@router.post("/ulb", status_code=status.HTTP_201_CREATED)
@router.post("/academics/ulbs", status_code=status.HTTP_201_CREATED)
async def create_ulb(
    payload: UlbCreateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await location_service.create_ulb(db, payload)
    return success_response(
        message="ULB created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/ulb/{ulb_id}")
@router.patch("/academics/ulbs/{ulb_id}")
async def update_ulb(
    ulb_id: uuid.UUID,
    payload: UlbUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await location_service.update_ulb(db, ulb_id, payload)
    return success_response(message="ULB updated successfully.", data=data)


@router.delete("/ulb/{ulb_id}")
@router.delete("/academics/ulbs/{ulb_id}")
async def delete_ulb(
    ulb_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await location_service.delete_ulb(db, ulb_id)
    return success_response(message="ULB deleted successfully.")


# ==============================================================================
# Wards (/ward and /academics/wards)
# ==============================================================================

@router.get("/ward")
@router.get("/academics/wards")
async def list_wards(
    ulb_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = Query(None),
    status: str | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await location_service.list_wards(
        db, ulb_id=ulb_id, page=page, limit=limit, search=search, status=status
    )
    return success_response(message="Wards fetched successfully.", data=data)


@router.get("/ward/{ward_id}")
@router.get("/academics/wards/{ward_id}")
async def get_ward(
    ward_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await location_service.get_ward(db, ward_id)
    return success_response(message="Ward fetched successfully.", data=data)


@router.post("/ward", status_code=status.HTTP_201_CREATED)
@router.post("/academics/wards", status_code=status.HTTP_201_CREATED)
async def create_ward(
    payload: WardCreateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await location_service.create_ward(db, payload)
    return success_response(
        message="Ward created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/ward/{ward_id}")
@router.patch("/academics/wards/{ward_id}")
async def update_ward(
    ward_id: uuid.UUID,
    payload: WardUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await location_service.update_ward(db, ward_id, payload)
    return success_response(message="Ward updated successfully.", data=data)


@router.delete("/ward/{ward_id}")
@router.delete("/academics/wards/{ward_id}")
async def delete_ward(
    ward_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await location_service.delete_ward(db, ward_id)
    return success_response(message="Ward deleted successfully.")
