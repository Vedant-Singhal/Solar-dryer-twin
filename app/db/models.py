from datetime import datetime
from sqlalchemy import Float, Integer, String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    heat_flux: Mapped[float] = mapped_column(Float)
    porosity: Mapped[float] = mapped_column(Float)
    ambient_c: Mapped[float] = mapped_column(Float)
    wind_mps: Mapped[float] = mapped_column(Float)

    t1_c: Mapped[float] = mapped_column(Float)
    t2_c: Mapped[float] = mapped_column(Float)
    t3_c: Mapped[float] = mapped_column(Float)
    t4_c: Mapped[float] = mapped_column(Float)

    model_version: Mapped[str] = mapped_column(String(16), index=True)
    cached: Mapped[int] = mapped_column(Integer, default=0)  # 0/1 for analytics

    __table_args__ = (
        Index("ix_predictions_inputs", "heat_flux", "porosity"),
    )
