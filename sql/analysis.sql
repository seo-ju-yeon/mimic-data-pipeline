-- 환자별 입원 횟수를 구한 뒤, 입원 횟수별 환자 수를 집계한다.
WITH patient_admission_counts AS (
    SELECT
        p.subject_id,
        COUNT(a.hadm_id) AS admission_count
    FROM patients AS p
    LEFT JOIN admissions AS a
        ON p.subject_id = a.subject_id
    GROUP BY p.subject_id
)
SELECT
    admission_count,
    COUNT(*) AS patient_count
FROM patient_admission_counts
GROUP BY admission_count
ORDER BY admission_count;