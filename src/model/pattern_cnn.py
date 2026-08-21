"""A-3. 웨이퍼 단위 결함 패턴 분류기 + Grad-CAM 근거 히트맵.

    .venv/bin/python src/model/pattern_cnn.py

분할 규칙 — 로트 단위 (코드로 강제)
    같은 로트의 웨이퍼는 같은 공정 조건을 지나므로 서로 닮는다. 웨이퍼 단위로
    섞으면 같은 로트가 학습/검증 양쪽에 걸려 성능이 낙관적으로 나온다.
    `split_by_lot()`이 로트를 통째로 배정하고 교집합이 없음을 assert 한다.

이 모델은 '판정'이 아니라 '후보 제시'다. 출력은 항상 근거 히트맵과 함께 쓴다.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
MODELS = ROOT / "models"

SEED = 20260821
IMG = 64                      # 원본 맵이 22~51로 제각각이라 고정 크기로 리샘플링
PATTERNS = ["none", "Center", "Donut", "Edge-Loc", "Edge-Ring",
            "Loc", "Random", "Scratch", "Near-full"]
P2I = {p: i for i, p in enumerate(PATTERNS)}


# --------------------------------------------------------------------------
# 데이터
# --------------------------------------------------------------------------
def build_tensors(dies: pd.DataFrame, meta: pd.DataFrame):
    """웨이퍼 맵을 (N, 2, IMG, IMG) 텐서로 만든다.

    채널 0 = 유효 다이 밀도, 채널 1 = 불량 다이 밀도.
    크기가 다른 웨이퍼를 같은 입력으로 다루려면 리샘플링이 불가피하다.
    area 보간을 쓰면 이진값이 밀도로 바뀌지만, 불량 '개수'보다 '밀도'가
    보존되는 편이 공간 패턴 판별에 적합하다.
    """
    x = torch.zeros(len(meta), 2, IMG, IMG)
    groups = dict(tuple(dies.groupby("wafer_id", sort=False)))
    for i, r in enumerate(meta.itertuples()):
        g = groups[r.wafer_id]
        h, w = int(r.map_h), int(r.map_w)
        valid = np.zeros((h, w), dtype=np.float32)
        fail = np.zeros((h, w), dtype=np.float32)
        ys, xs = g.die_y.to_numpy(), g.die_x.to_numpy()
        valid[ys, xs] = 1.0
        fail[ys, xs] = g.is_fail.to_numpy().astype(np.float32)
        src = torch.from_numpy(np.stack([valid, fail]))[None]
        x[i] = F.interpolate(src, size=(IMG, IMG), mode="area")[0]
    y = torch.tensor([P2I[p] for p in meta.pattern_label], dtype=torch.long)
    return x, y


def split_by_lot(meta: pd.DataFrame, frac=(0.70, 0.15, 0.15), seed=SEED):
    """로트를 통째로 train/val/test에 배정한다.

    패턴별로 로트를 나눠 배정해 클래스 비율이 크게 흔들리지 않게 한다.
    """
    rng = np.random.default_rng(seed)
    lot_pat = meta.groupby("lot_id").pattern_label.agg(
        lambda s: s.value_counts().index[0])            # 로트 대표 패턴
    tr, va, te = [], [], []
    for p in PATTERNS:                                  # 순서 고정 → 재현 가능
        lots = np.sort(lot_pat.index[lot_pat == p].to_numpy())
        rng.shuffle(lots)
        n = len(lots)
        i1, i2 = int(n * frac[0]), int(n * (frac[0] + frac[1]))
        tr += list(lots[:i1]); va += list(lots[i1:i2]); te += list(lots[i2:])
    s_tr, s_va, s_te = set(tr), set(va), set(te)
    # 로트 단위 분할 강제
    assert not (s_tr & s_va) and not (s_tr & s_te) and not (s_va & s_te), \
        "로트가 두 분할에 동시에 배정되었다"
    idx = [np.flatnonzero(meta.lot_id.isin(s).to_numpy()) for s in (s_tr, s_va, s_te)]
    assert sum(len(i) for i in idx) == len(meta)
    return idx


# --------------------------------------------------------------------------
# 모델
# --------------------------------------------------------------------------
class WaferCNN(nn.Module):
    """작은 CNN. Grad-CAM을 위해 마지막 conv 출력을 함께 돌려준다."""

    def __init__(self, n_class=len(PATTERNS)):
        super().__init__()

        def blk(i, o):
            return nn.Sequential(
                nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
                nn.Conv2d(o, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
                nn.MaxPool2d(2))

        self.features = nn.Sequential(blk(2, 16), blk(16, 32), blk(32, 64))  # 64 → 8
        self.head = nn.Linear(64, n_class)

    def forward(self, x, return_maps: bool = False):
        fmap = self.features(x)                  # (N, 64, 8, 8)
        logits = self.head(fmap.mean((2, 3)))    # GAP → FC
        return (logits, fmap) if return_maps else logits


def grad_cam(model: WaferCNN, x: torch.Tensor, cls: int | None = None):
    """Grad-CAM 히트맵.

    특징맵에 대한 클래스 점수의 기울기를 채널 중요도로 삼아 가중합한다.
    훅을 걸지 않고 autograd.grad로 직접 받는다.

    반환: ((IMG, IMG) 0~1 히트맵, 사용한 클래스 인덱스, 클래스 확률 벡터)
    """
    model.eval()
    x = x[None] if x.dim() == 3 else x
    logits, fmap = model(x, return_maps=True)
    if cls is None:
        cls = int(logits.argmax(1)[0])
    grads = torch.autograd.grad(logits[0, cls], fmap)[0]   # (1, C, h, w)
    weights = grads.mean((2, 3), keepdim=True)
    cam = F.relu((weights * fmap).sum(1, keepdim=True))
    cam = F.interpolate(cam, size=(IMG, IMG), mode="bilinear", align_corners=False)
    cam = cam[0, 0].detach()
    if cam.max() > 0:
        cam = cam / cam.max()
    prob = torch.softmax(logits, 1)[0].detach().numpy()
    return cam.numpy(), cls, prob


# --------------------------------------------------------------------------
# 학습 · 평가
# --------------------------------------------------------------------------
def macro_f1(y_true: np.ndarray, y_pred: np.ndarray, n_class: int):
    """클래스별 (precision, recall, f1, support)와 macro-F1을 함께 돌려준다.

    표본 수가 적은 클래스의 F1은 잡음이므로 support를 항상 같이 본다.
    """
    rows = []
    for c in range(n_class):
        tp = int(((y_pred == c) & (y_true == c)).sum())
        fp = int(((y_pred == c) & (y_true != c)).sum())
        fn = int(((y_pred != c) & (y_true == c)).sum())
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        rows.append((p, r, f, tp + fn))
    return rows, float(np.mean([r[2] for r in rows]))


def train(x, y, idx, epochs=60, bs=64, lr=3e-3):
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    tr, va, te = idx
    model = WaferCNN()
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    # Near-full은 83장뿐이라 다른 클래스의 1/3 미만이다. 빈도 역수로 보정한다.
    cnt = torch.bincount(y[tr], minlength=len(PATTERNS)).float()
    w = (cnt.sum() / (len(PATTERNS) * cnt.clamp(min=1)))
    lossf = nn.CrossEntropyLoss(weight=w)

    g = torch.Generator().manual_seed(SEED)
    best_f1, best_state = -1.0, None
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(tr), generator=g)
        tot = 0.0
        for i in range(0, len(tr), bs):
            b = tr[perm[i:i + bs].numpy()]
            opt.zero_grad(set_to_none=True)
            loss = lossf(model(x[b]), y[b])
            loss.backward()
            opt.step()
            tot += float(loss) * len(b)
        sched.step()
        model.eval()
        with torch.no_grad():
            pv = model(x[va]).argmax(1).numpy()
        _, f1 = macro_f1(y[va].numpy(), pv, len(PATTERNS))
        if f1 > best_f1:
            best_f1, best_state = f1, {k: v.clone() for k, v in model.state_dict().items()}
        if (ep + 1) % 10 == 0:
            print(f"  ep {ep+1:3d}  loss {tot/len(tr):.4f}  val macro-F1 {f1:.4f}"
                  f"  (best {best_f1:.4f})")
    model.load_state_dict(best_state)
    return model, best_f1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--epochs", type=int, default=60)
    args = ap.parse_args()

    dies = pd.read_parquet(INTERIM / "wafers.parquet")
    meta = pd.read_parquet(INTERIM / "wafers_meta.parquet").reset_index(drop=True)
    print(f"입력: 웨이퍼 {len(meta):,}장 / 로트 {meta.lot_id.nunique():,}개")

    t0 = time.time()
    x, y = build_tensors(dies, meta)
    print(f"텐서 {tuple(x.shape)} 생성 {time.time()-t0:.1f}s")

    idx = split_by_lot(meta)
    names = ["train", "val", "test"]
    print("\n로트 단위 분할")
    for nm, i in zip(names, idx):
        lots = meta.lot_id.iloc[i].nunique()
        print(f"  {nm:6s} 웨이퍼 {len(i):5,}  로트 {lots:5,}")
    # 분할 간 로트 교집합이 실제로 0인지 다시 확인 (assert와 별개로 수치로 보고)
    lot_sets = [set(meta.lot_id.iloc[i]) for i in idx]
    print(f"  로트 교집합: train∩val {len(lot_sets[0]&lot_sets[1])}, "
          f"train∩test {len(lot_sets[0]&lot_sets[2])}, "
          f"val∩test {len(lot_sets[1]&lot_sets[2])}")

    print(f"\n학습 (CPU, {torch.get_num_threads()} threads)")
    t0 = time.time()
    model, val_f1 = train(x, y, idx, epochs=args.epochs)
    print(f"  학습 시간 {time.time()-t0:.1f}s | 최고 val macro-F1 {val_f1:.4f}")

    model.eval()
    with torch.no_grad():
        pred = model(x[idx[2]]).argmax(1).numpy()
    true = y[idx[2]].numpy()
    rows, mf1 = macro_f1(true, pred, len(PATTERNS))

    print(f"\n[표 A-3] test 분할 클래스별 성능   (WM-811K 실데이터, 로트 단위 분할)")
    print(f"  {'클래스':12s}{'표본':>6s}{'precision':>11s}{'recall':>9s}{'F1':>8s}")
    for i, p in enumerate(PATTERNS):
        pr, rc, f1, sup = rows[i]
        print(f"  {p:12s}{sup:6d}{pr:11.3f}{rc:9.3f}{f1:8.3f}")
    acc = float((pred == true).mean())
    print(f"  {'macro-F1':12s}{'':6s}{'':11s}{'':9s}{mf1:8.3f}")
    print(f"  {'accuracy':12s}{'':6s}{'':11s}{'':9s}{acc:8.3f}   ← 단독 사용 금지")

    print("\n혼동행렬 (행=실제, 열=예측)")
    cm = np.zeros((len(PATTERNS), len(PATTERNS)), dtype=int)
    for t_, p_ in zip(true, pred):
        cm[t_, p_] += 1
    print("  " + " " * 12 + "".join(f"{p[:5]:>7s}" for p in PATTERNS))
    for i, p in enumerate(PATTERNS):
        print(f"  {p:12s}" + "".join(f"{v:7d}" for v in cm[i]))

    MODELS.mkdir(exist_ok=True)
    PROCESSED.mkdir(exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "patterns": PATTERNS,
                "img": IMG, "seed": SEED}, MODELS / "pattern_cnn.pt")
    report = {
        "seed": SEED, "split": "lot-level 70/15/15", "img": IMG,
        "n_wafer": int(len(meta)), "n_lot": int(meta.lot_id.nunique()),
        "n_test": int(len(true)), "val_macro_f1": val_f1,
        "test_macro_f1": mf1, "test_accuracy": acc,
        "per_class": {p: {"precision": rows[i][0], "recall": rows[i][1],
                          "f1": rows[i][2], "support": rows[i][3]}
                      for i, p in enumerate(PATTERNS)},
        "confusion_matrix": cm.tolist(),
    }
    (PROCESSED / "pattern_eval.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: models/pattern_cnn.pt, data/processed/pattern_eval.json")

    # Grad-CAM 동작 확인 — test 분할에서 클래스별 1장
    print("\nGrad-CAM 동작 확인 (test 분할, 클래스별 1장)")
    for c, p in enumerate(PATTERNS):
        cand = np.flatnonzero(true == c)
        if not len(cand):
            print(f"  {p:12s} test 표본 없음")
            continue
        i = idx[2][cand[0]]
        cam, cls, prob = grad_cam(model, x[i])
        print(f"  {p:12s} 예측 {PATTERNS[cls]:10s} p={prob[cls]:.3f}  "
              f"cam 합 {cam.sum():8.1f}  최대 위치 {np.unravel_index(cam.argmax(), cam.shape)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
