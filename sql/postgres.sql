-- 환자 한 명을 한 행으로 저장하는 테이블
CREATE TABLE patients (
    subject_id INTEGER NOT NULL,
    gender CHAR(1) NOT NULL,
    anchor_age SMALLINT NOT NULL,
    anchor_year SMALLINT NOT NULL,
    anchor_year_group VARCHAR(20) NOT NULL,
    dod DATE,

    PRIMARY KEY (subject_id)
);


-- 입원 한 건을 한 행으로 저장하는 테이블
CREATE TABLE admissions (
    subject_id INTEGER NOT NULL,
    hadm_id INTEGER NOT NULL,
    admittime TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL,
    dischtime TIMESTAMP(6) WITHOUT TIME ZONE,
    deathtime TIMESTAMP(6) WITHOUT TIME ZONE,
    admission_type VARCHAR(40) NOT NULL,
    admit_provider_id VARCHAR(10),
    admission_location VARCHAR(60) NOT NULL,
    discharge_location VARCHAR(60),
    insurance VARCHAR(30),
    language VARCHAR(30),
    marital_status VARCHAR(30),
    race VARCHAR(80),
    edregtime TIMESTAMP(6) WITHOUT TIME ZONE,
    edouttime TIMESTAMP(6) WITHOUT TIME ZONE,
    hospital_expire_flag SMALLINT NOT NULL,

    PRIMARY KEY (hadm_id),

    CONSTRAINT fk_admissions_patient
        FOREIGN KEY (subject_id)
        REFERENCES patients(subject_id),

    CONSTRAINT ck_hospital_expire_flag
        CHECK (hospital_expire_flag IN (0, 1))
);


-- 환자별 입원 조회와 외래키 관련 검색을 위한 인덱스
CREATE INDEX idx_admissions_subject_id
    ON admissions(subject_id);