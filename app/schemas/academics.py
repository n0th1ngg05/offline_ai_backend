"""
Pydantic request schemas for Location & Academic endpoints, aligned with
the frontend's CreateRegionManagementPage, CreateClassManagementPage,
CreateSubjectManagementPage, and QualificationManagementPage payloads.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DistrictNestedInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: uuid.UUID | None = None
    name: str
    code: str | None = None
    status: str = "ACTIVE"


class StateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1, max_length=150)
    code: str | None = None
    status: str = "ACTIVE"
    districts: list[DistrictNestedInput] = Field(default_factory=list)


class StateUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    code: str | None = None
    status: str | None = None
    districts: list[DistrictNestedInput] | None = None
    remove_district_ids: list[uuid.UUID] = Field(default_factory=list)


class DistrictCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    state_id: uuid.UUID
    name: str = Field(min_length=1, max_length=150)
    code: str | None = None
    status: str = "ACTIVE"


class DistrictUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    state_id: uuid.UUID | None = None
    name: str | None = None
    code: str | None = None
    status: str | None = None


class UlbCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    district_id: uuid.UUID
    name: str = Field(min_length=1, max_length=150)
    code: str | None = None
    status: str = "ACTIVE"


class UlbUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    district_id: uuid.UUID | None = None
    name: str | None = None
    code: str | None = None
    status: str | None = None


class WardCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    ulb_id: uuid.UUID
    name: str = Field(min_length=1, max_length=150)
    code: str | None = None
    status: str = "ACTIVE"


class WardUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    ulb_id: uuid.UUID | None = None
    name: str | None = None
    code: str | None = None
    status: str | None = None


class SectionNestedInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: uuid.UUID | None = None
    name: str
    code: str | None = None
    status: str = "ACTIVE"


class ClassCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1, max_length=100)
    code: str | None = None
    has_streams: bool = False
    status: str = "ACTIVE"
    sections: list[str | SectionNestedInput | dict[str, Any]] = Field(default_factory=list)


class ClassUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    code: str | None = None
    has_streams: bool | None = None
    status: str | None = None
    sections: list[str | SectionNestedInput | dict[str, Any]] | None = None
    add_sections: list[str | SectionNestedInput | dict[str, Any]] = Field(default_factory=list)
    remove_section_ids: list[uuid.UUID] = Field(default_factory=list)


class SectionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    class_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=100)
    code: str | None = None
    status: str = "ACTIVE"


class SectionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    class_id: uuid.UUID | None = None
    name: str | None = None
    code: str | None = None
    status: str | None = None


class StreamCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    class_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=100)
    code: str | None = None
    status: str = "ACTIVE"


class StreamUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    class_id: uuid.UUID | None = None
    name: str | None = None
    code: str | None = None
    status: str | None = None


class ChapterNestedInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: uuid.UUID | None = None
    name: str
    code: str | None = None
    status: str = "ACTIVE"
    topics: list[str | dict[str, Any]] = Field(default_factory=list)


class SubjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1, max_length=150)
    code: str | None = None
    class_id: uuid.UUID | None = None
    school_id: uuid.UUID | None = None
    section_ids: list[uuid.UUID] = Field(default_factory=list)
    chapters: list[ChapterNestedInput | dict[str, Any]] = Field(default_factory=list)
    status: str = "ACTIVE"


class SubjectUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    code: str | None = None
    class_id: uuid.UUID | None = None
    school_id: uuid.UUID | None = None
    section_ids: list[uuid.UUID] | None = None
    chapters: list[ChapterNestedInput | dict[str, Any]] | None = None
    removed_chapter_ids: list[uuid.UUID] = Field(default_factory=list)
    removed_topic_ids: list[uuid.UUID] = Field(default_factory=list)
    removed_class_ids: list[uuid.UUID] = Field(default_factory=list)
    removed_section_ids: list[uuid.UUID] = Field(default_factory=list)
    status: str | None = None


class ChapterCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    subject_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    code: str | None = None
    status: str = "ACTIVE"
    topics: list[str | dict[str, Any]] = Field(default_factory=list)


class ChapterUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    subject_id: uuid.UUID | None = None
    name: str | None = None
    code: str | None = None
    status: str | None = None
    topics: list[str | dict[str, Any]] | None = None


class TopicCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    chapter_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    code: str | None = None
    status: str = "ACTIVE"


class TopicUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    chapter_id: uuid.UUID | None = None
    name: str | None = None
    code: str | None = None
    status: str | None = None


class QualificationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1, max_length=150)
    code: str | None = None
    status: str = "ACTIVE"


class QualificationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    code: str | None = None
    status: str | None = None
