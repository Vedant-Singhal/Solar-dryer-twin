# Solar Dryer Digital Twin — Production Service

Inference API for the CFD-trained surrogate of the IIT Delhi solar air dryer.
Given `(heat_flux, porosity, ambient_c, wind_mps)` returns 4 tray temperatures
and (with `/simulate`) per-tray Lewis drying times + thermal efficiency.

## System architecture

```
Client (Streamlit / React / IoT)
        │  HTTPS JSON
        ▼
  FastAPI (uvicorn, k8s HPA)
        │
  ┌─────┼──────────┬─────────────┐
  │     │          │             │
  ▼     ▼          ▼             ▼
Surrogate  Physics  Redis cache  Postgres (history)
(joblib)   (numpy)  (LRU)        (analytics, audit)

Offline: CSV ──► train_surrogate.py ──► models/surrogate-v{N}.joblib
```

### Data flow (single request)
1. `POST /v1/simulate` validated by pydantic (range checks per CFD sweep envelope).
2. Cache key `pred:{model_version}:{round(hf,2)}:{round(p,2)}` → if hit, skip surrogate.
3. Surrogate (in-process polynomial pipeline) → 4 tray temps in K.
4. Physics layer applies wind correction (flat-plate Nu) and Lewis kinetics per crop.
5. Row appended to `predictions` table (audit + retraining flywheel).
6. Response serialized.

### Why these picks
| Layer | Choice | Reason |
|---|---|---|
| Inference | sklearn polynomial in-process | model is 4 KB; network hop to a model server costs more than the math |
| API | FastAPI | async + pydantic validation + free OpenAPI |
| Cache | Redis LRU | rounded inputs → very high hit rate; survives a pod restart |
| DB | Postgres | fixed schema, analytical queries on `(heat_flux, porosity)` distribution |
| Telemetry | Prometheus `/metrics` | counters + latency histogram per route |
| Container | distroless-ish slim, non-root | small attack surface, k8s-friendly |

### Scaling
- **Latency**: p50 < 5 ms warm-cache, p99 < 50 ms cold (single-shot polynomial eval).
- **Horizontal**: stateless workers; HPA on RPS or CPU.
- **Model lifecycle**: `DRYER_MODEL_VERSION` controls the served artifact; deploy a new version side-by-side and shift traffic at the LB.
- **Data flywheel**: `predictions` table reveals the actual `(I, ε)` query distribution → informs where to densify the next CFD sweep.

## API

| Verb | Path | Purpose |
|---|---|---|
| `GET` | `/healthz` | liveness |
| `GET` | `/readyz` | model + db + redis readiness |
| `GET` | `/metrics` | Prometheus scrape |
| `POST` | `/v1/predict` | tray temps only |
| `POST` | `/v1/simulate` | tray temps + drying time + efficiency |
| `GET` | `/v1/predictions/recent?limit=N` | audit feed |

OpenAPI / Swagger UI at `/docs`.

### `POST /v1/predict`
```json
{ "heat_flux": 600, "porosity": 0.7, "ambient_c": 25, "wind_mps": 2 }
```
→
```json
{
  "temps": { "t1_c": 56.2, "t2_c": 46.1, "t3_c": 39.6, "t4_c": 35.1 },
  "wind_correction_k": 1.34,
  "model_version": "v1",
  "cached": false
}
```

### `POST /v1/simulate`
Same as above plus `crop`, `initial_moisture_db`, `target_moisture_db`. Returns per-tray
drying time (hours) from the Lewis thin-layer model with Arrhenius `k(T)`.

## Database schema

```sql
CREATE TABLE predictions (
    id            SERIAL PRIMARY KEY,
    created_at    TIMESTAMP NOT NULL DEFAULT now(),
    heat_flux     DOUBLE PRECISION NOT NULL,
    porosity      DOUBLE PRECISION NOT NULL,
    ambient_c     DOUBLE PRECISION NOT NULL,
    wind_mps      DOUBLE PRECISION NOT NULL,
    t1_c          DOUBLE PRECISION NOT NULL,
    t2_c          DOUBLE PRECISION NOT NULL,
    t3_c          DOUBLE PRECISION NOT NULL,
    t4_c          DOUBLE PRECISION NOT NULL,
    model_version VARCHAR(16) NOT NULL,
    cached        SMALLINT NOT NULL DEFAULT 0
);
CREATE INDEX ix_predictions_created_at ON predictions(created_at);
CREATE INDEX ix_predictions_model_version ON predictions(model_version);
CREATE INDEX ix_predictions_inputs ON predictions(heat_flux, porosity);
```

The CFD design points themselves stay in `Data_Raw/` and source control — they are
the model's training set, not online state.

## Caching strategy

- **Key**: `pred:{model_version}:{round(hf,2)}:{round(porosity,2)}` — model version is part of the key so version bumps invalidate automatically.
- **TTL**: 1 hour (configurable). Surrogate is deterministic, so TTL only exists to bound memory.
- **Eviction**: Redis `allkeys-lru` with 128 MB cap.
- **Invalidation**: implicit via `model_version` change; no explicit purge needed.
- **Failure mode**: cache errors are swallowed (best-effort). The system stays correct without Redis, only slower.

## Local development

```bash
# 1. Train the model from the CFD dataset
python -m app.train.train_surrogate \
    --csv Data_Raw/solar_dryer_ml.csv \
    --out models/surrogate-v1.joblib

# 2. Bring up dependencies + API
docker compose up --build

# 3. Try it
curl -X POST localhost:8000/v1/simulate \
    -H 'content-type: application/json' \
    -d '{"heat_flux":700,"porosity":0.7,"ambient_c":28,"wind_mps":3,"crop":"tomato"}'
```

## Tests

```bash
pytest tests/test_physics.py            # pure-function checks, no deps
pytest tests/test_surrogate.py          # needs CSV
pytest tests/test_api.py                # needs model + redis + postgres
```

## Repo layout

```
app/
  main.py                  # FastAPI app, lifespan, middleware, /metrics
  config.py                # pydantic-settings, env-driven
  schemas.py               # request/response models
  api/
    routes_health.py
    routes_predict.py
    routes_simulate.py
  services/
    surrogate.py           # joblib pipeline wrapper, singleton
    physics.py             # wind correction, Lewis kinetics, efficiency
    cache.py               # Redis LRU prediction cache
  db/
    session.py             # engine + Base + get_db
    models.py              # Prediction ORM model
    crud.py                # record_prediction, recent_predictions
  train/
    train_surrogate.py     # CSV -> joblib + metrics.json (R2 / MAE gate)
tests/
models/                    # generated artifacts
Data_Raw/                  # CFD CSV + images (training input)
Dockerfile, docker-compose.yml
```
