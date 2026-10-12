"""
Users Management router across all roles:
- School Admins: /api/v1/user/school
- Content Admins: /api/v1/user/content
- Generic Users: /api/v1/users
- Teachers: /api/v1/user/teacher, /api/v1/teachers/bulk-upload/*, /api/v1/teacher/class, /api/v1/teacher/subject
- Classroom Operators: /api/v1/user/class-room, /api/v1/classroom-operators/bulk-upload/*, /api/v1/classroom-operator/class, /api/v1/classroom-operator/subject
- Students: /api/v1/user/student, /api/v1/students/bulk-upload/*
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_admin_user_id, get_current_user_id
from app.core.database import get_async_db
from app.core.response import success_response
from app.schemas.users import (
    ClassroomOperatorCreateRequest,
    ClassroomOperatorUpdateRequest,
    ContentAdminCreateRequest,
    ContentAdminUpdateRequest,
    GenericUserCreateRequest,
    GenericUserUpdateRequest,
    SchoolAdminCreateRequest,
    SchoolAdminUpdateRequest,
    StudentCreateRequest,
    StudentUpdateRequest,
    TeacherCreateRequest,
    TeacherUpdateRequest,
)
from app.services import (
    academic_service,
    admin_user_service,
    classroom_operator_service,
    student_service,
    teacher_service,
)

router = APIRouter(tags=["users"])


async def _extract_uploaded_csv_bytes(request: Request) -> bytes:
    """Extracts uploaded CSV bytes from a multipart/form-data request or raw
    request body without requiring python-multipart at route registration time."""
    raw = await request.body()
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type and "boundary=" in content_type:
        boundary = content_type.split("boundary=")[-1].split(";")[0].strip().strip('"').encode()
        parts = raw.split(b"--" + boundary)
        for part in parts:
            if b"Content-Disposition" in part and b"\r\n\r\n" in part:
                _headers, body = part.split(b"\r\n\r\n", 1)
                if body.endswith(b"\r\n"):
                    body = body[:-2]
                if body.strip():
                    return body
    return raw



# ==============================================================================
# School Admins (/user/school)
# ==============================================================================

@router.get("/user/school")
async def list_school_admins(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=500),
    search: str | None = Query(None),
    status: str | None = Query(None),
    school_id: uuid.UUID | None = Query(None),
    unassigned: bool | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await admin_user_service.list_school_admins(
        db,
        page=page,
        limit=limit,
        search=search,
        status=status,
        school_id=school_id,
        unassigned=unassigned,
    )
    return success_response(message="School admins fetched successfully.", data=data)



@router.get("/user/school/{user_id}")
async def get_school_admin(
    user_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await admin_user_service.get_school_admin(db, user_id)
    return success_response(message="School admin fetched successfully.", data=data)


@router.post("/user/school", status_code=status.HTTP_201_CREATED)
async def create_school_admin(
    payload: SchoolAdminCreateRequest,
    current_user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await admin_user_service.create_school_admin(
        db, payload, created_by=current_user_id
    )
    return success_response(
        message="School admin created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/user/school/{user_id}")
async def update_school_admin(
    user_id: uuid.UUID,
    payload: SchoolAdminUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await admin_user_service.update_school_admin(db, user_id, payload)
    return success_response(message="School admin updated successfully.", data=data)


@router.delete("/user/school/{user_id}")
async def delete_school_admin(
    user_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await admin_user_service.delete_school_admin(db, user_id)
    return success_response(message="School admin deleted successfully.")


# ==============================================================================
# Content Admins (/user/content)
# ==============================================================================

@router.get("/user/content")
async def list_content_admins(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=500),
    search: str | None = Query(None),
    status: str | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await admin_user_service.list_content_admins(
        db, page=page, limit=limit, search=search, status=status
    )
    return success_response(message="Content admins fetched successfully.", data=data)


@router.get("/user/content/{user_id}")
async def get_content_admin(
    user_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await admin_user_service.get_content_admin(db, user_id)
    return success_response(message="Content admin fetched successfully.", data=data)


@router.post("/user/content", status_code=status.HTTP_201_CREATED)
async def create_content_admin(
    payload: ContentAdminCreateRequest,
    current_user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await admin_user_service.create_content_admin(
        db, payload, created_by=current_user_id
    )
    return success_response(
        message="Content admin created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/user/content/{user_id}")
async def update_content_admin(
    user_id: uuid.UUID,
    payload: ContentAdminUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await admin_user_service.update_content_admin(db, user_id, payload)
    return success_response(message="Content admin updated successfully.", data=data)


@router.delete("/user/content/{user_id}")
async def delete_content_admin(
    user_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await admin_user_service.delete_content_admin(db, user_id)
    return success_response(message="Content admin deleted successfully.")


# ==============================================================================
# Generic Users (/users)
# ==============================================================================

@router.get("/users")
async def list_generic_users(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=500),
    search: str | None = Query(None),
    status: str | None = Query(None),
    role: str | None = Query(None),
    school_id: uuid.UUID | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await admin_user_service.list_generic_users(
        db,
        page=page,
        limit=limit,
        search=search,
        status=status,
        role=role,
        school_id=school_id,
    )
    return success_response(message="Users fetched successfully.", data=data)


@router.get("/users/{user_id}")
async def get_generic_user(
    user_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await admin_user_service.get_generic_user(db, user_id)
    return success_response(message="User fetched successfully.", data=data)


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_generic_user(
    payload: GenericUserCreateRequest,
    current_user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await admin_user_service.create_generic_user(
        db, payload, created_by=current_user_id
    )
    return success_response(
        message="User created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/users/{user_id}")
async def update_generic_user(
    user_id: uuid.UUID,
    payload: GenericUserUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await admin_user_service.update_generic_user(db, user_id, payload)
    return success_response(message="User updated successfully.", data=data)


@router.delete("/users/{user_id}")
async def delete_generic_user(
    user_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await admin_user_service.delete_generic_user(db, user_id)
    return success_response(message="User deleted successfully.")


# ==============================================================================
# Teachers (/user/teacher, /teachers/bulk-upload/*, /teacher/class, /teacher/subject)
# ==============================================================================

@router.get("/user/teacher")
async def list_teachers(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=500),
    search: str | None = Query(None),
    status: str | None = Query(None),
    school_id: uuid.UUID | None = Query(None),
    class_id: uuid.UUID | None = Query(None),
    subject_id: uuid.UUID | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await teacher_service.list_teachers(
        db,
        page=page,
        limit=limit,
        search=search,
        status=status,
        school_id=school_id,
        class_id=class_id,
        subject_id=subject_id,
    )
    return success_response(message="Teachers fetched successfully.", data=data)


@router.get("/user/teacher/{teacher_id}")
async def get_teacher(
    teacher_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await teacher_service.get_teacher(db, teacher_id)
    return success_response(message="Teacher fetched successfully.", data=data)


@router.post("/user/teacher", status_code=status.HTTP_201_CREATED)
async def create_teacher(
    payload: TeacherCreateRequest,
    current_user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await teacher_service.create_teacher(db, payload, created_by=current_user_id)
    return success_response(
        message="Teacher created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/user/teacher/{teacher_id}")
async def update_teacher(
    teacher_id: uuid.UUID,
    payload: TeacherUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await teacher_service.update_teacher(db, teacher_id, payload)
    return success_response(message="Teacher updated successfully.", data=data)


@router.delete("/user/teacher/{teacher_id}")
async def delete_teacher(
    teacher_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await teacher_service.delete_teacher(db, teacher_id)
    return success_response(message="Teacher deleted successfully.")


@router.get("/teacher/class")
async def list_teacher_classes(
    school_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.list_classes(
        db, school_id=school_id, page=page, limit=limit
    )
    return success_response(message="Teacher classes fetched successfully.", data=data)


@router.get("/teacher/subject")
async def list_teacher_subjects(
    class_id: uuid.UUID | None = Query(None),
    school_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.list_subjects(
        db, class_id=class_id, school_id=school_id, page=page, limit=limit
    )
    return success_response(message="Teacher subjects fetched successfully.", data=data)


@router.get("/teachers/bulk-upload/template")
async def teacher_bulk_template(_user_id: uuid.UUID = Depends(get_current_admin_user_id)):
    csv_text = teacher_service.get_teacher_bulk_template_csv()
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="teachers_template.csv"'},
    )


@router.post("/teachers/bulk-upload/preview")
async def teacher_bulk_preview(
    request: Request,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
):
    content = await _extract_uploaded_csv_bytes(request)
    data = await teacher_service.preview_teacher_bulk_upload(content)
    return success_response(message="Bulk upload preview generated.", data=data)



@router.post("/teachers/bulk-upload/commit")
async def teacher_bulk_commit(
    payload: dict[str, Any],
    current_user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await teacher_service.commit_teacher_bulk_upload(
        db, payload, created_by=current_user_id
    )
    return success_response(message="Teachers bulk upload committed.", data=data)


# ==============================================================================
# Classroom Operators (/user/class-room, /classroom-operators/bulk-upload/*,
# /classroom-operator/class, /classroom-operator/subject)
# ==============================================================================

@router.get("/user/class-room")
async def list_classroom_operators(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=500),
    search: str | None = Query(None),
    status: str | None = Query(None),
    school_id: uuid.UUID | None = Query(None),
    class_id: uuid.UUID | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await classroom_operator_service.list_classroom_operators(
        db,
        page=page,
        limit=limit,
        search=search,
        status=status,
        school_id=school_id,
        class_id=class_id,
    )
    return success_response(message="Classroom operators fetched successfully.", data=data)


@router.get("/user/class-room/{operator_id}")
async def get_classroom_operator(
    operator_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await classroom_operator_service.get_classroom_operator(db, operator_id)
    return success_response(message="Classroom operator fetched successfully.", data=data)


@router.post("/user/class-room", status_code=status.HTTP_201_CREATED)
async def create_classroom_operator(
    payload: ClassroomOperatorCreateRequest,
    current_user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await classroom_operator_service.create_classroom_operator(
        db, payload, created_by=current_user_id
    )
    return success_response(
        message="Classroom operator created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/user/class-room/{operator_id}")
async def update_classroom_operator(
    operator_id: uuid.UUID,
    payload: ClassroomOperatorUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await classroom_operator_service.update_classroom_operator(
        db, operator_id, payload
    )
    return success_response(message="Classroom operator updated successfully.", data=data)


@router.delete("/user/class-room/{operator_id}")
async def delete_classroom_operator(
    operator_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await classroom_operator_service.delete_classroom_operator(db, operator_id)
    return success_response(message="Classroom operator deleted successfully.")


@router.get("/classroom-operator/class")
async def list_operator_classes(
    school_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.list_classes(
        db, school_id=school_id, page=page, limit=limit
    )
    return success_response(
        message="Classroom operator classes fetched successfully.", data=data
    )


@router.get("/classroom-operator/subject")
async def list_operator_subjects(
    class_id: uuid.UUID | None = Query(None),
    school_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.list_subjects(
        db, class_id=class_id, school_id=school_id, page=page, limit=limit
    )
    return success_response(
        message="Classroom operator subjects fetched successfully.", data=data
    )


@router.get("/classroom-operators/bulk-upload/template")
async def operator_bulk_template(_user_id: uuid.UUID = Depends(get_current_admin_user_id)):
    csv_text = classroom_operator_service.get_operator_bulk_template_csv()
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="classroom_operators_template.csv"'
        },
    )


@router.post("/classroom-operators/bulk-upload/preview")
async def operator_bulk_preview(
    request: Request,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
):
    content = await _extract_uploaded_csv_bytes(request)
    data = await classroom_operator_service.preview_operator_bulk_upload(content)
    return success_response(message="Bulk upload preview generated.", data=data)



@router.post("/classroom-operators/bulk-upload/commit")
async def operator_bulk_commit(
    payload: dict[str, Any],
    current_user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await classroom_operator_service.commit_operator_bulk_upload(
        db, payload, created_by=current_user_id
    )
    return success_response(
        message="Classroom operators bulk upload committed.", data=data
    )


# ==============================================================================
# Students (/user/student, /students/bulk-upload/*)
# ==============================================================================

@router.get("/user/student")
async def list_students(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=500),
    search: str | None = Query(None),
    status: str | None = Query(None),
    school_id: uuid.UUID | None = Query(None),
    class_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await student_service.list_students(
        db,
        page=page,
        limit=limit,
        search=search,
        status=status,
        school_id=school_id,
        class_id=class_id,
        section_id=section_id,
    )
    return success_response(message="Students fetched successfully.", data=data)


@router.get("/user/student/{student_id}")
async def get_student(
    student_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await student_service.get_student(db, student_id)
    return success_response(message="Student fetched successfully.", data=data)


@router.post("/user/student", status_code=status.HTTP_201_CREATED)
async def create_student(
    payload: StudentCreateRequest,
    current_user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await student_service.create_student(
        db, payload, created_by=current_user_id
    )
    return success_response(
        message="Student created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/user/student/{student_id}")
async def update_student(
    student_id: uuid.UUID,
    payload: StudentUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await student_service.update_student(db, student_id, payload)
    return success_response(message="Student updated successfully.", data=data)


@router.delete("/user/student/{student_id}")
async def delete_student(
    student_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await student_service.delete_student(db, student_id)
    return success_response(message="Student deleted successfully.")


@router.get("/students/bulk-upload/template")
async def student_bulk_template(_user_id: uuid.UUID = Depends(get_current_admin_user_id)):
    csv_text = student_service.get_student_bulk_template_csv()
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="students_template.csv"'},
    )


@router.post("/students/bulk-upload/preview")
async def student_bulk_preview(
    request: Request,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
):
    content = await _extract_uploaded_csv_bytes(request)
    data = await student_service.preview_student_bulk_upload(content)
    return success_response(message="Bulk upload preview generated.", data=data)



@router.post("/students/bulk-upload/commit")
async def student_bulk_commit(
    payload: dict[str, Any],
    current_user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await student_service.commit_student_bulk_upload(
        db, payload, created_by=current_user_id
    )
    return success_response(message="Students bulk upload committed.", data=data)
