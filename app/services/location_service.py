"""
Location hierarchy service: States, Districts, ULBs, Wards.
Supports both dropdown lookups (/api/v1/state, /api/v1/district, /api/v1/ulb,
/api/v1/ward) and Region Management CRUD (/api/v1/academics/states, etc.).
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import AppError, paginated_data
from app.models.location import District, State, Ulb, Ward
from app.models.school import School
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


def _slug_code(name: str, prefix: str = "") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", name.strip()).strip("_").upper()
    if not cleaned:
        cleaned = uuid.uuid4().hex[:6].upper()
    return f"{prefix}{cleaned}"[:50]


def _normalize_status(status_val: str | None, default: str = "ACTIVE") -> str:
    if not status_val:
        return default
    val = status_val.strip().upper()
    if val in ("ACTIVE", "INACTIVE", "DELETED"):
        return val
    return default


async def _serialize_states(db: AsyncSession, states: list[State]) -> list[dict[str, Any]]:
    if not states:
        return []
    state_ids = [s.id for s in states]

    dist_rows = (
        await db.execute(
            select(District)
            .where(District.state_id.in_(state_ids), District.is_deleted.is_(False))
            .order_by(District.name.asc())
        )
    ).scalars().all()

    school_counts_rows = (
        await db.execute(
            select(School.state_id, func.count(School.id))
            .where(School.state_id.in_(state_ids), School.is_deleted.is_(False))
            .group_by(School.state_id)
        )
    ).all()
    school_counts = {row[0]: row[1] for row in school_counts_rows}

    districts_by_state: dict[uuid.UUID, list[dict[str, Any]]] = {sid: [] for sid in state_ids}
    for d in dist_rows:
        districts_by_state.setdefault(d.state_id, []).append(
            {
                "id": str(d.id),
                "state_id": str(d.state_id),
                "name": d.name,
                "code": d.code,
                "status": d.status,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
        )

    result = []
    for s in states:
        dists = districts_by_state.get(s.id, [])
        result.append(
            {
                "id": str(s.id),
                "name": s.name,
                "code": s.code,
                "status": s.status,
                "districts": dists,
                "district_count": len(dists),
                "total_districts": len(dists),
                "school_count": school_counts.get(s.id, 0),
                "total_schools": school_counts.get(s.id, 0),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
        )
    return result


async def list_states(
    db: AsyncSession,
    *,
    page: int = 1,
    limit: int = 100,
    search: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    stmt = select(State).where(State.is_deleted.is_(False))
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(or_(State.name.ilike(q), State.code.ilike(q)))
    if status and status.strip():
        stmt = stmt.where(State.status == status.strip().upper())

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(State.name.asc()).offset((max(1, page) - 1) * max(1, limit)).limit(max(1, limit))
    rows = (await db.execute(stmt)).scalars().all()
    items = await _serialize_states(db, list(rows))
    return paginated_data(items=items, total=total, page=page, limit=limit)


async def get_state(db: AsyncSession, state_id: uuid.UUID) -> dict[str, Any]:
    row = (
        await db.execute(select(State).where(State.id == state_id, State.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not row:
        raise AppError("State not found.", status_code=404)
    serialized = await _serialize_states(db, [row])
    return serialized[0]


async def create_state(db: AsyncSession, payload: StateCreateRequest) -> dict[str, Any]:
    name = payload.name.strip()
    code = (payload.code or _slug_code(name)).strip().upper()

    existing = (
        await db.execute(
            select(State).where(
                or_(func.lower(State.name) == name.lower(), func.lower(State.code) == code.lower()),
                State.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise AppError("A state with this name or code already exists.", status_code=400)

    state = State(name=name, code=code, status=_normalize_status(payload.status))
    db.add(state)
    await db.flush()

    for idx, d_in in enumerate(payload.districts or []):
        d_name = d_in.name.strip()
        if not d_name:
            continue
        d_code = (d_in.code or _slug_code(d_name, f"{code}_")).strip().upper()
        dist = District(
            state_id=state.id,
            name=d_name,
            code=f"{d_code}_{idx + 1}" if idx > 0 and not d_in.code else d_code,
            status=_normalize_status(d_in.status),
        )
        db.add(dist)

    await db.commit()
    await db.refresh(state)
    return await get_state(db, state.id)


async def update_state(
    db: AsyncSession, state_id: uuid.UUID, payload: StateUpdateRequest
) -> dict[str, Any]:
    state = (
        await db.execute(select(State).where(State.id == state_id, State.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not state:
        raise AppError("State not found.", status_code=404)

    if payload.name is not None:
        state.name = payload.name.strip()
    if payload.code is not None and payload.code.strip():
        state.code = payload.code.strip().upper()
    if payload.status is not None:
        state.status = _normalize_status(payload.status, state.status)

    if payload.remove_district_ids:
        rem_rows = (
            await db.execute(
                select(District).where(
                    District.id.in_(payload.remove_district_ids),
                    District.state_id == state.id,
                )
            )
        ).scalars().all()
        for r in rem_rows:
            r.is_deleted = True

    if payload.districts is not None:
        existing_dists = (
            await db.execute(
                select(District).where(District.state_id == state.id, District.is_deleted.is_(False))
            )
        ).scalars().all()
        by_id = {d.id: d for d in existing_dists}
        by_name = {d.name.lower(): d for d in existing_dists}

        for d_in in payload.districts:
            d_name = d_in.name.strip()
            if not d_name:
                continue
            d_code = (d_in.code or _slug_code(d_name)).strip().upper()
            target = None
            if d_in.id and d_in.id in by_id:
                target = by_id[d_in.id]
            elif d_name.lower() in by_name:
                target = by_name[d_name.lower()]

            if target:
                target.name = d_name
                if d_in.code:
                    target.code = d_code
                if d_in.status:
                    target.status = _normalize_status(d_in.status, target.status)
            else:
                db.add(
                    District(
                        state_id=state.id,
                        name=d_name,
                        code=d_code,
                        status=_normalize_status(d_in.status),
                    )
                )

    await db.commit()
    return await get_state(db, state.id)


async def delete_state(db: AsyncSession, state_id: uuid.UUID) -> None:
    state = (
        await db.execute(select(State).where(State.id == state_id, State.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not state:
        raise AppError("State not found.", status_code=404)
    state.is_deleted = True
    state.status = "INACTIVE"
    await db.commit()


# ==============================================================================
# Districts
# ==============================================================================

async def list_districts(
    db: AsyncSession,
    *,
    state_id: uuid.UUID | None = None,
    page: int = 1,
    limit: int = 100,
    search: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    stmt = select(District).where(District.is_deleted.is_(False))
    if state_id:
        stmt = stmt.where(District.state_id == state_id)
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(or_(District.name.ilike(q), District.code.ilike(q)))
    if status and status.strip():
        stmt = stmt.where(District.status == status.strip().upper())

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(District.name.asc())
            .offset((max(1, page) - 1) * max(1, limit))
            .limit(max(1, limit))
        )
    ).scalars().all()

    state_ids = list({r.state_id for r in rows})
    states_map = {}
    if state_ids:
        st_rows = (await db.execute(select(State).where(State.id.in_(state_ids)))).scalars().all()
        states_map = {s.id: s for s in st_rows}

    items = []
    for d in rows:
        st = states_map.get(d.state_id)
        items.append(
            {
                "id": str(d.id),
                "state_id": str(d.state_id),
                "name": d.name,
                "code": d.code,
                "status": d.status,
                "state": {"id": str(st.id), "name": st.name, "code": st.code} if st else None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
        )
    return paginated_data(items=items, total=total, page=page, limit=limit)


async def get_district(db: AsyncSession, district_id: uuid.UUID) -> dict[str, Any]:
    d = (
        await db.execute(
            select(District).where(District.id == district_id, District.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not d:
        raise AppError("District not found.", status_code=404)
    st = (await db.execute(select(State).where(State.id == d.state_id))).scalar_one_or_none()
    return {
        "id": str(d.id),
        "state_id": str(d.state_id),
        "name": d.name,
        "code": d.code,
        "status": d.status,
        "state": {"id": str(st.id), "name": st.name, "code": st.code} if st else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


async def create_district(db: AsyncSession, payload: DistrictCreateRequest) -> dict[str, Any]:
    name = payload.name.strip()
    code = (payload.code or _slug_code(name)).strip().upper()
    d = District(
        state_id=payload.state_id,
        name=name,
        code=code,
        status=_normalize_status(payload.status),
    )
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return await get_district(db, d.id)


async def update_district(
    db: AsyncSession, district_id: uuid.UUID, payload: DistrictUpdateRequest
) -> dict[str, Any]:
    d = (
        await db.execute(
            select(District).where(District.id == district_id, District.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not d:
        raise AppError("District not found.", status_code=404)
    if payload.state_id is not None:
        d.state_id = payload.state_id
    if payload.name is not None:
        d.name = payload.name.strip()
    if payload.code is not None and payload.code.strip():
        d.code = payload.code.strip().upper()
    if payload.status is not None:
        d.status = _normalize_status(payload.status, d.status)
    await db.commit()
    return await get_district(db, d.id)


async def delete_district(db: AsyncSession, district_id: uuid.UUID) -> None:
    d = (
        await db.execute(
            select(District).where(District.id == district_id, District.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not d:
        raise AppError("District not found.", status_code=404)
    d.is_deleted = True
    d.status = "INACTIVE"
    await db.commit()


# ==============================================================================
# ULBs
# ==============================================================================

async def list_ulbs(
    db: AsyncSession,
    *,
    district_id: uuid.UUID | None = None,
    page: int = 1,
    limit: int = 100,
    search: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    stmt = select(Ulb).where(Ulb.is_deleted.is_(False))
    if district_id:
        stmt = stmt.where(Ulb.district_id == district_id)
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(or_(Ulb.name.ilike(q), Ulb.code.ilike(q)))
    if status and status.strip():
        stmt = stmt.where(Ulb.status == status.strip().upper())

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(Ulb.name.asc())
            .offset((max(1, page) - 1) * max(1, limit))
            .limit(max(1, limit))
        )
    ).scalars().all()

    items = [
        {
            "id": str(u.id),
            "district_id": str(u.district_id),
            "name": u.name,
            "code": u.code,
            "status": u.status,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in rows
    ]
    return paginated_data(items=items, total=total, page=page, limit=limit)


async def get_ulb(db: AsyncSession, ulb_id: uuid.UUID) -> dict[str, Any]:
    u = (
        await db.execute(select(Ulb).where(Ulb.id == ulb_id, Ulb.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not u:
        raise AppError("ULB not found.", status_code=404)
    return {
        "id": str(u.id),
        "district_id": str(u.district_id),
        "name": u.name,
        "code": u.code,
        "status": u.status,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


async def create_ulb(db: AsyncSession, payload: UlbCreateRequest) -> dict[str, Any]:
    name = payload.name.strip()
    code = (payload.code or _slug_code(name)).strip().upper()
    u = Ulb(
        district_id=payload.district_id,
        name=name,
        code=code,
        status=_normalize_status(payload.status),
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return await get_ulb(db, u.id)


async def update_ulb(
    db: AsyncSession, ulb_id: uuid.UUID, payload: UlbUpdateRequest
) -> dict[str, Any]:
    u = (
        await db.execute(select(Ulb).where(Ulb.id == ulb_id, Ulb.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not u:
        raise AppError("ULB not found.", status_code=404)
    if payload.district_id is not None:
        u.district_id = payload.district_id
    if payload.name is not None:
        u.name = payload.name.strip()
    if payload.code is not None and payload.code.strip():
        u.code = payload.code.strip().upper()
    if payload.status is not None:
        u.status = _normalize_status(payload.status, u.status)
    await db.commit()
    return await get_ulb(db, u.id)


async def delete_ulb(db: AsyncSession, ulb_id: uuid.UUID) -> None:
    u = (
        await db.execute(select(Ulb).where(Ulb.id == ulb_id, Ulb.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not u:
        raise AppError("ULB not found.", status_code=404)
    u.is_deleted = True
    u.status = "INACTIVE"
    await db.commit()


# ==============================================================================
# Wards
# ==============================================================================

async def list_wards(
    db: AsyncSession,
    *,
    ulb_id: uuid.UUID | None = None,
    page: int = 1,
    limit: int = 100,
    search: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    stmt = select(Ward).where(Ward.is_deleted.is_(False))
    if ulb_id:
        stmt = stmt.where(Ward.ulb_id == ulb_id)
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(or_(Ward.name.ilike(q), Ward.code.ilike(q)))
    if status and status.strip():
        stmt = stmt.where(Ward.status == status.strip().upper())

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(Ward.name.asc())
            .offset((max(1, page) - 1) * max(1, limit))
            .limit(max(1, limit))
        )
    ).scalars().all()

    items = [
        {
            "id": str(w.id),
            "ulb_id": str(w.ulb_id),
            "name": w.name,
            "code": w.code,
            "status": w.status,
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
        for w in rows
    ]
    return paginated_data(items=items, total=total, page=page, limit=limit)


async def get_ward(db: AsyncSession, ward_id: uuid.UUID) -> dict[str, Any]:
    w = (
        await db.execute(select(Ward).where(Ward.id == ward_id, Ward.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not w:
        raise AppError("Ward not found.", status_code=404)
    return {
        "id": str(w.id),
        "ulb_id": str(w.ulb_id),
        "name": w.name,
        "code": w.code,
        "status": w.status,
        "created_at": w.created_at.isoformat() if w.created_at else None,
    }


async def create_ward(db: AsyncSession, payload: WardCreateRequest) -> dict[str, Any]:
    name = payload.name.strip()
    code = (payload.code or _slug_code(name)).strip().upper()
    w = Ward(
        ulb_id=payload.ulb_id,
        name=name,
        code=code,
        status=_normalize_status(payload.status),
    )
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return await get_ward(db, w.id)


async def update_ward(
    db: AsyncSession, ward_id: uuid.UUID, payload: WardUpdateRequest
) -> dict[str, Any]:
    w = (
        await db.execute(select(Ward).where(Ward.id == ward_id, Ward.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not w:
        raise AppError("Ward not found.", status_code=404)
    if payload.ulb_id is not None:
        w.ulb_id = payload.ulb_id
    if payload.name is not None:
        w.name = payload.name.strip()
    if payload.code is not None and payload.code.strip():
        w.code = payload.code.strip().upper()
    if payload.status is not None:
        w.status = _normalize_status(payload.status, w.status)
    await db.commit()
    return await get_ward(db, w.id)


async def delete_ward(db: AsyncSession, ward_id: uuid.UUID) -> None:
    w = (
        await db.execute(select(Ward).where(Ward.id == ward_id, Ward.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not w:
        raise AppError("Ward not found.", status_code=404)
    w.is_deleted = True
    w.status = "INACTIVE"
    await db.commit()
