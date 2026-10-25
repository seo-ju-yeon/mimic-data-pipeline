# 실패 시 롤백 동작을 실행하는 파일

# CheckViolation : PostgreSQL 드라이버가 전달하는 CHECK 제약조건 위반 예외
from psycopg.errors import CheckViolation

from db import connect_postgres, read_tables, save_dataset


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


if __name__ == "__main__":
    test_postgres_rollback()