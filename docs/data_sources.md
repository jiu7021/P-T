# 데이터 출처와 라이선스

원본 데이터 파일은 저장소에 커밋하지 않는다(`.gitignore`에 `data/raw/` 등록).
`python src/data/download.py` 로 자동 내려받는다. 두 데이터셋 모두 인증이 필요 없다.

아래 수치는 **2026-08-21 실제로 내려받아 확인한 값**이며, 데이터셋 설명서의 서술과
실측이 다른 경우 실측값을 함께 적었다.

---

## 1. WM-811K (MIR-WM811K) — 웨이퍼 맵 실데이터

| 항목 | 내용 (실측) |
|---|---|
| 배포처 | MIR Lab, National Taiwan University — http://mirlab.org/dataSet/public/ |
| 파일 | `MIR-WM811K.zip` (344,542,743 B ≈ 329 MiB), 인증 불필요 직접 다운로드 |
| 사용 파일 | `MIR-WM811K/Python/WM811K.pkl` (2,022,961,642 B ≈ 1.9 GiB, pandas pickle) |
| 웨이퍼 맵 | 811,457장 |
| 로트 | **46,293개** (`lotName` 고유값 실측. 문헌에 흔히 인용되는 46,393은 실측과 불일치) |
| 웨이퍼 인덱스 | 로트 내 1~25 |
| 패턴 라벨 보유 | **172,950장** (21.31%) |
| 픽셀값 | 0 = 웨이퍼 밖, 1 = 정상 다이, 2 = 불량 다이 (실측 고유값 {0,1,2}) |
| 다이 수(`dieSize`) | 중앙값 953, 1% 503, 99% 14,116, 최소 3, 최대 48,099 |
| 열 구성 | `dieSize`, `failureType`, `lotName`, `trainTestLabel`, `waferIndex`, `waferMap` |
| 배치 경로 | `data/raw/wm811k/MIR-WM811K/Python/WM811K.pkl` |

### 패턴 라벨 실측 분포 (라벨 보유 172,950장)

| 라벨 | 장수 | 라벨 보유분 대비 |
|---|---:|---:|
| none | 147,431 | 85.25% |
| Edge-Ring | 9,680 | 5.60% |
| Edge-Loc | 5,189 | 3.00% |
| Center | 4,294 | 2.48% |
| Loc | 3,593 | 2.08% |
| Scratch | 1,193 | 0.69% |
| Random | 866 | 0.50% |
| Donut | 555 | 0.32% |
| Near-full | 149 | 0.09% |

※ `failureType`, `trainTestLabel` 필드는 중첩 ndarray / 빈 배열 / 문자열이 섞여 있다.
   평탄화 함수 없이 인덱싱하면 `IndexError`가 난다. 로더가 이를 처리한다.
※ 데이터셋에 이미 `trainTestLabel`(Training 54,355 / Test 118,595)이 있으나,
   본 프로젝트는 **로트 단위 분할**을 직접 수행하므로 이 필드를 분할에 쓰지 않는다.

### 라이선스 — 확정 (zip 내 `readme.txt`)

> Copyright 2015 Jyh-Shing Roger Jang.
> 어떤 형태로 재배포하든 위 저작권 고지와 조건 목록을 유지해야 하며,
> 재배포·사용 시 아래 두 인용을 반드시 병기해야 한다.

필수 인용 2건:

1. M.-J. Wu, J.-S. R. Jang, J.-L. Chen, "Wafer Map Failure Pattern Recognition and
   Similarity Ranking for Large-Scale Data Sets," *IEEE Transactions on Semiconductor
   Manufacturing*, vol. 28, no. 1, pp. 1–12, Feb. 2015. doi: 10.1109/TSM.2014.2364237
2. MIR-WM811K: Dataset for wafer map failure pattern recognition, 2015.
   http://mirlab.org/dataset/public/

→ 본 저장소는 원본 데이터를 재배포하지 않으며(다운로드 스크립트만 제공),
   위 두 인용을 README와 대시보드에 표기한다.

---

## 2. Carinthia-S — SEM 결함 이미지 실데이터

| 항목 | 내용 (실측) |
|---|---|
| DOI / URL | 10.5281/zenodo.16895427 / https://zenodo.org/records/16895427 |
| 공개일 | 2025-08-20 |
| 파일 | `data.zip` (139.2 MB, 실측 133 MiB), `carinthia-s_dataset.html` (2.0 MB 설명서) |
| 구성 | `data/images/*.jpg` 4,591장 + `data/masks/*.png` 4,591장 + `data/carinthia-s.csv` |
| CSV 열 | `image_path;mask_path;filename;label` (구분자 세미콜론), 4,591행, 파일명 중복 0 |
| 마스크 | 전문가 검증 이진 세그멘테이션 마스크 |
| 층 | 패턴 없는 비구조화 웨이퍼 층 **1개** |
| 제작 | Corinna Kofler (KAI GmbH), Vahidin Hasić (University of Sarajevo) |
| **라이선스** | **CC BY 4.0** (Zenodo 페이지 확인) — 출처 표기 시 사용 가능 |
| 배치 경로 | `data/raw/carinthia_s/data/` |

### 결함 클래스 실측 분포

| label | 장수 | 비율 |
|---:|---:|---:|
| 1 | 55 | 1.20% |
| 2 | 8 | 0.17% |
| 3 | 4,008 | 87.30% |
| 4 | 289 | 6.29% |
| 5 | 4 | 0.09% |
| 6 | 227 | 4.94% |

최대/최소 불균형비 **1002 : 1**. 이 수치의 의미는 `docs/data_limits.md` L6·L7 참조.

### 원본 데이터셋

C. Kofler, S. Strauß, A. Zernig, E. Lazaro Garcia, M. Boxleitner, B. Mayr,
I. Dicillia-Kovatsch, C. A. Dohr, "Carinthia dataset," Zenodo, Feb. 2024.
doi: 10.5281/zenodo.10715190 (마스크 없음, CC BY 4.0)
소속: KAI GmbH, Infineon Technologies Dresden GmbH & Co. KG, Infineon Technologies Austria AG.

---

## 3. 합성 데이터

Module C의 항목별 테스트 합불·소요 시간·파라메트릭 마진은 **공개 데이터가 없어
물리 가정 기반으로 합성**한다. 가정과 근거는 `docs/assumptions.md`에 전부 기록한다.
모든 산출물(대시보드 포함)에 실데이터 / 합성 데이터 경계를 표기한다.
