from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

# Disable pydantic's "model_*" protected namespace globally for this module —
# the domain uses model_version/model_path naturally.
_BASE_CFG = ConfigDict(protected_namespaces=())

CropType = Literal["tomato", "mango", "chilli", "onion"]


class PredictRequest(BaseModel):
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={"example": {"heat_flux": 600, "porosity": 0.7, "ambient_c": 25, "wind_mps": 2}},
    )
    heat_flux: float = Field(..., ge=300, le=800, description="Solar heat flux on absorber, W/m^2")
    porosity: float = Field(..., ge=0.5, le=0.9, description="Crop porosity, dimensionless")
    ambient_c: float = Field(25.0, ge=-10, le=55)
    wind_mps: float = Field(0.0, ge=0, le=20)


class TrayTemps(BaseModel):
    t1_c: float
    t2_c: float
    t3_c: float
    t4_c: float


class PredictResponse(BaseModel):
    model_config = _BASE_CFG
    temps: TrayTemps
    wind_correction_k: float
    model_version: str
    cached: bool


class SimulateRequest(PredictRequest):
    crop: CropType = "tomato"
    initial_moisture_db: float = Field(9.0, gt=0, le=15, description="Initial dry-basis moisture")
    target_moisture_db: float = Field(0.15, gt=0, le=1.0)


class TrayDrying(BaseModel):
    tray: int
    temp_c: float
    drying_time_hours: float
    rate_constant_per_hour: float


class SimulateResponse(BaseModel):
    model_config = _BASE_CFG
    temps: TrayTemps
    wind_correction_k: float
    trays: list[TrayDrying]
    thermal_efficiency: float
    model_version: str


class PredictionRecord(BaseModel):
    id: int
    created_at: datetime
    heat_flux: float
    porosity: float
    ambient_c: float
    wind_mps: float
    t1_c: float
    t2_c: float
    t3_c: float
    t4_c: float
    model_version: str

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
