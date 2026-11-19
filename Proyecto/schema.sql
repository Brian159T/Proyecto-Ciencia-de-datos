-- Esquema de persistencia de la aplicación de objetos perdidos.
-- PostgreSQL 12+.
--
-- Uso:
--   createdb -U postgres objetos_perdidos
--   psql -U postgres -d objetos_perdidos -f schema.sql
--
-- Después define la variable de entorno:
--   DATABASE_URL=postgresql://postgres:TU_CLAVE@localhost:5432/objetos_perdidos

BEGIN;

CREATE TABLE IF NOT EXISTS analyses (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at      timestamptz NOT NULL DEFAULT now(),
    app_version     text NOT NULL DEFAULT '1.0',
    model_name      text NOT NULL DEFAULT 'linear_regression',
    model_config    jsonb NOT NULL DEFAULT '{}'::jsonb,
    origin_date     date NOT NULL,
    last_date       date NOT NULL,
    horizon         integer NOT NULL CHECK (horizon BETWEEN 1 AND 365),
    record_count    integer NOT NULL CHECK (record_count >= 3),
    average         numeric(14,4) NOT NULL,
    slope           numeric(16,10) NOT NULL,
    intercept       numeric(16,6) NOT NULL,
    equation        text NOT NULL,
    trend           text NOT NULL,
    trend_direction text NOT NULL CHECK (trend_direction IN ('creciente','decreciente','estable')),
    near_zero       boolean NOT NULL DEFAULT false,
    clipped         boolean NOT NULL DEFAULT false,
    quality         text NOT NULL,
    quality_level   text NOT NULL CHECK (quality_level IN ('good','mid','low','neutral')),
    fit_r2          numeric(12,8),
    fit_mae         numeric(16,6) NOT NULL,
    fit_mse         numeric(20,6) NOT NULL,
    fit_rmse        numeric(16,6) NOT NULL,
    train_count     integer CHECK (train_count IS NULL OR train_count > 0),
    test_count      integer CHECK (test_count IS NULL OR test_count > 0),
    eval_r2         numeric(12,8),
    eval_mae        numeric(16,6),
    eval_mse        numeric(20,6),
    eval_rmse       numeric(16,6),
    total           numeric(18,4) NOT NULL,
    future_average  numeric(16,6) NOT NULL,
    first_pred      numeric(16,6) NOT NULL,
    last_pred       numeric(16,6) NOT NULL,
    notes           text,
    CONSTRAINT analyses_dates_ck CHECK (last_date >= origin_date)
);

CREATE TABLE IF NOT EXISTS analysis_records (
    analysis_id      bigint NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    observation_date date NOT NULL,
    quantity         integer NOT NULL CHECK (quantity BETWEEN 0 AND 1000000),
    source           text NOT NULL DEFAULT 'tabla'
                     CHECK (source IN ('tabla','texto','excel','csv','mixto')),
    PRIMARY KEY (analysis_id, observation_date)
);

ALTER TABLE analysis_records DROP CONSTRAINT IF EXISTS analysis_records_source_check;
ALTER TABLE analysis_records ADD CONSTRAINT analysis_records_source_check
    CHECK (source IN ('tabla','texto','excel','csv','mixto'));

CREATE TABLE IF NOT EXISTS analysis_predictions (
    analysis_id     bigint NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    forecast_date   date NOT NULL,
    raw_value       numeric(18,6) NOT NULL,
    predicted_value numeric(18,6) NOT NULL,
    PRIMARY KEY (analysis_id, forecast_date),
    CONSTRAINT predictions_clip_ck CHECK (predicted_value = GREATEST(raw_value, 0))
);

CREATE INDEX IF NOT EXISTS analyses_created_at_idx ON analyses (created_at DESC);
CREATE INDEX IF NOT EXISTS analyses_last_date_idx ON analyses (last_date DESC);
CREATE INDEX IF NOT EXISTS analysis_records_date_idx ON analysis_records (observation_date);
CREATE INDEX IF NOT EXISTS analysis_predictions_date_idx ON analysis_predictions (forecast_date);

COMMENT ON TABLE analyses IS 'Cabecera de cada ejecución guardada del modelo de regresión lineal.';
COMMENT ON TABLE analysis_records IS 'Observaciones reales usadas para entrenar el análisis guardado.';
COMMENT ON TABLE analysis_predictions IS 'Predicciones diarias generadas por un análisis guardado.';
COMMENT ON COLUMN analysis_predictions.raw_value IS 'Salida lineal antes de recortar a cero.';
COMMENT ON COLUMN analysis_predictions.predicted_value IS 'Valor mostrado y totalizado, nunca negativo.';
COMMENT ON COLUMN analyses.trend_direction IS 'Dirección normalizada: creciente, decreciente o estable.';

CREATE OR REPLACE VIEW v_analysis_summary AS
SELECT a.id,
       a.created_at,
       a.origin_date,
       a.last_date,
       a.horizon,
       a.record_count,
       a.slope,
       a.fit_r2,
       a.eval_r2,
       a.total,
       a.future_average,
       a.trend_direction,
       a.quality_level,
       count(p.forecast_date) AS prediction_count
FROM analyses a
LEFT JOIN analysis_predictions p ON p.analysis_id = a.id
GROUP BY a.id;

COMMIT;
