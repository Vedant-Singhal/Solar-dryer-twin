from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.db import crud
from app.db.session import get_db
from app.schemas import SimulateRequest, SimulateResponse, TrayDrying, TrayTemps
from app.services.physics import lewis_drying_time, thermal_efficiency
from app.api.routes_predict import _apply_physics, _predict_temps_k

router = APIRouter(prefix="/v1", tags=["simulate"])


@router.post("/simulate", response_model=SimulateResponse)
def simulate(req: SimulateRequest, db: Session = Depends(get_db)) -> SimulateResponse:
    temps_k, was_cached = _predict_temps_k(req.heat_flux, req.porosity)
    corrected, applied_dt_k = _apply_physics(temps_k, req.ambient_c, req.wind_mps, req.heat_flux)

    trays = []
    for i, t_c in enumerate(corrected, start=1):
        time_h, k_per_h = lewis_drying_time(
            tray_temp_c=t_c,
            crop=req.crop,
            initial_moisture_db=req.initial_moisture_db,
            target_moisture_db=req.target_moisture_db,
        )
        trays.append(TrayDrying(tray=i, temp_c=t_c, drying_time_hours=time_h, rate_constant_per_hour=k_per_h))

    eff = thermal_efficiency(t_outlet_c=corrected[3], t_inlet_c=req.ambient_c, heat_flux=req.heat_flux)

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

    return SimulateResponse(
        temps=TrayTemps(t1_c=corrected[0], t2_c=corrected[1], t3_c=corrected[2], t4_c=corrected[3]),
        wind_correction_k=applied_dt_k,
        trays=trays,
        thermal_efficiency=eff,
        model_version=settings.model_version,
    )
