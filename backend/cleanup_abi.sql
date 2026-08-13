-- ==============================================================================
-- cleanup_abi.sql — Standalone Database Cleanup & Reset Script for AgentCampus
--
-- DO NOT EXECUTE AUTOMATICALLY. FOR MANUAL REVIEW / EXECUTION ONLY.
-- Resets database to clean baseline:
-- 1. Protects baseline tables (students, courses, history).
-- 2. Drops leftover dynamic test tables created during test runs.
-- 3. Deletes test/junk rows inserted into students and courses during test runs.
-- 4. Removes test-related history audit log entries.
-- ==============================================================================

BEGIN;

-- 1. Drop leftover dynamic test tables created during test runs
DROP TABLE IF EXISTS public."enrollments" CASCADE;
DROP TABLE IF EXISTS public."libraryBookLoans" CASCADE;
DROP TABLE IF EXISTS public."bookLoans" CASCADE;
DROP TABLE IF EXISTS public._exec_sql_patch CASCADE;

-- Drop any leftover test tables matching test patterns
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public' 
          AND (tablename LIKE 'testdrop%' OR tablename LIKE 'testDrop%' OR tablename LIKE 'testloans%' OR tablename LIKE 'testLoans%')
    ) LOOP
        EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE;';
    END LOOP;
END $$;

-- 2. Clean up test/junk rows from students table inserted during test suite runs
DELETE FROM public.students
WHERE id LIKE 'STU-ABI-%'
   OR id LIKE 'STU-FULL-%'
   OR id LIKE 'STU-BUG1-%'
   OR id LIKE 'STU-DIRECT-%'
   OR id LIKE 'STU-FIELD-%'
   OR id LIKE 'STU-COLS-%'
   OR id LIKE 'STU-TRIG-%'
   OR email LIKE 'grace.%@campus.edu'
   OR email LIKE 'ada.%@campus.edu'
   OR email LIKE '%.campus.edu';

-- 3. Clean up test/junk rows from courses table inserted during test suite runs
DELETE FROM public.courses
WHERE id LIKE 'CRS-ABI-%'
   OR id LIKE 'CRS-FULL-%'
   OR id LIKE 'CRS-TEST-%'
   OR courseCode LIKE 'CS-B05-%'
   OR courseCode LIKE 'CS-B06-%'
   OR courseCode LIKE 'CS-B07-%'
   OR courseCode LIKE 'CS-B08-%'
   OR courseCode LIKE 'CS-D01-%'
   OR courseCode LIKE 'CS-F05-%'
   OR courseCode LIKE 'CS-G09-%'
   OR courseCode LIKE 'TC777%';

-- 4. Clean up test-related audit entries from history table
DELETE FROM public.history
WHERE "rowId" LIKE 'STU-ABI-%'
   OR "rowId" LIKE 'STU-FULL-%'
   OR "rowId" LIKE 'CRS-ABI-%'
   OR "rowId" LIKE 'CRS-FULL-%'
   OR "rowId" LIKE 'ENR-ABI-%'
   OR "originalTable" IN ('enrollments', 'libraryBookLoans', 'bookLoans')
   OR "original_table" IN ('enrollments', 'libraryBookLoans', 'bookLoans');

COMMIT;
