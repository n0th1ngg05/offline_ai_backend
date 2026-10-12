"""
Academic & Qualification router:
- /api/v1/class & /api/v1/academics/classes
- /api/v1/section & /api/v1/academics/sections
- /api/v1/academics/streams
- /api/v1/subject & /api/v1/academics/subjects
- /api/v1/academics/chapters
- /api/v1/academics/topics
- /api/v1/qualification & /api/v1/academics/qualifications
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_admin_user_id, get_current_user_id
from app.core.database import get_async_db
from app.core.response import success_response
from app.schemas.academics import (
    ChapterCreateRequest,
    ChapterUpdateRequest,
    ClassCreateRequest,
    ClassUpdateRequest,
    QualificationCreateRequest,
    QualificationUpdateRequest,
    SectionCreateRequest,
    SectionUpdateRequest,
    StreamCreateRequest,
    StreamUpdateRequest,
    SubjectCreateRequest,
    SubjectUpdateRequest,
    TopicCreateRequest,
    TopicUpdateRequest,
)
from app.services import academic_service

router = APIRouter(tags=["academics"])


# ==============================================================================
# Classes (/class and /academics/classes)
# ==============================================================================

@router.get("/class")
@router.get("/academics/classes")
async def list_classes(
    school_id: uuid.UUID | None = Query(None),
    required_section: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = Query(None),
    status: str | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.list_classes(
        db,
        school_id=school_id,
        required_section=required_section,
        page=page,
        limit=limit,
        search=search,
        status=status,
    )
    return success_response(message="Classes fetched successfully.", data=data)


@router.get("/class/{class_id}")
@router.get("/academics/classes/{class_id}")
async def get_class(
    class_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.get_class(db, class_id)
    return success_response(message="Class fetched successfully.", data=data)


@router.post("/class", status_code=status.HTTP_201_CREATED)
@router.post("/academics/classes", status_code=status.HTTP_201_CREATED)
async def create_class(
    payload: ClassCreateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.create_class(db, payload)
    return success_response(
        message="Class created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/class/{class_id}")
@router.patch("/academics/classes/{class_id}")
async def update_class(
    class_id: uuid.UUID,
    payload: ClassUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.update_class(db, class_id, payload)
    return success_response(message="Class updated successfully.", data=data)


@router.delete("/class/{class_id}")
@router.delete("/academics/classes/{class_id}")
async def delete_class(
    class_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await academic_service.delete_class(db, class_id)
    return success_response(message="Class deleted successfully.")


# ==============================================================================
# Sections (/section and /academics/sections)
# ==============================================================================

@router.get("/section")
@router.get("/academics/sections")
async def list_sections(
    class_id: uuid.UUID | None = Query(None),
    school_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = Query(None),
    status: str | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.list_sections(
        db,
        class_id=class_id,
        school_id=school_id,
        page=page,
        limit=limit,
        search=search,
        status=status,
    )
    return success_response(message="Sections fetched successfully.", data=data)


@router.get("/section/{section_id}")
@router.get("/academics/sections/{section_id}")
async def get_section(
    section_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.get_section(db, section_id)
    return success_response(message="Section fetched successfully.", data=data)


@router.post("/section", status_code=status.HTTP_201_CREATED)
@router.post("/academics/sections", status_code=status.HTTP_201_CREATED)
async def create_section(
    payload: SectionCreateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.create_section(db, payload)
    return success_response(
        message="Section created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/section/{section_id}")
@router.patch("/academics/sections/{section_id}")
async def update_section(
    section_id: uuid.UUID,
    payload: SectionUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.update_section(db, section_id, payload)
    return success_response(message="Section updated successfully.", data=data)


@router.delete("/section/{section_id}")
@router.delete("/academics/sections/{section_id}")
async def delete_section(
    section_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await academic_service.delete_section(db, section_id)
    return success_response(message="Section deleted successfully.")


# ==============================================================================
# Streams (/academics/streams)
# ==============================================================================

@router.get("/academics/streams")
async def list_streams(
    class_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.list_streams(
        db, class_id=class_id, page=page, limit=limit, search=search
    )
    return success_response(message="Streams fetched successfully.", data=data)


@router.get("/academics/streams/{stream_id}")
async def get_stream(
    stream_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.get_stream(db, stream_id)
    return success_response(message="Stream fetched successfully.", data=data)


@router.post("/academics/streams", status_code=status.HTTP_201_CREATED)
async def create_stream(
    payload: StreamCreateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.create_stream(db, payload)
    return success_response(
        message="Stream created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/academics/streams/{stream_id}")
async def update_stream(
    stream_id: uuid.UUID,
    payload: StreamUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.update_stream(db, stream_id, payload)
    return success_response(message="Stream updated successfully.", data=data)


@router.delete("/academics/streams/{stream_id}")
async def delete_stream(
    stream_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await academic_service.delete_stream(db, stream_id)
    return success_response(message="Stream deleted successfully.")


# ==============================================================================
# Subjects (/subject and /academics/subjects)
# ==============================================================================

@router.get("/subject")
@router.get("/academics/subjects")
async def list_subjects(
    class_id: uuid.UUID | None = Query(None),
    school_id: uuid.UUID | None = Query(None),
    section_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = Query(None),
    status: str | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.list_subjects(
        db,
        class_id=class_id,
        school_id=school_id,
        section_id=section_id,
        page=page,
        limit=limit,
        search=search,
        status=status,
    )
    return success_response(message="Subjects fetched successfully.", data=data)


@router.get("/subject/{subject_id}")
@router.get("/academics/subjects/{subject_id}")
async def get_subject(
    subject_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.get_subject(db, subject_id)
    return success_response(message="Subject fetched successfully.", data=data)


@router.post("/subject", status_code=status.HTTP_201_CREATED)
@router.post("/academics/subjects", status_code=status.HTTP_201_CREATED)
async def create_subject(
    payload: SubjectCreateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.create_subject(db, payload)
    return success_response(
        message="Subject created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/subject/{subject_id}")
@router.patch("/academics/subjects/{subject_id}")
async def update_subject(
    subject_id: uuid.UUID,
    payload: SubjectUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.update_subject(db, subject_id, payload)
    return success_response(message="Subject updated successfully.", data=data)


@router.delete("/subject/{subject_id}")
@router.delete("/academics/subjects/{subject_id}")
async def delete_subject(
    subject_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await academic_service.delete_subject(db, subject_id)
    return success_response(message="Subject deleted successfully.")


# ==============================================================================
# Chapters & Topics (/academics/chapters, /academics/topics)
# ==============================================================================

@router.get("/academics/chapters")
async def list_chapters(
    subject_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.list_chapters(
        db, subject_id=subject_id, page=page, limit=limit, search=search
    )
    return success_response(message="Chapters fetched successfully.", data=data)


@router.get("/academics/chapters/{chapter_id}")
async def get_chapter(
    chapter_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.get_chapter(db, chapter_id)
    return success_response(message="Chapter fetched successfully.", data=data)


@router.post("/academics/chapters", status_code=status.HTTP_201_CREATED)
async def create_chapter(
    payload: ChapterCreateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.create_chapter(db, payload)
    return success_response(
        message="Chapter created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/academics/chapters/{chapter_id}")
async def update_chapter(
    chapter_id: uuid.UUID,
    payload: ChapterUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.update_chapter(db, chapter_id, payload)
    return success_response(message="Chapter updated successfully.", data=data)


@router.delete("/academics/chapters/{chapter_id}")
async def delete_chapter(
    chapter_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await academic_service.delete_chapter(db, chapter_id)
    return success_response(message="Chapter deleted successfully.")


@router.get("/academics/topics")
async def list_topics(
    chapter_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.list_topics(
        db, chapter_id=chapter_id, page=page, limit=limit, search=search
    )
    return success_response(message="Topics fetched successfully.", data=data)


@router.get("/academics/topics/{topic_id}")
async def get_topic(
    topic_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.get_topic(db, topic_id)
    return success_response(message="Topic fetched successfully.", data=data)


@router.post("/academics/topics", status_code=status.HTTP_201_CREATED)
async def create_topic(
    payload: TopicCreateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.create_topic(db, payload)
    return success_response(
        message="Topic created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/academics/topics/{topic_id}")
async def update_topic(
    topic_id: uuid.UUID,
    payload: TopicUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.update_topic(db, topic_id, payload)
    return success_response(message="Topic updated successfully.", data=data)


@router.delete("/academics/topics/{topic_id}")
async def delete_topic(
    topic_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await academic_service.delete_topic(db, topic_id)
    return success_response(message="Topic deleted successfully.")


# ==============================================================================
# Qualifications (/qualification and /academics/qualifications)
# ==============================================================================

@router.get("/qualification")
@router.get("/academics/qualifications")
async def list_qualifications(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = Query(None),
    status: str | None = Query(None),
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.list_qualifications(
        db, page=page, limit=limit, search=search, status=status
    )
    return success_response(message="Qualifications fetched successfully.", data=data)


@router.get("/qualification/{qualification_id}")
@router.get("/academics/qualifications/{qualification_id}")
async def get_qualification(
    qualification_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.get_qualification(db, qualification_id)
    return success_response(message="Qualification fetched successfully.", data=data)


@router.post("/qualification", status_code=status.HTTP_201_CREATED)
@router.post("/academics/qualifications", status_code=status.HTTP_201_CREATED)
async def create_qualification(
    payload: QualificationCreateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.create_qualification(db, payload)
    return success_response(
        message="Qualification created successfully.",
        data=data,
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/qualification/{qualification_id}")
@router.patch("/academics/qualifications/{qualification_id}")
async def update_qualification(
    qualification_id: uuid.UUID,
    payload: QualificationUpdateRequest,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await academic_service.update_qualification(db, qualification_id, payload)
    return success_response(message="Qualification updated successfully.", data=data)


@router.delete("/qualification/{qualification_id}")
@router.delete("/academics/qualifications/{qualification_id}")
async def delete_qualification(
    qualification_id: uuid.UUID,
    _user_id: uuid.UUID = Depends(get_current_admin_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    await academic_service.delete_qualification(db, qualification_id)
    return success_response(message="Qualification deleted successfully.")
