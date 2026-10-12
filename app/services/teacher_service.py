"""
Teacher Management service (/api/v1/user/teacher, /api/v1/teachers/bulk-upload/*,
/api/v1/teacher/class, /api/v1/teacher/subject).
"""

from __future__ import annotations

import csv
import io
import secrets
import uuid
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import AppError, paginated_data
from app.core.security import hash_password
from app.models.academic import AcademicClass, Qualification, Subject
from app.models.assignments import TeacherAssignment, TeacherQualification, UserSchool
from app.models.school import School
from app.models.user import User, UserStatus
from app.schemas.users import TeacherCreateRequest, TeacherUpdateRequest
from app.services.admin_user_service import (
    _ensure_email_and_phone_unique,
    _format_phone,
    _normalize_user_status,
)


async def _serialize_teachers(db: AsyncSession, users: list[User]) -> list[dict[str, Any]]:
    if not users:
        return []
    user_ids = [u.id for u in users]

    # Fetch qualifications
    tq_rows = (
        await db.execute(
            select(TeacherQualification, Qualification)
            .join(Qualification, Qualification.id == TeacherQualification.qualification_id)
            .where(
                TeacherQualification.teacher_id.in_(user_ids),
                Qualification.is_deleted.is_(False),
            )
            .order_by(Qualification.name.asc())
        )
    ).all()

    quals_by_teacher: dict[uuid.UUID, list[dict[str, Any]]] = {uid: [] for uid in user_ids}
    for tq, qual in tq_rows:
        quals_by_teacher.setdefault(tq.teacher_id, []).append(
            {
                "id": str(qual.id),
                "qualification_id": str(qual.id),
                "relation_id": str(tq.id),
                "name": qual.name,
                "code": qual.code,
            }
        )

    # Fetch assignments (school -> class -> subject)
    ta_rows = (
        await db.execute(
            select(TeacherAssignment, School, AcademicClass, Subject)
            .join(School, School.id == TeacherAssignment.school_id)
            .join(AcademicClass, AcademicClass.id == TeacherAssignment.class_id)
            .join(Subject, Subject.id == TeacherAssignment.subject_id)
            .where(
                TeacherAssignment.teacher_id.in_(user_ids),
                TeacherAssignment.is_deleted.is_(False),
                School.is_deleted.is_(False),
            )
            .order_by(School.name.asc(), AcademicClass.created_at.asc(), Subject.name.asc())
        )
    ).all()

    # Group by teacher_id -> school_id -> class_id -> subjects
    grouped: dict[uuid.UUID, dict[uuid.UUID, dict[str, Any]]] = {uid: {} for uid in user_ids}
    schools_by_teacher: dict[uuid.UUID, dict[uuid.UUID, dict[str, Any]]] = {
        uid: {} for uid in user_ids
    }
    classes_by_teacher: dict[uuid.UUID, dict[uuid.UUID, dict[str, Any]]] = {
        uid: {} for uid in user_ids
    }
    subjects_by_teacher: dict[uuid.UUID, dict[uuid.UUID, dict[str, Any]]] = {
        uid: {} for uid in user_ids
    }

    for ta, sch, cls_obj, sub_obj in ta_rows:
        tid = ta.teacher_id
        sch_summary = {
            "id": str(sch.id),
            "school_id": str(sch.id),
            "name": sch.name,
            "code": sch.udise_code,
            "udise_code": sch.udise_code,
        }
        schools_by_teacher[tid][sch.id] = sch_summary
        classes_by_teacher[tid][cls_obj.id] = {
            "id": str(cls_obj.id),
            "class_id": str(cls_obj.id),
            "name": cls_obj.name,
            "code": cls_obj.code,
        }
        subjects_by_teacher[tid][sub_obj.id] = {
            "id": str(sub_obj.id),
            "subject_id": str(sub_obj.id),
            "name": sub_obj.name,
            "code": sub_obj.code,
        }

        t_schools = grouped.setdefault(tid, {})
        if sch.id not in t_schools:
            t_schools[sch.id] = {
                "id": str(sch.id),
                "school_id": str(sch.id),
                "name": sch.name,
                "code": sch.udise_code,
                "udise_code": sch.udise_code,
                "school": sch_summary,
                "_classes_map": {},
            }

        c_map = t_schools[sch.id]["_classes_map"]
        if cls_obj.id not in c_map:
            c_map[cls_obj.id] = {
                "id": str(cls_obj.id),
                "class_id": str(cls_obj.id),
                "name": cls_obj.name,
                "code": cls_obj.code,
                "class": {
                    "id": str(cls_obj.id),
                    "name": cls_obj.name,
                    "code": cls_obj.code,
                },
                "subjects": [],
            }

        c_map[cls_obj.id]["subjects"].append(
            {
                "id": str(sub_obj.id),
                "subject_id": str(sub_obj.id),
                "relation_id": str(ta.id),
                "assignment_id": str(ta.id),
                "name": sub_obj.name,
                "code": sub_obj.code,
                "subject": {
                    "id": str(sub_obj.id),
                    "name": sub_obj.name,
                    "code": sub_obj.code,
                },
            }
        )

    result = []
    for u in users:
        quals = quals_by_teacher.get(u.id, [])
        t_schools_dict = grouped.get(u.id, {})
        assignments_list = []
        for sch_entry in t_schools_dict.values():
            cls_list = list(sch_entry["_classes_map"].values())
            assignments_list.append(
                {
                    "id": sch_entry["id"],
                    "school_id": sch_entry["school_id"],
                    "name": sch_entry["name"],
                    "code": sch_entry["code"],
                    "udise_code": sch_entry["udise_code"],
                    "school": sch_entry["school"],
                    "classes": cls_list,
                    "class": cls_list,
                }
            )

        u_schools = list(schools_by_teacher.get(u.id, {}).values())
        u_classes = list(classes_by_teacher.get(u.id, {}).values())
        u_subjects = list(subjects_by_teacher.get(u.id, {}).values())
        primary_school = u_schools[0] if u_schools else None

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
                "status": u.status,
                "qualifications": quals,
                "qualification_ids": [q["id"] for q in quals],
                "schools": u_schools,
                "school": primary_school,
                "school_id": primary_school["id"] if primary_school else None,
                "school_name": primary_school["name"] if primary_school else None,
                "classes": u_classes,
                "subjects": u_subjects,
                "assignments": assignments_list,
                "school_assignments": assignments_list,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "updated_at": u.updated_at.isoformat() if u.updated_at else None,
            }
        )
    return result


