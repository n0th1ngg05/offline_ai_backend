-- ============================================================
-- Auth & Platform Backend — Complete Schema & Seed Init
-- Creates the `offlineai` schema, core platform tables, and
-- idempotent seed data. Safe to run repeatedly on an existing
-- `auth_backend` database.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS offlineai;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'user_status' AND n.nspname = 'offlineai'
    ) THEN
        CREATE TYPE offlineai.user_status AS ENUM ('ACTIVE', 'INACTIVE', 'DELETED');
    END IF;
END
$$;

-- ============================================================
-- 1. Users Table (offlineai.users)
-- ============================================================
CREATE TABLE IF NOT EXISTS offlineai.users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               VARCHAR(255) UNIQUE NOT NULL,
    hashed_password     TEXT NOT NULL,
    first_name          VARCHAR(100) NOT NULL,
    last_name           VARCHAR(100) NOT NULL,
    username            VARCHAR(100) UNIQUE,
    country_code        VARCHAR(10) DEFAULT '+91',
    phone_number        VARCHAR(30),
    phone               VARCHAR(30) UNIQUE,
    gender              VARCHAR(20),
    user_type           VARCHAR(50) NOT NULL,
    status              offlineai.user_status NOT NULL DEFAULT 'ACTIVE',
    is_first_login      BOOLEAN NOT NULL DEFAULT true,
    last_login_at       TIMESTAMPTZ,
    profile_picture_url TEXT,
    created_by          UUID REFERENCES offlineai.users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    deleted_by          UUID
);

-- Upgrade existing users table if created in Phase 1
ALTER TABLE offlineai.users
    ADD COLUMN IF NOT EXISTS username VARCHAR(100) UNIQUE,
    ADD COLUMN IF NOT EXISTS country_code VARCHAR(10) DEFAULT '+91',
    ADD COLUMN IF NOT EXISTS phone_number VARCHAR(30),
    ADD COLUMN IF NOT EXISTS gender VARCHAR(20);

CREATE INDEX IF NOT EXISTS idx_users_email ON offlineai.users(email);
CREATE INDEX IF NOT EXISTS idx_users_user_type ON offlineai.users(user_type);

-- ============================================================
-- 2. Location Hierarchy: States -> Districts -> ULBs -> Wards
-- ============================================================
CREATE TABLE IF NOT EXISTS offlineai.states (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(150) NOT NULL,
    code        VARCHAR(50) NOT NULL UNIQUE,
    status      VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    deleted_by  UUID
);

CREATE TABLE IF NOT EXISTS offlineai.districts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_id    UUID NOT NULL REFERENCES offlineai.states(id) ON DELETE CASCADE,
    name        VARCHAR(150) NOT NULL,
    code        VARCHAR(50) NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    deleted_by  UUID,
    UNIQUE (state_id, code)
);

CREATE TABLE IF NOT EXISTS offlineai.ulbs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    district_id UUID NOT NULL REFERENCES offlineai.districts(id) ON DELETE CASCADE,
    name        VARCHAR(150) NOT NULL,
    code        VARCHAR(50) NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    deleted_by  UUID,
    UNIQUE (district_id, code)
);

CREATE TABLE IF NOT EXISTS offlineai.wards (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ulb_id      UUID NOT NULL REFERENCES offlineai.ulbs(id) ON DELETE CASCADE,
    name        VARCHAR(150) NOT NULL,
    code        VARCHAR(50) NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    deleted_by  UUID,
    UNIQUE (ulb_id, code)
);

-- ============================================================
-- 3. Academic Hierarchy: Classes, Sections, Streams,
--    Qualifications
-- ============================================================
CREATE TABLE IF NOT EXISTS offlineai.classes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(100) NOT NULL,
    code        VARCHAR(50),
    has_streams BOOLEAN NOT NULL DEFAULT FALSE,
    status      VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    deleted_by  UUID
);

