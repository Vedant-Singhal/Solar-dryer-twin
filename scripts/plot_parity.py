"""Generate parity plot: CFD truth vs surrogate prediction on the held-out test set.

Run from repo root:
    python scripts/plot_parity.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.train.train_surrogate import load  # noqa: E402
CSV = REPO / "Data_Raw" / "solar_dryer_ml.csv"
MODEL = REPO / "models" / "surrogate-v1.joblib"
METRICS = REPO / "models" / "surrogate-v1.metrics.json"
OUT = REPO / "figures" / "parity_plot.png"

TRAY_LABELS = ["T₁", "T₂", "T₃", "T₄"]
TRAY_COLORS = ["#FF6B35", "#F7C59F", "#8FBF9F", "#004E89"]


def main() -> None:
    df = load(CSV)
    x = df[["HeatFlux_Wm2", "Porosity"]].values
    y = df[["T1_K", "T2_K", "T3_K", "T4_K"]].values
    _, x_te, _, y_te = train_test_split(x, y, test_size=0.2, random_state=42)

    pipe = joblib.load(MODEL)
    y_pred = pipe.predict(x_te)

    metrics = json.loads(METRICS.read_text())
    mae = metrics["mae_per_tray_k"]
    r2 = metrics["r2_per_tray"]

    fig, ax = plt.subplots(figsize=(7, 7))
    for i, (label, color) in enumerate(zip(TRAY_LABELS, TRAY_COLORS)):
        ax.scatter(
            y_te[:, i], y_pred[:, i],
            label=f"{label}  (MAE={mae[i]:.2f} K, R²={r2[i]:.3f})",
            color=color, alpha=0.8, s=55, edgecolor="black", linewidth=0.4,
        )

    lo = min(y_te.min(), y_pred.min()) - 1
    hi = max(y_te.max(), y_pred.max()) + 1
    ax.plot([lo, hi], [lo, hi], "k--", lw=1, label="y = x (perfect)")

    ax.set_xlabel("CFD truth (K)", fontsize=12)
    ax.set_ylabel("Surrogate prediction (K)", fontsize=12)
    ax.set_title(
        f"Surrogate parity plot — held-out test set "
        f"(n={metrics['n_test']}, degree {metrics['degree']})",
        fontsize=12,
    )
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.95)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUT, dpi=200, bbox_inches="tight")
    print(f"saved -> {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
