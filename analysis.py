import csv
from pathlib import Path

import matplotlib.pyplot as plt

from db import connect_postgres

PROJECT_ROOT = Path(__file__).resolve().parent

SQL_PATH = PROJECT_ROOT / "sql" / "analysis.sql"
ADMISSION_TYPE_SQL_PATH = (
        PROJECT_ROOT / "sql" / "admission_type_distribution.sql"
)
REPORT_DIR = PROJECT_ROOT / "reports"
ADMISSION_TYPE_CSV_PATH = (
    REPORT_DIR / "admission_type_distribution.csv"
)
ADMISSION_TYPE_CHART_PATH = (
    REPORT_DIR / "admission_type_distribution.png"
)
OUTPUT_PATH = REPORT_DIR / "admission_count_distribution.csv"
CHART_PATH = REPORT_DIR / "admission_count_distribution.png"


def save_admission_chart(distribution, output_path):
    """입원 횟수별 환자 수를 막대그래프로 저장한다."""
    admission_counts = [
        row["admission_count"]
        for row in distribution
    ]
    patient_counts = [
        row["patient_count"]
        for row in distribution
    ]

    # fig : 제목, 축, 그래프 포함하는 그림 전체
    # ax : 데이터 그리는 영역
    fig, ax = plt.subplots(figsize=(10, 5))

    # 입원 횟수를 X축, 환자 수를 막대 높이로 표현
    bars = ax.bar(
        admission_counts,
        patient_counts,
        color="#3975B7",
        width=0.7,
    )

    ax.bar_label(bars, padding=3, fontsize=9)

    ax.set_title("Admissions per Patient — MIMIC-IV Demo 2.2")
    ax.set_xlabel("Number of admissions")
    ax.set_ylabel("Number of patients")

    ax.set_xticks(admission_counts)
    ax.set_ylim(0, max(patient_counts) * 1.15)

    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=0.25)

    fig.text(
        0.01,
        0.01,
        "Source: PhysioNet MIMIC-IV Demo 2.2 | Aggregated from PostgreSQL",
        fontsize=8,
        color="gray",
    )

    fig.tight_layout(rect=(0, 0.05, 1, 1))

    try:
        # PNG파일로 저장
        fig.savefig(output_path, dpi=160)

        # 그래프 창을 띄워 화면에서 확인
        plt.show()
    finally:
        plt.close(fig)


def save_admission_type_chart(distribution, output_path):
    """입원 유형별 입원 건수를 가로 막대그래프로 저장한다."""
    admission_types = [
        row["admission_type"]
        for row in distribution
    ]
    admission_counts = [
        row["admission_count"]
        for row in distribution
    ]

    fig, ax = plt.subplots(figsize=(12, 6))

    # 유형 이름을 세로축에, 입원 건수를 가로축에 표시
    bars = ax.barh(
        admission_types,
        admission_counts,
        color="#3975B7",
    )

    # SQL에서 건수가 많은 순서로 조회했으므로 첫 항목을 맨 위에 표시
    ax.invert_yaxis()

    ax.bar_label(bars, padding=4, fontsize=9)

    ax.set_title("Admissions by Type — MIMIC-IV Demo 2.2")
    ax.set_xlabel("Number of admissions")
    ax.set_ylabel("Admission type")

    # 막대 끝에 표시한 숫자가 잘리지 않도록 여백 확보
    ax.set_xlim(0, max(admission_counts) * 1.15)

    ax.set_axisbelow(True)
    ax.grid(axis="x", alpha=0.25)

    fig.text(
        0.01,
        0.01,
        "Source: PhysioNet MIMIC-IV Demo 2.2 | Aggregated from PostgreSQL",
        fontsize=8,
        color="gray",
    )

    fig.tight_layout(rect=(0, 0.05, 1, 1))

    try:
        fig.savefig(output_path, dpi=160)
    finally:
        plt.close(fig)


