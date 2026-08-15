-- Legacy SQL query template for student selection with filters, sorting, and limit
-- Replace filter conditions, sort field, direction, and LIMIT values before running in Supabase SQL Editor
SELECT *
FROM students
WHERE department = 'Computer Science'
  AND cgpa >= 8.5
ORDER BY cgpa DESC
LIMIT 100;
