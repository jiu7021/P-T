"""Module D 준비. 대시보드에 인라인 임베드할 데이터를 모은다.

    .venv/bin/python src/viz/collect_dashboard_data.py

대시보드는 외부 API를 호출하지 않는다. 필요한 모든 데이터를 단일 HTML에
인라인으로 넣기 위해, 여기서 표본을 골라 JSON 하나로 만든다.

표본 선정 원칙: 잘된 사례만 고르지 않는다. 오분류·저성능 사례를 반드시 포함한다.

출력: data/processed/dashboard_data.json
"""
from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
MODELS = ROOT / "models"
sys.path.insert(0, str(ROOT))

from src.model.pattern_cnn import (PATTERNS, WaferCNN, build_tensors,  # noqa: E402
                                   grad_cam, split_by_lot)
from src.model.defect_unet import UNet, CLASSES  # noqa: E402
from src.model.cause_lookup import load_map  # noqa: E402

SEED = 20260821
N_WAFER_PER_PATTERN = 6
N_SEM_PER_MORPH = 6


def png_b64(arr: np.ndarray) -> str:
    """uint8 배열을 PNG data URI로 만든다. 외부 파일 참조를 없애기 위함이다."""
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def rle(mask: np.ndarray) -> list[int]:
    """이진 마스크를 런렝스로 압축한다(0에서 시작하는 교대 길이).

    base64 PNG보다 훨씬 작고, JS에서 복원이 단순하다.
    """
    flat = mask.ravel().astype(np.uint8)
    if flat.size == 0:
        return []
    changes = np.flatnonzero(np.diff(flat)) + 1
    bounds = np.concatenate([[0], changes, [flat.size]])
    lens = np.diff(bounds).tolist()
    return lens if flat[0] == 0 else [0] + lens


