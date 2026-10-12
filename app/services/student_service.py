"""
Student Management service (/api/v1/user/student, /api/v1/students/bulk-upload/*).
Supports both camelCase (sent by CreateStudentPage.helpers.js) and snake_case
fields, and returns rich nested profile + guardian objects expected by
StudentsPage.helpers.js and CreateStudentPage.helpers.js.
"""

from __future__ import annotations

import csv
import io
import secrets
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import AppError, paginated_data
from app.core.security import hash_password
from app.models.academic import AcademicClass, Section
from app.models.assignments import StudentProfile, UserSchool
from app.models.school import School
from app.models.user import User, UserStatus
from app.schemas.users import StudentCreateRequest, StudentUpdateRequest
from app.services.admin_user_service import _normalize_user_status


def _parse_dob(dob_val: date | str | None) -> date | None:
    if not dob_val:
        return None
    if isinstance(dob_val, date):
        return dob_val
    val = str(dob_val).strip()
    if not val:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(val[:10], fmt).date()
        except ValueError:
            continue
    return None


async def _serialize_students(db: AsyncSession, users: list[User]) -> list[dict[str, Any]]:
    if not users:
        return []
    user_ids = [u.id for u in users]

    prof_rows = (
        await db.execute(
            select(StudentProfile, School, AcademicClass, Section)
            .join(School, School.id == StudentProfile.school_id)
            .join(AcademicClass, AcademicClass.id == StudentProfile.class_id)
            .join(Section, Section.id == StudentProfile.section_id)
            .where(
                StudentProfile.user_id.in_(user_ids),
                StudentProfile.is_deleted.is_(False),
            )
        )
    ).all()

    prof_by_user: dict[uuid.UUID, tuple[StudentProfile, School, AcademicClass, Section]] = {
        sp.user_id: (sp, sch, cls_obj, sec_obj)
        for sp, sch, cls_obj, sec_obj in prof_rows
    }

    result = []
    for u in users:
        tup = prof_by_user.get(u.id)
        if tup:
            sp, sch, cls_obj, sec_obj = tup
            school_dict = {
                "id": str(sch.id),
                "school_id": str(sch.id),
                "name": sch.name,
                "code": sch.udise_code,
                "udise_code": sch.udise_code,
            }
            class_dict = {
                "id": str(cls_obj.id),
                "class_id": str(cls_obj.id),
                "name": cls_obj.name,
                "code": cls_obj.code,
            }
            section_dict = {
                "id": str(sec_obj.id),
                "section_id": str(sec_obj.id),
                "name": sec_obj.name,
                "code": sec_obj.code or sec_obj.name,
            }
            g_first = sp.guardian_first_name or ""
            g_last = sp.guardian_last_name or ""
            g_full = f"{g_first} {g_last}".strip()
            g_email = sp.guardian_email or (
                u.email if not u.email.endswith("@student.offlineai.local") else None
            )
            g_cc = sp.guardian_country_code or "+91"
            g_phone = sp.guardian_phone
            dob_str = sp.dob.isoformat() if sp.dob else None
            roll_num = sp.roll_number
            acad_year = sp.academic_year or "2025-2026"
            gender_val = sp.gender or u.gender
        else:
            school_dict = None
            class_dict = None
            section_dict = None
            g_first = ""
            g_last = ""
            g_full = ""
            g_email = u.email if not u.email.endswith("@student.offlineai.local") else None
            g_cc = "+91"
            g_phone = None
            dob_str = None
            roll_num = None
            acad_year = "2025-2026"
            gender_val = u.gender

        guardian_dict = {
            "first_name": g_first,
            "last_name": g_last,
            "firstName": g_first,
            "lastName": g_last,
            "full_name": g_full,
            "name": g_full,
            "email": g_email,
            "country_code": g_cc,
            "countryCode": g_cc,
            "phone": g_phone,
            "phone_number": g_phone,
        }

        profile_dict = {
            "roll_number": roll_num,
            "rollNumber": roll_num,
            "academic_year": acad_year,
            "academicYear": acad_year,
            "gender": gender_val,
            "dob": dob_str,
            "school_id": school_dict["id"] if school_dict else None,
            "class_id": class_dict["id"] if class_dict else None,
            "section_id": section_dict["id"] if section_dict else None,
            "school": school_dict,
            "class": class_dict,
            "section": section_dict,
            "guardian": guardian_dict,
        }

        result.append(
            {
                "id": str(u.id),
                "user_id": str(u.id),
                "student_id": str(u.id),
                "first_name": u.first_name,
                "last_name": u.last_name,
                "firstName": u.first_name,
                "lastName": u.last_name,
                "full_name": u.full_name,
                "name": u.full_name,
                "username": u.username or roll_num,
                "email": g_email or u.email,
                "country_code": u.country_code or "+91",
                "studentCountryCode": u.country_code or "+91",
                "phone_number": u.phone_number,
                "phoneNumber": u.phone_number,
                "phone": u.phone_number or g_phone,
                "gender": gender_val,
                "dob": dob_str,
                "roll_number": roll_num,
                "rollNumber": roll_num,
                "academic_year": acad_year,
                "academicYear": acad_year,
                "school_id": school_dict["id"] if school_dict else None,
                "class_id": class_dict["id"] if class_dict else None,
                "section_id": section_dict["id"] if section_dict else None,
                "school": school_dict,
                "schools": [school_dict] if school_dict else [],
                "class": class_dict,
                "section": section_dict,
                "school_name": school_dict["name"] if school_dict else None,
                "class_name": class_dict["name"] if class_dict else None,
                "section_name": section_dict["name"] if section_dict else None,
                "guardian_first_name": g_first,
                "guardian_last_name": g_last,
                "guardianFirstName": g_first,
                "guardianLastName": g_last,
                "guardian_name": g_full,
                "guardian_email": g_email,
                "guardian_country_code": g_cc,
                "countryCode": g_cc,
                "guardian_phone": g_phone,
                "guardianPhone": g_phone,
                "guardian": guardian_dict,
                "profile": profile_dict,
                "user_type": "student",
                "role": "student",
                "status": u.status,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "updated_at": u.updated_at.isoformat() if u.updated_at else None,
            }
        )
    return result


