"""요구 ②. 엔지니어 판정 기록과 학습 준비도 판단.

    # 후보 제시 (판정하지 않는다)
    .venv/bin/python src/model/feedback.py show --image <filename>
    # 엔지니어 판정 기록
    .venv/bin/python src/model/feedback.py add --image <filename> \
        --process CMP --engineer hong --confidence high --rationale "연마 방향과 일치"
    # 누적 현황과 학습 준비도
    .venv/bin/python src/model/feedback.py stats
    # 학습용 데이터셋 내보내기 (준비되지 않으면 거부한다)
    .venv/bin/python src/model/feedback.py export

설계 원칙
    1. AI는 후보와 근거만 제시한다. 원인 공정을 판정하지 않는다.
    2. 판정은 사람이 하고, 그 판정을 append-only 로그에 남긴다.
       기존 기록을 수정하지 않는다 — 판단이 바뀐 이력도 데이터다.
    3. 판정이 충분히 쌓이기 전에는 학습을 **거부**한다.
       적은 표본으로 학습해 그럴듯한 모델을 만드는 것이 이 프로젝트에서 가장
       위험한 실패다.
    4. 데모용으로 만든 가짜 판정은 `source="demo"`로 표시하고 학습에서 제외한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
LOG = PROCESSED / "verdicts.jsonl"

# 학습을 허용하기 위한 최소 조건 — (가정치)
# 근거: 공개된 기준이 없다. 클래스당 수십 건 미만으로 학습한 분류기는 검증셋을
# 나누는 것조차 성립하지 않는다(Module B의 class 5가 4장이라 지표가 무의미했던
# 것과 같은 문제). 아래 값은 "최소한 이만큼은 있어야 한다"는 하한이며,
# 이 값을 넘겨도 성능이 보장되지는 않는다.
MIN_PER_PROCESS = 30
MIN_PROCESSES = 2
MIN_TOTAL = 100


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_shape() -> pd.DataFrame:
    p = INTERIM / "defect_shape.parquet"
    if not p.exists():
        print(f"없음: {p}\n먼저 실행: .venv/bin/python src/features/defect_shape.py",
              file=sys.stderr)
        raise SystemExit(1)
    return pd.read_parquet(p)


def load_cause_map() -> dict:
    sys.path.insert(0, str(ROOT))
    from src.model.cause_lookup import load_map
    return load_map()


def read_log() -> list[dict]:
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]


def append_log(rec: dict) -> None:
    PROCESSED.mkdir(exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
def cmd_show(args) -> int:
    s = load_shape()
    m = load_cause_map()
    row = s[s.filename == args.image]
    if not len(row):
        print(f"이미지를 찾을 수 없다: {args.image}", file=sys.stderr)
        return 1
    r = row.iloc[0]
    cands = m["morphologies"][r.morphology]["candidates"]

    print(f"이미지 {r.filename}")
    print(f"  데이터셋 라벨: {int(r.label)}  (이름은 공개되지 않음)")
    el = "∞" if not pd.notna(r.elongation) else f"{r.elongation:.2f}"
    print(f"  측정된 형태: {r.morphology}  "
          f"(면적 {r.area_frac*100:.3f}%, 가늘기 {el}, 성분 {int(r.n_components)}개)")
    print(f"\n  원인 공정 후보 — 제시일 뿐 확정이 아니다")
    for i, c in enumerate(cands, 1):
        print(f"   [{i}] {c['process']} / {c.get('sub','')}")
        print(f"       근거: {c['rationale'].strip()}")
        for ref in c["reference"]:
            print(f"       출처: {ref}")
        print(f"       {c['confidence_note'].strip()}")
    print(f"\n  {m['meta']['disclaimer']}")
    print(f"\n  판정 기록:  .venv/bin/python src/model/feedback.py add "
          f"--image {r.filename} --process <공정> --engineer <이름>")
    return 0


def cmd_add(args) -> int:
    s = load_shape()
    m = load_cause_map()
    row = s[s.filename == args.image]
    if not len(row):
        print(f"이미지를 찾을 수 없다: {args.image}", file=sys.stderr)
        return 1
    r = row.iloc[0]
    cands = [c["process"] for c in m["morphologies"][r.morphology]["candidates"]]
    if args.process not in cands:
        # 후보 밖 판정을 막지 않는다. 룩업 표가 불완전할 수 있고, 그 사실 자체가
        # 표를 개정할 근거가 된다. 다만 기록에 표시해 둔다.
        print(f"  주의: '{args.process}'는 이 형태의 후보 목록에 없다. "
              f"후보={cands}. 기록은 남기되 off_list로 표시한다.")
    rec = {
        "ts": _now(),
        "dataset": "carinthia_s",
        "image_id": args.image,
        "label": int(r.label),
        "morphology": r.morphology,
        "candidates_shown": cands,
        "verdict_process": args.process,
        "off_list": args.process not in cands,
        "confidence": args.confidence,
        "rationale": args.rationale or "",
        "engineer": args.engineer,
        "source": args.source,          # engineer | demo
        "model_suggestion": None,       # 학습 모델이 생기면 그때 기록한다
    }
    append_log(rec)
    print(f"기록 완료 → {LOG.name}  (총 {len(read_log())}건)")
    return 0


def readiness(recs: list[dict]) -> tuple[bool, list[str]]:
    """학습을 시작해도 되는지 판단한다. 부족하면 이유를 전부 돌려준다."""
    usable = [r for r in recs if r.get("source") == "engineer"]
    reasons = []
    if len(usable) < MIN_TOTAL:
        reasons.append(f"엔지니어 판정 총 {len(usable)}건 < 최소 {MIN_TOTAL}건")
    per = Counter(r["verdict_process"] for r in usable)
    enough = [p for p, c in per.items() if c >= MIN_PER_PROCESS]
    if len(enough) < MIN_PROCESSES:
        reasons.append(f"{MIN_PER_PROCESS}건 이상 모인 공정이 {len(enough)}종 "
                       f"< 최소 {MIN_PROCESSES}종")
    return (not reasons), reasons


def cmd_stats(args) -> int:
    recs = read_log()
    if not recs:
        print(f"판정 기록이 없다. ({LOG})")
        print(f"학습 준비도: 불가 — 기록 0건")
        return 0
    usable = [r for r in recs if r.get("source") == "engineer"]
    demo = len(recs) - len(usable)
    print(f"판정 기록 {len(recs)}건 (엔지니어 {len(usable)}, 데모 {demo})")

    per = Counter(r["verdict_process"] for r in usable)
    print(f"\n  공정별 판정 수 (엔지니어 판정만)")
    for p, c in per.most_common():
        mark = "" if c >= MIN_PER_PROCESS else f"  ← {MIN_PER_PROCESS}건 미만"
        print(f"    {p:24s}{c:5d}{mark}")

    morph = Counter(r["morphology"] for r in usable)
    print(f"\n  형태별 판정 수: {dict(morph)}")
    off = sum(1 for r in usable if r.get("off_list"))
    print(f"  후보 목록 밖 판정: {off}건"
          + ("  ← cause_map.yaml 개정을 검토할 근거" if off else ""))

    conf = Counter(r.get("confidence") for r in usable)
    print(f"  판정 확신도 분포: {dict(conf)}")

    ok, reasons = readiness(recs)
    print(f"\n  학습 준비도: {'가능' if ok else '불가'}")
    for r in reasons:
        print(f"    - {r}")
    if ok:
        print(f"    내보내기: .venv/bin/python src/model/feedback.py export")
    print(f"\n  기준(가정치): 총 {MIN_TOTAL}건 이상, {MIN_PER_PROCESS}건 이상인 공정이 "
          f"{MIN_PROCESSES}종 이상")
    return 0


def cmd_export(args) -> int:
    recs = read_log()
    ok, reasons = readiness(recs)
    if not ok and not args.force:
        print("학습용 데이터를 내보내지 않는다. 이유:", file=sys.stderr)
        for r in reasons:
            print(f"  - {r}", file=sys.stderr)
        print("\n표본이 부족한 상태로 학습하면 근거 없는 모델이 만들어진다.\n"
              "그래도 진행하려면 --force. 그 경우 결과를 성능으로 인용하지 말 것.",
              file=sys.stderr)
        return 1
    usable = [r for r in recs if r.get("source") == "engineer"]
    out = PROCESSED / "verdict_trainset.parquet"
    pd.DataFrame(usable).to_parquet(out, index=False)
    print(f"저장: {out.name}  {len(usable)}건")
    if not ok:
        print("경고: 준비 기준을 충족하지 않은 채 --force로 내보냈다.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("show", help="후보와 근거를 제시한다 (판정하지 않는다)")
    p.add_argument("--image", required=True)
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("add", help="엔지니어 판정을 기록한다")
    p.add_argument("--image", required=True)
    p.add_argument("--process", required=True)
    p.add_argument("--engineer", required=True)
    p.add_argument("--confidence", default="medium", choices=["high", "medium", "low"])
    p.add_argument("--rationale", default="")
    p.add_argument("--source", default="engineer", choices=["engineer", "demo"])
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("stats", help="누적 현황과 학습 준비도")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("export", help="학습용 데이터 내보내기")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_export)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
