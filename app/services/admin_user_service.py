"""
Admin & Generic User management service:
- School Admins (/api/v1/user/school)
- Content Admins (/api/v1/user/content)
- Generic Users (/api/v1/users)
"""

from __future__ import annotations

import secrets
import uuid
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import AppError, paginated_data
from app.core.security import hash_password
from app.models.assignments import UserSchool
from app.models.school import School
from app.models.user import User, UserStatus
from app.schemas.users import (
    ContentAdminCreateRequest,
    ContentAdminUpdateRequest,
    GenericUserCreateRequest,
    GenericUserUpdateRequest,
    SchoolAdminCreateRequest,
    SchoolAdminUpdateRequest,
)


def _normalize_user_status(status_val: str | None, default: str = UserStatus.ACTIVE) -> str:
    if not status_val:
        return default
    val = status_val.strip().upper()
    if val in (UserStatus.ACTIVE, UserStatus.INACTIVE, UserStatus.DELETED):
        return val
    return default


import re

_E164_PREFIX_RE = re.compile(
    r"^\+?(1|7|2[07]|3[0-469]|4[013-9]|5[1-8]|6[0-6]|8[1246]|9[0-58]|[2-9]\d{2})(\d{7,15})$"
)


def _format_phone(country_code: str | None, phone_number: str | None) -> tuple[str, str | None, str | None]:
    raw = (phone_number or "").strip()
    if not raw:
        cc = (country_code or "+91").strip()
        if not cc.startswith("+"):
            cc = f"+{cc}"
        return cc, None, None

    # If a combined E.164 string like "+971507652362" was passed without separate country_code
    if not country_code and (raw.startswith("+") or len(re.sub(r"\D", "", raw)) > 10):
        digits = re.sub(r"\D", "", raw)
        m = _E164_PREFIX_RE.match(digits)
        if m:
            cc = f"+{m.group(1)}"
            sub = m.group(2)
            return cc, sub, f"{cc}{sub}"

    cc = (country_code or "+91").strip()
    if not cc.startswith("+"):
        cc = f"+{cc}"
    if raw.startswith(cc):
        sub = raw[len(cc) :].strip()
    else:
        sub = raw.lstrip("+").strip()
    return cc, sub, f"{cc}{sub}"



from app.models.location import District, State


async def _serialize_users(db: AsyncSession, users: list[User]) -> list[dict[str, Any]]:
    if not users:
        return []

    user_ids = [u.id for u in users]
    us_rows = (
        await db.execute(
            select(UserSchool, School)
            .join(School, School.id == UserSchool.school_id)
            .where(
                UserSchool.user_id.in_(user_ids),
                UserSchool.is_deleted.is_(False),
                School.is_deleted.is_(False),
            )
            .order_by(School.name.asc())
        )
    ).all()

    state_ids = list({sch.state_id for _us, sch in us_rows if sch.state_id})
    district_ids = list({sch.district_id for _us, sch in us_rows if sch.district_id})

    states_map = {}
    if state_ids:
        st_rows = (await db.execute(select(State).where(State.id.in_(state_ids)))).scalars().all()
        states_map = {s.id: s for s in st_rows}

    districts_map = {}
    if district_ids:
        dt_rows = (
            await db.execute(select(District).where(District.id.in_(district_ids)))
        ).scalars().all()
        districts_map = {d.id: d for d in dt_rows}

    schools_by_user: dict[uuid.UUID, list[dict[str, Any]]] = {uid: [] for uid in user_ids}
    for us, sch in us_rows:
        st = states_map.get(sch.state_id) if sch.state_id else None
        dt = districts_map.get(sch.district_id) if sch.district_id else None
        state_name = st.name if st else None
        district_name = dt.name if dt else None
        region_name = (
            f"{district_name}, {state_name}"
            if district_name and state_name
            else (state_name or district_name)
        )
        school_obj = {
            "id": str(sch.id),
            "school_id": str(sch.id),
            "relation_id": str(us.id),
            "name": sch.name,
            "code": sch.udise_code,
            "udise_code": sch.udise_code,
            "state_name": state_name,
            "district_name": district_name,
            "region_name": region_name,
            "status": sch.status,
        }
        schools_by_user.setdefault(us.user_id, []).append(
            {
                "id": str(us.id),
                "relation_id": str(us.id),
                "school_id": str(sch.id),
                "name": sch.name,
                "code": sch.udise_code,
                "udise_code": sch.udise_code,
                "state_name": state_name,
                "district_name": district_name,
                "region_name": region_name,
                "status": sch.status,
                "school": school_obj,
            }
        )

    result = []
    for u in users:
        u_schools = schools_by_user.get(u.id, [])
        primary_school = u_schools[0]["school"] if u_schools else None
        result.append(
            {
                "id": str(u.id),
                "user_id": str(u.id),
                "first_name": u.first_name,
                "last_name": u.last_name,
                "full_name": u.full_name,
                "name": u.full_name,
                "email": u.email,
                "country_code": u.country_code or "+91",
                "phone_number": u.phone_number or u.phone,
                "phone": u.phone or u.phone_number,
                "gender": u.gender,
                "user_type": u.user_type,
                "role": u.user_type,
                "role_id": u.user_type,
                "status": u.status,
                "is_first_login": u.is_first_login,
                "schools": u_schools,
                "assigned_schools": [s["school"] for s in u_schools],
                "school_ids": [s["school_id"] for s in u_schools],
                "school": primary_school,
                "school_id": primary_school["id"] if primary_school else None,
                "school_name": primary_school["name"] if primary_school else None,
                "state_name": primary_school.get("state_name") if primary_school else None,
                "district_name": primary_school.get("district_name") if primary_school else None,
                "region_name": primary_school.get("region_name") if primary_school else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "updated_at": u.updated_at.isoformat() if u.updated_at else None,
            }
        )
    return result


