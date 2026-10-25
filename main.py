import csv
import gzip
import hashlib
from pathlib import Path
from urllib.request import urlopen
from collections import Counter
from datetime import date, datetime
from db import connect_mariadb, save_patients, save_admissions

def convert_patient(patient):
    """환자 한 행의 숫자, 날짜 자료형을 변환함. 빈 사망일은 None으로 처리함."""
    return {
        "subject_id": int(patient["subject_id"]),
        "gender": patient["gender"],
        "anchor_age": int(patient["anchor_age"]),
        "anchor_year": int(patient["anchor_year"]),
        "anchor_year_group": patient["anchor_year_group"],
        "dod": (
            None
            if patient["dod"] == ""
            else date.fromisoformat(patient["dod"])
        ),
    }

def parse_optional_datetime(value):
    """빈 문자열은 None으로, 값이 있으면 날짜/시각으로 변환함."""
    if value == "":
        return None
    return datetime.fromisoformat(value)


def parse_optional_text(value):
    """빈 문자열은 None으로 바꾸고, 나머지 문자열은 그대로 유지함."""
    if value == "":
        return None
    return value


def convert_admission(admission):
    """입원 한 행의 ID/시각/사망 표시를 변환하고 선택 항목의 빈 값을 처리함."""
    expire_flag = int(admission["hospital_expire_flag"])

    if expire_flag not in (0, 1):
        raise ValueError("hospital_expire_flag는 0 또는 1이어야 합니다.")

    return {
        "subject_id": int(admission["subject_id"]),
        "hadm_id": int(admission["hadm_id"]),
        "admittime": datetime.fromisoformat(admission["admittime"]),
        "dischtime": parse_optional_datetime(admission["dischtime"]),
        "deathtime": parse_optional_datetime(admission["deathtime"]),
        "admission_type": admission["admission_type"],
        "admit_provider_id": parse_optional_text(
            admission["admit_provider_id"]
        ),
        "admission_location": admission["admission_location"],
        "discharge_location": parse_optional_text(
            admission["discharge_location"]
        ),
        "insurance": parse_optional_text(admission["insurance"]),
        "language": parse_optional_text(admission["language"]),
        "marital_status": parse_optional_text(admission["marital_status"]),
        "race": parse_optional_text(admission["race"]),
        "edregtime": parse_optional_datetime(admission["edregtime"]),
        "edouttime": parse_optional_datetime(admission["edouttime"]),
        "hospital_expire_flag": expire_flag,
    }


# 1. 원본 데이터 저장 위치 준비
PROJECT_ROOT = Path(__file__).resolve().parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"

RAW_DIR.mkdir(parents=True, exist_ok=True)

print(f"원본 데이터 저장 폴더: {RAW_DIR}")

# 2. 다운로드할 주소와 저장할 파일 경로 지정
# 환자 데이터 다운로드
PATIENTS_URL = (
    "https://physionet.org/files/mimic-iv-demo/2.2/hosp/patients.csv.gz"
)
PATIENTS_GZ_PATH = RAW_DIR / "patients.csv.gz"

# 3. 서버에서 파일의 내용을 바이트로 읽기
with urlopen(PATIENTS_URL, timeout=30) as response:
    downloaded_bytes = response.read()

# 4. 읽은 내용을 로컬 파일로 저장
written_bytes = PATIENTS_GZ_PATH.write_bytes(downloaded_bytes)

print(f"다운로드 완료: {PATIENTS_GZ_PATH}")
print(f"저장한 크기: {written_bytes:,} bytes")

# 5. 저장된 압축 파일의 SHA-256 검증
EXPECTED_PATIENTS_SHA256 = (
    "59dcc6cd8450ddf03ad32cc7d76e41caa4c9633541715987f590c74835cf6fae"
)

saved_bytes = PATIENTS_GZ_PATH.read_bytes()
actual_sha256 = hashlib.sha256(saved_bytes).hexdigest()

