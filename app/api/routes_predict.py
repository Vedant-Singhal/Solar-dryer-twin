from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.db import crud
from app.db.session import get_db
from app.schemas import (
    PredictRequest,
    PredictResponse,
    PredictionRecord,
    TrayTemps,
)
from app.services.cache import get_cache
from app.services.physics import apply_wind_to_trays, wind_correction
from app.services.surrogate import Surrogate, SurrogateInput

router = APIRouter(prefix="/v1", tags=["predict"])


def _predict_temps_k(hf: float, porosity: float) -> tuple[tuple[float, float, float, float], bool]:
    cache = get_cache()
    cached = cache.get(hf, porosity)
    if cached is not None:
        return cached, True
    temps = Surrogate.get().predict(SurrogateInput(hf, porosity))
    cache.set(hf, porosity, temps)
    return temps, False


def _apply_physics(
    temps_k: tuple[float, float, float, float],
    ambient_c: float,
    wind_mps: float,
    heat_flux: float,
):
    """Common pipeline: K -> C, wind correction, return (corrected_c, applied_dt_k)."""
    temps_c = tuple(t - 273.15 for t in temps_k)
    wind = wind_correction(
        t_cover_c=temps_c[0],
        ambient_c=ambient_c,
        wind_mps=wind_mps,
        heat_flux_w_m2=heat_flux,
    )
    corrected = apply_wind_to_trays(temps_c, ambient_c, wind.loss_fraction)
    applied_dt_k = temps_c[0] - corrected[0]  # display value: drop seen by hottest tray
    return corrected, applied_dt_k


@router.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest, db: Session = Depends(get_db)) -> PredictResponse:
    temps_k, was_cached = _predict_temps_k(req.heat_flux, req.porosity)
    corrected, applied_dt_k = _apply_physics(temps_k, req.ambient_c, req.wind_mps, req.heat_flux)

    crud.record_prediction(
        db,
        heat_flux=req.heat_flux,
        porosity=req.porosity,
        ambient_c=req.ambient_c,
        wind_mps=req.wind_mps,
        temps_c=corrected,
        model_version=settings.model_version,
        cached=was_cached,
    )

    return PredictResponse(
        temps=TrayTemps(t1_c=corrected[0], t2_c=corrected[1], t3_c=corrected[2], t4_c=corrected[3]),
        wind_correction_k=applied_dt_k,
        model_version=settings.model_version,
        cached=was_cached,
    )


@router.get("/predictions/recent", response_model=list[PredictionRecord])
def recent(limit: int = 50, db: Session = Depends(get_db)) -> list[PredictionRecord]:
    return [PredictionRecord.model_validate(r) for r in crud.recent_predictions(db, limit=limit)]