async def _ensure_email_and_phone_unique(
    db: AsyncSession,
    *,
    email: str,
    phone: str | None = None,
    exclude_user_id: uuid.UUID | None = None,
) -> None:
    stmt = select(User).where(func.lower(User.email) == email.lower())
    if exclude_user_id:
        stmt = stmt.where(User.id != exclude_user_id)
    existing_email = (await db.execute(stmt)).scalar_one_or_none()
    if existing_email:
        raise AppError(
            "A user with this email address already exists.",
            status_code=400,
            errors={"email": "Email is already registered."},
        )

    if phone:
        p_stmt = select(User).where(User.phone == phone)
        if exclude_user_id:
            p_stmt = p_stmt.where(User.id != exclude_user_id)
        existing_phone = (await db.execute(p_stmt)).scalar_one_or_none()
        if existing_phone:
            raise AppError(
                "A user with this phone number already exists.",
                status_code=400,
                errors={"phone_number": "Phone number is already registered."},
            )


async def _sync_user_schools(
    db: AsyncSession,
    user_id: uuid.UUID,
    role: str,
    school_ids: list[uuid.UUID] | None,
    removed_relations: list[uuid.UUID] | None = None,
) -> None:
    if removed_relations:
        await db.execute(
            delete(UserSchool).where(
                UserSchool.user_id == user_id,
                or_(
                    UserSchool.id.in_(removed_relations),
                    UserSchool.school_id.in_(removed_relations),
                ),
            )
        )

    if school_ids is not None:
        unique_sids = set(school_ids)
        if unique_sids:
            found_schools = (
                await db.execute(
                    select(School.id).where(
                        School.id.in_(unique_sids),
                        School.is_deleted.is_(False),
                    )
                )
            ).scalars().all()
            if len(found_schools) != len(unique_sids):
                raise AppError(
                    "One or more specified schools do not exist.",
                    status_code=404,
                    errors={"school_ids": "School not found."},
                )

        existing_rows = (
            await db.execute(select(UserSchool).where(UserSchool.user_id == user_id))
        ).scalars().all()
        by_school = {r.school_id: r for r in existing_rows}

        for sid in unique_sids:
            if sid in by_school:
                by_school[sid].is_deleted = False
            else:
                db.add(UserSchool(user_id=user_id, school_id=sid, role=role))


# ==============================================================================
# School Admins (/api/v1/user/school)
# ==============================================================================