CREATE TABLE IF NOT EXISTS offlineai.sections (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id    UUID REFERENCES offlineai.classes(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    code        VARCHAR(50),
    status      VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    deleted_by  UUID
);

CREATE TABLE IF NOT EXISTS offlineai.streams (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id    UUID REFERENCES offlineai.classes(id) ON DELETE SET NULL,
    name        VARCHAR(100) NOT NULL,
    code        VARCHAR(50) NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    deleted_by  UUID
);

CREATE TABLE IF NOT EXISTS offlineai.qualifications (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(150) NOT NULL UNIQUE,
    code        VARCHAR(50),
    status      VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    deleted_by  UUID
);

-- ============================================================
-- 4. Schools & School-Class-Section Mappings
-- ============================================================
CREATE TABLE IF NOT EXISTS offlineai.schools (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         VARCHAR(255) NOT NULL,
    udise_code   VARCHAR(100) NOT NULL UNIQUE,
    country_code VARCHAR(10) DEFAULT '+91',
    phone        VARCHAR(30),
    state_id     UUID REFERENCES offlineai.states(id) ON DELETE RESTRICT,
    district_id  UUID REFERENCES offlineai.districts(id) ON DELETE RESTRICT,
    ulb_id       UUID REFERENCES offlineai.ulbs(id) ON DELETE SET NULL,
    ward_id      UUID REFERENCES offlineai.wards(id) ON DELETE SET NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at   TIMESTAMPTZ,
    deleted_by   UUID
);

CREATE TABLE IF NOT EXISTS offlineai.school_class_sections (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id    UUID NOT NULL REFERENCES offlineai.schools(id) ON DELETE CASCADE,
    class_id     UUID NOT NULL REFERENCES offlineai.classes(id) ON DELETE CASCADE,
    section_id   UUID NOT NULL REFERENCES offlineai.sections(id) ON DELETE CASCADE,
    custom_name  VARCHAR(100),
    custom_code  VARCHAR(50),
    status       VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at   TIMESTAMPTZ,
    deleted_by   UUID,
    UNIQUE (school_id, class_id, section_id)
);

-- ============================================================
-- 5. Subjects, Subject-Sections, Chapters, Topics
-- ============================================================
CREATE TABLE IF NOT EXISTS offlineai.subjects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(150) NOT NULL,
    code        VARCHAR(50),
    class_id    UUID REFERENCES offlineai.classes(id) ON DELETE CASCADE,
    school_id   UUID REFERENCES offlineai.schools(id) ON DELETE CASCADE,
    status      VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    deleted_by  UUID
);

CREATE TABLE IF NOT EXISTS offlineai.subject_sections (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id  UUID NOT NULL REFERENCES offlineai.subjects(id) ON DELETE CASCADE,
    section_id  UUID NOT NULL REFERENCES offlineai.sections(id) ON DELETE CASCADE,
    UNIQUE (subject_id, section_id)
);

