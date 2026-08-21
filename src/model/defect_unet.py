"""B-2. SEM 결함 세그멘테이션 + 클래스 분류 (U-Net, 공유 인코더).

    .venv/bin/python src/model/defect_unet.py --epochs 30

지표 원칙 (docs/data_limits.md L5·L7)
    - 클래스 불균형이 1002:1이므로 accuracy 단독 사용 금지. macro-F1을 주 지표로
      쓰되 클래스별 표본 수를 항상 병기한다. class 2(8장)·5(4장)의 F1은 잡음이다.
    - 픽셀 단위로도 결함이 1.7%(중앙값)뿐이라 BCE 단독은 전부 배경으로 수렴한다.
      BCE + soft Dice를 병용한다.
    - 분할이 이미지 단위라 수치는 낙관 편향을 갖는다. 일반화 성능이 아니다.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
MODELS = ROOT / "models"

SEED = 20260821
CLASSES = [1, 2, 3, 4, 5, 6]          # 이름은 공개되어 있지 않다(data_limits L6)


class Block(nn.Module):
    def __init__(self, i, o):
        super().__init__()
        self.f = nn.Sequential(
            nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
            nn.Conv2d(o, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True))

    def forward(self, x):
        return self.f(x)


class UNet(nn.Module):
    """U-Net 인코더를 분류 헤드와 공유한다.

    결함 위치(세그멘테이션)와 결함 종류(분류)는 같은 시각 근거에서 나오므로
    인코더를 공유하는 편이 자연스럽고, CPU 학습 비용도 절반이 된다.
    """

    def __init__(self, base=16, n_class=len(CLASSES)):
        super().__init__()
        b = base
        self.e1, self.e2, self.e3, self.e4 = Block(1, b), Block(b, b*2), Block(b*2, b*4), Block(b*4, b*8)
        self.d3, self.d2, self.d1 = Block(b*8 + b*4, b*4), Block(b*4 + b*2, b*2), Block(b*2 + b, b)
        self.out = nn.Conv2d(b, 1, 1)
        self.cls = nn.Linear(b*8, n_class)
        self.pool = nn.MaxPool2d(2)

    def forward(self, x):
        e1 = self.e1(x)
        e2 = self.e2(self.pool(e1))
        e3 = self.e3(self.pool(e2))
        e4 = self.e4(self.pool(e3))
        logits_cls = self.cls(e4.mean((2, 3)))
        d = self.d3(torch.cat([F.interpolate(e4, scale_factor=2, mode="nearest"), e3], 1))
        d = self.d2(torch.cat([F.interpolate(d, scale_factor=2, mode="nearest"), e2], 1))
        d = self.d1(torch.cat([F.interpolate(d, scale_factor=2, mode="nearest"), e1], 1))
        return self.out(d), logits_cls


def dice_loss(logits, target, eps=1.0):
    """soft Dice. 결함 픽셀이 1.7%뿐이라 BCE 단독으로는 학습되지 않는다."""
    p = torch.sigmoid(logits)
    num = 2 * (p * target).sum((1, 2, 3)) + eps
    den = p.sum((1, 2, 3)) + target.sum((1, 2, 3)) + eps
    return 1 - (num / den).mean()


def augment(x, m, g):
    """뒤집기·90도 회전. SEM 이미지는 방향에 물리적 의미가 없다.

    (설명서에 이미지 오른쪽 3픽셀 검은 테두리가 언급되어 있으나 결함과 무관한
     장비 아티팩트이므로 뒤집어도 문제되지 않는다.)
    """
    if torch.rand(1, generator=g).item() < 0.5:
        x, m = x.flip(-1), m.flip(-1)
    if torch.rand(1, generator=g).item() < 0.5:
        x, m = x.flip(-2), m.flip(-2)
    k = int(torch.randint(0, 4, (1,), generator=g).item())
    if k:
        x, m = torch.rot90(x, k, (-2, -1)), torch.rot90(m, k, (-2, -1))
    return x, m


def seg_metrics(pred: np.ndarray, true: np.ndarray):
    """이미지별 Dice·IoU와 전체(micro) Dice·IoU를 함께 낸다.

    빈 정답 마스크(class 6)는 Dice가 정의되지 않으므로 이미지별 평균에서 제외하고,
    '오검출 픽셀 수'로 따로 보고한다. 제외 사실을 숨기지 않는다.
    """
    inter = (pred & true).sum((1, 2)).astype(np.float64)
    psum = pred.sum((1, 2)).astype(np.float64)
    tsum = true.sum((1, 2)).astype(np.float64)
    has = tsum > 0
    dice_i = 2 * inter[has] / (psum[has] + tsum[has])
    union = psum[has] + tsum[has] - inter[has]
    iou_i = inter[has] / np.maximum(union, 1)
    micro_dice = 2 * inter.sum() / max(psum.sum() + tsum.sum(), 1)
    micro_iou = inter.sum() / max(psum.sum() + tsum.sum() - inter.sum(), 1)
    empty_fp = psum[~has]
    return {
        "dice_image_mean": float(dice_i.mean()) if len(dice_i) else float("nan"),
        "iou_image_mean": float(iou_i.mean()) if len(iou_i) else float("nan"),
        "dice_micro": float(micro_dice), "iou_micro": float(micro_iou),
        "n_with_defect": int(has.sum()), "n_empty_gt": int((~has).sum()),
        "empty_gt_fp_pixels_mean": float(empty_fp.mean()) if len(empty_fp) else 0.0,
        "empty_gt_clean_ratio": float((empty_fp == 0).mean()) if len(empty_fp) else float("nan"),
    }


def macro_f1(y_true, y_pred, n_class):
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


@torch.no_grad()
def evaluate(model, X, M, Y, bs=32, thr=0.5):
    model.eval()
    seg_pred, cls_pred = [], []
    for i in range(0, len(X), bs):
        lo, lc = model(X[i:i+bs])
        seg_pred.append((torch.sigmoid(lo)[:, 0] > thr).numpy())
        cls_pred.append(lc.argmax(1).numpy())
    seg_pred = np.concatenate(seg_pred)
    cls_pred = np.concatenate(cls_pred)
    sm = seg_metrics(seg_pred, M[:, 0].numpy().astype(bool))
    rows, mf1 = macro_f1(Y.numpy(), cls_pred, len(CLASSES))
    return sm, rows, mf1, seg_pred, cls_pred


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--size", type=int, default=128)
    ap.add_argument("--bs", type=int, default=16)
    ap.add_argument("--patience", type=int, default=8)
    args = ap.parse_args()

    cache = INTERIM / f"carinthia_cache_{args.size}.npz"
    if not cache.exists():
        print(f"없음: {cache}\n먼저 실행: .venv/bin/python "
              f"src/data/cache_carinthia.py --size {args.size}")
        return 1
    z = np.load(cache, allow_pickle=False)
    imgs, masks, label, split = z["imgs"], z["masks"], z["label"], z["split"].astype(str)

    torch.manual_seed(SEED)
    np.random.seed(SEED)

    X = torch.from_numpy(imgs).float().div_(255.0).unsqueeze(1)
    X = (X - X.mean()) / X.std()
    M = torch.from_numpy(masks).float().unsqueeze(1)
    Y = torch.from_numpy(np.searchsorted(CLASSES, label)).long()

    idx = {s: np.flatnonzero(split == s) for s in ("train", "val", "test")}
    print(f"입력 {tuple(X.shape)} | train {len(idx['train']):,} "
          f"val {len(idx['val']):,} test {len(idx['test']):,}")

    model = UNet()
    print(f"파라미터 {sum(p.numel() for p in model.parameters())/1e3:.0f}K | "
          f"CPU {torch.get_num_threads()} threads")
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    cnt = torch.bincount(Y[idx["train"]], minlength=len(CLASSES)).float()
    w = cnt.sum() / (len(CLASSES) * cnt.clamp(min=1))
    print("분류 클래스 가중치:", {CLASSES[i]: round(float(w[i]), 2) for i in range(len(CLASSES))})
    cls_loss = nn.CrossEntropyLoss(weight=w)

    g = torch.Generator().manual_seed(SEED)
    tr = idx["train"]
    best, best_state, bad = -1.0, None, 0
    t_start = time.time()
    for ep in range(args.epochs):
        model.train()
        perm = torch.randperm(len(tr), generator=g)
        tot = 0.0
        t0 = time.time()
        for i in range(0, len(tr), args.bs):
            b = tr[perm[i:i+args.bs].numpy()]
            xb, mb = augment(X[b], M[b], g)
            opt.zero_grad(set_to_none=True)
            lo, lc = model(xb)
            loss = (F.binary_cross_entropy_with_logits(lo, mb)
                    + dice_loss(lo, mb) + 0.5 * cls_loss(lc, Y[b]))
            loss.backward()
            opt.step()
            tot += float(loss) * len(b)
        sched.step()
        sm, _, mf1, _, _ = evaluate(model, X[idx["val"]], M[idx["val"]], Y[idx["val"]])
        score = sm["dice_image_mean"]
        flag = ""
        if score > best:
            best, bad = score, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            flag = "  *"
        else:
            bad += 1
        print(f"  ep {ep+1:3d}/{args.epochs}  loss {tot/len(tr):.4f}  "
              f"val Dice {score:.4f}  macro-F1 {mf1:.4f}  "
              f"{time.time()-t0:5.0f}s{flag}", flush=True)
        if bad >= args.patience:
            print(f"  조기 종료 (val Dice가 {args.patience} 에폭 동안 개선 없음)")
            break
    print(f"학습 시간 {(time.time()-t_start)/60:.1f}분 | 최고 val Dice {best:.4f}")

    model.load_state_dict(best_state)
    sm, rows, mf1, seg_pred, cls_pred = evaluate(
        model, X[idx["test"]], M[idx["test"]], Y[idx["test"]])
    y_true = Y[idx["test"]].numpy()
    acc = float((cls_pred == y_true).mean())

    print(f"\n[표 B-2a] test 세그멘테이션   (Carinthia-S 실데이터, 이미지 단위 분할)")
    print(f"  이미지별 Dice 평균 {sm['dice_image_mean']:.4f}  "
          f"(정답 결함이 있는 {sm['n_with_defect']}장 대상)")
    print(f"  이미지별 IoU  평균 {sm['iou_image_mean']:.4f}")
    print(f"  micro Dice {sm['dice_micro']:.4f} | micro IoU {sm['iou_micro']:.4f}")
    print(f"  정답이 빈 마스크인 {sm['n_empty_gt']}장: 오검출 픽셀 평균 "
          f"{sm['empty_gt_fp_pixels_mean']:.1f}, 완전 무검출 비율 "
          f"{sm['empty_gt_clean_ratio']*100:.1f}%")

    print(f"\n[표 B-2b] test 분류 클래스별 성능")
    print(f"  {'class':>6s}{'표본':>6s}{'precision':>11s}{'recall':>9s}{'F1':>8s}   비고")
    note = {2: "표본 극소, 잡음", 5: "표본 극소, 잡음", 6: "결함 없음 클래스"}
    for i, c in enumerate(CLASSES):
        p, r, f, sup = rows[i]
        print(f"  {c:6d}{sup:6d}{p:11.3f}{r:9.3f}{f:8.3f}   {note.get(c,'')}")
    print(f"  {'macro-F1':>6s}{'':6s}{'':11s}{'':9s}{mf1:8.3f}")
    print(f"  {'acc':>6s}{'':6s}{'':11s}{'':9s}{acc:8.3f}   ← 단독 사용 금지 "
          f"(class 3만 찍어도 0.873)")

    MODELS.mkdir(exist_ok=True)
    PROCESSED.mkdir(exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "classes": CLASSES,
                "size": args.size, "seed": SEED}, MODELS / "defect_unet.pt")
    (PROCESSED / "defect_eval.json").write_text(json.dumps({
        "seed": SEED, "size": args.size, "split": "image-level (상위 단위 식별자 없음)",
        "epochs_run": ep + 1, "best_val_dice": best,
        "test_segmentation": sm, "test_macro_f1": mf1, "test_accuracy": acc,
        "per_class": {str(c): {"precision": rows[i][0], "recall": rows[i][1],
                               "f1": rows[i][2], "support": rows[i][3]}
                      for i, c in enumerate(CLASSES)},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    np.savez_compressed(PROCESSED / "defect_test_pred.npz",
                        seg_pred=seg_pred, cls_pred=cls_pred,
                        test_idx=idx["test"])
    print(f"\n저장: models/defect_unet.pt, data/processed/defect_eval.json, "
          f"data/processed/defect_test_pred.npz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