async def list_school_admins(
    db: AsyncSession,
    *,
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    status: str | None = None,
    school_id: uuid.UUID | None = None,
    unassigned: bool | None = None,
) -> dict[str, Any]:
    stmt = select(User).where(
        User.user_type == "school_admin",
        User.is_deleted.is_(False),
    )
    if school_id:
        uid_sub = select(UserSchool.user_id).where(
            UserSchool.school_id == school_id,
            UserSchool.is_deleted.is_(False),
        )
        stmt = stmt.where(User.id.in_(uid_sub))
    elif unassigned is True:
        assigned_sub = (
            select(UserSchool.user_id)
            .join(School, School.id == UserSchool.school_id)
            .where(
                UserSchool.is_deleted.is_(False),
                School.is_deleted.is_(False),
            )
        )
        stmt = stmt.where(User.id.not_in(assigned_sub))
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                User.first_name.ilike(q),
                User.last_name.ilike(q),
                User.email.ilike(q),
                User.phone_number.ilike(q),
                User.phone.ilike(q),
            )
        )
    if status and status.strip():
        stmt = stmt.where(User.status == _normalize_user_status(status))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(User.created_at.desc(), User.first_name.asc())
            .offset((max(1, page) - 1) * max(1, limit))
            .limit(max(1, limit))
        )
    ).scalars().all()

    items = await _serialize_users(db, list(rows))
    return paginated_data(items=items, total=total, page=page, limit=limit)



