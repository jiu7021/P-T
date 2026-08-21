# 데이터 출처와 라이선스

원본 데이터 파일은 저장소에 커밋하지 않는다(`.gitignore`에 `data/raw/` 등록).
아래 절차로 각자 내려받아 지정 경로에 둔다.

---

## 1. WM-811K (LSWMD) — 웨이퍼 맵 실데이터

| 항목 | 내용 |
|---|---|
| 규모 | 웨이퍼 맵 811,457장, 약 46,393 로트 |
| 라벨 | 그중 172,950장에 전문가 결함 패턴 라벨 (약 21.3%) |
| 라벨 9종 | None, Center, Donut, Edge-Loc, Edge-Ring, Loc, Random, Scratch, Near-Full |
| 픽셀값 | 0 = 웨이퍼 밖, 1 = 정상 다이, 2 = 불량 다이 |
| 파일 | `LSWMD.pkl` (pickle, 약 214 MB) |
| 배포 | MIR Lab(National Taiwan University, Roger Jang 연구실) 공개 데이터셋, Kaggle 미러 |
| Kaggle | https://www.kaggle.com/datasets/qingyi/wm811k-wafer-map |
| 배치 경로 | `data/raw/wm811k/LSWMD.pkl` |

원논문
: M.-J. Wu, J.-S. R. Jang, J.-L. Chen, "Wafer Map Failure Pattern Recognition and
  Similarity Ranking for Large-Scale Data Sets," *IEEE Transactions on Semiconductor
  Manufacturing*, vol. 28, no. 1, pp. 1–12, 2015.

**라이선스: 미확인.** (2026-08-21 기준) Kaggle 데이터셋 페이지의 라이선스 표기를
자동으로 확인하지 못했다. 내려받을 때 페이지의 License 항목을 직접 확인하고 이 표에
채워 넣을 것. 확인 전까지는 "출처 표기 후 비상업적 학습·포트폴리오 용도"로만 사용한다.

---

## 2. Carinthia-S — SEM 결함 이미지 실데이터

| 항목 | 내용 |
|---|---|
| 규모 | SEM 이미지 4,591장, 각 이미지마다 전문가 검증 이진 세그멘테이션 마스크 1장 |
| 클래스 | 결함 6종, 불균등 분포 |
| 층 | 패턴이 없는 **비구조화(unstructured) 웨이퍼 층 1개** (→ `data_limits.md`) |
| 파일 | `data.zip` (139.2 MB), `carinthia-s_dataset.html` (2.1 MB, 데이터셋 설명서) |
| DOI | 10.5281/zenodo.16895427 |
| URL | https://zenodo.org/records/16895427 |
| 공개일 | 2025-08-20 |
| 제작 | Corinna Kofler (KAI Kompetenzzentrum Automobil- und Industrieelektronik GmbH), Vahidin Hasić (University of Sarajevo, Faculty of Electrical Engineering) |
| **라이선스** | **Creative Commons Attribution 4.0 International (CC BY 4.0)** — 출처 표기 시 사용 가능 (Zenodo 페이지 확인, 2026-08-21) |
| 배치 경로 | `data/raw/carinthia_s/` 에 `data.zip` 압축 해제 |

원본 Carinthia 데이터셋(세그멘테이션 마스크 없음): Zenodo record 10715190.

※ 제작 주체는 Zenodo 기록상 KAI GmbH이다. KAI는 인피니언(Infineon) 계열
   연구센터이며, 이미지는 생산 라인에서 취득된 것으로 기술되어 있다. 본 저장소는
   "인피니언 생산 라인"이라는 표현 대신 Zenodo 기록상의 표기를 따른다.

---

## 3. 합성 데이터

Module C의 항목별 테스트 합불·소요 시간·파라메트릭 마진은 **공개 데이터가 없어
물리 가정 기반으로 합성**했다. 가정과 근거는 `docs/assumptions.md`에 전부 기록한다.
모든 산출물(대시보드 포함)에 실데이터 / 합성 데이터 경계를 표기한다.
