-- 환자 한 명을 한 행으로 저장하는 테이블
CREATE TABLE patients (
    subject_id INTEGER NOT NULL,
    gender CHAR(1) NOT NULL,
    anchor_age SMALLINT NOT NULL,
    anchor_year SMALLINT NOT NULL,
    anchor_year_group VARCHAR(20) NOT NULL,
    dod DATE,

    PRIMARY KEY (subject_id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_bin;


-- 입원 한 건을 한 행으로 저장하는 테이블
CREATE TABLE admissions (
    subject_id INTEGER NOT NULL,
    hadm_id INTEGER NOT NULL,
    admittime DATETIME(6) NOT NULL,
    dischtime DATETIME(6),
    deathtime DATETIME(6),
    admission_type VARCHAR(40) NOT NULL,
    admit_provider_id VARCHAR(10),
    admission_location VARCHAR(60) NOT NULL,
    discharge_location VARCHAR(60),
    insurance VARCHAR(30),
    language VARCHAR(30),
    marital_status VARCHAR(30),
    race VARCHAR(80),
    edregtime DATETIME(6),
    edouttime DATETIME(6),
    hospital_expire_flag SMALLINT NOT NULL,

    PRIMARY KEY (hadm_id),

    CONSTRAINT fk_admissions_patient
        FOREIGN KEY (subject_id)
        REFERENCES patients(subject_id),

    CONSTRAINT ck_hospital_expire_flag
        CHECK (hospital_expire_flag IN (0, 1))
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_bin;