def main():
    """PostgreSQL에서 입원 횟수별 환자 수를 집계하고 CSV로 저장한다."""

    # SQL_PATH.read_text : 저장한 SQL 파일의 내용을 읽음
    query = SQL_PATH.read_text(encoding="utf-8")
    admission_type_query = ADMISSION_TYPE_SQL_PATH.read_text(
        encoding="utf-8"
    )

    connection = connect_postgres()

    try:
        with connection.cursor() as cursor:
            # 모든 조회가 같은 데이터 상태를 보도록 설정
            cursor.execute(
                # 두 조회가 같은 데이터상태를 보도록 하고, 해당 트랜잭션의 쓰기를 제한함
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
            )

            # 읽은 SQL 실행
            # 환자별 입원 횟수 분포 조회
            cursor.execute(query)
            distribution = cursor.fetchall()

            # 입원 유형별 건수 조회
            cursor.execute(admission_type_query)
            admission_type_distribution = cursor.fetchall()

            # 분석 결과와 비교할 원본 테이블의 행 수 조회
            cursor.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM patients) AS patient_count,
                    (SELECT COUNT(*) FROM admissions) AS admission_count
                """
            )
            db_counts = cursor.fetchone()

    finally:
        connection.close()

    if not distribution:
        raise ValueError("분석 결과가 없습니다.")

    total_patients = sum(
        row["patient_count"]
        for row in distribution
    )

    total_admissions = sum(
        row["admission_count"] * row["patient_count"]
        for row in distribution
    )

    if total_patients != db_counts["patient_count"]:
        raise ValueError("분포의 환자 수 합계가 DB의 환자 수와 다릅니다.")

    if total_admissions != db_counts["admission_count"]:
        raise ValueError("분포의 입원 건수 합계가 DB의 입원 건수와 다릅니다.")

    if not admission_type_distribution:
        raise ValueError("입원 유형별 분석 결과가 없습니다.")

    type_total_admissions = sum(
        row["admission_count"]
        for row in admission_type_distribution
    )

    if type_total_admissions != db_counts["admission_count"]:
        raise ValueError(
            "유형별 입원 건수 합계가 DB의 입원 건수와 다릅니다."
        )

    print("입원 유형별 분석 결과:")

    for row in admission_type_distribution:
        print(
            f"  {row['admission_type']}: "
            f"{row['admission_count']}건"
        )

    print(f"입원 유형 수: {len(admission_type_distribution)}")
    print(f"유형별 입원 건수 합계: {type_total_admissions}")
    print("입원 유형별 합계 검증 통과")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open(
            "w", encoding="utf-8", newline=""
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=["admission_count", "patient_count"],
        )
        writer.writeheader()
        writer.writerows(distribution)

    print("분석 데이터 출처: PostgreSQL")
    print(f"입원 횟수 구간 수: {len(distribution)}")
    print(f"환자 수 합계: {total_patients}")
    print(f"입원 건수 합계: {total_admissions}")
    print("분석 결과 합계 검증 통과")
    print(f"CSV 저장 완료: {OUTPUT_PATH}")

    # main() 안에서 조회한 distribution을 전달
    save_admission_chart(distribution, CHART_PATH)
    print(f"그래프 저장 완료: {CHART_PATH}")

    # 입원 유형별 분석 결과를 CSV로 저장
    with ADMISSION_TYPE_CSV_PATH.open(
            "w",
            encoding="utf-8",
            newline="",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=["admission_type", "admission_count"],
        )
        writer.writeheader()
        writer.writerows(admission_type_distribution)

    print(f"입원 유형 CSV 저장 완료: {ADMISSION_TYPE_CSV_PATH}")

    # 동일한 분석 결과를 그래프로 저장
    save_admission_type_chart(
        admission_type_distribution,
        ADMISSION_TYPE_CHART_PATH,
    )

    print(f"입원 유형 그래프 저장 완료: {ADMISSION_TYPE_CHART_PATH}")


if __name__ == "__main__":
    main()
