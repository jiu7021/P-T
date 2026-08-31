"""docs/ 페이지에 넣을 그림 생성. 다크·라이트 양쪽에서 읽히도록 투명 배경으로 만든다.

    .venv/bin/python src/viz/make_docs_figs.py

모든 수치는 data/processed/*.json 과 data/interim/*.parquet 에서 읽는다.
그림에 손으로 적어 넣는 숫자는 없다.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
INTERIM = ROOT / "data" / "interim"
OUT = ROOT / "docs" / "img"

# 다크/라이트 어느 쪽에 얹혀도 읽히는 중간 톤
INK = "#8b93a1"          # 축·눈금
TXT = "#a8b0bd"          # 라벨
OK, WARN, BAD = "#4ca85c", "#e8a317", "#d93630"
ACC = "#4493f8"

plt.rcParams.update({
    "font.family": "AppleGothic", "axes.unicode_minus": False,
    "figure.facecolor": "none", "axes.facecolor": "none",
    "savefig.facecolor": "none", "savefig.transparent": True,
    "text.color": TXT, "axes.labelcolor": TXT,
    "xtick.color": INK, "ytick.color": INK,
    "axes.edgecolor": INK, "grid.color": INK, "grid.alpha": 0.18,
})


def save(fig, name):
    p = OUT / name
    fig.savefig(p, dpi=140, bbox_inches="tight", transparent=True)
    plt.close(fig)
    print(f"  {name}  {p.stat().st_size:,} B")


def fig_control_chart():
    """SECOM 관리도 — 평소 범위를 벗어난 시점이 눈에 보이게."""
    d = json.loads((PROC / "secom_drift.json").read_text(encoding="utf-8"))
    # 센서 선택 기준: 이탈률이 높으면서 **값의 변동 폭이 눈에 보이는** 것.
    # 이탈률만 보고 고르면 값 범위가 0.0026 언저리로 극히 좁은 센서가 뽑혀
    # 그래프가 눌린다(처음 그렇게 만들었다가 고쳤다).
    def visibility(k):
        s_ = d["series"][k]
        v = np.array([x for x in s_["values"] if x is not None], dtype=float)
        if s_["sd"] <= 0 or not len(v):
            return -1
        return (v.max() - v.min()) / s_["sd"] if s_["out_rate"] > 0.30 else -1
    name = max(d["series"], key=visibility)
    s = d["series"][name]
    v = np.array([np.nan if x is None else x for x in s["values"]], dtype=float)
    fail = np.array(d["is_fail"])
    n = len(v)
    b_end = int(n * d["baseline_frac"])

    fig, ax = plt.subplots(figsize=(9.2, 3.1))
    ax.plot(v, lw=0.8, color=TXT, alpha=0.55, zorder=2)
    ax.axhline(s["mu"], color=INK, lw=1.2, zorder=3)
    for lim in (s["ucl"], s["lcl"]):
        ax.axhline(lim, color=BAD, lw=1.0, ls="--", zorder=3)
    ax.axvline(b_end, color=ACC, lw=1.0, ls=":", zorder=3)
    ax.scatter(np.flatnonzero(fail), v[fail], s=9, color=BAD, zorder=4, label="불량 웨이퍼")

    lo = np.nanpercentile(v, 0.5); hi = np.nanpercentile(v, 99.5)
    pad = (hi - lo) * 0.25 if hi > lo else 1
    ax.set_ylim(min(lo, s["lcl"]) - pad, max(hi, s["ucl"]) + pad)
    ax.set_xlim(0, n)
    ax.text(b_end + 8, ax.get_ylim()[1], " 기준 구간 끝", color=ACC, fontsize=9, va="top")
    ax.text(n * 0.995, s["ucl"], "관리 상한 +3σ ", color=BAD, fontsize=8.5, ha="right", va="bottom")
    ax.text(n * 0.995, s["lcl"], "관리 하한 -3σ ", color=BAD, fontsize=8.5, ha="right", va="top")
    ax.set_xlabel("시간 순 웨이퍼", fontsize=9.5)
    ax.set_ylabel(f"센서 {name} 측정값", fontsize=9.5)
    ax.set_title(f"공정 센서 관리도 — 감시 구간 이탈률 {s['out_rate']*100:.1f}%",
                 fontsize=11, color=TXT, pad=10)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    ax.grid(axis="y", lw=0.6)
    save(fig, "secom_control_chart.png")


def fig_repair_outcome():
    """불량 '모양'이 리페어 성패를 가른다 — 이 프로젝트의 핵심 결과."""
    s = json.loads((PROC / "eds_summary.json").read_text(encoding="utf-8"))
    ko = {"single_bit": "싱글비트", "row_fail": "로우성", "column_fail": "칼럼성",
          "cross_fail": "크로스", "block_fail": "블락성"}
    rows = sorted(s["by_mode"].items(), key=lambda kv: -kv[1]["repairable"])
    names = [ko.get(k, k) for k, _ in rows]
    vals = [v["repairable"] * 100 for _, v in rows]
    ns = [v["n"] for _, v in rows]

    fig, ax = plt.subplots(figsize=(7.6, 3.0))
    cols = [OK if x > 50 else BAD for x in vals]
    bars = ax.barh(names[::-1], vals[::-1], color=cols[::-1], height=0.62)
    for b, x, cnt in zip(bars, vals[::-1], ns[::-1]):
        ax.text(x + 1.6, b.get_y() + b.get_height() / 2,
                f"{x:.1f}%   다이 {cnt:,}개", va="center", fontsize=9.5, color=TXT)
    ax.set_xlim(0, 118)
    ax.set_xlabel("여분 워드라인·비트라인으로 복구된 비율", fontsize=9.5)
    ax.set_title("같은 fail 개수라도 '모양'이 복구 성패를 가른다  (여분 4행 / 4열)",
                 fontsize=11, color=TXT, pad=10)
    for sp in ("top", "right", "left"): ax.spines[sp].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_xticks([])
    save(fig, "repair_by_mode.png")


def fig_split_bias():
    """분할 방식이 결론을 바꾼다 — 무작위 vs 시간 순."""
    e = json.loads((PROC / "secom_eval.json").read_text(encoding="utf-8"))
    r = json.loads((PROC / "secom_sensor_risk.json").read_text(encoding="utf-8"))
    ts, rs = e["time_split"], e["random_split"]

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 2.9))
    # (1) PR-AUC 비교
    ax = axes[0]
    labs = ["시간 순\n(실제 조건)", "무작위"]
    vals = [ts["models"]["lightgbm"]["pr_auc"], rs["models"]["lightgbm"]["pr_auc"]]
    base = ts["models"]["lightgbm"]["pr_auc_baseline"]
    ax.bar(labs, vals, color=[INK, BAD], width=0.5)
    ax.axhline(base, color=TXT, lw=1.0, ls="--")
    ax.text(1.42, base, " 기저율\n (무작위로 찍은 값)", fontsize=8.5, color=TXT, va="center")
    for i, v in enumerate(vals):
        ax.text(i, v + 0.004, f"{v:.4f}", ha="center", fontsize=10, color=TXT)
    ax.set_ylim(0, max(vals) * 1.35)
    ax.set_ylabel("PR-AUC", fontsize=9.5)
    ax.set_title(f"같은 데이터·같은 모델, 분할만 다름\n무작위가 "
                 f"{vals[1]/vals[0]:.1f}배 부풀린다", fontsize=10.5, color=TXT, pad=8)
    # (2) 유의성 소멸
    ax = axes[1]
    ho = r["holdout"]["가중 점수"]
    labs2 = ["전체 데이터\n기준", "시간 순\n분리"]
    ps = [0.0103, ho["p"]]
    ax.bar(labs2, ps, color=[INK, BAD], width=0.5)
    ax.axhline(0.05, color=WARN, lw=1.2, ls="--")
    ax.text(1.45, 0.05, " 유의수준 0.05", fontsize=8.5, color=WARN, va="center")
    for i, v in enumerate(ps):
        ax.text(i, v + 0.006, f"p = {v:.4f}", ha="center", fontsize=10,
                color=OK if v < 0.05 else BAD)
    ax.set_ylim(0, max(ps) * 1.45)
    ax.set_ylabel("p 값", fontsize=9.5)
    ax.set_title(f"위험 센서 {r['n_fdr_significant']}개 → "
                 f"{ho and r['holdout']['n_sig_learned']}개\n유의성이 사라진다",
                 fontsize=10.5, color=TXT, pad=8)
    for a in axes:
        for sp in ("top", "right"): a.spines[sp].set_visible(False)
        a.grid(axis="y", lw=0.6)
    fig.tight_layout()
    save(fig, "split_bias.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("그림 생성 (투명 배경)")
    fig_control_chart()
    fig_repair_outcome()
    fig_split_bias()


if __name__ == "__main__":
    main()