print(f"기대 SHA-256: {EXPECTED_PATIENTS_SHA256}")
print(f"실제 SHA-256: {actual_sha256}")

if actual_sha256 != EXPECTED_PATIENTS_SHA256:
    raise ValueError("환자 데이터 파일의 SHA-256이 공식 원본과 다릅니다.")

print("SHA-256 검증 통과: 공식 원본과 일치합니다.")

# 6. 검증한 압축 파일을 풀어 CSV로 저장
PATIENTS_CSV_PATH = RAW_DIR / "patients.csv"

# r: 읽기, b: 바이트 단위
with gzip.open(PATIENTS_GZ_PATH, "rb") as compressed_file:
    csv_bytes = compressed_file.read()

csv_written_bytes = PATIENTS_CSV_PATH.write_bytes(csv_bytes)

print(f"압축 해제 완료: {PATIENTS_CSV_PATH}")
print(f"CSV 저장 크기: {csv_written_bytes:,} bytes")

# 7. CSV를 읽어 구조와 행 수 확인
with PATIENTS_CSV_PATH.open(
        "r", encoding="utf-8", newline=""
) as csv_file:
    reader = csv.DictReader(csv_file)
    column_names = reader.fieldnames
    patients = list(reader)

print(f"열 이름: {column_names}")
print(f"열 개수: {len(column_names)}")
print(f"환자 데이터 행 수: {len(patients)}")

if patients:
    first_patient = patients[0]

    print(f"첫 번째 환자: {first_patient}")
    print(f"subject_id 자료형: {type(first_patient['subject_id']).__name__}")
    # dod: Date of Death(환자의 사망일)
    print(f"dod 값 확인: {first_patient['dod']!r}")

# 8. 환자 ID의 누락/중복과 사망일 결측 현황 확인
# 각 환자 행에서 ID만 꺼내 리스트로 만듦
subject_ids = [patient["subject_id"] for patient in patients]

missing_id_count = subject_ids.count("")
id_counts = Counter(subject_ids)

duplicate_ids = [
    subject_id
    # 한 쌍식 꺼냄
    for subject_id, count in id_counts.items()
    if subject_id != "" and count > 1
]

unique_id_count = len({
    subject_id for subject_id in subject_ids if subject_id != ""
})

missing_dod_count = sum(
    patient["dod"] == "" for patient in patients
)

print(f"누락된 환자 ID 수: {missing_id_count}")
print(f"고유한 환자 ID 수: {unique_id_count}")
print(f"중복된 환자 ID 목록: {duplicate_ids}")
print(f"사망일이 없는 행 수: {missing_dod_count}")
print(f"사망일이 있는 행 수: {len(patients) - missing_dod_count}")

if missing_id_count > 0 or duplicate_ids:
    raise ValueError("환자 ID에 누락 또는 중복이 있습니다.")

print("환자 ID 검증 통과")

# 9. CSV 문자열을 정수, 날짜, 결측값으로 변환
typed_patients = []

for patient in patients:
    typed_patient = convert_patient(patient)
    typed_patients.append(typed_patient)

print(f"변환한 환자 수: {len(typed_patients)}")

first_typed_patient = typed_patients[0]

print(f"변환 후 첫 번째 환자: {first_typed_patient}")
print(
    "변환 후 subject_id 자료형: "
    f"{type(first_typed_patient['subject_id']).__name__}"
)
print(f"변환 후 첫 번째 환자의 dod: {first_typed_patient['dod']!r}")

date_count = sum(
    isinstance(patient["dod"], date)
    for patient in typed_patients
)
none_count = sum(
    patient["dod"] is None
    for patient in typed_patients
)

print(f"dod가 날짜인 행 수: {date_count}")
print(f"dod가 None인 행 수: {none_count}")


# 10. 입원 데이터 다운로드
ADMISSIONS_URL = (
    "https://physionet.org/files/mimic-iv-demo/2.2/hosp/admissions.csv.gz"
)
ADMISSIONS_GZ_PATH = RAW_DIR / "admissions.csv.gz"
ADMISSIONS_CSV_PATH = RAW_DIR / "admissions.csv"