async def list_students(
    db: AsyncSession,
    *,
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    status: str | None = None,
    school_id: uuid.UUID | None = None,
    class_id: uuid.UUID | None = None,
    section_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    stmt = select(User).where(User.user_type == "student", User.is_deleted.is_(False))

    if school_id or class_id or section_id:
        sp_sub = select(StudentProfile.user_id).where(StudentProfile.is_deleted.is_(False))
        if school_id:
            sp_sub = sp_sub.where(StudentProfile.school_id == school_id)
        if class_id:
            sp_sub = sp_sub.where(StudentProfile.class_id == class_id)
        if section_id:
            sp_sub = sp_sub.where(StudentProfile.section_id == section_id)
        stmt = stmt.where(User.id.in_(sp_sub))

    if search and search.strip():
        q = f"%{search.strip()}%"
        sp_search_sub = select(StudentProfile.user_id).where(
            or_(
                StudentProfile.roll_number.ilike(q),
                StudentProfile.guardian_first_name.ilike(q),
                StudentProfile.guardian_last_name.ilike(q),
                StudentProfile.guardian_phone.ilike(q),
                StudentProfile.guardian_email.ilike(q),
            )
        )
        stmt = stmt.where(
            or_(
                User.first_name.ilike(q),
                User.last_name.ilike(q),
                User.email.ilike(q),
                User.phone_number.ilike(q),
                User.username.ilike(q),
                User.id.in_(sp_search_sub),
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

    items = await _serialize_students(db, list(rows))
    return paginated_data(items=items, total=total, page=page, limit=limit)


async def get_student(db: AsyncSession, student_id: uuid.UUID) -> dict[str, Any]:
    u = (
        await db.execute(
            select(User).where(User.id == student_id, User.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not u:
        raise AppError("Student not found.", status_code=404)
    items = await _serialize_students(db, [u])
    return items[0]


async def _resolve_unique_student_email(
    db: AsyncSession,
    candidate_email: str | None,
    *,
    exclude_user_id: uuid.UUID | None = None,
) -> str:
    if candidate_email and candidate_email.strip() and "@" in candidate_email:
        clean = candidate_email.strip().lower()
        stmt = select(User.id).where(func.lower(User.email) == clean)
        if exclude_user_id:
            stmt = stmt.where(User.id != exclude_user_id)
        exists = (await db.execute(stmt)).scalar_one_or_none()
        if not exists:
            return clean
    return f"student.{uuid.uuid4().hex[:10]}@student.offlineai.local"


async def create_student(
    db: AsyncSession,
    payload: StudentCreateRequest,
    *,
    created_by: uuid.UUID | None = None,
) -> dict[str, Any]:
    first_name = (payload.firstName or payload.first_name or "").strip()
    last_name = (payload.lastName or payload.last_name or "").strip()
    if not first_name:
        raise AppError("Student first name is required.", status_code=400)

    guardian_email = (payload.email or payload.guardian_email or "").strip().lower() or None
    user_email = await _resolve_unique_student_email(db, guardian_email)

    student_cc = (payload.studentCountryCode or payload.student_country_code or "+91").strip()
    student_phone = (payload.phoneNumber or payload.phone_number or "").strip() or None

    unique_phone = None
    if student_phone:
        dup_p = (
            await db.execute(select(User.id).where(User.phone == student_phone))
        ).scalar_one_or_none()
        if not dup_p:
            unique_phone = student_phone

    gender_val = (payload.gender or "").strip() or None
    raw_password = (payload.password or "").strip() or f"Student@{secrets.randbelow(9000) + 1000}"

    u = User(
        email=user_email,
        hashed_password=hash_password(raw_password),
        first_name=first_name,
        last_name=last_name,
        country_code=student_cc,
        phone_number=student_phone,
        phone=unique_phone,
        gender=gender_val,
        user_type="student",
        status=_normalize_user_status(payload.status),
        created_by=created_by,
    )
    db.add(u)
    await db.flush()

    roll_number = (payload.rollNumber or payload.roll_number or "").strip() or None
    academic_year = (payload.academicYear or payload.academic_year or "2025-2026").strip()
    g_first = (payload.guardianFirstName or payload.guardian_first_name or "").strip() or None
    g_last = (payload.guardianLastName or payload.guardian_last_name or "").strip() or None
    g_cc = (payload.countryCode or payload.guardian_country_code or "+91").strip()
    g_phone = (payload.guardianPhone or payload.guardian_phone or "").strip() or None

    sp = StudentProfile(
        user_id=u.id,
        school_id=payload.school_id,
        class_id=payload.class_id,
        section_id=payload.section_id,
        roll_number=roll_number,
        academic_year=academic_year,
        gender=gender_val,
        dob=_parse_dob(payload.dob),
        guardian_first_name=g_first,
        guardian_last_name=g_last,
        guardian_email=guardian_email,
        guardian_country_code=g_cc,
        guardian_phone=g_phone,
    )
    db.add(sp)
    db.add(UserSchool(user_id=u.id, school_id=payload.school_id, role="student"))

    await db.commit()
    return await get_student(db, u.id)


async def update_student(
    db: AsyncSession, student_id: uuid.UUID, payload: StudentUpdateRequest
) -> dict[str, Any]:
    u = (
        await db.execute(
            select(User).where(User.id == student_id, User.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not u:
        raise AppError("Student not found.", status_code=404)

    sp = (
        await db.execute(
            select(StudentProfile).where(StudentProfile.user_id == u.id)
        )
    ).scalar_one_or_none()

    first_name = payload.firstName if payload.firstName is not None else payload.first_name
    last_name = payload.lastName if payload.lastName is not None else payload.last_name
    if first_name is not None and first_name.strip():
        u.first_name = first_name.strip()
    if last_name is not None:
        u.last_name = last_name.strip()

    student_cc = (
        payload.studentCountryCode
        if payload.studentCountryCode is not None
        else payload.student_country_code
    )
    if student_cc is not None:
        u.country_code = student_cc.strip() or "+91"

    student_phone = (
        payload.phoneNumber if payload.phoneNumber is not None else payload.phone_number
    )
    if student_phone is not None:
        u.phone_number = student_phone.strip() or None

    if payload.gender is not None:
        u.gender = payload.gender.strip() or None
    if payload.status is not None:
        u.status = _normalize_user_status(payload.status, u.status)
    if payload.password and payload.password.strip():
        u.hashed_password = hash_password(payload.password.strip())

    if sp:
        if payload.school_id is not None:
            sp.school_id = payload.school_id
        if payload.class_id is not None:
            sp.class_id = payload.class_id
        if payload.section_id is not None:
            sp.section_id = payload.section_id

        roll_in = payload.rollNumber if payload.rollNumber is not None else payload.roll_number
        if roll_in is not None:
            sp.roll_number = roll_in.strip() or None

        acad_in = (
            payload.academicYear if payload.academicYear is not None else payload.academic_year
        )
        if acad_in is not None:
            sp.academic_year = acad_in.strip() or sp.academic_year

        if payload.gender is not None:
            sp.gender = payload.gender.strip() or None
        if payload.dob is not None:
            sp.dob = _parse_dob(payload.dob)

        g_first = (
            payload.guardianFirstName
            if payload.guardianFirstName is not None
            else payload.guardian_first_name
        )
        if g_first is not None:
            sp.guardian_first_name = g_first.strip() or None

        g_last = (
            payload.guardianLastName
            if payload.guardianLastName is not None
            else payload.guardian_last_name
        )
        if g_last is not None:
            sp.guardian_last_name = g_last.strip() or None

        g_email = payload.email if payload.email is not None else payload.guardian_email
        if g_email is not None:
            sp.guardian_email = g_email.strip().lower() or None

        g_cc = (
            payload.countryCode
            if payload.countryCode is not None
            else payload.guardian_country_code
        )
        if g_cc is not None:
            sp.guardian_country_code = g_cc.strip() or "+91"

        g_phone = (
            payload.guardianPhone
            if payload.guardianPhone is not None
            else payload.guardian_phone
        )
        if g_phone is not None:
            sp.guardian_phone = g_phone.strip() or None

    await db.commit()
    return await get_student(db, u.id)


async def delete_student(db: AsyncSession, student_id: uuid.UUID) -> None:
    u = (
        await db.execute(
            select(User).where(User.id == student_id, User.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not u:
        raise AppError("Student not found.", status_code=404)
    u.is_deleted = True
    u.status = UserStatus.DELETED

    sp = (
        await db.execute(select(StudentProfile).where(StudentProfile.user_id == u.id))
    ).scalar_one_or_none()
    if sp:
        sp.is_deleted = True

    await db.commit()


# ==============================================================================
# Student Bulk Upload
# ==============================================================================

def get_student_bulk_template_csv() -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "firstName",
            "lastName",
            "rollNumber",
            "academicYear",
            "gender",
            "dob",
            "phoneNumber",
            "guardianFirstName",
            "guardianLastName",
            "guardianPhone",
            "email",
            "status",
        ]
    )
    writer.writerow(
        [
            "Aarav",
            "Patel",
            "ROLL-001",
            "2025-2026",
            "MALE",
            "2010-05-15",
            "9876543211",
            "Rajesh",
            "Patel",
            "9876543212",
            "rajesh.patel@example.com",
            "ACTIVE",
        ]
    )
    return output.getvalue()


async def preview_student_bulk_upload(file_bytes: bytes) -> dict[str, Any]:
    text_content = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text_content))
    rows = []
    valid_count = 0
    invalid_count = 0

    for idx, row in enumerate(reader, start=1):
        first_name = (
            row.get("firstName") or row.get("first_name") or row.get("First Name") or ""
        ).strip()
        last_name = (
            row.get("lastName") or row.get("last_name") or row.get("Last Name") or ""
        ).strip()
        errors = []
        if not first_name:
            errors.append("Student first name is required")

        is_valid = len(errors) == 0
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1

        rows.append(
            {
                "row_number": idx,
                "firstName": first_name,
                "lastName": last_name,
                "rollNumber": (row.get("rollNumber") or row.get("roll_number") or "").strip(),
                "academicYear": (
                    row.get("academicYear") or row.get("academic_year") or "2025-2026"
                ).strip(),
                "gender": (row.get("gender") or "MALE").strip(),
                "dob": (row.get("dob") or "").strip(),
                "phoneNumber": (row.get("phoneNumber") or row.get("phone_number") or "").strip(),
                "guardianFirstName": (
                    row.get("guardianFirstName") or row.get("guardian_first_name") or ""
                ).strip(),
                "guardianLastName": (
                    row.get("guardianLastName") or row.get("guardian_last_name") or ""
                ).strip(),
                "guardianPhone": (
                    row.get("guardianPhone") or row.get("guardian_phone") or ""
                ).strip(),
                "email": (row.get("email") or row.get("guardian_email") or "").strip(),
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


async def commit_student_bulk_upload(
    db: AsyncSession, payload: dict[str, Any], *, created_by: uuid.UUID | None = None
) -> dict[str, Any]:
    rows = payload.get("rows") or payload.get("students") or payload.get("data") or []
    default_school_id = payload.get("school_id")
    default_class_id = payload.get("class_id")
    default_section_id = payload.get("section_id")

    created = []
    skipped = []
    for row in rows:
        if row.get("is_valid") is False:
            skipped.append({"firstName": row.get("firstName"), "reason": "Invalid row"})
            continue
        try:
            sch_id = row.get("school_id") or default_school_id
            cls_id = row.get("class_id") or default_class_id
            sec_id = row.get("section_id") or default_section_id
            if not (sch_id and cls_id and sec_id):
                skipped.append(
                    {
                        "firstName": row.get("firstName"),
                        "reason": "school_id, class_id, and section_id are required",
                    }
                )
                continue
            req = StudentCreateRequest(
                firstName=row.get("firstName") or row.get("first_name"),
                lastName=row.get("lastName") or row.get("last_name"),
                school_id=uuid.UUID(str(sch_id)),
                class_id=uuid.UUID(str(cls_id)),
                section_id=uuid.UUID(str(sec_id)),
                rollNumber=row.get("rollNumber") or row.get("roll_number"),
                academicYear=row.get("academicYear") or row.get("academic_year"),
                gender=row.get("gender"),
                dob=row.get("dob"),
                phoneNumber=row.get("phoneNumber") or row.get("phone_number"),
                guardianFirstName=row.get("guardianFirstName") or row.get("guardian_first_name"),
                guardianLastName=row.get("guardianLastName") or row.get("guardian_last_name"),
                guardianPhone=row.get("guardianPhone") or row.get("guardian_phone"),
                email=row.get("email") or row.get("guardian_email"),
                status=row.get("status") or "ACTIVE",
            )
            st = await create_student(db, req, created_by=created_by)
            created.append(st)
        except Exception as exc:
            skipped.append({"firstName": row.get("firstName"), "reason": str(exc)})

    return {
        "created_count": len(created),
        "skipped_count": len(skipped),
        "created": created,
        "skipped": skipped,
    }
