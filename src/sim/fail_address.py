"""Module E. Fail Address 합성과 불량 모드 규칙 기반 판별.

    .venv/bin/python src/sim/fail_address.py            # 데모 + 자기검증
    .venv/bin/python src/sim/fail_address.py --demo row_fail

**이것은 모델이 아니다.** 학습하지 않고 파라미터도 없다. config/fail_modes.yaml의
규칙을 그대로 적용할 뿐이며, 판별 결과에는 항상 수치 근거를 함께 낸다.

**주소 데이터는 전부 합성이다.** 셀 단위 Fail Address 비트맵은 공개 데이터가
존재하지 않는다(docs/data_limits.md L3). WM-811K는 다이 단위 합불만 제공한다.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "fail_modes.yaml"
PROCESSED = ROOT / "data" / "processed"

SEED = 20260821


def load_cfg() -> dict:
    with open(CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# 합성
# ---------------------------------------------------------------------------
def synth(mode: str, n_fail: int, rng: np.random.Generator, cfg: dict,
          stride: int = 16, pair: int = 2) -> list[tuple[int, int]]:
    """불량 모드에 맞는 fail 주소 리스트를 만든다.

    stride / pair
        SK하이닉스 공개 영상의 Fail Address 화면에서 Y 값이
        0,1,10,11,20,21,… / 2a0,2a1,2b0,2b1,… 로 나타난다. 16진수로 풀면
        **16 간격으로 2개씩 묶인** 구조다. 라인성 fail에서 이 형태를 재현할 수
        있도록 간격(stride)과 묶음 수(pair)를 인자로 둔다.
        (가정치) 실제 주소 매핑 구조는 공개되어 있지 않다.
    """
    xmax = (1 << cfg["address_space"]["x_bits"]) - 1
    ymax = (1 << cfg["address_space"]["y_bits"]) - 1
    out: list[tuple[int, int]] = []

    def line_ys(n: int) -> list[int]:
        """stride 간격으로 pair개씩 묶인 Y 주소를 n개 만든다."""
        ys, base = [], int(rng.integers(0, max(ymax - stride * (n // pair + 2), 1)))
        while len(ys) < n:
            blk = base + stride * (len(ys) // pair)
            for k in range(pair):
                if len(ys) < n:
                    ys.append(min(blk + k, ymax))
        return ys

    if mode == "single_bit":
        for _ in range(n_fail):
            out.append((int(rng.integers(0, xmax)), int(rng.integers(0, ymax))))

    elif mode == "row_fail":
        x = int(rng.integers(0, xmax))
        for y in line_ys(n_fail):
            out.append((x, y))

    elif mode == "column_fail":
        y = int(rng.integers(0, ymax))
        base = int(rng.integers(0, max(xmax - stride * (n_fail // pair + 2), 1)))
        xs = []
        while len(xs) < n_fail:
            blk = base + stride * (len(xs) // pair)
            for k in range(pair):
                if len(xs) < n_fail:
                    xs.append(min(blk + k, xmax))
        for x in xs:
            out.append((x, y))

    elif mode == "block_fail":
        wx, wy = cfg["rules"]["block_window_x"], cfg["rules"]["block_window_y"]
        x0 = int(rng.integers(0, max(xmax - wx, 1)))
        y0 = int(rng.integers(0, max(ymax - wy, 1)))
        for _ in range(n_fail):
            out.append((x0 + int(rng.integers(0, wx)), y0 + int(rng.integers(0, wy))))

    elif mode == "cross_fail":
        half = max(n_fail // 2, 1)
        out += synth("row_fail", half, rng, cfg, stride, pair)
        out += synth("column_fail", n_fail - half, rng, cfg, stride, pair)

    else:
        raise ValueError(f"알 수 없는 모드: {mode}")

    # 중복 주소 제거 (같은 셀이 두 번 fail로 기록되지 않는다)
    return sorted(set(out))


def add_noise(addrs, n_noise: int, rng, cfg) -> list[tuple[int, int]]:
    """산발 싱글비트 잡음을 섞는다. 실제 웨이퍼에서 라인성 불량만 단독으로
    나타나는 경우는 드물다."""
    xmax = (1 << cfg["address_space"]["x_bits"]) - 1
    ymax = (1 << cfg["address_space"]["y_bits"]) - 1
    extra = [(int(rng.integers(0, xmax)), int(rng.integers(0, ymax)))
             for _ in range(n_noise)]
    return sorted(set(addrs) | set(extra))


# ---------------------------------------------------------------------------
# 판별 (규칙 기반)
# ---------------------------------------------------------------------------
def classify(addrs: list[tuple[int, int]], cfg: dict) -> dict:
    """불량 모드를 판별하고 근거를 함께 돌려준다.

    점수는 '전체 fail 중 그 구조가 설명하는 비율'이다. 확률이 아니다.
    임계값은 전부 가정치이므로, 상위 두 후보의 점수가 가까우면 경계 사례로 표시하고
    단정하지 않는다.
    """
    r = cfg["rules"]
    n = len(addrs)
    ev: dict = {"n_fail": n}
    if n == 0:
        return {"mode": None, "label": "fail 없음", "score": 0.0,
                "ambiguous": False, "evidence": ev, "runner_up": None}

    xs = Counter(x for x, _ in addrs)
    ys = Counter(y for _, y in addrs)
    (tx, cx), = xs.most_common(1)
    (ty, cy), = ys.most_common(1)

    row_ratio = cx / n
    col_ratio = cy / n
    ev["top_x"] = {"addr": tx, "hex": f"0x{tx:04x}", "count": cx, "ratio": row_ratio}
    ev["top_y"] = {"addr": ty, "hex": f"0x{ty:03x}", "count": cy, "ratio": col_ratio}

    # 블록: 각 fail을 좌상단으로 하는 창 안의 fail 수 중 최대. n이 작아 O(n^2)로 충분하다.
    wx, wy = r["block_window_x"], r["block_window_y"]
    arr = np.asarray(addrs)
    best_cnt, best_box = 0, None
    for x0, y0 in addrs:
        inside = ((arr[:, 0] >= x0) & (arr[:, 0] < x0 + wx)
                  & (arr[:, 1] >= y0) & (arr[:, 1] < y0 + wy))
        c = int(inside.sum())
        if c > best_cnt:
            best_cnt, best_box = c, (x0, y0)
    blk_ratio = best_cnt / n
    ev["top_block"] = {"x0": best_box[0], "y0": best_box[1],
                       "hex": f"0x{best_box[0]:04x}~0x{best_box[0]+wx-1:04x} / "
                              f"0x{best_box[1]:03x}~0x{best_box[1]+wy-1:03x}",
                       "count": best_cnt, "ratio": blk_ratio,
                       "window": [wx, wy]}

    # 규칙 적용 — 임계를 넘지 못하면 그 구조는 아무것도 설명하지 못한 것으로 본다
    row_ok = cx >= r["line_min_count"] and row_ratio >= r["line_min_ratio"]
    col_ok = cy >= r["line_min_count"] and col_ratio >= r["line_min_ratio"]
    blk_ok = best_cnt >= r["block_min_count"] and blk_ratio >= r["block_min_ratio"]

    # 각 구조가 '설명하는' fail 집합. 점수는 집합 크기 비율이며 확률이 아니다.
    idx = set(range(n))
    row_set = {i for i in idx if addrs[i][0] == tx} if row_ok else set()
    col_set = {i for i in idx if addrs[i][1] == ty} if col_ok else set()
    if blk_ok:
        bx, by = best_box
        blk_set = {i for i in idx
                   if bx <= addrs[i][0] < bx + wx and by <= addrs[i][1] < by + wy}
    else:
        blk_set = set()

    scores = {
        "row_fail": len(row_set) / n,
        "column_fail": len(col_set) / n,
        "block_fail": len(blk_set) / n,
    }
    # 크로스: 로우성과 칼럼성이 동시에 성립할 때만. 두 구조가 함께 설명하는 비율이다.
    if row_ok and col_ok:
        scores["cross_fail"] = len(row_set | col_set) / n
    # 싱글비트: 위 어느 구조로도 설명되지 않은 fail의 비율.
    # (합집합으로 계산한다. 최대 구조 하나만 빼면 크로스가 싱글비트와 동점이 된다.)
    explained = row_set | col_set | blk_set
    scores["single_bit"] = 1.0 - len(explained) / n

    # 순위 결정. cross는 row/column을 포함하므로 동점일 때 더 구체적인 쪽(cross)을 택한다.
    priority = {"cross_fail": 3, "block_fail": 2, "row_fail": 1,
                "column_fail": 1, "single_bit": 0}
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], -priority[kv[0]]))
    top, top_s = ranked[0]
    second, second_s = ranked[1]
    # 상위 두 후보의 점수가 가까우면 단정하지 않고 경계 사례로 표시한다.
    ambiguous = (top_s - second_s) < r["ambiguous_margin"]

    ev["scores"] = scores
    ev["thresholds_used"] = {k: r[k] for k in
                             ("line_min_count", "line_min_ratio", "block_min_count",
                              "block_min_ratio", "ambiguous_margin")}
    return {"mode": top, "label": cfg["modes"][top]["label"], "score": top_s,
            "ambiguous": ambiguous, "runner_up": {"mode": second, "score": second_s},
            "evidence": ev}


def render_table(addrs, cfg, max_rows=12) -> str:
    """영상의 Fail Address 화면처럼 X | Y 16진수 표로 만든다."""
    lines = [f"  {'X':>6s} | {'Y':<5s}", f"  {'-'*6}-+-{'-'*5}"]
    for i, (x, y) in enumerate(addrs[:max_rows]):
        lines.append(f"  {x:04x} | {y:03x}")
    if len(addrs) > max_rows:
        lines.append(f"  … 외 {len(addrs)-max_rows}건")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
def self_check(cfg) -> tuple[int, int]:
    """합성한 모드를 판별기가 되찾아내는지 확인한다.

    합성 규칙과 판별 규칙은 서로 독립이다(합성은 주소를 만들고, 판별은 개수와
    분포만 본다). 그래도 완전한 검증은 아니다 — 같은 가정 위에 서 있기 때문이다.
    이 수치는 '판별기가 의도한 형태를 구분한다'는 최소 확인일 뿐이다.
    """
    rng = np.random.default_rng(SEED)
    modes = ["single_bit", "row_fail", "column_fail", "block_fail", "cross_fail"]
    ok = tot = 0
    conf = {m: Counter() for m in modes}
    for m in modes:
        for _ in range(200):
            n = int(rng.integers(8, 40))
            a = synth(m, n, rng, cfg)
            a = add_noise(a, int(rng.integers(0, 4)), rng, cfg)
            got = classify(a, cfg)["mode"]
            conf[m][got] += 1
            ok += (got == m)
            tot += 1
    print("\n[자기검증] 합성 모드 → 판별 결과 (각 200회, 잡음 0~3건 포함)")
    cols = modes
    print(f"  {'합성\\판별':<14s}" + "".join(f"{c[:9]:>11s}" for c in cols))
    for m in modes:
        print(f"  {m:<14s}" + "".join(f"{conf[m][c]:11d}" for c in cols))
    print(f"  일치 {ok}/{tot} ({ok/tot*100:.1f}%)")
    return ok, tot


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--demo", default=None, help="특정 모드 예시만 출력")
    ap.add_argument("--n", type=int, default=20)
    args = ap.parse_args()
    cfg = load_cfg()
    rng = np.random.default_rng(SEED)

    print(f"주소 공간: X {cfg['address_space']['x_bits']}bit, "
          f"Y {cfg['address_space']['y_bits']}bit  (표기는 16진수)")
    print(f"데이터 성격: {cfg['meta']['data_origin']}  ← 합성이다. 실데이터가 아니다.")

    modes = [args.demo] if args.demo else list(cfg["modes"])
    samples = []
    for m in modes:
        a = add_noise(synth(m, args.n, rng, cfg), 2, rng, cfg)
        res = classify(a, cfg)
        print(f"\n{'='*66}\n[합성: {m}]  fail {len(a)}건")
        print(render_table(a, cfg))
        e = res["evidence"]
        print(f"\n  판별: {res['label']} ({res['mode']})  점수 {res['score']:.3f}"
              + ("   ← 경계 사례" if res["ambiguous"] else ""))
        print(f"  차상위: {e['scores'] and res['runner_up']['mode']} "
              f"{res['runner_up']['score']:.3f}")
        print(f"  근거")
        print(f"    최다 X = {e['top_x']['hex']} : {e['top_x']['count']}건 "
              f"({e['top_x']['ratio']*100:.1f}%)")
        print(f"    최다 Y = {e['top_y']['hex']} : {e['top_y']['count']}건 "
              f"({e['top_y']['ratio']*100:.1f}%)")
        print(f"    최밀 블록 {e['top_block']['hex']} : {e['top_block']['count']}건 "
              f"({e['top_block']['ratio']*100:.1f}%, 창 {e['top_block']['window']})")
        samples.append({"synth_mode": m, "addresses": [[int(x), int(y)] for x, y in a],
                        "result": res})

    ok, tot = self_check(cfg)

    PROCESSED.mkdir(exist_ok=True)
    (PROCESSED / "fail_address_demo.json").write_text(json.dumps(
        {"meta": cfg["meta"], "address_space": cfg["address_space"],
         "rules": cfg["rules"], "samples": samples,
         "self_check": {"match": ok, "total": tot}},
        ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n저장: data/processed/fail_address_demo.json")
    print(f"\n  {cfg['reporting']['disclaimer']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