EXPECTED_ADMISSIONS_SHA256 = (
    "910b9f160ffdf1e08ea673585393f347c773ccc87d66875c627584a903ae8493"
)

with urlopen(ADMISSIONS_URL, timeout=30) as response:
    admissions_downloaded_bytes = response.read()

ADMISSIONS_GZ_PATH.write_bytes(admissions_downloaded_bytes)

print(f"입원 데이터 다운로드 완료: {ADMISSIONS_GZ_PATH}")


# 11. 저장된 입원 압축 파일 검증
admissions_saved_bytes = ADMISSIONS_GZ_PATH.read_bytes()
admissions_sha256 = hashlib.sha256(admissions_saved_bytes).hexdigest()

print(f"입원 데이터 기대 SHA-256: {EXPECTED_ADMISSIONS_SHA256}")
print(f"입원 데이터 실제 SHA-256: {admissions_sha256}")

if admissions_sha256 != EXPECTED_ADMISSIONS_SHA256:
    raise ValueError("입원 데이터 파일의 SHA-256이 공식 원본과 다릅니다.")

print("입원 데이터 SHA-256 검증 통과")


# 12. 검증한 입원 압축 파일을 풀어 CSV로 저장
with gzip.open(ADMISSIONS_GZ_PATH, "rb") as compressed_file:
    admissions_csv_bytes = compressed_file.read()

admissions_written_bytes = ADMISSIONS_CSV_PATH.write_bytes(
    admissions_csv_bytes
)

print(f"입원 데이터 압축 해제 완료: {ADMISSIONS_CSV_PATH}")
print(f"입원 CSV 저장 크기: {admissions_written_bytes:,} bytes")

# 13. 입원 CSV 읽기
with ADMISSIONS_CSV_PATH.open(
    "r", encoding="utf-8", newline=""
) as csv_file:
    reader = csv.DictReader(csv_file)
    admission_column_names = reader.fieldnames
    admissions = list(reader)

print(f"입원 데이터 열 이름: {admission_column_names}")
print(f"입원 데이터 열 개수: {len(admission_column_names)}")
print(f"입원 데이터 행 수: {len(admissions)}")


# 14. 입원 ID의 누락/중복 확인
hadm_ids = [admission["hadm_id"] for admission in admissions]

missing_hadm_count = hadm_ids.count("")
hadm_counts = Counter(hadm_ids)

duplicate_hadm_ids = [
    hadm_id
    for hadm_id, count in hadm_counts.items()
    if hadm_id != "" and count > 1
]

print(f"누락된 입원 ID 수: {missing_hadm_count}")
print(f"중복된 입원 ID 목록: {duplicate_hadm_ids}")


# 15. 모든 입원 기록이 환자 데이터에 연결되는지 확인
# 환자 테이블에 있는 ID를 set으로 모음
patient_id_set = {
    patient["subject_id"] for patient in patients
}

orphan_admissions = [
    admission
    for admission in admissions
    # 각 입원 기록의 환자 ID가 그 집합에 없는지 검사함
    if admission["subject_id"] not in patient_id_set
]

print(f"환자 데이터에 연결되지 않는 입원 행 수: {len(orphan_admissions)}")

if missing_hadm_count > 0 or duplicate_hadm_ids or orphan_admissions:
    raise ValueError("입원 ID 또는 환자 데이터와의 연결 관계에 문제가 있습니다.")

print("입원 ID 및 환자 연결 검증 통과")


# 16. 환자별 입원 건수 집계
# 1) 입원 테이블에서 환자 ID 등장 횟수를 count
admission_counts = Counter(
    admission["subject_id"] for admission in admissions
)

# 2) 환자 테이블을 기준으로 환자의 입원 건수를 구성
patient_admission_counts = {
    patient["subject_id"]: admission_counts[patient["subject_id"]]
    for patient in patients
}

