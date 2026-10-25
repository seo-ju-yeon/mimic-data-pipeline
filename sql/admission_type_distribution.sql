-- 입원 유형별 입원 건수를 집계한다.
SELECT
    admission_type,
    COUNT(*) AS admission_count
FROM admissions
GROUP BY admission_type
ORDER BY admission_count DESC, admission_type ASC;