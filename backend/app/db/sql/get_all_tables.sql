-- Query information_schema to list all table names in the public schema
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public';
