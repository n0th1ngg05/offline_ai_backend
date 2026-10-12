"""
Dashboard Summary & Role Permissions Matrix service:
- GET /api/v1/dashboard/summary & GET /api/v1/reports/summary
- GET /api/v1/role-permissions/matrix
- PATCH /api/v1/role-permissions/{role_id}
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import AppError
from app.models.academic import AcademicClass, Subject
from app.models.assignments import RolePermission
from app.models.location import District, State
from app.models.school import School
from app.models.user import User
from app.schemas.users import RolePermissionUpdateRequest


PERMISSION_MODULES_DEFINITION = [
    {
        "module": "dashboard",
        "label": "Dashboard",
        "actions": ["view"],
    },
    {
        "module": "schools",
        "label": "Schools Management",
        "actions": ["view", "create", "edit", "delete"],
    },
    {
        "module": "users",
        "label": "Users Management",
        "actions": ["view", "create", "edit", "delete"],
    },
    {
        "module": "teachers",
        "label": "Teachers Management",
        "actions": ["view", "create", "edit", "delete"],
    },
    {
        "module": "students",
        "label": "Students Management",
        "actions": ["view", "create", "edit", "delete"],
    },
    {
        "module": "classroom_operators",
        "label": "Classroom Operators",
        "actions": ["view", "create", "edit", "delete"],
    },
    {
        "module": "academics",
        "label": "Academics & Curriculum",
        "actions": ["view", "create", "edit", "delete"],
    },
    {
        "module": "content",
        "label": "Content Library",
        "actions": ["view", "create", "edit", "delete"],
    },
    {
        "module": "reports",
        "label": "Reports & Analytics",
        "actions": ["view"],
    },
]


async def get_dashboard_summary(db: AsyncSession) -> dict[str, Any]:
    total_schools = (
        await db.execute(select(func.count(School.id)).where(School.is_deleted.is_(False)))
    ).scalar_one()
    active_schools = (
        await db.execute(
            select(func.count(School.id)).where(
                School.is_deleted.is_(False), School.status == "ACTIVE"
            )
        )
    ).scalar_one()

    role_counts_rows = (
        await db.execute(
            select(User.user_type, func.count(User.id))
            .where(User.is_deleted.is_(False))
            .group_by(User.user_type)
        )
    ).all()
    role_counts = {r[0]: r[1] for r in role_counts_rows}

    total_users = sum(role_counts.values())
    total_teachers = role_counts.get("teacher", 0)
    total_students = role_counts.get("student", 0)
    total_school_admins = role_counts.get("school_admin", 0)
    total_content_admins = role_counts.get("content_admin", 0) + role_counts.get(
        "content_manager", 0
    )
    total_operators = role_counts.get("classroom_operator", 0) + role_counts.get(
        "class_room_operator", 0
    )

    total_classes = (
        await db.execute(
            select(func.count(AcademicClass.id)).where(AcademicClass.is_deleted.is_(False))
        )
    ).scalar_one()
    total_subjects = (
        await db.execute(select(func.count(Subject.id)).where(Subject.is_deleted.is_(False)))
    ).scalar_one()
    total_states = (
        await db.execute(select(func.count(State.id)).where(State.is_deleted.is_(False)))
    ).scalar_one()
    total_districts = (
        await db.execute(select(func.count(District.id)).where(District.is_deleted.is_(False)))
    ).scalar_one()

    return {
        "total_schools": total_schools,
        "active_schools": active_schools,
        "offline_schools": max(0, total_schools - active_schools),
        "total_users": total_users,
        "total_teachers": total_teachers,
        "total_students": total_students,
        "total_school_admins": total_school_admins,
        "total_content_admins": total_content_admins,
        "total_classroom_operators": total_operators,
        "total_classes": total_classes,
        "total_subjects": total_subjects,
        "total_states": total_states,
        "total_districts": total_districts,
        "average_sync_rate": 100 if total_schools > 0 else 0,
        "cards": {
            "schools": total_schools,
            "teachers": total_teachers,
            "students": total_students,
            "users": total_users,
        },
    }


async def get_role_permissions_matrix(db: AsyncSession) -> dict[str, Any]:
    rows = (
        await db.execute(select(RolePermission).order_by(RolePermission.created_at.asc()))
    ).scalars().all()

    roles_list = []
    role_permissions_map: dict[str, list[str]] = {}
    for r in rows:
        roles_list.append(
            {
                "id": str(r.id),
                "role_id": str(r.id),
                "name": r.role_name,
                "role_name": r.role_name,
                "label": r.label,
                "readonly": r.readonly,
                "permission_codes": list(r.permission_codes or []),
            }
        )
        role_permissions_map[r.role_name] = list(r.permission_codes or [])

    all_actions = ["view", "create", "edit", "delete"]
    modules_list = []
    for mod in PERMISSION_MODULES_DEFINITION:
        mod_key = mod["module"]
        avail_set = set(mod["actions"])
        actions_out = []
        for act in all_actions:
            is_avail = act in avail_set
            actions_out.append(
                {
                    "action": act,
                    "available": is_avail,
                    "permission_code": f"{mod_key}.{act}" if is_avail else None,
                }
            )
        modules_list.append(
            {
                "module": mod_key,
                "label": mod["label"],
                "actions": actions_out,
            }
        )

    return {
        "roles": roles_list,
        "modules": modules_list,
        "role_permissions": role_permissions_map,
    }


async def update_role_permissions(
    db: AsyncSession, role_identifier: str, payload: RolePermissionUpdateRequest
) -> dict[str, Any]:
    row = None
    try:
        parsed_uuid = uuid.UUID(role_identifier)
        row = (
            await db.execute(select(RolePermission).where(RolePermission.id == parsed_uuid))
        ).scalar_one_or_none()
    except ValueError:
        pass

    if not row:
        row = (
            await db.execute(
                select(RolePermission).where(
                    func.lower(RolePermission.role_name) == role_identifier.strip().lower()
                )
            )
        ).scalar_one_or_none()

    if not row:
        raise AppError("Role not found.", status_code=404)

    if row.readonly:
        raise AppError("This role's permissions are read-only.", status_code=400)

    codes = payload.permission_codes if payload.permission_codes else (payload.permissions or [])
    row.permission_codes = list(dict.fromkeys(codes))
    await db.commit()
    await db.refresh(row)

    return {
        "id": str(row.id),
        "name": row.role_name,
        "label": row.label,
        "readonly": row.readonly,
        "permission_codes": list(row.permission_codes or []),
    }
