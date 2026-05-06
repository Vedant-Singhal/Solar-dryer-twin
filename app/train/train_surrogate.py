"""Train the polynomial surrogate from the canonical CFD CSV.

Run:
    python -m app.train.train_surrogate \
        --csv Data_Raw/solar_dryer_ml.csv --out models/surrogate-v1.joblib
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures


COLS = ["Name", "HeatFlux_Wm2", "Porosity", "T1_K", "T2_K", "T3_K", "T4_K"]


def load(csv: Path) -> pd.DataFrame:
    df = pd.read_csv(csv, comment="#")
    df.columns = COLS
    return df


def train(df: pd.DataFrame, degree: int = 3, seed: int = 42) -> tuple[object, dict]:
    x = df[["HeatFlux_Wm2", "Porosity"]].values
    y = df[["T1_K", "T2_K", "T3_K", "T4_K"]].values
    x_tr, x_te, y_tr, y_te = train_test_split(x, y, test_size=0.2, random_state=seed)

    pipe = make_pipeline(PolynomialFeatures(degree=degree, include_bias=False), LinearRegression())
    pipe.fit(x_tr, y_tr)

    y_pred = pipe.predict(x_te)
    metrics = {
        "degree": degree,
        "r2_overall": float(r2_score(y_te, y_pred)),
        "r2_per_tray": [float(r2_score(y_te[:, i], y_pred[:, i])) for i in range(4)],
        "mae_per_tray_k": [float(mean_absolute_error(y_te[:, i], y_pred[:, i])) for i in range(4)],
        "n_train": int(len(x_tr)),
        "n_test": int(len(x_te)),
    }
    return pipe, metrics


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--degree", type=int, default=3)
    args = ap.parse_args()

    df = load(args.csv)
    pipe, metrics = train(df, degree=args.degree)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, args.out)

    metrics_path = args.out.with_suffix(".metrics.json")
    metrics_path.write_text(json.dumps(metrics, indent=2))

    print(f"saved model -> {args.out}")
    print(f"metrics      -> {metrics_path}")
    print(json.dumps(metrics, indent=2))

    # Acceptance gate. Per-tray MAE is the real success criterion (dossier sec 8).
    # Overall R^2 is misleading here because T4's variance is small, so even sub-K
    # errors look bad in R^2 terms. We gate on what actually matters:
    #   - per-tray MAE  < 0.5 K   (engineering accuracy on each tray)
    #   - per-tray R^2  > 0.98    (relative fit, robust to small-variance outputs)
    max_mae = max(metrics["mae_per_tray_k"])
    min_r2 = min(metrics["r2_per_tray"])
    assert max_mae < 0.5, f"per-tray MAE {max_mae:.3f} K exceeds 0.5 K"
    assert min_r2 > 0.98, f"per-tray R2 {min_r2:.4f} below 0.98"


if __name__ == "__main__":
    main()
