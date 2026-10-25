# 실패 시 롤백 동작을 실행하는 파일

# CheckViolation : PostgreSQL 드라이버가 전달하는 CHECK 제약조건 위반 예외
from psycopg.errors import CheckViolation
from pymysql.err import MySQLError

from db import (
    connect_mariadb,
    connect_postgres,
    read_tables,
    save_dataset,
)


def test_postgres_rollback():
    """입원 저장 실패 시 같은 트랜잭션의 환자 INSERT도 취소되는지 검사한다."""
    connection = connect_postgres()

    try:
        # 임시 테이블을 만들기 전에 기존 데이터에서 테스트 입력을 읽음
        source_data = read_tables(connection)

        if not source_data["patients"] or not source_data["admissions"]:
            raise ValueError("테스트 입력으로 사용할 데이터가 없습니다.")

        # 입원 행을 복사한 뒤 첫 행의 사망 표시만 잘못된 값으로 바꿈
        invalid_admissions = [
            dict(row) for row in source_data["admissions"]
        ]
        invalid_admissions[0]["hospital_expire_flag"] = 2

        with connection.cursor() as cursor:
            # 열, NOT NULL, CHECK, 기본키 및 인덱스를 복사함
            # 데이터는 복사하지 않음
            cursor.execute(
                """
                CREATE TEMP TABLE patients
                (LIKE public.patients INCLUDING ALL)
                ON COMMIT PRESERVE ROWS
                """
            )

            cursor.execute(
                """
                CREATE TEMP TABLE admissions
                (LIKE public.admissions INCLUDING ALL)
                ON COMMIT PRESERVE ROWS
                """
            )

            # LIKE는 외래키를 복사하지 않으므로 별도로 연결해줌
            cursor.execute(
                """
                ALTER TABLE pg_temp.admissions
                ADD CONSTRAINT fk_test_admissions_patient
                FOREIGN KEY (subject_id)
                REFERENCES pg_temp.patients(subject_id)
                """
            )

            cursor.execute("SET search_path TO pg_temp, public")

        # 테스트 준비를 확정함
        # 이후 롤백해도 빈 임시 테이블 자체는 남아 있어야 함
        connection.commit()

        before_data = read_tables(connection)

        if before_data != {"patients": [], "admissions": []}:
            raise AssertionError("테스트 시작 시 임시 테이블이 비어 있지 않습니다.")

        try:
            save_dataset(
                connection,
                source_data["patients"],
                invalid_admissions,
            )

        except CheckViolation as error:
            if error.diag.constraint_name != "ck_hospital_expire_flag":
                raise AssertionError("예상과 다른 CHECK 제약조건 위반입니다.") from error

            print("예상한 실패 확인: hospital_expire_flag=2 저장 거부")

        else:
            raise AssertionError("잘못된 사망 표시가 거부되지 않았습니다.")

        # 여기서 직접 rollback()하지 않음
        # save_dataset()이 수행한 롤백 결과를 검사해야 함
        after_data = read_tables(connection)

        patient_count = len(after_data["patients"])
        admission_count = len(after_data["admissions"])

        print(f"롤백 후 임시 환자 테이블: {patient_count}행")
        print(f"롤백 후 임시 입원 테이블: {admission_count}행")

        if patient_count != 0 or admission_count != 0:
            raise AssertionError("실패한 트랜잭션의 데이터가 남아 있습니다.")

        print("PostgreSQL 두 테이블 롤백 검증 통과")

    finally:
        connection.close()
        print("테스트 연결 종료: 임시 테이블 자동 제거")


def test_mariadb_rollback():
    """입원 저장 실패 시 MariaDB의 환자 INSERT도 취소되는지 검사한다."""
    connection = connect_mariadb()

    try:
        # 기존 테이블에서 테스트 입력을 읽음
        source_data = read_tables(connection)

        if not source_data["patients"] or not source_data["admissions"]:
            raise ValueError("테스트 입력으로 사용할 데이터가 없습니다.")

        # 메모리의 복사본에서 첫 번째 입원 행만 잘못된 값으로 변경함
        invalid_admissions = [
            dict(row) for row in source_data["admissions"]
        ]
        invalid_admissions[0]["hospital_expire_flag"] = 2

        with connection.cursor() as cursor:
            # 1. 기존 테이블의 구조를 다른 이름의 임시 테이블로 복사함
            cursor.execute(
                """
                CREATE TEMPORARY TABLE rollback_patients_template
                LIKE patients
                """
            )
            cursor.execute(
                """
                CREATE TEMPORARY TABLE rollback_admissions_template
                LIKE admissions
                """
            )

            # 2. 복사본을 이용해 저장 함수가 사용할 이름으로 만듦
            cursor.execute(
                """
                CREATE TEMPORARY TABLE patients
                LIKE rollback_patients_template
                """
            )
            cursor.execute(
                """
                CREATE TEMPORARY TABLE admissions
                LIKE rollback_admissions_template
                """
            )

            # 테스트에 필요한 CHECK 제약조건이 복사됐는지 확인함
            cursor.execute("SHOW CREATE TABLE admissions")
            create_sql = cursor.fetchone()["Create Table"]

            if "ck_hospital_expire_flag" not in create_sql:
                raise AssertionError("임시 테이블에 필요한 CHECK가 없습니다.")

        # 준비 단계와 실제 저장 테스트의 트랜잭션을 구분함
        connection.commit()

        before_data = read_tables(connection)

        if before_data != {"patients": [], "admissions": []}:
            raise AssertionError("테스트 시작 시 임시 테이블이 비어 있지 않습니다.")

        try:
            save_dataset(
                connection,
                source_data["patients"],
                invalid_admissions,
            )

        except MySQLError as error:
            error_code = error.args[0]
            error_message = str(error)

            # MariaDB의 4025 : CHECK 제약조건 위반 오류
            if (
                    error_code != 4025
                    or "ck_hospital_expire_flag" not in error_message
            ):
                raise AssertionError("예상과 다른 DB 오류입니다.") from error

            print("예상한 실패 확인: hospital_expire_flag=2 저장 거부")

        else:
            raise AssertionError("잘못된 사망 표시가 거부되지 않았습니다.")

        # 테스트가 대신 롤백하지 않고 save_dataset의 처리 결과를 확인함
        after_data = read_tables(connection)

        patient_count = len(after_data["patients"])
        admission_count = len(after_data["admissions"])

        print(f"롤백 후 임시 환자 테이블: {patient_count}행")
        print(f"롤백 후 임시 입원 테이블: {admission_count}행")

        if patient_count != 0 or admission_count != 0:
            raise AssertionError("실패한 트랜잭션의 데이터가 남아 있습니다.")

        print("MariaDB 두 테이블 롤백 검증 통과")

    finally:
        connection.close()
        print("MariaDB 테스트 연결 종료: 임시 테이블 자동 제거")


if __name__ == "__main__":
    print("PostgreSQL 롤백 검사 시작")
    test_postgres_rollback()

    print("MariaDB 롤백 검사 시작")
    test_mariadb_rollback()
