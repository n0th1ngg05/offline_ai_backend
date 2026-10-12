"""
Pydantic request schemas for School Management & Create/Edit School
(traced from src/pages/schools/CreateSchoolPage.helpers.js).
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class SchoolClassSectionEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    class_id: uuid.UUID
    section_ids: list[uuid.UUID] = Field(default_factory=list)


class SchoolCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1, max_length=255)
    udise_code: str = Field(min_length=1, max_length=100)
    country_code: str | None = "+91"
    phone: str | None = None
    state_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None
    ulb_id: uuid.UUID | None = None
    ward_id: uuid.UUID | None = None
    status: str = "ACTIVE"

    school_admin_ids: list[uuid.UUID] = Field(default_factory=list)
    class_section: list[SchoolClassSectionEntry] = Field(default_factory=list)


class SchoolUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    udise_code: str | None = None
    country_code: str | None = None
    phone: str | None = None
    state_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None
    ulb_id: uuid.UUID | None = None
    ward_id: uuid.UUID | None = None
    status: str | None = None

    school_admin_ids: list[uuid.UUID] | None = None
    removed_relations: list[uuid.UUID] = Field(default_factory=list)
    class_section: list[SchoolClassSectionEntry] | None = None
    removed_class_section: list[SchoolClassSectionEntry] = Field(default_factory=list)


class SchoolClassSectionPatchRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    custom_name: str | None = None
    custom_code: str | None = None
    status: str | None = None
