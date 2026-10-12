"""
Academic & Qualification management service:
- Classes (/api/v1/class, /api/v1/academics/classes)
- Sections (/api/v1/section, /api/v1/academics/sections)
- Streams (/api/v1/academics/streams)
- Subjects (/api/v1/subject, /api/v1/academics/subjects)
- Chapters & Topics (/api/v1/academics/chapters, /api/v1/academics/topics)
- Qualifications (/api/v1/qualification, /api/v1/academics/qualifications)
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import AppError, paginated_data
from app.models.academic import (
    AcademicClass,
    Chapter,
    Qualification,
    Section,
    Stream,
    Subject,
    SubjectSection,
    Topic,
)
from app.models.school import School, SchoolClassSection
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


# ==============================================================================
# Classes & Sections
# ==============================================================================

async def _serialize_classes(
    db: AsyncSession,
    classes: list[AcademicClass],
    *,
    school_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    if not classes:
        return []
    class_ids = [c.id for c in classes]

    sec_rows = (
        await db.execute(
            select(Section)
            .where(
                or_(Section.class_id.in_(class_ids), Section.class_id.is_(None)),
                Section.is_deleted.is_(False),
            )
            .order_by(Section.name.asc())
        )
    ).scalars().all()

    stream_rows = (
        await db.execute(
            select(Stream)
            .where(Stream.class_id.in_(class_ids), Stream.is_deleted.is_(False))
            .order_by(Stream.name.asc())
        )
    ).scalars().all()

    school_scs_by_class: dict[uuid.UUID, list[Section]] = {}
    if school_id:
        scs_rows = (
            await db.execute(
                select(SchoolClassSection, Section)
                .join(Section, Section.id == SchoolClassSection.section_id)
                .where(
                    SchoolClassSection.school_id == school_id,
                    SchoolClassSection.class_id.in_(class_ids),
                    SchoolClassSection.is_deleted.is_(False),
                    Section.is_deleted.is_(False),
                )
                .order_by(Section.name.asc())
            )
        ).all()
        for _scs, sec in scs_rows:
            school_scs_by_class.setdefault(_scs.class_id, []).append(sec)

    sections_by_class: dict[uuid.UUID, list[Section]] = {cid: [] for cid in class_ids}
    global_sections: list[Section] = []
    for s in sec_rows:
        if s.class_id:
            sections_by_class.setdefault(s.class_id, []).append(s)
        else:
            global_sections.append(s)

    streams_by_class: dict[uuid.UUID, list[dict[str, Any]]] = {cid: [] for cid in class_ids}
    for st in stream_rows:
        if st.class_id:
            streams_by_class.setdefault(st.class_id, []).append(
                {
                    "id": str(st.id),
                    "class_id": str(st.class_id),
                    "name": st.name,
                    "code": st.code,
                    "status": st.status,
                }
            )

    result = []
    for c in classes:
        if school_id and c.id in school_scs_by_class:
            c_secs = school_scs_by_class[c.id]
        else:
            c_secs = sections_by_class.get(c.id) or global_sections

        serialized_secs = [
            {
                "id": str(sec.id),
                "section_id": str(sec.id),
                "class_id": str(sec.class_id) if sec.class_id else str(c.id),
                "name": sec.name,
                "code": sec.code or sec.name,
                "status": sec.status,
            }
            for sec in c_secs
        ]

        result.append(
            {
                "id": str(c.id),
                "class_id": str(c.id),
                "name": c.name,
                "code": c.code or _slug_code(c.name),
                "has_streams": c.has_streams,
                "status": c.status,
                "sections": serialized_secs,
                "section_count": len(serialized_secs),
                "streams": streams_by_class.get(c.id, []),
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
        )
    return result


async def list_classes(
    db: AsyncSession,
    *,
    school_id: uuid.UUID | None = None,
    required_section: bool | None = None,
    page: int = 1,
    limit: int = 100,
    search: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    stmt = select(AcademicClass).where(AcademicClass.is_deleted.is_(False))

    if school_id:
        assigned_class_ids = (
            await db.execute(
                select(SchoolClassSection.class_id)
                .where(
                    SchoolClassSection.school_id == school_id,
                    SchoolClassSection.is_deleted.is_(False),
                )
                .distinct()
            )
        ).scalars().all()
        if assigned_class_ids:
            stmt = stmt.where(AcademicClass.id.in_(assigned_class_ids))

    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(or_(AcademicClass.name.ilike(q), AcademicClass.code.ilike(q)))
    if status and status.strip():
        stmt = stmt.where(AcademicClass.status == status.strip().upper())

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(AcademicClass.created_at.asc(), AcademicClass.name.asc())
            .offset((max(1, page) - 1) * max(1, limit))
            .limit(max(1, limit))
        )
    ).scalars().all()

    items = await _serialize_classes(db, list(rows), school_id=school_id)
    return paginated_data(items=items, total=total, page=page, limit=limit)


async def get_class(db: AsyncSession, class_id: uuid.UUID) -> dict[str, Any]:
    c = (
        await db.execute(
            select(AcademicClass).where(
                AcademicClass.id == class_id, AcademicClass.is_deleted.is_(False)
            )
        )
    ).scalar_one_or_none()
    if not c:
        raise AppError("Class not found.", status_code=404)
    items = await _serialize_classes(db, [c])
    return items[0]


def _extract_section_name_and_code(sec_item: Any) -> tuple[uuid.UUID | None, str, str | None, str]:
    if isinstance(sec_item, str):
        name = sec_item.strip()
        return None, name, _slug_code(name, "SEC_"), "ACTIVE"
    if isinstance(sec_item, dict):
        sid = sec_item.get("id")
        parsed_id = uuid.UUID(str(sid)) if sid else None
        name = str(sec_item.get("name") or "").strip()
        code = sec_item.get("code")
        status = _normalize_status(sec_item.get("status"))
        return parsed_id, name, code, status
    # SectionNestedInput
    name = sec_item.name.strip()
    return sec_item.id, name, sec_item.code, _normalize_status(sec_item.status)


async def create_class(db: AsyncSession, payload: ClassCreateRequest) -> dict[str, Any]:
    name = payload.name.strip()
    code = (payload.code or _slug_code(name)).strip().upper()

    c = AcademicClass(
        name=name,
        code=code,
        has_streams=bool(payload.has_streams),
        status=_normalize_status(payload.status),
    )
    db.add(c)
    await db.flush()

    sections_input = payload.sections or ["A", "B"]
    for s_item in sections_input:
        _, s_name, s_code, s_status = _extract_section_name_and_code(s_item)
        if not s_name:
            continue
        db.add(
            Section(
                class_id=c.id,
                name=s_name,
                code=(s_code or _slug_code(s_name, "SEC_")).strip().upper(),
                status=s_status,
            )
        )

    await db.commit()
    return await get_class(db, c.id)


async def update_class(
    db: AsyncSession, class_id: uuid.UUID, payload: ClassUpdateRequest
) -> dict[str, Any]:
    c = (
        await db.execute(
            select(AcademicClass).where(
                AcademicClass.id == class_id, AcademicClass.is_deleted.is_(False)
            )
        )
    ).scalar_one_or_none()
    if not c:
        raise AppError("Class not found.", status_code=404)

    if payload.name is not None:
        c.name = payload.name.strip()
    if payload.code is not None and payload.code.strip():
        c.code = payload.code.strip().upper()
    if payload.has_streams is not None:
        c.has_streams = payload.has_streams
    if payload.status is not None:
        c.status = _normalize_status(payload.status, c.status)

    if payload.remove_section_ids:
        rem_secs = (
            await db.execute(
                select(Section).where(
                    Section.id.in_(payload.remove_section_ids),
                    Section.class_id == c.id,
                )
            )
        ).scalars().all()
        for rs in rem_secs:
            rs.is_deleted = True

    sections_to_upsert = payload.add_sections or payload.sections or []
    if sections_to_upsert:
        existing_secs = (
            await db.execute(
                select(Section).where(Section.class_id == c.id, Section.is_deleted.is_(False))
            )
        ).scalars().all()
        by_id = {s.id: s for s in existing_secs}
        by_name = {s.name.lower(): s for s in existing_secs}

        for s_item in sections_to_upsert:
            sid, s_name, s_code, s_status = _extract_section_name_and_code(s_item)
            if not s_name:
                continue
            target = None
            if sid and sid in by_id:
                target = by_id[sid]
            elif s_name.lower() in by_name:
                target = by_name[s_name.lower()]

            if target:
                target.name = s_name
                if s_code:
                    target.code = s_code.strip().upper()
                target.status = s_status
            else:
                db.add(
                    Section(
                        class_id=c.id,
                        name=s_name,
                        code=(s_code or _slug_code(s_name, "SEC_")).strip().upper(),
                        status=s_status,
                    )
                )

    await db.commit()
    return await get_class(db, c.id)


async def delete_class(db: AsyncSession, class_id: uuid.UUID) -> None:
    c = (
        await db.execute(
            select(AcademicClass).where(
                AcademicClass.id == class_id, AcademicClass.is_deleted.is_(False)
            )
        )
    ).scalar_one_or_none()
    if not c:
        raise AppError("Class not found.", status_code=404)
    c.is_deleted = True
    c.status = "INACTIVE"
    await db.commit()


# ==============================================================================
# Sections
# ==============================================================================

async def list_sections(
    db: AsyncSession,
    *,
    class_id: uuid.UUID | None = None,
    school_id: uuid.UUID | None = None,
    page: int = 1,
    limit: int = 100,
    search: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    stmt = select(Section).where(Section.is_deleted.is_(False))
    if school_id and class_id:
        sec_ids = (
            await db.execute(
                select(SchoolClassSection.section_id).where(
                    SchoolClassSection.school_id == school_id,
                    SchoolClassSection.class_id == class_id,
                    SchoolClassSection.is_deleted.is_(False),
                )
            )
        ).scalars().all()
        if sec_ids:
            stmt = stmt.where(Section.id.in_(sec_ids))
        else:
            stmt = stmt.where(Section.class_id == class_id)
    elif class_id:
        stmt = stmt.where(Section.class_id == class_id)

    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(or_(Section.name.ilike(q), Section.code.ilike(q)))
    if status and status.strip():
        stmt = stmt.where(Section.status == status.strip().upper())

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(Section.name.asc())
            .offset((max(1, page) - 1) * max(1, limit))
            .limit(max(1, limit))
        )
    ).scalars().all()

    items = [
        {
            "id": str(s.id),
            "section_id": str(s.id),
            "class_id": str(s.class_id) if s.class_id else None,
            "name": s.name,
            "code": s.code or s.name,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in rows
    ]
    return paginated_data(items=items, total=total, page=page, limit=limit)


async def get_section(db: AsyncSession, section_id: uuid.UUID) -> dict[str, Any]:
    s = (
        await db.execute(select(Section).where(Section.id == section_id, Section.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not s:
        raise AppError("Section not found.", status_code=404)
    return {
        "id": str(s.id),
        "section_id": str(s.id),
        "class_id": str(s.class_id) if s.class_id else None,
        "name": s.name,
        "code": s.code or s.name,
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


async def create_section(db: AsyncSession, payload: SectionCreateRequest) -> dict[str, Any]:
    name = payload.name.strip()
    code = (payload.code or _slug_code(name, "SEC_")).strip().upper()
    s = Section(
        class_id=payload.class_id,
        name=name,
        code=code,
        status=_normalize_status(payload.status),
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return await get_section(db, s.id)


async def update_section(
    db: AsyncSession, section_id: uuid.UUID, payload: SectionUpdateRequest
) -> dict[str, Any]:
    s = (
        await db.execute(select(Section).where(Section.id == section_id, Section.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not s:
        raise AppError("Section not found.", status_code=404)
    if payload.class_id is not None:
        s.class_id = payload.class_id
    if payload.name is not None:
        s.name = payload.name.strip()
    if payload.code is not None and payload.code.strip():
        s.code = payload.code.strip().upper()
    if payload.status is not None:
        s.status = _normalize_status(payload.status, s.status)
    await db.commit()
    return await get_section(db, s.id)


async def delete_section(db: AsyncSession, section_id: uuid.UUID) -> None:
    s = (
        await db.execute(select(Section).where(Section.id == section_id, Section.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not s:
        raise AppError("Section not found.", status_code=404)
    s.is_deleted = True
    s.status = "INACTIVE"
    await db.commit()


# ==============================================================================
# Streams
# ==============================================================================

async def list_streams(
    db: AsyncSession,
    *,
    class_id: uuid.UUID | None = None,
    page: int = 1,
    limit: int = 100,
    search: str | None = None,
) -> dict[str, Any]:
    stmt = select(Stream).where(Stream.is_deleted.is_(False))
    if class_id:
        stmt = stmt.where(Stream.class_id == class_id)
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(or_(Stream.name.ilike(q), Stream.code.ilike(q)))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(Stream.name.asc())
            .offset((max(1, page) - 1) * max(1, limit))
            .limit(max(1, limit))
        )
    ).scalars().all()

    items = [
        {
            "id": str(st.id),
            "class_id": str(st.class_id) if st.class_id else None,
            "name": st.name,
            "code": st.code,
            "status": st.status,
            "created_at": st.created_at.isoformat() if st.created_at else None,
        }
        for st in rows
    ]
    return paginated_data(items=items, total=total, page=page, limit=limit)


async def get_stream(db: AsyncSession, stream_id: uuid.UUID) -> dict[str, Any]:
    st = (
        await db.execute(select(Stream).where(Stream.id == stream_id, Stream.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not st:
        raise AppError("Stream not found.", status_code=404)
    return {
        "id": str(st.id),
        "class_id": str(st.class_id) if st.class_id else None,
        "name": st.name,
        "code": st.code,
        "status": st.status,
        "created_at": st.created_at.isoformat() if st.created_at else None,
    }


async def create_stream(db: AsyncSession, payload: StreamCreateRequest) -> dict[str, Any]:
    name = payload.name.strip()
    code = (payload.code or _slug_code(name, "STR_")).strip().upper()
    st = Stream(
        class_id=payload.class_id,
        name=name,
        code=code,
        status=_normalize_status(payload.status),
    )
    db.add(st)
    await db.commit()
    await db.refresh(st)
    return await get_stream(db, st.id)


async def update_stream(
    db: AsyncSession, stream_id: uuid.UUID, payload: StreamUpdateRequest
) -> dict[str, Any]:
    st = (
        await db.execute(select(Stream).where(Stream.id == stream_id, Stream.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not st:
        raise AppError("Stream not found.", status_code=404)
    if payload.class_id is not None:
        st.class_id = payload.class_id
    if payload.name is not None:
        st.name = payload.name.strip()
    if payload.code is not None and payload.code.strip():
        st.code = payload.code.strip().upper()
    if payload.status is not None:
        st.status = _normalize_status(payload.status, st.status)
    await db.commit()
    return await get_stream(db, st.id)


async def delete_stream(db: AsyncSession, stream_id: uuid.UUID) -> None:
    st = (
        await db.execute(select(Stream).where(Stream.id == stream_id, Stream.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not st:
        raise AppError("Stream not found.", status_code=404)
    st.is_deleted = True
    st.status = "INACTIVE"
    await db.commit()


# ==============================================================================
# Subjects, Chapters & Topics
# ==============================================================================

async def _serialize_subjects(
    db: AsyncSession, subjects: list[Subject]
) -> list[dict[str, Any]]:
    if not subjects:
        return []
    subject_ids = [s.id for s in subjects]
    class_ids = list({s.class_id for s in subjects if s.class_id})
    school_ids = list({s.school_id for s in subjects if s.school_id})

    classes_map = {}
    if class_ids:
        c_rows = (
            await db.execute(select(AcademicClass).where(AcademicClass.id.in_(class_ids)))
        ).scalars().all()
        classes_map = {c.id: c for c in c_rows}

    schools_map = {}
    if school_ids:
        sch_rows = (
            await db.execute(select(School).where(School.id.in_(school_ids)))
        ).scalars().all()
        schools_map = {sch.id: sch for sch in sch_rows}

    sub_sec_rows = (
        await db.execute(
            select(SubjectSection, Section)
            .join(Section, Section.id == SubjectSection.section_id)
            .where(
                SubjectSection.subject_id.in_(subject_ids),
                Section.is_deleted.is_(False),
            )
            .order_by(Section.name.asc())
        )
    ).all()
    sections_by_subject: dict[uuid.UUID, list[dict[str, Any]]] = {sid: [] for sid in subject_ids}
    for ss, sec in sub_sec_rows:
        sections_by_subject.setdefault(ss.subject_id, []).append(
            {
                "id": str(sec.id),
                "section_id": str(sec.id),
                "name": sec.name,
                "code": sec.code or sec.name,
            }
        )

    chapter_rows = (
        await db.execute(
            select(Chapter)
            .where(Chapter.subject_id.in_(subject_ids), Chapter.is_deleted.is_(False))
            .order_by(Chapter.created_at.asc(), Chapter.name.asc())
        )
    ).scalars().all()
    chapter_ids = [ch.id for ch in chapter_rows]

    topics_by_chapter: dict[uuid.UUID, list[dict[str, Any]]] = {cid: [] for cid in chapter_ids}
    if chapter_ids:
        topic_rows = (
            await db.execute(
                select(Topic)
                .where(Topic.chapter_id.in_(chapter_ids), Topic.is_deleted.is_(False))
                .order_by(Topic.created_at.asc(), Topic.name.asc())
            )
        ).scalars().all()
        for t in topic_rows:
            topics_by_chapter.setdefault(t.chapter_id, []).append(
                {
                    "id": str(t.id),
                    "topic_id": str(t.id),
                    "chapter_id": str(t.chapter_id),
                    "name": t.name,
                    "code": t.code,
                    "status": t.status,
                }
            )

    chapters_by_subject: dict[uuid.UUID, list[dict[str, Any]]] = {sid: [] for sid in subject_ids}
    for ch in chapter_rows:
        ch_topics = topics_by_chapter.get(ch.id, [])
        chapters_by_subject.setdefault(ch.subject_id, []).append(
            {
                "id": str(ch.id),
                "chapter_id": str(ch.id),
                "subject_id": str(ch.subject_id),
                "name": ch.name,
                "code": ch.code,
                "status": ch.status,
                "topics": ch_topics,
                "topic_count": len(ch_topics),
            }
        )

    result = []
    for sub in subjects:
        cls_obj = classes_map.get(sub.class_id) if sub.class_id else None
        sch_obj = schools_map.get(sub.school_id) if sub.school_id else None
        secs = sections_by_subject.get(sub.id, [])
        chaps = chapters_by_subject.get(sub.id, [])
        result.append(
            {
                "id": str(sub.id),
                "subject_id": str(sub.id),
                "name": sub.name,
                "code": sub.code or _slug_code(sub.name, "SUB_"),
                "status": sub.status,
                "class_id": str(sub.class_id) if sub.class_id else None,
                "school_id": str(sub.school_id) if sub.school_id else None,
                "class": (
                    {"id": str(cls_obj.id), "name": cls_obj.name, "code": cls_obj.code}
                    if cls_obj
                    else None
                ),
                "school": (
                    {
                        "id": str(sch_obj.id),
                        "name": sch_obj.name,
                        "code": sch_obj.udise_code,
                        "udise_code": sch_obj.udise_code,
                    }
                    if sch_obj
                    else None
                ),
                "sections": secs,
                "section_ids": [s["id"] for s in secs],
                "chapters": chaps,
                "chapter_count": len(chaps),
                "created_at": sub.created_at.isoformat() if sub.created_at else None,
                "updated_at": sub.updated_at.isoformat() if sub.updated_at else None,
            }
        )
    return result


async def list_subjects(
    db: AsyncSession,
    *,
    class_id: uuid.UUID | None = None,
    school_id: uuid.UUID | None = None,
    section_id: uuid.UUID | None = None,
    page: int = 1,
    limit: int = 100,
    search: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    stmt = select(Subject).where(Subject.is_deleted.is_(False))
    if class_id:
        stmt = stmt.where(Subject.class_id == class_id)
    if school_id:
        stmt = stmt.where(or_(Subject.school_id == school_id, Subject.school_id.is_(None)))
    if section_id:
        sub_ids_with_sec = (
            await db.execute(
                select(SubjectSection.subject_id).where(SubjectSection.section_id == section_id)
            )
        ).scalars().all()
        if sub_ids_with_sec:
            stmt = stmt.where(Subject.id.in_(sub_ids_with_sec))

    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(or_(Subject.name.ilike(q), Subject.code.ilike(q)))
    if status and status.strip():
        stmt = stmt.where(Subject.status == status.strip().upper())

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(Subject.name.asc())
            .offset((max(1, page) - 1) * max(1, limit))
            .limit(max(1, limit))
        )
    ).scalars().all()

    items = await _serialize_subjects(db, list(rows))
    return paginated_data(items=items, total=total, page=page, limit=limit)


async def get_subject(db: AsyncSession, subject_id: uuid.UUID) -> dict[str, Any]:
    sub = (
        await db.execute(
            select(Subject).where(Subject.id == subject_id, Subject.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not sub:
        raise AppError("Subject not found.", status_code=404)
    items = await _serialize_subjects(db, [sub])
    return items[0]


async def _sync_subject_chapters(
    db: AsyncSession, subject_id: uuid.UUID, chapters_input: list[Any]
) -> None:
    existing_chaps = (
        await db.execute(
            select(Chapter).where(Chapter.subject_id == subject_id, Chapter.is_deleted.is_(False))
        )
    ).scalars().all()
    chap_by_id = {c.id: c for c in existing_chaps}
    chap_by_name = {c.name.lower(): c for c in existing_chaps}

    for ch_in in chapters_input:
        if isinstance(ch_in, dict):
            cid_raw = ch_in.get("id") or ch_in.get("chapter_id")
            cid = uuid.UUID(str(cid_raw)) if cid_raw else None
            ch_name = str(ch_in.get("name") or "").strip()
            ch_code = ch_in.get("code")
            ch_status = _normalize_status(ch_in.get("status"))
            topics_in = ch_in.get("topics") or []
        else:
            cid = ch_in.id
            ch_name = ch_in.name.strip()
            ch_code = ch_in.code
            ch_status = _normalize_status(ch_in.status)
            topics_in = ch_in.topics or []

        if not ch_name:
            continue

        chapter_obj = None
        if cid and cid in chap_by_id:
            chapter_obj = chap_by_id[cid]
        elif ch_name.lower() in chap_by_name:
            chapter_obj = chap_by_name[ch_name.lower()]

        if chapter_obj:
            chapter_obj.name = ch_name
            if ch_code:
                chapter_obj.code = str(ch_code).strip().upper()
            chapter_obj.status = ch_status
        else:
            chapter_obj = Chapter(
                subject_id=subject_id,
                name=ch_name,
                code=(str(ch_code) if ch_code else _slug_code(ch_name, "CH_")).strip().upper(),
                status=ch_status,
            )
            db.add(chapter_obj)
            await db.flush()

        existing_topics = (
            await db.execute(
                select(Topic).where(
                    Topic.chapter_id == chapter_obj.id, Topic.is_deleted.is_(False)
                )
            )
        ).scalars().all()
        topic_by_id = {t.id: t for t in existing_topics}
        topic_by_name = {t.name.lower(): t for t in existing_topics}

        for t_in in topics_in:
            if isinstance(t_in, str):
                tid = None
                t_name = t_in.strip()
                t_code = None
            elif isinstance(t_in, dict):
                tid_raw = t_in.get("id") or t_in.get("topic_id")
                tid = uuid.UUID(str(tid_raw)) if tid_raw else None
                t_name = str(t_in.get("name") or t_in.get("title") or "").strip()
                t_code = t_in.get("code")
            else:
                continue

            if not t_name:
                continue

            topic_obj = None
            if tid and tid in topic_by_id:
                topic_obj = topic_by_id[tid]
            elif t_name.lower() in topic_by_name:
                topic_obj = topic_by_name[t_name.lower()]

            if topic_obj:
                topic_obj.name = t_name
                if t_code:
                    topic_obj.code = str(t_code).strip().upper()
            else:
                db.add(
                    Topic(
                        chapter_id=chapter_obj.id,
                        name=t_name,
                        code=(str(t_code) if t_code else _slug_code(t_name, "TOP_")).strip().upper(),
                        status="ACTIVE",
                    )
                )


async def create_subject(db: AsyncSession, payload: SubjectCreateRequest) -> dict[str, Any]:
    name = payload.name.strip()
    code = (payload.code or _slug_code(name, "SUB_")).strip().upper()

    sub = Subject(
        name=name,
        code=code,
        class_id=payload.class_id,
        school_id=payload.school_id,
        status=_normalize_status(payload.status),
    )
    db.add(sub)
    await db.flush()

    for sec_id in set(payload.section_ids or []):
        db.add(SubjectSection(subject_id=sub.id, section_id=sec_id))

    if payload.chapters:
        await _sync_subject_chapters(db, sub.id, payload.chapters)

    await db.commit()
    return await get_subject(db, sub.id)


async def update_subject(
    db: AsyncSession, subject_id: uuid.UUID, payload: SubjectUpdateRequest
) -> dict[str, Any]:
    sub = (
        await db.execute(
            select(Subject).where(Subject.id == subject_id, Subject.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not sub:
        raise AppError("Subject not found.", status_code=404)

    if payload.name is not None:
        sub.name = payload.name.strip()
    if payload.code is not None and payload.code.strip():
        sub.code = payload.code.strip().upper()
    if payload.class_id is not None:
        sub.class_id = payload.class_id
    if payload.school_id is not None:
        sub.school_id = payload.school_id
    if payload.status is not None:
        sub.status = _normalize_status(payload.status, sub.status)

    if payload.removed_section_ids:
        await db.execute(
            delete(SubjectSection).where(
                SubjectSection.subject_id == sub.id,
                SubjectSection.section_id.in_(payload.removed_section_ids),
            )
        )

    if payload.section_ids is not None:
        existing_sec_ids = set(
            (
                await db.execute(
                    select(SubjectSection.section_id).where(SubjectSection.subject_id == sub.id)
                )
            ).scalars().all()
        )
        for sec_id in set(payload.section_ids):
            if sec_id not in existing_sec_ids:
                db.add(SubjectSection(subject_id=sub.id, section_id=sec_id))

    if payload.removed_chapter_ids:
        rem_chaps = (
            await db.execute(
                select(Chapter).where(
                    Chapter.id.in_(payload.removed_chapter_ids),
                    Chapter.subject_id == sub.id,
                )
            )
        ).scalars().all()
        for ch in rem_chaps:
            ch.is_deleted = True

    if payload.removed_topic_ids:
        rem_tops = (
            await db.execute(select(Topic).where(Topic.id.in_(payload.removed_topic_ids)))
        ).scalars().all()
        for tp in rem_tops:
            tp.is_deleted = True

    if payload.chapters is not None:
        await _sync_subject_chapters(db, sub.id, payload.chapters)

    await db.commit()
    return await get_subject(db, sub.id)


async def delete_subject(db: AsyncSession, subject_id: uuid.UUID) -> None:
    sub = (
        await db.execute(
            select(Subject).where(Subject.id == subject_id, Subject.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not sub:
        raise AppError("Subject not found.", status_code=404)
    sub.is_deleted = True
    sub.status = "INACTIVE"
    await db.commit()


# ==============================================================================
# Standalone Chapters & Topics CRUD
# ==============================================================================

async def list_chapters(
    db: AsyncSession,
    *,
    subject_id: uuid.UUID | None = None,
    page: int = 1,
    limit: int = 100,
    search: str | None = None,
) -> dict[str, Any]:
    stmt = select(Chapter).where(Chapter.is_deleted.is_(False))
    if subject_id:
        stmt = stmt.where(Chapter.subject_id == subject_id)
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(or_(Chapter.name.ilike(q), Chapter.code.ilike(q)))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(Chapter.created_at.asc(), Chapter.name.asc())
            .offset((max(1, page) - 1) * max(1, limit))
            .limit(max(1, limit))
        )
    ).scalars().all()

    items = [
        {
            "id": str(ch.id),
            "subject_id": str(ch.subject_id),
            "name": ch.name,
            "code": ch.code,
            "status": ch.status,
            "created_at": ch.created_at.isoformat() if ch.created_at else None,
        }
        for ch in rows
    ]
    return paginated_data(items=items, total=total, page=page, limit=limit)


async def get_chapter(db: AsyncSession, chapter_id: uuid.UUID) -> dict[str, Any]:
    ch = (
        await db.execute(
            select(Chapter).where(Chapter.id == chapter_id, Chapter.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not ch:
        raise AppError("Chapter not found.", status_code=404)
    topics = (
        await db.execute(
            select(Topic).where(Topic.chapter_id == ch.id, Topic.is_deleted.is_(False))
        )
    ).scalars().all()
    return {
        "id": str(ch.id),
        "subject_id": str(ch.subject_id),
        "name": ch.name,
        "code": ch.code,
        "status": ch.status,
        "topics": [
            {"id": str(t.id), "name": t.name, "code": t.code, "status": t.status} for t in topics
        ],
        "created_at": ch.created_at.isoformat() if ch.created_at else None,
    }


async def create_chapter(db: AsyncSession, payload: ChapterCreateRequest) -> dict[str, Any]:
    name = payload.name.strip()
    code = (payload.code or _slug_code(name, "CH_")).strip().upper()
    ch = Chapter(
        subject_id=payload.subject_id,
        name=name,
        code=code,
        status=_normalize_status(payload.status),
    )
    db.add(ch)
    await db.flush()
    for t_in in payload.topics or []:
        t_name = t_in.strip() if isinstance(t_in, str) else str(t_in.get("name") or "").strip()
        if t_name:
            db.add(
                Topic(
                    chapter_id=ch.id,
                    name=t_name,
                    code=_slug_code(t_name, "TOP_"),
                    status="ACTIVE",
                )
            )
    await db.commit()
    return await get_chapter(db, ch.id)


async def update_chapter(
    db: AsyncSession, chapter_id: uuid.UUID, payload: ChapterUpdateRequest
) -> dict[str, Any]:
    ch = (
        await db.execute(
            select(Chapter).where(Chapter.id == chapter_id, Chapter.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not ch:
        raise AppError("Chapter not found.", status_code=404)
    if payload.subject_id is not None:
        ch.subject_id = payload.subject_id
    if payload.name is not None:
        ch.name = payload.name.strip()
    if payload.code is not None and payload.code.strip():
        ch.code = payload.code.strip().upper()
    if payload.status is not None:
        ch.status = _normalize_status(payload.status, ch.status)
    await db.commit()
    return await get_chapter(db, ch.id)


async def delete_chapter(db: AsyncSession, chapter_id: uuid.UUID) -> None:
    ch = (
        await db.execute(
            select(Chapter).where(Chapter.id == chapter_id, Chapter.is_deleted.is_(False))
        )
    ).scalar_one_or_none()
    if not ch:
        raise AppError("Chapter not found.", status_code=404)
    ch.is_deleted = True
    ch.status = "INACTIVE"
    await db.commit()


async def list_topics(
    db: AsyncSession,
    *,
    chapter_id: uuid.UUID | None = None,
    page: int = 1,
    limit: int = 100,
    search: str | None = None,
) -> dict[str, Any]:
    stmt = select(Topic).where(Topic.is_deleted.is_(False))
    if chapter_id:
        stmt = stmt.where(Topic.chapter_id == chapter_id)
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(or_(Topic.name.ilike(q), Topic.code.ilike(q)))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(Topic.created_at.asc(), Topic.name.asc())
            .offset((max(1, page) - 1) * max(1, limit))
            .limit(max(1, limit))
        )
    ).scalars().all()

    items = [
        {
            "id": str(t.id),
            "chapter_id": str(t.chapter_id),
            "name": t.name,
            "code": t.code,
            "status": t.status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in rows
    ]
    return paginated_data(items=items, total=total, page=page, limit=limit)


async def get_topic(db: AsyncSession, topic_id: uuid.UUID) -> dict[str, Any]:
    t = (
        await db.execute(select(Topic).where(Topic.id == topic_id, Topic.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not t:
        raise AppError("Topic not found.", status_code=404)
    return {
        "id": str(t.id),
        "chapter_id": str(t.chapter_id),
        "name": t.name,
        "code": t.code,
        "status": t.status,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


async def create_topic(db: AsyncSession, payload: TopicCreateRequest) -> dict[str, Any]:
    name = payload.name.strip()
    code = (payload.code or _slug_code(name, "TOP_")).strip().upper()
    t = Topic(
        chapter_id=payload.chapter_id,
        name=name,
        code=code,
        status=_normalize_status(payload.status),
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return await get_topic(db, t.id)


async def update_topic(
    db: AsyncSession, topic_id: uuid.UUID, payload: TopicUpdateRequest
) -> dict[str, Any]:
    t = (
        await db.execute(select(Topic).where(Topic.id == topic_id, Topic.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not t:
        raise AppError("Topic not found.", status_code=404)
    if payload.chapter_id is not None:
        t.chapter_id = payload.chapter_id
    if payload.name is not None:
        t.name = payload.name.strip()
    if payload.code is not None and payload.code.strip():
        t.code = payload.code.strip().upper()
    if payload.status is not None:
        t.status = _normalize_status(payload.status, t.status)
    await db.commit()
    return await get_topic(db, t.id)


async def delete_topic(db: AsyncSession, topic_id: uuid.UUID) -> None:
    t = (
        await db.execute(select(Topic).where(Topic.id == topic_id, Topic.is_deleted.is_(False)))
    ).scalar_one_or_none()
    if not t:
        raise AppError("Topic not found.", status_code=404)
    t.is_deleted = True
    t.status = "INACTIVE"
    await db.commit()


# ==============================================================================
# Qualifications
# ==============================================================================

async def list_qualifications(
    db: AsyncSession,
    *,
    page: int = 1,
    limit: int = 100,
    search: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    stmt = select(Qualification).where(Qualification.is_deleted.is_(False))
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(or_(Qualification.name.ilike(q), Qualification.code.ilike(q)))
    if status and status.strip():
        stmt = stmt.where(Qualification.status == status.strip().upper())

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(Qualification.name.asc())
            .offset((max(1, page) - 1) * max(1, limit))
            .limit(max(1, limit))
        )
    ).scalars().all()

    items = [
        {
            "id": str(q.id),
            "name": q.name,
            "code": q.code or _slug_code(q.name),
            "status": q.status,
            "created_at": q.created_at.isoformat() if q.created_at else None,
        }
        for q in rows
    ]
    return paginated_data(items=items, total=total, page=page, limit=limit)


async def get_qualification(db: AsyncSession, qualification_id: uuid.UUID) -> dict[str, Any]:
    q = (
        await db.execute(
            select(Qualification).where(
                Qualification.id == qualification_id, Qualification.is_deleted.is_(False)
            )
        )
    ).scalar_one_or_none()
    if not q:
        raise AppError("Qualification not found.", status_code=404)
    return {
        "id": str(q.id),
        "name": q.name,
        "code": q.code or _slug_code(q.name),
        "status": q.status,
        "created_at": q.created_at.isoformat() if q.created_at else None,
    }


async def create_qualification(
    db: AsyncSession, payload: QualificationCreateRequest
) -> dict[str, Any]:
    name = payload.name.strip()
    code = (payload.code or _slug_code(name)).strip().upper()
    existing = (
        await db.execute(
            select(Qualification).where(
                func.lower(Qualification.name) == name.lower(),
                Qualification.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise AppError("A qualification with this name already exists.", status_code=400)

    q = Qualification(name=name, code=code, status=_normalize_status(payload.status))
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return await get_qualification(db, q.id)


async def update_qualification(
    db: AsyncSession, qualification_id: uuid.UUID, payload: QualificationUpdateRequest
) -> dict[str, Any]:
    q = (
        await db.execute(
            select(Qualification).where(
                Qualification.id == qualification_id, Qualification.is_deleted.is_(False)
            )
        )
    ).scalar_one_or_none()
    if not q:
        raise AppError("Qualification not found.", status_code=404)
    if payload.name is not None:
        q.name = payload.name.strip()
    if payload.code is not None and payload.code.strip():
        q.code = payload.code.strip().upper()
    if payload.status is not None:
        q.status = _normalize_status(payload.status, q.status)
    await db.commit()
    return await get_qualification(db, q.id)


async def delete_qualification(db: AsyncSession, qualification_id: uuid.UUID) -> None:
    q = (
        await db.execute(
            select(Qualification).where(
                Qualification.id == qualification_id, Qualification.is_deleted.is_(False)
            )
        )
    ).scalar_one_or_none()
    if not q:
        raise AppError("Qualification not found.", status_code=404)
    q.is_deleted = True
    q.status = "INACTIVE"
    await db.commit()
