# MariaDB → PostgreSQL 이관 실행을 담당
from db import (
    connect_mariadb,
    connect_postgres,
    read_tables,
    save_dataset,
)


if __name__ == "__main__":
    maria_connection = connect_mariadb()

    try:
        source_data = read_tables(maria_connection)
    finally:
        maria_connection.close()

    source_patients = source_data["patients"]
    source_admissions = source_data["admissions"]

    if not source_patients or not source_admissions:
        raise ValueError("이관할 환자 또는 입원 데이터가 없습니다.")

    print("이관 데이터 출처: MariaDB")
    print(f"조회한 환자 수: {len(source_patients)}")
    print(f"조회한 입원 수: {len(source_admissions)}")

    first_patient = source_patients[0]
    first_admission = source_admissions[0]

    print(f"첫 번째 환자: {first_patient}")
    print(f"첫 번째 입원: {first_admission}")

    print(
        "환자 ID 자료형:",
        type(first_patient["subject_id"]).__name__,
    )
    print(
        "입원 시각 자료형:",
        type(first_admission["admittime"]).__name__,
    )

    # MariaDB에서 읽은 두 테이블을 하나의 트랜잭션으로 이관
    pg_connection = connect_postgres()

    try:
        target_data = save_dataset(
            pg_connection,
            source_patients,
            source_admissions,
        )

        print("MariaDB → PostgreSQL 이관 결과 비교 통과")
        print(f"PostgreSQL 환자 수: {len(target_data['patients'])}")
        print(f"PostgreSQL 입원 수: {len(target_data['admissions'])}")

    finally:
        pg_connection.close()
        print("PostgreSQL 연결 종료")