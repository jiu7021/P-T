# P&T 불량 분석 · 테스트 정책 워크벤치

반도체 후공정(P&T, Package & Test)의 불량 분석과 테스트 정책 결정을 지원하는 웹 워크벤치.

## 이 프로젝트가 주장하는 것과 주장하지 않는 것

- 웨이퍼 맵의 다이 합불과 공간 분포는 **WM-811K 실데이터**다.
- SEM 결함 이미지와 세그멘테이션 마스크는 **Carinthia-S 실데이터**다.
- **항목별 테스트 결과와 소요 시간은 공개 데이터가 없어 물리 가정 기반으로 합성**했다.
  절대값이 실제 라인과 같다고 주장하지 않는다. 상대적 크기만 물리적으로 타당하게 잡았다.
- **원인 공정 추정은 모델이 아니라 문헌 기반 룩업**이며, 확정 판단은 사람이 수행한다.
- 따라서 이 프로젝트가 주장하는 것은 **모델 성능이 아니라 분석 흐름의 설계와
  의사결정 근거의 가시화**다.

## 모사하는 업무 루프

**웨이퍼 테스트(EDS)는 전기 시험이다.** 프로브 카드를 다이에 대고 전압을 인가해
출력이 규격에 맞는지 본다. 결함 이미지 분석은 이 단계가 아니라 FA에서 한다.

```
[웨이퍼 테스트 = EDS]
  전압 인가 · 고온 동작 → 항목별 측정값
    → 규격 대비 판정 → Good / Repairable / Fail
       └ fail bit 주소를 모아 리페어 분석 (여분 행·열로 덮이나?)
    → 웨이퍼 좌표에 등급 시각화
[FA — 걸러진 다이를 나중에 뜯어볼 때]
  SEM 결함 이미지 → 형태 측정 → 원인 공정 후보(문헌 룩업) → 엔지니어 판정 누적
```

| 모듈 | 단계 | 데이터 |
|---|---|---|
| 1. 웨이퍼 맵 분석 | 이상 분포 발견 | WM-811K (실데이터) |
| 2. **EDS 웨이퍼 테스트** | 전기 시험 → 다이 등급 판정 | 불량 위치 실데이터 + **측정값 합성** |
| 3. Fail Address 분석 | 칩 내부 불량 모드 판별 | **합성** (공개 데이터 없음) |
| 4. FA — SEM 결함 분석 | 결함 특정과 원인 후보 제시 | Carinthia-S (실데이터) |
| 5. 판정 피드백 | 엔지니어 판정 누적 | — |
| 6. 통합 대시보드 | 단일 HTML | 위 결과를 인라인 임베드 |

### 데이터 계층 — 혼동하지 말 것

| 계층 | 단위 | 데이터 |
|---|---|---|
| 웨이퍼 맵 | 다이 1개 = 점 1개 (pass/fail) | WM-811K **실데이터** |
| Fail Address | 다이 **내부** 셀 주소 (16진수 X/Y) | **합성** |
| SEM 이미지 | 결함 1개의 확대 이미지 | Carinthia-S **실데이터** |

> 테스트 정책 시뮬레이터(STOF·순서 재배치·τ 스윕·스택 단수별 원가)는 **보류**했다.

## 데이터 준비 (수동)

원본 데이터는 저장소에 포함되지 않는다. 자동 다운로드 코드도 두지 않는다.

1. **WM-811K**: https://www.kaggle.com/datasets/qingyi/wm811k-wafer-map 에서
   `LSWMD.pkl` 을 받아 `data/raw/wm811k/LSWMD.pkl` 에 둔다.
2. **Carinthia-S**: https://zenodo.org/records/16895427 에서 `data.zip` (139.2 MB)을 받아
   `data/raw/carinthia_s/` 에 압축 해제한다. (CC BY 4.0)

상세와 라이선스는 [docs/data_sources.md](docs/data_sources.md).
데이터의 한계는 [docs/data_limits.md](docs/data_limits.md) — **결과 해석 전에 반드시 읽을 것.**

## 환경

```
bash setup.sh                                   # venv 생성·설치 (Intel Mac 제약 자동 처리)
.venv/bin/python src/data/download.py           # 데이터 자동 다운로드 (인증 불필요)
```

재현 순서:

```
.venv/bin/python src/data/load_wm811k.py        # A-1
.venv/bin/python src/features/spatial.py        # A-2 (누수 검증 포함)
.venv/bin/python src/model/pattern_cnn.py       # A-3 (CPU 약 10분)
.venv/bin/python src/data/load_carinthia.py     # B-1
.venv/bin/python src/data/cache_carinthia.py    # B-2 준비
.venv/bin/python src/model/defect_unet.py       # B-2 (CPU 약 90분)
.venv/bin/python src/features/defect_shape.py   # B-3 형태 측정
.venv/bin/python src/model/cause_lookup.py      # B-3 원인 후보 룩업
.venv/bin/python src/sim/fail_address.py        # 3   Fail Address
.venv/bin/python src/sim/eds.py                # 2   EDS 전기 시험 (약 2.5분)
.venv/bin/python src/sim/eds_sensitivity.py    #     EDS 민감도
.venv/bin/python src/viz/collect_dashboard_data.py
.venv/bin/python src/viz/build_dashboard.py     # D   output/dashboard.html
```

난수 시드는 전 과정에서 고정한다. 재현되지 않는 결과는 결과로 취급하지 않는다.

## 진행 상태

| 단계 | 상태 |
|---|---|
| 저장소 뼈대 · 문서 | 완료 |
| 데이터 확보 (자동 다운로드) | 완료 — `src/data/download.py` |
| 1. 웨이퍼 맵 분석 | **완료** — 공간 상관 9.7배 확인 |
| 2. **EDS 웨이퍼 테스트** | **완료** — Good 76.96% / Repairable 12.35% / Fail 10.70%, 민감도 포함 |
| 3. Fail Address 분석 | **완료** — 규칙 판별 자기검증 99.3%, 임계값 민감도 포함 |
| 4. FA — SEM 결함 분석 | **완료** — 원인 공정 룩업 10후보 전부 문헌 출처 보유 |
| 판정 피드백 루프 | **완료** — 표본 부족 시 학습 거부 |
| Module D 통합 대시보드 | **완료** — `output/dashboard.html` (0.95 MB, 단일 파일) |
| Module C 테스트 정책 시뮬레이터 | 보류 |

## 문서

- [docs/data_sources.md](docs/data_sources.md) — 데이터셋 출처와 라이선스
- [docs/data_limits.md](docs/data_limits.md) — 데이터의 한계
- [docs/assumptions.md](docs/assumptions.md) — 모든 가정과 근거
- docs/results.md — 모듈별 결과, 민감도 분석 (Module 진행 후 작성)
