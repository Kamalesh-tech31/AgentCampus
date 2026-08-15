-- Query information_schema to discover column names and data types for a table
-- Replace 'students' with your target table name before running in Supabase SQL Editor
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'students';
