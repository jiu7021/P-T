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

```
웨이퍼 테스트 결과에서 이상 분포를 발견   →  Module A
  → 해당 좌표의 결함을 이미지로 특정      →  Module B
    → 원인 공정을 추적                    →  Module B-3 (룩업, 사람이 확정)
      → 테스트 조건과 정책을 조정          →  Module C
```

| 모듈 | 단계 | 데이터 |
|---|---|---|
| A. 웨이퍼 맵 분석 | 이상 분포 발견 | WM-811K (실데이터) |
| B. SEM 결함 분석 | 결함 특정과 원인 후보 제시 | Carinthia-S (실데이터) |
| C. 테스트 정책 시뮬레이터 | 정책 조정 | A의 실데이터 + 항목 결과는 합성 |

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
pip install -r requirements.txt
```

난수 시드는 전 과정에서 고정한다. 재현되지 않는 결과는 결과로 취급하지 않는다.

## 진행 상태

| 단계 | 상태 |
|---|---|
| 저장소 뼈대 · 문서 초안 | 완료 |
| 데이터 확보 | **미완 — 위 2개 파일 수동 다운로드 필요** |
| Module A 웨이퍼 맵 분석 | 미착수 |
| Module B SEM 결함 분석 | 미착수 |
| Module C 테스트 정책 시뮬레이터 | 미착수 |
| Module D 통합 대시보드 | 미착수 |

## 문서

- [docs/data_sources.md](docs/data_sources.md) — 데이터셋 출처와 라이선스
- [docs/data_limits.md](docs/data_limits.md) — 데이터의 한계
- [docs/assumptions.md](docs/assumptions.md) — 모든 가정과 근거
- docs/results.md — 모듈별 결과, 민감도 분석 (Module 진행 후 작성)