def _safe_corr(a, b) -> float | None:
    """상관계수. 한쪽이 상수면(불량 0개 또는 전부 불량) 정의되지 않으므로 None."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.std() == 0 or b.std() == 0 or len(a) < 3:
        return None
    return round(float(np.corrcoef(a, b)[0, 1]), 4)


def collect_wafers() -> list[dict]:
    dies = pd.read_parquet(INTERIM / "wafers.parquet")
    meta = pd.read_parquet(INTERIM / "wafers_meta.parquet").reset_index(drop=True)
    feats = pd.read_parquet(INTERIM / "die_features.parquet")

    x, y = build_tensors(dies, meta)
    idx = split_by_lot(meta)
    test_idx = idx[2]

    ck = torch.load(MODELS / "pattern_cnn.pt", map_location="cpu")
    model = WaferCNN()
    model.load_state_dict(ck["state_dict"])
    model.eval()

    rng = np.random.default_rng(SEED)
    groups = dict(tuple(dies.groupby("wafer_id", sort=False)))
    fgroups = dict(tuple(feats.groupby("wafer_id", sort=False)))

    picked: list[int] = []
    for p in PATTERNS:
        cand = [i for i in test_idx if meta.pattern_label.iloc[i] == p]
        if not cand:
            continue
        take = list(rng.choice(cand, size=min(N_WAFER_PER_PATTERN, len(cand)),
                               replace=False))
        picked += [int(v) for v in take]

    out = []
    for i in picked:
        m = meta.iloc[i]
        g = groups[m.wafer_id]
        h, w = int(m.map_h), int(m.map_w)
        # 0=밖, 1=정상, 2=불량 을 그대로 보낸다. 색은 대시보드가 정한다.
        grid = np.zeros((h, w), dtype=np.uint8)
        grid[g.die_y.to_numpy(), g.die_x.to_numpy()] = np.where(g.is_fail, 2, 1)

        cam, cls, prob = grad_cam(model, x[i])
        fg = fgroups[m.wafer_id]
        out.append({
            "wafer_id": m.wafer_id, "lot_id": m.lot_id,
            "wafer_index": int(m.wafer_index),
            "true_label": m.pattern_label, "pred_label": PATTERNS[cls],
            "correct": bool(PATTERNS[cls] == m.pattern_label),
            "prob": {PATTERNS[k]: round(float(prob[k]), 4) for k in range(len(PATTERNS))},
            "h": h, "w": w,
            "grid": grid.ravel().tolist(),
            "cam": (cam * 100).round().astype(np.uint8).ravel().tolist(),  # 64x64, 0~100 정수로 축약
            "die_count": int(m.die_count), "fail_count": int(m.fail_count),
            "fail_rate": round(float(m.fail_rate), 4),
            "feat_summary": {
                "nb8_fail_rate_mean": round(float(fg.nb8_tested_fail_rate.mean()), 4),
                "r_norm_fail_corr": _safe_corr(fg.r_norm, fg.is_fail),
                "edge_dist_mean": round(float(fg.edge_dist.mean()), 3),
                "prev_wafer_available": bool(fg.prev_wafer_fail.notna().any()),
            },
        })
    # 표본에 오분류가 하나도 없으면 편향된 표본이다. 수치로 확인만 하고
    # 인위적으로 바꾸지는 않는다(바꾸면 그것도 편향이다).
    return out


def collect_sem() -> dict:
    z = np.load(INTERIM / "carinthia_cache_128.npz", allow_pickle=False)
    pred = np.load(PROCESSED / "defect_test_pred.npz")
    shape = pd.read_parquet(INTERIM / "defect_shape.parquet")
    cause = load_map()

    imgs, masks, label = z["imgs"], z["masks"], z["label"]
    fname = z["filename"].astype(str)
    ti, seg, cls = pred["test_idx"], pred["seg_pred"], pred["cls_pred"]

    gt = masks[ti]
    inter = (seg & gt).sum((1, 2)).astype(float)
    denom = seg.sum((1, 2)) + gt.sum((1, 2))
    # 정답 마스크가 비어 있으면(class 6 등) Dice는 0이 아니라 **정의되지 않는다**.
    # 0으로 표시하면 성능이 나쁜 것처럼 오해를 준다. NaN으로 두고 화면에서 구분한다.
    dice = np.where(gt.sum((1, 2)) > 0, 2 * inter / np.maximum(denom, 1), np.nan)

    sh = shape.set_index("filename")
    rng = np.random.default_rng(SEED)

    rows = []
    for k, gi in enumerate(ti):
        fn = fname[gi]
        r = sh.loc[fn]
        rows.append({"k": k, "gi": int(gi), "filename": fn,
                     "morph": r.morphology, "dice": float(dice[k]),
                     "label": int(label[gi])})  # dice가 NaN이면 정의 불가
    df = pd.DataFrame(rows)

    # 결함이 있는 형태를 앞에 둔다. none(정답 마스크 없음)은 Dice가 정의되지 않아
    # 목록 맨 앞에 오면 "성능 0"처럼 읽힌다.
    picked = []
    for morph in ["linear_fine", "linear_broad", "compact", "none"]:
        sub = df[df.morph == morph]
        if not len(sub):
            continue
        if morph == "none":
            take = sub.head(3)           # 전부 동일 성격이므로 3장만
        else:
            # 잘된 것만 고르지 않는다: 하위·중앙값·상위를 섞는다.
            ss = sub.sort_values("dice")
            take = pd.concat([ss.head(2), ss.iloc[len(ss)//2:len(ss)//2+2], ss.tail(2)])
        picked += take.k.tolist()
    picked = [int(v) for v in dict.fromkeys(picked)]   # 순서 유지 중복 제거

    items = []
    for k in picked:
        gi = int(ti[k])
        fn = fname[gi]
        r = sh.loc[fn]
        el = None if not np.isfinite(r.elongation) else round(float(r.elongation), 2)
        items.append({
            "filename": fn, "label": int(label[gi]),
            "morphology": r.morphology,
            "img": png_b64(imgs[gi]),
            "gt_rle": rle(masks[gi]), "pred_rle": rle(seg[k]),
            "dice": None if np.isnan(dice[k]) else round(float(dice[k]), 4),
            "gt_px": int(masks[gi].sum()), "pred_px": int(seg[k].sum()),
            "cls_pred": int(CLASSES[cls[k]]),
            "shape": {"area_frac": round(float(r.area_frac), 5),
                      "elongation": el,
                      "n_components": int(r.n_components),
                      "solidity": None if pd.isna(r.solidity) else round(float(r.solidity), 3),
                      "circularity": None if pd.isna(r.circularity) else round(float(r.circularity), 4)},
        })
    return {"items": items, "cause_map": cause}


MODES = ["", "single_bit", "row_fail", "column_fail", "block_fail", "cross_fail",
         "open_short", "idd_standby", "idd_active"]
GRADE_I = {"good": 0, "repairable": 1, "fail": 2}


def collect_eds(n_wafer: int = 12) -> dict:
    """EDS 판정 결과. 웨이퍼 몇 장은 다이별 측정값까지 담는다.

    전체 2,000장의 측정값을 다 넣으면 파일이 수십 MB가 된다. 패턴별로 골라
    소수를 담되, **잘 나온 웨이퍼만 고르지 않는다**(Fail 비율 상·하위를 섞는다).
    값은 정수로 축약한다(전압 ×100, 전류 ×10 등). 화면에서 되돌린다.
    """
    res = pd.read_parquet(PROCESSED / "eds_results.parquet")
    meta = pd.read_parquet(INTERIM / "wafers_meta.parquet").set_index("wafer_id")
    summary = json.loads((PROCESSED / "eds_summary.json").read_text(encoding="utf-8"))
    sens = json.loads((PROCESSED / "eds_sensitivity.json").read_text(encoding="utf-8"))
    with open(ROOT / "config" / "eds_tests.yaml", encoding="utf-8") as f:
        import yaml
        cfg = yaml.safe_load(f)

    fail_rate = res.groupby("wafer_id").grade.apply(lambda s: (s == "fail").mean())
    picks = []
    for p, sub in meta.groupby("pattern_label"):
        ids = [w for w in sub.index if w in fail_rate.index]
        if not ids:
            continue
        fr = fail_rate.loc[ids].sort_values()
        picks += [fr.index[0], fr.index[-1]]        # Fail 최저·최고를 함께
    picks = list(dict.fromkeys(picks))[:n_wafer * 2]

    groups = dict(tuple(res[res.wafer_id.isin(picks)].groupby("wafer_id", sort=False)))
    wafers = []
    for wid in picks:
        g = groups[wid]
        m = meta.loc[wid]
        wafers.append({
            "wafer_id": wid, "pattern": m.pattern_label,
            "h": int(m.map_h), "w": int(m.map_w),
            "x": g.die_x.astype(int).tolist(),
            "y": g.die_y.astype(int).tolist(),
            "grade": [GRADE_I[v] for v in g.grade],
            "mode": [MODES.index(v) if v in MODES else 0 for v in g.fail_mode],
            "nbits": g.n_fail_bits.astype(int).tolist(),
            "ur": g.used_spare_rows.astype(int).tolist(),
            "uc": g.used_spare_cols.astype(int).tolist(),
            # 측정값은 정수로 축약 (전압 ×100, 전류 ×10, 리텐션 ×10)
            "os": (g.open_short_v * 100).round().astype(int).tolist(),
            "ids": (g.idd_standby_ma * 100).round().astype(int).tolist(),
            "ida": (g.idd_active_ma * 10).round().astype(int).tolist(),
            "ret": (g.retention_hot_ms * 10).round().astype(int).tolist(),
            "counts": {k: int((g.grade == k).sum()) for k in GRADE_I},
        })
    return {"wafers": wafers, "summary": summary, "sensitivity": sens,
            "tests": cfg["tests"], "repair": cfg["repair"], "grades": cfg["grades"],
            "temperatures": cfg["temperatures"], "modes": MODES}


def main() -> int:
    print("웨이퍼 맵 수집 중…")
    wafers = collect_wafers()
    print(f"  {len(wafers)}장 (오분류 {sum(1 for w in wafers if not w['correct'])}장 포함)")

    print("SEM 수집 중…")
    sem = collect_sem()
    print(f"  {len(sem['items'])}장")

    print("EDS 판정 수집 중…")
    eds = collect_eds()
    print(f"  웨이퍼 {len(eds['wafers'])}장")

    print("SECOM 결과 로드…")
    secom = json.loads((PROCESSED / "secom_eval.json").read_text(encoding="utf-8"))
    secom["drift"] = json.loads((PROCESSED / "secom_drift.json").read_text(encoding="utf-8"))
    secom["risk"] = json.loads((PROCESSED / "secom_sensor_risk.json").read_text(encoding="utf-8"))

    print("평가 지표 로드…")
    pat_eval = json.loads((PROCESSED / "pattern_eval.json").read_text(encoding="utf-8"))
    def_eval = json.loads((PROCESSED / "defect_eval.json").read_text(encoding="utf-8"))
    fail_cfg = json.loads((PROCESSED / "fail_address_demo.json").read_text(encoding="utf-8"))
    import yaml
    with open(ROOT / "config" / "fail_modes.yaml", encoding="utf-8") as f:
        fail_modes = yaml.safe_load(f)["modes"]

    data = {
        "meta": {
            "generated": pd.Timestamp.now().isoformat(timespec="seconds"),
            "seed": SEED,
            "data_origin": {
                "wafer_map": "WM-811K 실데이터",
                "sem": "Carinthia-S 실데이터",
                "eds_measurement": "합성 (측정값·fail address). 불량 위치는 실데이터",
                "secom": "UCI SECOM 실데이터 (합성 없음)",
                "fail_address": "합성 (공개 데이터 없음)",
                "cause_process": "문헌 기반 룩업 (모델 아님)",
            },
        },
        "wafers": wafers,
        "eds": eds,
        "secom": secom,
        "sem": sem,
        "pattern_eval": pat_eval,
        "defect_eval": def_eval,
        "fail_address": {"address_space": fail_cfg["address_space"],
                         "rules": fail_cfg["rules"],
                         "modes_meta": fail_cfg["meta"],
                         "modes": fail_modes},
    }
    out = PROCESSED / "dashboard_data.json"
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str),
                   encoding="utf-8")
    print(f"저장: {out.name}  {out.stat().st_size:,} B "
          f"({out.stat().st_size/1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
