"""
School Management service (/api/v1/school):
- Paginated list with stat cards in pagination.extra
- Detail view with nested state/district/ulb/ward, school_admins, and class_section
- Create & Update with atomic school_admin_ids + class_section synchronization
- School class-section listing & custom naming (/api/v1/school/{id}/class-section)
- CSV export (/api/v1/school/export)
"""

from __future__ import annotations

import csv
import io
import uuid
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import AppError, paginated_data
from app.models.academic import AcademicClass, Section
from app.models.assignments import StudentProfile, TeacherAssignment, UserSchool
from app.models.location import District, State, Ulb, Ward
from app.models.school import School, SchoolClassSection
from app.models.user import User
from app.schemas.school import (
    SchoolClassSectionPatchRequest,
    SchoolCreateRequest,
    SchoolUpdateRequest,
)


def _normalize_status(status_val: str | None, default: str = "ACTIVE") -> str:
    if not status_val:
        return default
    val = status_val.strip().upper()
    if val in ("ACTIVE", "INACTIVE", "DELETED"):
        return val
    return default


async def _serialize_schools(
    db: AsyncSession, schools: list[School]
) -> list[dict[str, Any]]:
    if not schools:
        return []

    school_ids = [s.id for s in schools]
    state_ids = list({s.state_id for s in schools if s.state_id})
    district_ids = list({s.district_id for s in schools if s.district_id})
    ulb_ids = list({s.ulb_id for s in schools if s.ulb_id})
    ward_ids = list({s.ward_id for s in schools if s.ward_id})

    states_map = {}
    if state_ids:
        rows = (await db.execute(select(State).where(State.id.in_(state_ids)))).scalars().all()
        states_map = {r.id: r for r in rows}

    districts_map = {}
    if district_ids:
        rows = (
            await db.execute(select(District).where(District.id.in_(district_ids)))
        ).scalars().all()
        districts_map = {r.id: r for r in rows}

    ulbs_map = {}
    if ulb_ids:
        rows = (await db.execute(select(Ulb).where(Ulb.id.in_(ulb_ids)))).scalars().all()
        ulbs_map = {r.id: r for r in rows}

    wards_map = {}
    if ward_ids:
        rows = (await db.execute(select(Ward).where(Ward.id.in_(ward_ids)))).scalars().all()
        wards_map = {r.id: r for r in rows}

    # Fetch school admins via user_schools
    admin_rows = (
        await db.execute(
            select(UserSchool, User)
            .join(User, User.id == UserSchool.user_id)
            .where(
                UserSchool.school_id.in_(school_ids),
                UserSchool.is_deleted.is_(False),
                User.is_deleted.is_(False),
            )
            .order_by(User.first_name.asc())
        )
    ).all()

    admins_by_school: dict[uuid.UUID, list[dict[str, Any]]] = {sid: [] for sid in school_ids}
    for us, usr in admin_rows:
        user_summary = {
            "id": str(usr.id),
            "user_id": str(usr.id),
            "relation_id": str(us.id),
            "first_name": usr.first_name,
            "last_name": usr.last_name,
            "full_name": usr.full_name,
            "name": usr.full_name,
            "email": usr.email,
            "country_code": usr.country_code or "+91",
            "phone_number": usr.phone_number or usr.phone,
            "phone": usr.phone or usr.phone_number,
            "status": usr.status,
            "role": us.role or usr.user_type,
        }
        admins_by_school.setdefault(us.school_id, []).append(
            {
                **user_summary,
                "school_admin": user_summary,
                "user": user_summary,
            }
        )

    # Fetch class-section mappings
    scs_rows = (
        await db.execute(
            select(SchoolClassSection, AcademicClass, Section)
            .join(AcademicClass, AcademicClass.id == SchoolClassSection.class_id)
            .join(Section, Section.id == SchoolClassSection.section_id)
            .where(
                SchoolClassSection.school_id.in_(school_ids),
                SchoolClassSection.is_deleted.is_(False),
                AcademicClass.is_deleted.is_(False),
                Section.is_deleted.is_(False),
            )
            .order_by(AcademicClass.created_at.asc(), AcademicClass.name.asc(), Section.name.asc())
        )
    ).all()

    class_sections_by_school: dict[uuid.UUID, dict[uuid.UUID, dict[str, Any]]] = {
        sid: {} for sid in school_ids
    }
    flat_scs_by_school: dict[uuid.UUID, list[dict[str, Any]]] = {sid: [] for sid in school_ids}

    for scs, cls_obj, sec_obj in scs_rows:
        school_dict = class_sections_by_school.setdefault(scs.school_id, {})
        if cls_obj.id not in school_dict:
            school_dict[cls_obj.id] = {
                "id": str(cls_obj.id),
                "class_id": str(cls_obj.id),
                "name": cls_obj.name,
                "code": cls_obj.code,
                "class": {
                    "id": str(cls_obj.id),
                    "name": cls_obj.name,
                    "code": cls_obj.code,
                },
                "sections": [],
                "section_ids": [],
            }
        sec_entry = {
            "id": str(sec_obj.id),
            "section_id": str(sec_obj.id),
            "relation_id": str(scs.id),
            "school_class_section_id": str(scs.id),
            "name": scs.custom_name or sec_obj.name,
            "code": scs.custom_code or sec_obj.code or sec_obj.name,
            "section_name": sec_obj.name,
            "custom_name": scs.custom_name,
            "custom_code": scs.custom_code,
            "status": scs.status,
        }
        school_dict[cls_obj.id]["sections"].append(sec_entry)
        school_dict[cls_obj.id]["section_ids"].append(str(sec_obj.id))

        flat_scs_by_school.setdefault(scs.school_id, []).append(
            {
                "id": str(scs.id),
                "school_id": str(scs.school_id),
                "class_id": str(cls_obj.id),
                "class_name": cls_obj.name,
                "section_id": str(sec_obj.id),
                "section_name": sec_obj.name,
                "custom_name": scs.custom_name,
                "custom_code": scs.custom_code,
                "status": scs.status,
            }
        )

    # Counts of active (non-deleted) students & teachers per school
    student_counts_rows = (
        await db.execute(
            select(StudentProfile.school_id, func.count(StudentProfile.id))
            .join(User, User.id == StudentProfile.user_id)
            .where(
                StudentProfile.school_id.in_(school_ids),
                StudentProfile.is_deleted.is_(False),
                User.is_deleted.is_(False),
            )
            .group_by(StudentProfile.school_id)
        )
    ).all()
    student_counts = {r[0]: r[1] for r in student_counts_rows}

    teacher_counts_rows = (
        await db.execute(
            select(
                TeacherAssignment.school_id,
                func.count(func.distinct(TeacherAssignment.teacher_id)),
            )
            .join(User, User.id == TeacherAssignment.teacher_id)
            .where(
                TeacherAssignment.school_id.in_(school_ids),
                TeacherAssignment.is_deleted.is_(False),
                User.is_deleted.is_(False),
            )
            .group_by(TeacherAssignment.school_id)
        )
    ).all()
    teacher_counts = {r[0]: r[1] for r in teacher_counts_rows}


    result = []
    for s in schools:
        st = states_map.get(s.state_id) if s.state_id else None
        dt = districts_map.get(s.district_id) if s.district_id else None
        ul = ulbs_map.get(s.ulb_id) if s.ulb_id else None
        wd = wards_map.get(s.ward_id) if s.ward_id else None
        admins = admins_by_school.get(s.id, [])
        grouped_cs = list(class_sections_by_school.get(s.id, {}).values())

        result.append(
            {
                "id": str(s.id),
                "school_id": str(s.id),
                "name": s.name,
                "code": s.udise_code,
                "udise_code": s.udise_code,
                "country_code": s.country_code or "+91",
                "phone": s.phone,
                "phone_number": s.phone,
                "status": s.status,
                "state_id": str(s.state_id) if s.state_id else None,
                "district_id": str(s.district_id) if s.district_id else None,
                "ulb_id": str(s.ulb_id) if s.ulb_id else None,
                "ward_id": str(s.ward_id) if s.ward_id else None,
                "state": {"id": str(st.id), "name": st.name, "code": st.code} if st else None,
                "district": {"id": str(dt.id), "name": dt.name, "code": dt.code} if dt else None,
                "ulb": {"id": str(ul.id), "name": ul.name, "code": ul.code} if ul else None,
                "ward": {"id": str(wd.id), "name": wd.name, "code": wd.code} if wd else None,
                "state_name": st.name if st else None,
                "district_name": dt.name if dt else None,
                "ulb_name": ul.name if ul else None,
                "ward_name": wd.name if wd else None,
                "admin_users": admins,
                "school_admins": admins,
                "school_admin_ids": [a["id"] for a in admins],
                "class_section": grouped_cs,
                "class_sections": grouped_cs,
                "school_class_sections": flat_scs_by_school.get(s.id, []),
                "total_students": student_counts.get(s.id, 0),
                "student_count": student_counts.get(s.id, 0),
                "total_teachers": teacher_counts.get(s.id, 0),
                "teacher_count": teacher_counts.get(s.id, 0),
                "sync_status": "ONLINE" if s.status == "ACTIVE" else "OFFLINE",
                "sync_rate": 100 if s.status == "ACTIVE" else 0,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
        )
    return result


async def list_schools(
    db: AsyncSession,
    *,
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    status: str | None = None,
    state_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    ulb_id: uuid.UUID | None = None,
    ward_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    stmt = select(School).where(School.is_deleted.is_(False))
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                School.name.ilike(q),
                School.udise_code.ilike(q),
                School.phone.ilike(q),
            )
        )
    if status and status.strip():
        stmt = stmt.where(School.status == status.strip().upper())
    if state_id:
        stmt = stmt.where(School.state_id == state_id)
    if district_id:
        stmt = stmt.where(School.district_id == district_id)
    if ulb_id:
        stmt = stmt.where(School.ulb_id == ulb_id)
    if ward_id:
        stmt = stmt.where(School.ward_id == ward_id)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    # Compute overall stat cards for SchoolsPage.jsx
    total_all = (
        await db.execute(select(func.count(School.id)).where(School.is_deleted.is_(False)))
    ).scalar_one()
    active_all = (
        await db.execute(
            select(func.count(School.id)).where(
                School.is_deleted.is_(False), School.status == "ACTIVE"
            )
        )
    ).scalar_one()
    offline_all = max(0, total_all - active_all)

    rows = (
        await db.execute(
            stmt.order_by(School.created_at.desc(), School.name.asc())
            .offset((max(1, page) - 1) * max(1, limit))
            .limit(max(1, limit))
        )
    ).scalars().all()

    items = await _serialize_schools(db, list(rows))
    extra = {
        "total_schools": total_all,
        "active_schools": active_all,
        "offline_schools": offline_all,
        "average_sync_rate": 100 if total_all > 0 else 0,
    }
    return paginated_data(items=items, total=total, page=page, limit=limit, extra=extra)


