from pathlib import Path
import pandas as pd

from app.train.train_surrogate import load, train


def test_train_meets_acceptance():
    csv = Path("Data_Raw/solar_dryer_ml.csv")
    if not csv.exists():
        import pytest
        pytest.skip("dataset not available")
    df = load(csv)
    _, metrics = train(df, degree=3)
    # Per-tray MAE is the engineering criterion. Overall R^2 is misleading on
    # this dataset because T4 has the smallest variance.
    assert max(metrics["mae_per_tray_k"]) < 0.5
    assert min(metrics["r2_per_tray"]) > 0.98


def test_monotonicity_in_predictions():
    """Sanity check from dossier sec 5: T1 > T2 > T3 > T4 must always hold."""
    csv = Path("Data_Raw/solar_dryer_ml.csv")
    if not csv.exists():
        import pytest
        pytest.skip("dataset not available")
    df = load(csv)
    pipe, _ = train(df, degree=3)

    grid = pd.DataFrame(
        [(hf, p) for hf in [350, 500, 650, 800] for p in [0.55, 0.7, 0.85]],
        columns=["HeatFlux_Wm2", "Porosity"],
    )
    pred = pipe.predict(grid.values)
    for row in pred:
        assert row[0] > row[1] > row[2] > row[3], f"monotonicity broken: {row}"
