from sqlalchemy.orm import Session

from app.db.models import Prediction


def record_prediction(
    db: Session,
    *,
    heat_flux: float,
    porosity: float,
    ambient_c: float,
    wind_mps: float,
    temps_c: tuple[float, float, float, float],
    model_version: str,
    cached: bool,
) -> Prediction:
    row = Prediction(
        heat_flux=heat_flux,
        porosity=porosity,
        ambient_c=ambient_c,
        wind_mps=wind_mps,
        t1_c=temps_c[0],
        t2_c=temps_c[1],
        t3_c=temps_c[2],
        t4_c=temps_c[3],
        model_version=model_version,
        cached=int(cached),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def recent_predictions(db: Session, limit: int = 50) -> list[Prediction]:
    return (
        db.query(Prediction)
        .order_by(Prediction.created_at.desc())
        .limit(limit)
        .all()
    )