async def get_school(db: AsyncSession, school_id: uuid.UUID) -> dict[str, Any]:
    s = (
        await db.execute(
            select(School).where(School.id == school_id, School.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not s:
        raise AppError("School not found.", status_code=404)
    items = await _serialize_schools(db, [s])
    return items[0]


async def _sync_school_admins(
    db: AsyncSession,
    school_id: uuid.UUID,
    admin_ids: list[uuid.UUID] | None,
    removed_relations: list[uuid.UUID] | None = None,
) -> None:
    if removed_relations:
        await db.execute(
            delete(UserSchool).where(
                UserSchool.school_id == school_id,
                or_(
                    UserSchool.id.in_(removed_relations),
                    UserSchool.user_id.in_(removed_relations),
                ),
            )
        )

    if admin_ids is not None:
        unique_ids = set(admin_ids)
        if unique_ids:
            target_users = (
                await db.execute(
                    select(User).where(
                        User.id.in_(unique_ids),
                        User.is_deleted.is_(False),
                    )
                )
            ).scalars().all()
            if len(target_users) != len(unique_ids):
                raise AppError(
                    "One or more specified school admins do not exist.",
                    status_code=404,
                    errors={"school_admin_ids": "School admin not found."},
                )
            for u in target_users:
                if u.user_type.lower() != "school_admin":
                    raise AppError(
                        f"User '{u.email}' does not have the school_admin role.",
                        status_code=400,
                        errors={"school_admin_ids": "Assigned user must have the school_admin role."},
                    )

        existing_rows = (
            await db.execute(
                select(UserSchool).where(UserSchool.school_id == school_id)
            )
        ).scalars().all()
        by_user_id = {r.user_id: r for r in existing_rows}

        for uid in unique_ids:
            if uid in by_user_id:
                by_user_id[uid].is_deleted = False
            else:
                db.add(UserSchool(user_id=uid, school_id=school_id, role="school_admin"))



async def _sync_school_class_sections(
    db: AsyncSession,
    school_id: uuid.UUID,
    class_sections: list[Any] | None,
    removed_class_sections: list[Any] | None = None,
) -> None:
    if removed_class_sections:
        for rem in removed_class_sections:
            cid = rem.class_id if hasattr(rem, "class_id") else uuid.UUID(str(rem["class_id"]))
            sec_ids = (
                rem.section_ids
                if hasattr(rem, "section_ids")
                else [uuid.UUID(str(x)) for x in (rem.get("section_ids") or [])]
            )
            if sec_ids:
                await db.execute(
                    delete(SchoolClassSection).where(
                        SchoolClassSection.school_id == school_id,
                        SchoolClassSection.class_id == cid,
                        SchoolClassSection.section_id.in_(sec_ids),
                    )
                )
            else:
                await db.execute(
                    delete(SchoolClassSection).where(
                        SchoolClassSection.school_id == school_id,
                        SchoolClassSection.class_id == cid,
                    )
                )

    if class_sections is not None:
        existing_rows = (
            await db.execute(
                select(SchoolClassSection).where(SchoolClassSection.school_id == school_id)
            )
        ).scalars().all()
        by_pair = {(r.class_id, r.section_id): r for r in existing_rows}

        for entry in class_sections:
            cid = entry.class_id if hasattr(entry, "class_id") else uuid.UUID(str(entry["class_id"]))
            sec_ids = (
                entry.section_ids
                if hasattr(entry, "section_ids")
                else [uuid.UUID(str(x)) for x in (entry.get("section_ids") or [])]
            )
            for sid in set(sec_ids):
                pair = (cid, sid)
                if pair in by_pair:
                    by_pair[pair].is_deleted = False
                    by_pair[pair].status = "ACTIVE"
                else:
                    db.add(
                        SchoolClassSection(
                            school_id=school_id,
                            class_id=cid,
                            section_id=sid,
                            status="ACTIVE",
                        )
                    )


async def create_school(db: AsyncSession, payload: SchoolCreateRequest) -> dict[str, Any]:
    name = payload.name.strip()
    udise_code = payload.udise_code.strip()

    existing = (
        await db.execute(
            select(School).where(
                func.lower(School.udise_code) == udise_code.lower(),
                School.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise AppError(
            "A school with this UDISE code already exists.",
            status_code=400,
            errors={"udise_code": "UDISE code is already in use."},
        )

    school = School(
        name=name,
        udise_code=udise_code,
        country_code=(payload.country_code or "+91").strip(),
        phone=payload.phone.strip() if payload.phone else None,
        state_id=payload.state_id,
        district_id=payload.district_id,
        ulb_id=payload.ulb_id,
        ward_id=payload.ward_id,
        status=_normalize_status(payload.status),
    )
    db.add(school)
    await db.flush()

    await _sync_school_admins(db, school.id, payload.school_admin_ids)
    await _sync_school_class_sections(db, school.id, payload.class_section)

    await db.commit()
    return await get_school(db, school.id)


async def update_school(
    db: AsyncSession, school_id: uuid.UUID, payload: SchoolUpdateRequest
) -> dict[str, Any]:
    school = (
        await db.execute(
            select(School).where(School.id == school_id, School.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not school:
        raise AppError("School not found.", status_code=404)

    if payload.udise_code is not None and payload.udise_code.strip():
        new_code = payload.udise_code.strip()
        if new_code.lower() != school.udise_code.lower():
            dup = (
                await db.execute(
                    select(School).where(
                        func.lower(School.udise_code) == new_code.lower(),
                        School.id != school.id,
                        School.is_deleted.is_(False),
                    )
                )
            ).scalar_one_or_none()
            if dup:
                raise AppError("Another school with this UDISE code already exists.", status_code=400)
            school.udise_code = new_code

    if payload.name is not None and payload.name.strip():
        school.name = payload.name.strip()
    if payload.country_code is not None:
        school.country_code = payload.country_code.strip() or "+91"
    if payload.phone is not None:
        school.phone = payload.phone.strip() if payload.phone else None
    if payload.state_id is not None:
        school.state_id = payload.state_id
    if payload.district_id is not None:
        school.district_id = payload.district_id
    if "ulb_id" in payload.model_fields_set:
        school.ulb_id = payload.ulb_id
    if "ward_id" in payload.model_fields_set:
        school.ward_id = payload.ward_id
    if payload.status is not None:
        school.status = _normalize_status(payload.status, school.status)

    await _sync_school_admins(
        db,
        school.id,
        payload.school_admin_ids,
        payload.removed_relations,
    )
    await _sync_school_class_sections(
        db,
        school.id,
        payload.class_section,
        payload.removed_class_section,
    )

    await db.commit()
    return await get_school(db, school.id)


async def delete_school(db: AsyncSession, school_id: uuid.UUID) -> None:
    school = (
        await db.execute(
            select(School).where(School.id == school_id, School.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not school:
        raise AppError("School not found.", status_code=404)
    school.is_deleted = True
    school.status = "INACTIVE"

    scs_rows = (
        await db.execute(
            select(SchoolClassSection).where(
                SchoolClassSection.school_id == school.id,
                SchoolClassSection.is_deleted.is_(False),
            )
        )
    ).scalars().all()
    for scs in scs_rows:
        scs.is_deleted = True

    us_rows = (
        await db.execute(
            select(UserSchool).where(
                UserSchool.school_id == school.id,
                UserSchool.is_deleted.is_(False),
            )
        )
    ).scalars().all()
    for us in us_rows:
        us.is_deleted = True

    await db.commit()



async def list_school_class_sections(
    db: AsyncSession,
    school_id: uuid.UUID,
    *,
    page: int = 1,
    limit: int = 100,
    search: str | None = None,
) -> dict[str, Any]:
    stmt = (
        select(SchoolClassSection, AcademicClass, Section)
        .join(AcademicClass, AcademicClass.id == SchoolClassSection.class_id)
        .join(Section, Section.id == SchoolClassSection.section_id)
        .where(
            SchoolClassSection.school_id == school_id,
            SchoolClassSection.is_deleted.is_(False),
            AcademicClass.is_deleted.is_(False),
            Section.is_deleted.is_(False),
        )
    )
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                AcademicClass.name.ilike(q),
                Section.name.ilike(q),
                SchoolClassSection.custom_name.ilike(q),
            )
        )

    rows = (
        await db.execute(
            stmt.order_by(AcademicClass.created_at.asc(), Section.name.asc())
        )
    ).all()

    items = [
        {
            "id": str(scs.id),
            "school_id": str(scs.school_id),
            "class_id": str(cls_obj.id),
            "class_name": cls_obj.name,
            "class": {"id": str(cls_obj.id), "name": cls_obj.name, "code": cls_obj.code},
            "section_id": str(sec_obj.id),
            "section_name": sec_obj.name,
            "section": {"id": str(sec_obj.id), "name": sec_obj.name, "code": sec_obj.code},
            "name": scs.custom_name or f"{cls_obj.name} - {sec_obj.name}",
            "code": scs.custom_code or sec_obj.code or sec_obj.name,
            "custom_name": scs.custom_name,
            "custom_code": scs.custom_code,
            "status": scs.status,
        }
        for scs, cls_obj, sec_obj in rows
    ]
    total = len(items)
    start = (max(1, page) - 1) * max(1, limit)
    paged_items = items[start : start + max(1, limit)]
    return paginated_data(items=paged_items, total=total, page=page, limit=limit)


async def update_school_class_section(
    db: AsyncSession,
    school_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: SchoolClassSectionPatchRequest,
) -> dict[str, Any]:
    scs = (
        await db.execute(
            select(SchoolClassSection).where(
                SchoolClassSection.id == item_id,
                SchoolClassSection.school_id == school_id,
                SchoolClassSection.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if not scs:
        raise AppError("School class-section assignment not found.", status_code=404)

    if payload.custom_name is not None:
        scs.custom_name = payload.custom_name.strip() or None
    if payload.custom_code is not None:
        scs.custom_code = payload.custom_code.strip() or None
    if payload.status is not None:
        scs.status = _normalize_status(payload.status, scs.status)

    await db.commit()
    await db.refresh(scs)
    return {
        "id": str(scs.id),
        "school_id": str(scs.school_id),
        "class_id": str(scs.class_id),
        "section_id": str(scs.section_id),
        "custom_name": scs.custom_name,
        "custom_code": scs.custom_code,
        "status": scs.status,
    }


def _sanitize_csv_cell(value: Any) -> str:
    """Prevents CSV Formula Injection (CWE-1236) when opened in Excel or
    Google Sheets by prefixing dangerous leading characters with a single quote."""
    text = str(value or "")
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{text}"
    return text


async def export_schools_csv(
    db: AsyncSession,
    *,
    search: str | None = None,
    status: str | None = None,
    state_id: uuid.UUID | None = None,
    district_id: uuid.UUID | None = None,
    ulb_id: uuid.UUID | None = None,
    ward_id: uuid.UUID | None = None,
) -> str:
    data = await list_schools(
        db,
        page=1,
        limit=10000,
        search=search,
        status=status,
        state_id=state_id,
        district_id=district_id,
        ulb_id=ulb_id,
        ward_id=ward_id,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "School Name",
            "UDISE Code",
            "State",
            "District",
            "ULB",
            "Ward",
            "Phone",
            "School Admins",
            "Status",
        ]
    )
    for row in data["list"]:
        admins_str = ", ".join(
            a.get("full_name") or a.get("email") or "" for a in (row.get("admin_users") or [])
        )
        writer.writerow(
            [
                _sanitize_csv_cell(row.get("name")),
                _sanitize_csv_cell(row.get("udise_code")),
                _sanitize_csv_cell(row.get("state_name")),
                _sanitize_csv_cell(row.get("district_name")),
                _sanitize_csv_cell(row.get("ulb_name")),
                _sanitize_csv_cell(row.get("ward_name")),
                _sanitize_csv_cell(row.get("phone")),
                _sanitize_csv_cell(admins_str),
                _sanitize_csv_cell(row.get("status")),
            ]
        )
    return output.getvalue()