def _parse_teacher_assignment_tuples(
    assignments_input: list[dict[str, Any]],
) -> list[tuple[uuid.UUID, uuid.UUID, uuid.UUID]]:
    """Extracts (school_id, class_id, subject_id) tuples from the nested
    payload sent by CreateTeacherPage.helpers.js:
    assignments: [{ school_id, class: [{ class_id, subjects: [{ subject_id }] }] }]
    """
    tuples: list[tuple[uuid.UUID, uuid.UUID, uuid.UUID]] = []
    for sch_block in assignments_input or []:
        sch_id_raw = sch_block.get("school_id") or (sch_block.get("school") or {}).get("id")
        if not sch_id_raw:
            continue
        sch_id = uuid.UUID(str(sch_id_raw))
        classes_block = sch_block.get("class") or sch_block.get("classes") or []
        for cls_block in classes_block:
            cls_id_raw = cls_block.get("class_id") or cls_block.get("id") or (cls_block.get("class") or {}).get("id")
            if not cls_id_raw:
                continue
            cls_id = uuid.UUID(str(cls_id_raw))
            subjects_block = (
                cls_block.get("subjects")
                or cls_block.get("subject_ids")
                or cls_block.get("removed_subject_ids")
                or []
            )
            for sub_item in subjects_block:
                if isinstance(sub_item, (str, uuid.UUID)):
                    sub_id = uuid.UUID(str(sub_item))
                elif isinstance(sub_item, dict):
                    sub_id_raw = sub_item.get("subject_id") or sub_item.get("id")
                    if not sub_id_raw:
                        continue
                    sub_id = uuid.UUID(str(sub_id_raw))
                else:
                    continue
                tuples.append((sch_id, cls_id, sub_id))
    return list(dict.fromkeys(tuples))