CREATE TABLE IF NOT EXISTS offlineai.chapters (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id  UUID NOT NULL REFERENCES offlineai.subjects(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    code        VARCHAR(50),
    status      VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    deleted_by  UUID
);

CREATE TABLE IF NOT EXISTS offlineai.topics (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id  UUID NOT NULL REFERENCES offlineai.chapters(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    code        VARCHAR(50),
    status      VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    deleted_by  UUID
);

-- ============================================================
-- 6. User-School & Role-Specific Assignments (School Admin,
--    Teacher, Classroom Operator, Student)
-- ============================================================
CREATE TABLE IF NOT EXISTS offlineai.user_schools (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES offlineai.users(id) ON DELETE CASCADE,
    school_id   UUID NOT NULL REFERENCES offlineai.schools(id) ON DELETE CASCADE,
    role        VARCHAR(50) NOT NULL DEFAULT 'school_admin',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    deleted_by  UUID,
    UNIQUE (user_id, school_id)
);

CREATE TABLE IF NOT EXISTS offlineai.teacher_qualifications (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id       UUID NOT NULL REFERENCES offlineai.users(id) ON DELETE CASCADE,
    qualification_id UUID NOT NULL REFERENCES offlineai.qualifications(id) ON DELETE CASCADE,
    UNIQUE (teacher_id, qualification_id)
);

CREATE TABLE IF NOT EXISTS offlineai.teacher_assignments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id  UUID NOT NULL REFERENCES offlineai.users(id) ON DELETE CASCADE,
    school_id   UUID NOT NULL REFERENCES offlineai.schools(id) ON DELETE CASCADE,
    class_id    UUID NOT NULL REFERENCES offlineai.classes(id) ON DELETE CASCADE,
    subject_id  UUID NOT NULL REFERENCES offlineai.subjects(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    deleted_by  UUID,
    UNIQUE (teacher_id, school_id, class_id, subject_id)
);

CREATE TABLE IF NOT EXISTS offlineai.classroom_operator_assignments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES offlineai.users(id) ON DELETE CASCADE,
    school_id   UUID NOT NULL REFERENCES offlineai.schools(id) ON DELETE CASCADE,
    class_id    UUID NOT NULL REFERENCES offlineai.classes(id) ON DELETE CASCADE,
    section_id  UUID NOT NULL REFERENCES offlineai.sections(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    deleted_by  UUID,
    UNIQUE (operator_id, school_id, class_id, section_id)
);

CREATE TABLE IF NOT EXISTS offlineai.student_profiles (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               UUID NOT NULL UNIQUE REFERENCES offlineai.users(id) ON DELETE CASCADE,
    school_id             UUID NOT NULL REFERENCES offlineai.schools(id) ON DELETE CASCADE,
    class_id              UUID NOT NULL REFERENCES offlineai.classes(id) ON DELETE RESTRICT,
    section_id            UUID NOT NULL REFERENCES offlineai.sections(id) ON DELETE RESTRICT,
    roll_number           VARCHAR(50),
    academic_year         VARCHAR(20),
    gender                VARCHAR(20),
    dob                   DATE,
    guardian_first_name   VARCHAR(100),
    guardian_last_name    VARCHAR(100),
    guardian_email        VARCHAR(255),
    guardian_country_code VARCHAR(10) DEFAULT '+91',
    guardian_phone        VARCHAR(30),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at            TIMESTAMPTZ,
    deleted_by            UUID
);

-- ============================================================
-- 7. Role Permissions Matrix
-- ============================================================
CREATE TABLE IF NOT EXISTS offlineai.role_permissions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_name        VARCHAR(50) NOT NULL UNIQUE,
    label            VARCHAR(100) NOT NULL,
    readonly         BOOLEAN NOT NULL DEFAULT FALSE,
    permission_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 8. Seeds (Idempotent)
-- ============================================================

-- 8.1 Seed Super Admin
INSERT INTO offlineai.users
    (email, hashed_password, first_name, last_name, user_type, status, is_first_login)
VALUES
    (
        'humza.ahmad050504@gmail.com',
        '$2b$12$byYye4WTpLP6usKuvYRCCO/n0hJ2LTBTAzkzAEsqfyxdTIBRkWmSe',
        'Humza',
        'Ahmad',
        'super_admin',
        'ACTIVE',
        false
    )
ON CONFLICT (email) DO NOTHING;

-- 8.2 Seed States, Districts, ULBs, Wards
INSERT INTO offlineai.states (id, name, code, status) VALUES
    ('11111111-1111-4111-8111-111111111101', 'Manipur', 'MN', 'ACTIVE'),
    ('11111111-1111-4111-8111-111111111102', 'Assam', 'AS', 'ACTIVE'),
    ('11111111-1111-4111-8111-111111111103', 'West Bengal', 'WB', 'ACTIVE'),
    ('11111111-1111-4111-8111-111111111104', 'Delhi', 'DL', 'ACTIVE'),
    ('11111111-1111-4111-8111-111111111105', 'Maharashtra', 'MH', 'ACTIVE')
ON CONFLICT (code) DO NOTHING;

INSERT INTO offlineai.districts (id, state_id, name, code, status) VALUES
    ('22222222-2222-4222-8222-222222222201', '11111111-1111-4111-8111-111111111101', 'Imphal West', 'MN-IW', 'ACTIVE'),
    ('22222222-2222-4222-8222-222222222202', '11111111-1111-4111-8111-111111111101', 'Imphal East', 'MN-IE', 'ACTIVE'),
    ('22222222-2222-4222-8222-222222222203', '11111111-1111-4111-8111-111111111101', 'Thoubal', 'MN-TH', 'ACTIVE'),
    ('22222222-2222-4222-8222-222222222204', '11111111-1111-4111-8111-111111111102', 'Kamrup Metropolitan', 'AS-KM', 'ACTIVE'),
    ('22222222-2222-4222-8222-222222222205', '11111111-1111-4111-8111-111111111103', 'Kolkata', 'WB-KO', 'ACTIVE'),
    ('22222222-2222-4222-8222-222222222206', '11111111-1111-4111-8111-111111111104', 'New Delhi', 'DL-ND', 'ACTIVE'),
    ('22222222-2222-4222-8222-222222222207', '11111111-1111-4111-8111-111111111105', 'Mumbai Suburban', 'MH-MS', 'ACTIVE')
ON CONFLICT (state_id, code) DO NOTHING;

INSERT INTO offlineai.ulbs (id, district_id, name, code, status) VALUES
    ('33333333-3333-4333-8333-333333333301', '22222222-2222-4222-8222-222222222201', 'Imphal Municipal Corporation', 'IMC', 'ACTIVE'),
    ('33333333-3333-4333-8333-333333333302', '22222222-2222-4222-8222-222222222202', 'Porompat Municipal Council', 'PMC', 'ACTIVE'),
    ('33333333-3333-4333-8333-333333333303', '22222222-2222-4222-8222-222222222204', 'Guwahati Municipal Corporation', 'GMC', 'ACTIVE'),
    ('33333333-3333-4333-8333-333333333304', '22222222-2222-4222-8222-222222222205', 'Kolkata Municipal Corporation', 'KMC', 'ACTIVE')
ON CONFLICT (district_id, code) DO NOTHING;

INSERT INTO offlineai.wards (id, ulb_id, name, code, status) VALUES
    ('44444444-4444-4444-8444-444444444401', '33333333-3333-4333-8333-333333333301', 'Ward 1', 'W-01', 'ACTIVE'),
    ('44444444-4444-4444-8444-444444444402', '33333333-3333-4333-8333-333333333301', 'Ward 2', 'W-02', 'ACTIVE'),
    ('44444444-4444-4444-8444-444444444403', '33333333-3333-4333-8333-333333333302', 'Ward 1', 'PMC-W1', 'ACTIVE'),
    ('44444444-4444-4444-8444-444444444404', '33333333-3333-4333-8333-333333333303', 'Ward 1', 'GMC-W1', 'ACTIVE'),
    ('44444444-4444-4444-8444-444444444405', '33333333-3333-4333-8333-333333333304', 'Ward 1', 'KMC-W1', 'ACTIVE')
ON CONFLICT (ulb_id, code) DO NOTHING;

-- 8.3 Seed Qualifications
INSERT INTO offlineai.qualifications (id, name, code, status) VALUES
    ('55555555-5555-4555-8555-555555555501', 'B.Ed', 'BED', 'ACTIVE'),
    ('55555555-5555-4555-8555-555555555502', 'M.Ed', 'MED', 'ACTIVE'),
    ('55555555-5555-4555-8555-555555555503', 'B.Sc', 'BSC', 'ACTIVE'),
    ('55555555-5555-4555-8555-555555555504', 'M.Sc', 'MSC', 'ACTIVE'),
    ('55555555-5555-4555-8555-555555555505', 'B.A', 'BA', 'ACTIVE'),
    ('55555555-5555-4555-8555-555555555506', 'M.A', 'MA', 'ACTIVE'),
    ('55555555-5555-4555-8555-555555555507', 'D.El.Ed', 'DELED', 'ACTIVE'),
    ('55555555-5555-4555-8555-555555555508', 'Ph.D', 'PHD', 'ACTIVE')
ON CONFLICT (name) DO NOTHING;

-- 8.4 Seed Default Classes & Sections (Class 6 to Class 10)
INSERT INTO offlineai.classes (id, name, code, has_streams, status) VALUES
    ('66666666-6666-4666-8666-666666666606', 'Class 6', 'CLS-6', FALSE, 'ACTIVE'),
    ('66666666-6666-4666-8666-666666666607', 'Class 7', 'CLS-7', FALSE, 'ACTIVE'),
    ('66666666-6666-4666-8666-666666666608', 'Class 8', 'CLS-8', FALSE, 'ACTIVE'),
    ('66666666-6666-4666-8666-666666666609', 'Class 9', 'CLS-9', FALSE, 'ACTIVE'),
    ('66666666-6666-4666-8666-666666666610', 'Class 10', 'CLS-10', FALSE, 'ACTIVE')
ON CONFLICT (id) DO NOTHING;

INSERT INTO offlineai.sections (id, class_id, name, code, status) VALUES
    ('77777777-7777-4777-8777-777777770601', '66666666-6666-4666-8666-666666666606', 'Section A', 'SEC-A', 'ACTIVE'),
    ('77777777-7777-4777-8777-777777770602', '66666666-6666-4666-8666-666666666606', 'Section B', 'SEC-B', 'ACTIVE'),
    ('77777777-7777-4777-8777-777777770701', '66666666-6666-4666-8666-666666666607', 'Section A', 'SEC-A', 'ACTIVE'),
    ('77777777-7777-4777-8777-777777770702', '66666666-6666-4666-8666-666666666607', 'Section B', 'SEC-B', 'ACTIVE'),
    ('77777777-7777-4777-8777-777777770801', '66666666-6666-4666-8666-666666666608', 'Section A', 'SEC-A', 'ACTIVE'),
    ('77777777-7777-4777-8777-777777770802', '66666666-6666-4666-8666-666666666608', 'Section B', 'SEC-B', 'ACTIVE'),
    ('77777777-7777-4777-8777-777777770901', '66666666-6666-4666-8666-666666666609', 'Section A', 'SEC-A', 'ACTIVE'),
    ('77777777-7777-4777-8777-777777770902', '66666666-6666-4666-8666-666666666609', 'Section B', 'SEC-B', 'ACTIVE'),
    ('77777777-7777-4777-8777-777777771001', '66666666-6666-4666-8666-666666666610', 'Section A', 'SEC-A', 'ACTIVE'),
    ('77777777-7777-4777-8777-777777771002', '66666666-6666-4666-8666-666666666610', 'Section B', 'SEC-B', 'ACTIVE')
ON CONFLICT (id) DO NOTHING;

-- 8.5 Seed Default Subjects for Class 6-10
INSERT INTO offlineai.subjects (id, name, code, class_id, status) VALUES
    ('88888888-8888-4888-8888-888888880601', 'Mathematics', 'MATH-6', '66666666-6666-4666-8666-666666666606', 'ACTIVE'),
    ('88888888-8888-4888-8888-888888880602', 'Science', 'SCI-6', '66666666-6666-4666-8666-666666666606', 'ACTIVE'),
    ('88888888-8888-4888-8888-888888880701', 'Mathematics', 'MATH-7', '66666666-6666-4666-8666-666666666607', 'ACTIVE'),
    ('88888888-8888-4888-8888-888888880702', 'Science', 'SCI-7', '66666666-6666-4666-8666-666666666607', 'ACTIVE'),
    ('88888888-8888-4888-8888-888888880801', 'Mathematics', 'MATH-8', '66666666-6666-4666-8666-666666666608', 'ACTIVE'),
    ('88888888-8888-4888-8888-888888880802', 'Science', 'SCI-8', '66666666-6666-4666-8666-666666666608', 'ACTIVE'),
    ('88888888-8888-4888-8888-888888880901', 'Mathematics', 'MATH-9', '66666666-6666-4666-8666-666666666609', 'ACTIVE'),
    ('88888888-8888-4888-8888-888888880902', 'Science', 'SCI-9', '66666666-6666-4666-8666-666666666609', 'ACTIVE'),
    ('88888888-8888-4888-8888-888888881001', 'Mathematics', 'MATH-10', '66666666-6666-4666-8666-666666666610', 'ACTIVE'),
    ('88888888-8888-4888-8888-888888881002', 'Science', 'SCI-10', '66666666-6666-4666-8666-666666666610', 'ACTIVE')
ON CONFLICT (id) DO NOTHING;

-- 8.6 Seed Role Permissions Matrix
INSERT INTO offlineai.role_permissions (id, role_name, label, readonly, permission_codes) VALUES
    (
        '99999999-9999-4999-8999-999999999901',
        'SUPER_ADMIN',
        'Super Admin',
        TRUE,
        '["dashboard.view_system","dashboard.view_school","user.manage_school","permission.assign","student.view","student.edit","student.manage","teacher.view","teacher.edit","teacher.manage","school.create","school.map_admin","content.upload","content.approve","content.publish","academic.manage","academic.class.manage","academic.class.view","academic.subject.manage","academic.subject.view","quiz.generate","assistant.ask","copilot.generate","sync.view","sync.trigger"]'::jsonb
    ),
    (
        '99999999-9999-4999-8999-999999999902',
        'SCHOOL_ADMIN',
        'School Admin',
        FALSE,
        '["dashboard.view_school","user.manage_school","student.view","student.edit","student.manage","teacher.view","teacher.edit","teacher.manage","content.approve","academic.class.manage","academic.class.view","academic.subject.manage","academic.subject.view","quiz.generate","assistant.ask","copilot.generate","sync.view"]'::jsonb
    ),
    (
        '99999999-9999-4999-8999-999999999903',
        'CONTENT_ADMIN',
        'Content Admin',
        FALSE,
        '["dashboard.view_system","content.upload","content.approve","content.publish","academic.manage","academic.class.manage","academic.class.view","academic.subject.manage","academic.subject.view","quiz.generate","assistant.ask","copilot.generate"]'::jsonb
    ),
    (
        '99999999-9999-4999-8999-999999999904',
        'TEACHER',
        'Teacher',
        FALSE,
        '["dashboard.view_school","student.view","academic.class.view","academic.subject.view","quiz.generate","assistant.ask","copilot.generate"]'::jsonb
    ),
    (
        '99999999-9999-4999-8999-999999999905',
        'CLASSROOM_OPERATOR',
        'Classroom Operator',
        FALSE,
        '["dashboard.view_school","student.view","academic.class.view","academic.subject.view","assistant.ask"]'::jsonb
    ),
    (
        '99999999-9999-4999-8999-999999999906',
        'STUDENT',
        'Student',
        FALSE,
        '["assistant.ask"]'::jsonb
    )
ON CONFLICT (role_name) DO NOTHING;
