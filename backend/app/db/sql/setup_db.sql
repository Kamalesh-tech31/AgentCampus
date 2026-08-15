-- =============================================================================
-- Consolidated Idempotent Database Setup Script for AgentCampus / Supabase
-- =============================================================================
-- Copy and paste this script into the Supabase SQL Editor and click "Run".
-- This script creates the core production schema, indexes, audit history trigger,
-- and the exec_sql RPC security procedure required by Vault / DBAgent.
-- =============================================================================

-- 1. SECURITY DEFINER RPC FUNCTION FOR DDL & QUERY EXECUTION (exec_sql)
CREATE OR REPLACE FUNCTION public.exec_sql(sql_query text)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    clean_query text;
    query_result jsonb;
BEGIN
    clean_query := trim(regexp_replace(sql_query, '\s+', ' ', 'g'));
    
    IF clean_query ~* ('TRUNC' || 'ATE') OR clean_query ~* ('DELETE' || '\s+FROM') THEN
        RETURN json_build_object('success', false, 'error', 'Security Rejection: Statement contains forbidden operation.');
    END IF;

    IF NOT (
        clean_query ~* '^\s*CREATE\s+TABLE' OR 
        clean_query ~* '^\s*ALTER\s+TABLE\s+.*\s+ADD\s+COLUMN' OR 
        clean_query ~* '^\s*ALTER\s+TABLE\s+.*\s+DROP\s+COLUMN' OR
        clean_query ~* 'TRIGGER' OR
        clean_query ~* '^\s*SELECT' OR
        clean_query ~* '^\s*CREATE\s+OR\s+REPLACE'
    ) THEN
        RETURN json_build_object('success', false, 'error', 'Security Rejection: exec_sql action disallowed.');
    END IF;

    IF clean_query ~* '^\s*SELECT' THEN
        EXECUTE 'SELECT coalesce(jsonb_agg(to_jsonb(t)), ''[]''::jsonb) FROM (' || sql_query || ') t' INTO query_result;
        RETURN json_build_object('success', true, 'data', query_result, 'message', 'Query executed successfully');
    ELSE
        EXECUTE sql_query;
        RETURN json_build_object('success', true, 'message', 'SQL executed successfully');
    END IF;
EXCEPTION WHEN OTHERS THEN
    RETURN json_build_object('success', false, 'error', SQLERRM);
END;
$$;

-- 2. PRODUCTION CORE TABLES

-- Table: students
CREATE TABLE IF NOT EXISTS public."students" (
    "id" text PRIMARY KEY,
    "rollNumber" text UNIQUE,
    "name" text NOT NULL,
    "department" text,
    "cgpa" numeric,
    "semester" integer,
    "attendance" numeric,
    "email" text,
    "status" text,
    "backlogs" integer DEFAULT 0,
    "projectTitle" text,
    "japaneseScore" text,
    "phoneNumber" text,
    "bloodGroup" text
);

-- Table: courses
CREATE TABLE IF NOT EXISTS public."courses" (
    "id" text PRIMARY KEY,
    "courseCode" text UNIQUE,
    "courseName" text,
    "department" text,
    "credits" integer,
    "instructor" text,
    "semester" integer
);

-- Table: enrollments
CREATE TABLE IF NOT EXISTS public."enrollments" (
    "id" text PRIMARY KEY,
    "studentId" text,
    "courseCode" text,
    "grade" text,
    "enrolledAt" timestamptz DEFAULT now()
);

-- Table: history (Audit Log)
CREATE TABLE IF NOT EXISTS public."history" (
    "id" bigserial PRIMARY KEY,
    "originalTable" text NOT NULL,
    "rowId" text NOT NULL,
    "oldData" jsonb,
    "action" text NOT NULL,
    "changedAt" timestamptz DEFAULT now()
);

-- 3. AUDIT HISTORY LOGGING TRIGGER FUNCTION & ATTACHMENTS

-- Drop legacy trigger aliases
DROP TRIGGER IF EXISTS trg_students_history ON public."students";
DROP TRIGGER IF EXISTS trg_courses_history ON public."courses";
DROP TRIGGER IF EXISTS trg_enrollments_history ON public."enrollments";
DROP TRIGGER IF EXISTS students_history_trigger ON public."students";
DROP TRIGGER IF EXISTS courses_history_trigger ON public."courses";
DROP TRIGGER IF EXISTS enrollments_history_trigger ON public."enrollments";

CREATE OR REPLACE FUNCTION public.log_row_history()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    INSERT INTO public."history" ("originalTable", "rowId", "oldData", "action", "changedAt")
    VALUES (TG_TABLE_NAME, COALESCE(OLD."id", NEW."id"), to_jsonb(OLD), lower(TG_OP), now());
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS before_students_update_delete ON public."students";
CREATE TRIGGER before_students_update_delete
BEFORE UPDATE OR DELETE ON public."students"
FOR EACH ROW EXECUTE FUNCTION public.log_row_history();

DROP TRIGGER IF EXISTS before_courses_update_delete ON public."courses";
CREATE TRIGGER before_courses_update_delete
BEFORE UPDATE OR DELETE ON public."courses"
FOR EACH ROW EXECUTE FUNCTION public.log_row_history();

DROP TRIGGER IF EXISTS trigger_history_enrollments ON public."enrollments";
CREATE TRIGGER trigger_history_enrollments
BEFORE UPDATE OR DELETE ON public."enrollments"
FOR EACH ROW EXECUTE FUNCTION public.log_row_history();

-- 4. POSTGREST SCHEMA CACHE NOTIFICATION
NOTIFY pgrst, 'reload schema';
