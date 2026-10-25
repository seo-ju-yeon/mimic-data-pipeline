# DB 연결 코드를 모음
import os
from pathlib import Path

# pymysql : Python용 MariaDB 드라이버
# load_dotenv : .env 읽어 환경변수로 설정
import pymysql
from dotenv import load_dotenv

# psycopg : Python용 PostgreSQL 드라이버
import psycopg
from psycopg.rows import dict_row

PROJECT_ROOT = Path(__file__).resolve().parent


def connect_mariadb():
    """프로젝트의 설정을 읽어 MariaDB 연결을 반환한다."""
    load_dotenv(PROJECT_ROOT / ".env")

    password = os.environ.get("PIPELINE_MARIA_PASSWORD")

    if not password:
        raise ValueError("PIPELINE_MARIA_PASSWORD 설정이 필요합니다.")

    return pymysql.connect(
        host="127.0.0.1",
        port=13306,
        user="mimic",
        password=password,
        database="mimic_pipeline",
        charset="utf8mb4",
        # 조회 결과를 딕셔너리로 받음
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=10,
    )


def connect_postgres():
    """프로젝트의 설정을 읽어 PostgreSQL 연결을 반환한다."""
    load_dotenv(PROJECT_ROOT / ".env")

    password = os.environ.get("PIPELINE_PG_PASSWORD")

    if not password:
        raise ValueError("PIPELINE_PG_PASSWORD 설정이 필요합니다.")

    return psycopg.connect(
        host="127.0.0.1",
        port=15432,
        user="mimic",
        password=password,
        dbname="mimic_pipeline",
        # 딕셔너리 반환 설정
        row_factory=dict_row,
        autocommit=False,
        connect_timeout=10,
        options="-c search_path=public",
    )

def save_patients(connection, patients):
    """환자를 저장하고 조회 결과가 입력과 일치할 때만 커밋한다."""
    if not patients:
        raise ValueError("저장할 환자 데이터가 없습니다.")

    expected_rows = sorted(
        patients,
        key=lambda patient: patient["subject_id"],
    )

    select_sql = """
        SELECT
            subject_id, gender, anchor_age,
            anchor_year, anchor_year_group, dod
        FROM patients
        ORDER BY subject_id
    """

    insert_sql = """
        INSERT INTO patients (
            subject_id, gender, anchor_age,
            anchor_year, anchor_year_group, dod
        )
        VALUES (
            %(subject_id)s, %(gender)s, %(anchor_age)s,
            %(anchor_year)s, %(anchor_year_group)s, %(dod)s
        )
    """

    try:
        with connection.cursor() as cursor:
            cursor.execute(select_sql)
            existing_rows = cursor.fetchall()

            if existing_rows:
                if existing_rows == expected_rows:
                    connection.rollback()
                    print("환자 데이터가 이미 동일하게 저장되어 있습니다.")
                    return 0

                raise ValueError(
                    "DB에 입력과 다른 환자 데이터가 있습니다. 저장을 중단합니다."
                )

            cursor.executemany(insert_sql, expected_rows)

            cursor.execute(select_sql)
            actual_rows = cursor.fetchall()

            if actual_rows != expected_rows:
                raise ValueError("저장 후 조회한 환자 데이터가 입력과 다릅니다.")

        connection.commit()
        print(f"환자 {len(actual_rows)}행 저장 및 값 비교 통과")
        return len(actual_rows)

    except Exception:
        connection.rollback()
        raise


def save_admissions(connection, admissions):
    """입원을 저장하고 조회 결과가 입력과 일치할 때만 커밋한다."""
    if not admissions:
        raise ValueError("저장할 입원 데이터가 없습니다.")

    expected_rows = sorted(
        admissions,
        key=lambda admission: admission["hadm_id"],
    )

    select_sql = """
        SELECT
            subject_id, hadm_id, admittime, dischtime, deathtime,
            admission_type, admit_provider_id, admission_location,
            discharge_location, insurance, language, marital_status,
            race, edregtime, edouttime, hospital_expire_flag
        FROM admissions
        ORDER BY hadm_id
    """

    insert_sql = """
        INSERT INTO admissions (
            subject_id, hadm_id, admittime, dischtime, deathtime,
            admission_type, admit_provider_id, admission_location,
            discharge_location, insurance, language, marital_status,
            race, edregtime, edouttime, hospital_expire_flag
        )
        VALUES (
            %(subject_id)s, %(hadm_id)s, %(admittime)s,
            %(dischtime)s, %(deathtime)s, %(admission_type)s,
            %(admit_provider_id)s, %(admission_location)s,
            %(discharge_location)s, %(insurance)s, %(language)s,
            %(marital_status)s, %(race)s, %(edregtime)s,
            %(edouttime)s, %(hospital_expire_flag)s
        )
    """

    try:
        with connection.cursor() as cursor:
            cursor.execute(select_sql)
            existing_rows = cursor.fetchall()

            if existing_rows:
                if existing_rows == expected_rows:
                    connection.rollback()
                    print("입원 데이터가 이미 동일하게 저장되어 있습니다.")
                    return 0

                raise ValueError(
                    "DB에 입력과 다른 입원 데이터가 있습니다. 저장을 중단합니다."
                )

            cursor.executemany(insert_sql, expected_rows)

            cursor.execute(select_sql)
            actual_rows = cursor.fetchall()

            if actual_rows != expected_rows:
                raise ValueError("저장 후 조회한 입원 데이터가 입력과 다릅니다.")

        connection.commit()
        print(f"입원 {len(actual_rows)}행 저장 및 값 비교 통과")
        return len(actual_rows)

    except Exception:
        connection.rollback()
        raise


def read_tables(connection):
    """두 테이블의 전체 열을 기본키 순서로 조회해 반환한다."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                subject_id, gender, anchor_age,
                anchor_year, anchor_year_group, dod
            FROM patients
            ORDER BY subject_id
            """
        )
        patients = list(cursor.fetchall())

        cursor.execute(
            """
            SELECT
                subject_id, hadm_id, admittime, dischtime, deathtime,
                admission_type, admit_provider_id, admission_location,
                discharge_location, insurance, language, marital_status,
                race, edregtime, edouttime, hospital_expire_flag
            FROM admissions
            ORDER BY hadm_id
            """
        )
        admissions = list(cursor.fetchall())

    return {
        "patients": patients,
        "admissions": admissions,
    }


# 'python db.py'를 직접 실행할때만 아래의 접속 확인 코드를 실행함
if __name__ == "__main__":
    connection = connect_mariadb()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    VERSION() AS db_version,
                    DATABASE() AS database_name,
                    CURRENT_USER() AS account
                """
            )
            print("접속 정보:", cursor.fetchone())

            cursor.execute("SELECT COUNT(*) AS row_count FROM patients")
            print("환자 테이블:", cursor.fetchone())

            cursor.execute("SELECT COUNT(*) AS row_count FROM admissions")
            print("입원 테이블:", cursor.fetchone())

    finally:
        connection.close()
        print("MariaDB 연결 종료")


    pg_connection = connect_postgres()

    try:
        with pg_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    version() AS db_version,
                    current_database() AS database_name,
                    current_user AS account
                """
            )
            print("PostgreSQL 접속 정보:", cursor.fetchone())

            cursor.execute("SELECT COUNT(*) AS row_count FROM patients")
            print("PostgreSQL 환자 테이블:", cursor.fetchone())

            cursor.execute("SELECT COUNT(*) AS row_count FROM admissions")
            print("PostgreSQL 입원 테이블:", cursor.fetchone())

    finally:
        pg_connection.close()
        print("PostgreSQL 연결 종료")