print(f"집계 대상 환자 수: {len(patient_admission_counts)}")
print(f"환자별 입원 건수 합계: {sum(patient_admission_counts.values())}")


# 17. 입원 횟수별 환자 수 집계
admission_count_distribution = Counter(
    patient_admission_counts.values()
)

print("입원 횟수별 환자 수:")

for admission_count, patient_count in sorted(
    admission_count_distribution.items()
):
    print(f"  {admission_count}회 입원: {patient_count}명")


# 18. 집계 결과와 원본 행 수 비교
if len(patient_admission_counts) != len(patients):
    raise ValueError("집계 대상 환자 수가 원본 환자 수와 다릅니다.")

if sum(patient_admission_counts.values()) != len(admissions):
    raise ValueError("환자별 입원 건수 합계가 원본 입원 행 수와 다릅니다.")

print("환자별 입원 건수 집계 검증 통과")


# 19. 입원 데이터의 열별 빈 문자열 개수 확인
print("입원 데이터의 열별 빈 문자열 개수:")

for column_name in admission_column_names:
    empty_count = sum(
        admission[column_name] == ""
        for admission in admissions
    )
    print(f"  {column_name}: {empty_count}개")


# 20. 날짜/시각 열에서 값이 있는 예시 확인
datetime_columns = [
    "admittime",
    "dischtime",
    "deathtime",
    "edregtime",
    "edouttime",
]

print("날짜·시각 값 예시:")

for column_name in datetime_columns:
    example = next(
        (
            admission[column_name]
            for admission in admissions
            if admission[column_name] != ""
        ),
        None,
    )
    print(f"  {column_name}: {example!r}")


# 21. 사망 표시와 언어 열의 실제 값 확인
expire_flag_counts = Counter(
    admission["hospital_expire_flag"]
    for admission in admissions
)

language_counts = Counter(
    admission["language"]
    for admission in admissions
)

print(f"hospital_expire_flag 값별 건수: {dict(expire_flag_counts)}")
print(f"language 값별 건수: {dict(language_counts)}")


# 22. 입원 데이터 자료형 변환
typed_admissions = [
    convert_admission(admission)
    for admission in admissions
]

print(f"변환한 입원 행 수: {len(typed_admissions)}")

first_typed_admission = typed_admissions[0]

for column_name in [
    "subject_id", "hadm_id", "admittime", "hospital_expire_flag"
]:
    value = first_typed_admission[column_name]
    print(f"  {column_name}: {value!r} / 자료형: {type(value).__name__}")


# 23. 선택 항목의 빈 문자열이 None으로 변환됐는지 확인
optional_columns = [
    "dischtime",
    "deathtime",
    "admit_provider_id",
    "discharge_location",
    "insurance",
    "language",
    "marital_status",
    "race",
    "edregtime",
    "edouttime",
]

for column_name in optional_columns:
    before_count = sum(
        admission[column_name] == ""
        for admission in admissions
    )
    after_count = sum(
        admission[column_name] is None
        for admission in typed_admissions
    )

    print(
        f"  {column_name}: "
        f"변환 전 빈 문자열 {before_count}개 → 변환 후 None {after_count}개"
    )

    if before_count != after_count:
        raise ValueError(f"{column_name}의 결측값 개수가 달라졌습니다.")


print(
    "변환 후 사망 표시 분포:",
    dict(Counter(
        admission["hospital_expire_flag"]
        for admission in typed_admissions
    )),
)

print(
    "변환 후 언어 분포:",
    dict(Counter(
        admission["language"]
        for admission in typed_admissions
    )),
)

# 24. 변환한 환자 데이터를 MariaDB에 저장하고 비교
connection = connect_mariadb()

try:
    # typed_patients를 전달하므로 정수,날짜,None으로 변환한 값이 DB로 들어감
    save_patients(connection, typed_patients)
    save_admissions(connection, typed_admissions)
finally:
    connection.close()