async def _sync_teacher_relations(
    db: AsyncSession,
    teacher_id: uuid.UUID,
    *,
    qualification_ids: list[uuid.UUID] | None = None,
    removed_qualification_ids: list[uuid.UUID] | None = None,
    assignments: list[dict[str, Any]] | None = None,
    removed_assignments: list[dict[str, Any]] | None = None,
) -> None:
    if removed_qualification_ids:
        await db.execute(
            delete(TeacherQualification).where(
                TeacherQualification.teacher_id == teacher_id,
                or_(
                    TeacherQualification.qualification_id.in_(removed_qualification_ids),
                    TeacherQualification.id.in_(removed_qualification_ids),
                ),
            )
        )

    if qualification_ids is not None:
        existing_q = set(
            (
                await db.execute(
                    select(TeacherQualification.qualification_id).where(
                        TeacherQualification.teacher_id == teacher_id
                    )
                )
            ).scalars().all()
        )
        for qid in set(qualification_ids):
            if qid not in existing_q:
                db.add(TeacherQualification(teacher_id=teacher_id, qualification_id=qid))

    if removed_assignments:
        for rem_block in removed_assignments:
            sch_id_raw = rem_block.get("school_id") or rem_block.get("id")
            if not sch_id_raw:
                continue
            sch_id = uuid.UUID(str(sch_id_raw))
            classes_block = rem_block.get("class") or rem_block.get("classes")
            if not classes_block:
                # Remove entire school assignment
                await db.execute(
                    delete(TeacherAssignment).where(
                        TeacherAssignment.teacher_id == teacher_id,
                        TeacherAssignment.school_id == sch_id,
                    )
                )
            else:
                for cls_block in classes_block:
                    cls_id_raw = cls_block.get("class_id") or cls_block.get("id")
                    if not cls_id_raw:
                        continue
                    cls_id = uuid.UUID(str(cls_id_raw))
                    subs = (
                        cls_block.get("subjects")
                        or cls_block.get("subject_ids")
                        or cls_block.get("removed_subject_ids")
                    )
                    if not subs:
                        await db.execute(
                            delete(TeacherAssignment).where(
                                TeacherAssignment.teacher_id == teacher_id,
                                TeacherAssignment.school_id == sch_id,
                                TeacherAssignment.class_id == cls_id,
                            )
                        )
                    else:
                        sub_ids = []
                        for s_item in subs:
                            if isinstance(s_item, dict):
                                sid_raw = s_item.get("subject_id") or s_item.get("id")
                                if sid_raw:
                                    sub_ids.append(uuid.UUID(str(sid_raw)))
                            else:
                                sub_ids.append(uuid.UUID(str(s_item)))
                        if sub_ids:
                            await db.execute(
                                delete(TeacherAssignment).where(
                                    TeacherAssignment.teacher_id == teacher_id,
                                    TeacherAssignment.school_id == sch_id,
                                    TeacherAssignment.class_id == cls_id,
                                    TeacherAssignment.subject_id.in_(sub_ids),
                                )
                            )

    if assignments is not None:
        desired_tuples = _parse_teacher_assignment_tuples(assignments)
        existing_rows = (
            await db.execute(
                select(TeacherAssignment).where(TeacherAssignment.teacher_id == teacher_id)
            )
        ).scalars().all()
        by_key = {(r.school_id, r.class_id, r.subject_id): r for r in existing_rows}

        school_ids_set: set[uuid.UUID] = set()
        for sch_id, cls_id, sub_id in desired_tuples:
            school_ids_set.add(sch_id)
            key = (sch_id, cls_id, sub_id)
            if key in by_key:
                by_key[key].is_deleted = False
            else:
                db.add(
                    TeacherAssignment(
                        teacher_id=teacher_id,
                        school_id=sch_id,
                        class_id=cls_id,
                        subject_id=sub_id,
                    )
                )

        # Also mirror school membership in user_schools for quick school lookups
        existing_us = set(
            (
                await db.execute(
                    select(UserSchool.school_id).where(UserSchool.user_id == teacher_id)
                )
            ).scalars().all()
        )
        for sid in school_ids_set:
            if sid not in existing_us:
                db.add(UserSchool(user_id=teacher_id, school_id=sid, role="teacher"))