async def get_school_admin(db: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    u = (
        await db.execute(
            select(User).where(User.id == user_id, User.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not u:
        raise AppError("School admin not found.", status_code=404)
    items = await _serialize_users(db, [u])
    return items[0]


async def create_school_admin(
    db: AsyncSession,
    payload: SchoolAdminCreateRequest,
    *,
    created_by: uuid.UUID | None = None,
) -> dict[str, Any]:
    email = payload.email.strip().lower()
    cc, phone_num, unique_phone = _format_phone(
        payload.country_code, payload.phone_number or payload.phone
    )
    await _ensure_email_and_phone_unique(db, email=email, phone=unique_phone)

    raw_password = (payload.password or "").strip() or f"Admin@{secrets.randbelow(9000) + 1000}"
    u = User(
        email=email,
        hashed_password=hash_password(raw_password),
        first_name=payload.first_name.strip(),
        last_name=(payload.last_name or "").strip(),
        country_code=cc,
        phone_number=phone_num,
        phone=unique_phone,
        user_type="school_admin",
        status=_normalize_user_status(payload.status),
        created_by=created_by,
    )
    db.add(u)
    await db.flush()

    await _sync_user_schools(db, u.id, "school_admin", payload.school_ids)
    await db.commit()
    return await get_school_admin(db, u.id)


async def update_school_admin(
    db: AsyncSession, user_id: uuid.UUID, payload: SchoolAdminUpdateRequest
) -> dict[str, Any]:
    u = (
        await db.execute(
            select(User).where(User.id == user_id, User.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not u:
        raise AppError("School admin not found.", status_code=404)

    new_email = payload.email.strip().lower() if payload.email else u.email
    raw_phone_in = (
        payload.phone_number
        if payload.phone_number is not None
        else (payload.phone if payload.phone is not None else u.phone_number)
    )
    cc, phone_num, unique_phone = _format_phone(
        payload.country_code or u.country_code, raw_phone_in
    )
    await _ensure_email_and_phone_unique(
        db, email=new_email, phone=unique_phone, exclude_user_id=u.id
    )

    u.email = new_email
    if payload.first_name is not None:
        u.first_name = payload.first_name.strip()
    if payload.last_name is not None:
        u.last_name = payload.last_name.strip()
    u.country_code = cc
    u.phone_number = phone_num
    u.phone = unique_phone
    if payload.password and payload.password.strip():
        u.hashed_password = hash_password(payload.password.strip())
    if payload.status is not None:
        u.status = _normalize_user_status(payload.status, u.status)

    await _sync_user_schools(
        db,
        u.id,
        "school_admin",
        payload.school_ids,
        payload.removed_relations,
    )
    await db.commit()
    return await get_school_admin(db, u.id)


async def delete_school_admin(db: AsyncSession, user_id: uuid.UUID) -> None:
    u = (
        await db.execute(
            select(User).where(User.id == user_id, User.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not u:
        raise AppError("School admin not found.", status_code=404)
    u.is_deleted = True
    u.status = UserStatus.DELETED

    us_rows = (
        await db.execute(
            select(UserSchool).where(
                UserSchool.user_id == u.id, UserSchool.is_deleted.is_(False)
            )
        )
    ).scalars().all()
    for us in us_rows:
        us.is_deleted = True

    await db.commit()



# ==============================================================================
# Content Admins (/api/v1/user/content)
# ==============================================================================

async def list_content_admins(
    db: AsyncSession,
    *,
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    stmt = select(User).where(
        User.user_type.in_(["content_admin", "content_manager"]),
        User.is_deleted.is_(False),
    )
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                User.first_name.ilike(q),
                User.last_name.ilike(q),
                User.email.ilike(q),
                User.phone_number.ilike(q),
                User.phone.ilike(q),
            )
        )
    if status and status.strip():
        stmt = stmt.where(User.status == _normalize_user_status(status))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(User.created_at.desc(), User.first_name.asc())
            .offset((max(1, page) - 1) * max(1, limit))
            .limit(max(1, limit))
        )
    ).scalars().all()

    items = await _serialize_users(db, list(rows))
    return paginated_data(items=items, total=total, page=page, limit=limit)


async def get_content_admin(db: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    u = (
        await db.execute(
            select(User).where(User.id == user_id, User.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not u:
        raise AppError("Content admin not found.", status_code=404)
    items = await _serialize_users(db, [u])
    return items[0]


async def create_content_admin(
    db: AsyncSession,
    payload: ContentAdminCreateRequest,
    *,
    created_by: uuid.UUID | None = None,
) -> dict[str, Any]:
    email = payload.email.strip().lower()
    cc, phone_num, unique_phone = _format_phone(
        payload.country_code, payload.phone_number or payload.phone
    )
    await _ensure_email_and_phone_unique(db, email=email, phone=unique_phone)

    raw_password = (payload.password or "").strip() or f"Content@{secrets.randbelow(9000) + 1000}"
    u = User(
        email=email,
        hashed_password=hash_password(raw_password),
        first_name=payload.first_name.strip(),
        last_name=(payload.last_name or "").strip(),
        country_code=cc,
        phone_number=phone_num,
        phone=unique_phone,
        user_type="content_admin",
        status=_normalize_user_status(payload.status),
        created_by=created_by,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return await get_content_admin(db, u.id)


async def update_content_admin(
    db: AsyncSession, user_id: uuid.UUID, payload: ContentAdminUpdateRequest
) -> dict[str, Any]:
    u = (
        await db.execute(
            select(User).where(User.id == user_id, User.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not u:
        raise AppError("Content admin not found.", status_code=404)

    new_email = payload.email.strip().lower() if payload.email else u.email
    raw_phone_in = (
        payload.phone_number
        if payload.phone_number is not None
        else (payload.phone if payload.phone is not None else u.phone_number)
    )
    cc, phone_num, unique_phone = _format_phone(
        payload.country_code or u.country_code, raw_phone_in
    )
    await _ensure_email_and_phone_unique(
        db, email=new_email, phone=unique_phone, exclude_user_id=u.id
    )

    u.email = new_email
    if payload.first_name is not None:
        u.first_name = payload.first_name.strip()
    if payload.last_name is not None:
        u.last_name = payload.last_name.strip()
    u.country_code = cc
    u.phone_number = phone_num
    u.phone = unique_phone
    if payload.password and payload.password.strip():
        u.hashed_password = hash_password(payload.password.strip())
    if payload.status is not None:
        u.status = _normalize_user_status(payload.status, u.status)

    await db.commit()
    return await get_content_admin(db, u.id)


async def delete_content_admin(db: AsyncSession, user_id: uuid.UUID) -> None:
    u = (
        await db.execute(
            select(User).where(User.id == user_id, User.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not u:
        raise AppError("Content admin not found.", status_code=404)
    u.is_deleted = True
    u.status = UserStatus.DELETED
    await db.commit()


# ==============================================================================
# Generic Users (/api/v1/users)
# ==============================================================================

async def list_generic_users(
    db: AsyncSession,
    *,
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    status: str | None = None,
    role: str | None = None,
    school_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    stmt = select(User).where(User.is_deleted.is_(False))
    if role and role.strip():
        stmt = stmt.where(User.user_type == role.strip().lower())
    if school_id:
        uid_sub = select(UserSchool.user_id).where(
            UserSchool.school_id == school_id,
            UserSchool.is_deleted.is_(False),
        )
        stmt = stmt.where(User.id.in_(uid_sub))
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                User.first_name.ilike(q),
                User.last_name.ilike(q),
                User.email.ilike(q),
                User.phone_number.ilike(q),
            )
        )
    if status and status.strip():
        stmt = stmt.where(User.status == _normalize_user_status(status))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(User.created_at.desc(), User.first_name.asc())
            .offset((max(1, page) - 1) * max(1, limit))
            .limit(max(1, limit))
        )
    ).scalars().all()

    items = await _serialize_users(db, list(rows))
    return paginated_data(items=items, total=total, page=page, limit=limit)


async def get_generic_user(db: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    return await get_school_admin(db, user_id)


async def create_generic_user(
    db: AsyncSession,
    payload: GenericUserCreateRequest,
    *,
    created_by: uuid.UUID | None = None,
) -> dict[str, Any]:
    email = payload.email.strip().lower()
    cc, phone_num, unique_phone = _format_phone(
        payload.country_code, payload.phone_number or payload.phone
    )
    await _ensure_email_and_phone_unique(db, email=email, phone=unique_phone)

    user_type = (
        payload.user_type or payload.role_id or payload.role or "school_admin"
    ).strip().lower()
    raw_password = (payload.password or "").strip() or f"User@{secrets.randbelow(9000) + 1000}"

    u = User(
        email=email,
        hashed_password=hash_password(raw_password),
        first_name=payload.first_name.strip(),
        last_name=(payload.last_name or "").strip(),
        country_code=cc,
        phone_number=phone_num,
        phone=unique_phone,
        user_type=user_type,
        status=_normalize_user_status(payload.status),
        created_by=created_by,
    )
    db.add(u)
    await db.flush()

    if payload.school_ids:
        await _sync_user_schools(db, u.id, user_type, payload.school_ids)

    await db.commit()
    return await get_generic_user(db, u.id)


async def update_generic_user(
    db: AsyncSession, user_id: uuid.UUID, payload: GenericUserUpdateRequest
) -> dict[str, Any]:
    u = (
        await db.execute(
            select(User).where(User.id == user_id, User.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not u:
        raise AppError("User not found.", status_code=404)

    new_email = payload.email.strip().lower() if payload.email else u.email
    raw_phone_in = (
        payload.phone_number
        if payload.phone_number is not None
        else (payload.phone if payload.phone is not None else u.phone_number)
    )
    cc, phone_num, unique_phone = _format_phone(
        payload.country_code or u.country_code, raw_phone_in
    )
    await _ensure_email_and_phone_unique(
        db, email=new_email, phone=unique_phone, exclude_user_id=u.id
    )

    u.email = new_email
    if payload.first_name is not None:
        u.first_name = payload.first_name.strip()
    if payload.last_name is not None:
        u.last_name = payload.last_name.strip()
    u.country_code = cc
    u.phone_number = phone_num
    u.phone = unique_phone

    new_role = payload.user_type or payload.role_id or payload.role
    if new_role:
        u.user_type = new_role.strip().lower()
    if payload.password and payload.password.strip():
        u.hashed_password = hash_password(payload.password.strip())
    if payload.status is not None:
        u.status = _normalize_user_status(payload.status, u.status)

    await _sync_user_schools(
        db,
        u.id,
        u.user_type,
        payload.school_ids,
        payload.removed_relations,
    )
    await db.commit()
    return await get_generic_user(db, u.id)


async def delete_generic_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    await delete_school_admin(db, user_id)
