from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import threading

import joblib
import numpy as np

from app.config import settings


@dataclass(frozen=True)
class SurrogateInput:
    heat_flux: float
    porosity: float


class Surrogate:
    """Thin wrapper around the sklearn pipeline. Loaded once per worker."""

    _instance: "Surrogate | None" = None
    _lock = threading.Lock()

    def __init__(self, model_path: Path, version: str) -> None:
        self._pipeline = joblib.load(model_path)
        self.version = version

    @classmethod
    def get(cls) -> "Surrogate":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(settings.model_path, settings.model_version)
        return cls._instance

    def predict(self, x: SurrogateInput) -> tuple[float, float, float, float]:
        # Pipeline returns Kelvin; we keep K here and convert at the boundary.
        out = self._pipeline.predict(np.array([[x.heat_flux, x.porosity]]))[0]
        return float(out[0]), float(out[1]), float(out[2]), float(out[3])