async def list_teachers(
    db: AsyncSession,
    *,
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    status: str | None = None,
    school_id: uuid.UUID | None = None,
    class_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    stmt = select(User).where(User.user_type == "teacher", User.is_deleted.is_(False))

    if school_id or class_id or subject_id:
        ta_sub = select(TeacherAssignment.teacher_id).where(
            TeacherAssignment.is_deleted.is_(False)
        )
        if school_id:
            ta_sub = ta_sub.where(TeacherAssignment.school_id == school_id)
        if class_id:
            ta_sub = ta_sub.where(TeacherAssignment.class_id == class_id)
        if subject_id:
            ta_sub = ta_sub.where(TeacherAssignment.subject_id == subject_id)
        stmt = stmt.where(User.id.in_(ta_sub))

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

    items = await _serialize_teachers(db, list(rows))
    return paginated_data(items=items, total=total, page=page, limit=limit)


async def get_teacher(db: AsyncSession, teacher_id: uuid.UUID) -> dict[str, Any]:
    u = (
        await db.execute(
            select(User).where(User.id == teacher_id, User.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not u:
        raise AppError("Teacher not found.", status_code=404)
    items = await _serialize_teachers(db, [u])
    return items[0]


async def create_teacher(
    db: AsyncSession,
    payload: TeacherCreateRequest,
    *,
    created_by: uuid.UUID | None = None,
) -> dict[str, Any]:
    email = payload.email.strip().lower()
    cc, phone_num, unique_phone = _format_phone(
        payload.country_code, payload.phone_number or payload.phone
    )
    await _ensure_email_and_phone_unique(db, email=email, phone=unique_phone)

    raw_password = (payload.password or "").strip() or f"Teacher@{secrets.randbelow(9000) + 1000}"
    u = User(
        email=email,
        hashed_password=hash_password(raw_password),
        first_name=payload.first_name.strip(),
        last_name=(payload.last_name or "").strip(),
        country_code=cc,
        phone_number=phone_num,
        phone=unique_phone,
        gender=payload.gender,
        user_type="teacher",
        status=_normalize_user_status(payload.status),
        created_by=created_by,
    )
    db.add(u)
    await db.flush()

    await _sync_teacher_relations(
        db,
        u.id,
        qualification_ids=payload.qualification_ids,
        assignments=payload.assignments,
    )
    await db.commit()
    return await get_teacher(db, u.id)


async def update_teacher(
    db: AsyncSession, teacher_id: uuid.UUID, payload: TeacherUpdateRequest
) -> dict[str, Any]:
    u = (
        await db.execute(
            select(User).where(User.id == teacher_id, User.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not u:
        raise AppError("Teacher not found.", status_code=404)

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
    if payload.gender is not None:
        u.gender = payload.gender
    if payload.password and payload.password.strip():
        u.hashed_password = hash_password(payload.password.strip())
    if payload.status is not None:
        u.status = _normalize_user_status(payload.status, u.status)

    await _sync_teacher_relations(
        db,
        u.id,
        qualification_ids=payload.qualification_ids,
        removed_qualification_ids=payload.removed_qualification_ids,
        assignments=payload.assignments,
        removed_assignments=payload.removed_assignments,
    )
    await db.commit()
    return await get_teacher(db, u.id)


async def delete_teacher(db: AsyncSession, teacher_id: uuid.UUID) -> None:
    u = (
        await db.execute(
            select(User).where(User.id == teacher_id, User.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not u:
        raise AppError("Teacher not found.", status_code=404)
    u.is_deleted = True
    u.status = UserStatus.DELETED

    ta_rows = (
        await db.execute(
            select(TeacherAssignment).where(
                TeacherAssignment.teacher_id == u.id,
                TeacherAssignment.is_deleted.is_(False),
            )
        )
    ).scalars().all()
    for ta in ta_rows:
        ta.is_deleted = True

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
# Teacher Bulk Upload (Template / Preview / Commit)
# ==============================================================================

def get_teacher_bulk_template_csv() -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "first_name",
            "last_name",
            "email",
            "country_code",
            "phone_number",
            "gender",
            "status",
        ]
    )
    writer.writerow(
        [
            "Ramesh",
            "Sharma",
            "ramesh.sharma@example.com",
            "+91",
            "9876543210",
            "MALE",
            "ACTIVE",
        ]
    )
    return output.getvalue()


async def preview_teacher_bulk_upload(file_bytes: bytes) -> dict[str, Any]:
    text_content = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text_content))
    rows = []
    valid_count = 0
    invalid_count = 0

    for idx, row in enumerate(reader, start=1):
        first_name = (row.get("first_name") or row.get("First Name") or "").strip()
        last_name = (row.get("last_name") or row.get("Last Name") or "").strip()
        email = (row.get("email") or row.get("Email") or "").strip().lower()
        phone = (row.get("phone_number") or row.get("phone") or row.get("Phone") or "").strip()
        gender = (row.get("gender") or row.get("Gender") or "MALE").strip()
        errors = []
        if not first_name:
            errors.append("First name is required")
        if not email or "@" not in email:
            errors.append("Valid email is required")

        is_valid = len(errors) == 0
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1

        rows.append(
            {
                "row_number": idx,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "country_code": (row.get("country_code") or "+91").strip(),
                "phone_number": phone,
                "gender": gender,
                "status": (row.get("status") or "ACTIVE").strip().upper(),
                "is_valid": is_valid,
                "errors": errors,
            }
        )

    return {
        "total_rows": len(rows),
        "valid_rows": valid_count,
        "invalid_rows": invalid_count,
        "rows": rows,
        "preview": rows,
    }


async def commit_teacher_bulk_upload(
    db: AsyncSession, payload: dict[str, Any], *, created_by: uuid.UUID | None = None
) -> dict[str, Any]:
    rows = payload.get("rows") or payload.get("teachers") or payload.get("data") or []
    created = []
    skipped = []
    for row in rows:
        if row.get("is_valid") is False:
            skipped.append({"email": row.get("email"), "reason": "Invalid row"})
            continue
        try:
            req = TeacherCreateRequest(
                first_name=row.get("first_name") or "",
                last_name=row.get("last_name") or "",
                email=row.get("email") or "",
                country_code=row.get("country_code") or "+91",
                phone_number=row.get("phone_number") or row.get("phone"),
                gender=row.get("gender"),
                status=row.get("status") or "ACTIVE",
            )
            t = await create_teacher(db, req, created_by=created_by)
            created.append(t)
        except Exception as exc:
            skipped.append({"email": row.get("email"), "reason": str(exc)})

    return {
        "created_count": len(created),
        "skipped_count": len(skipped),
        "created": created,
        "skipped": skipped,
    }
