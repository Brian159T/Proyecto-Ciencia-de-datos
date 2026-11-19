"""Guardado opcional de análisis en PostgreSQL.

La aplicación funciona sin base de datos. Solo cuando el usuario pulsa
«Guardar predicción» se insertan el análisis, sus observaciones y sus
predicciones en las tablas definidas en schema.sql.
"""
import os


def _load_env_file():
    """Carga .env sin dependencias externas (no sobrescribe variables existentes)."""
    path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()


def is_configured():
    """Indica si hay una cadena de conexión o una contraseña configurada."""
    return bool(DATABASE_URL or os.environ.get("PGPASSWORD", "").strip())


def connect(**kwargs):
    """Abre una conexión usando DATABASE_URL o las variables PG* del entorno."""
    import psycopg

    if DATABASE_URL:
        return psycopg.connect(DATABASE_URL, connect_timeout=5, **kwargs)
    return psycopg.connect(connect_timeout=5, **kwargs)


def save_analysis(records, result):
    """Guarda un análisis completo en una sola transacción.

    Devuelve el id generado en la tabla analyses.
    """
    if not is_configured():
        raise RuntimeError("El guardado no está configurado. Define PGPASSWORD o DATABASE_URL en .env y reinicia la aplicación.")

    try:
        from psycopg.types.json import Jsonb
    except ImportError as exc:
        raise RuntimeError("Falta el controlador psycopg. Ejecuta: pip install -r requirements.txt.") from exc

    evaluation = result.get("evaluation") or {}
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO analyses (
                    app_version, model_name, model_config, origin_date, last_date,
                    horizon, record_count, average, slope, intercept, equation,
                    trend, trend_direction, near_zero, clipped, quality, quality_level,
                    fit_r2, fit_mae, fit_mse, fit_rmse,
                    train_count, test_count, eval_r2, eval_mae, eval_mse, eval_rmse,
                    total, future_average, first_pred, last_pred
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    "1.0",
                    "linear_regression",
                    Jsonb({"features": ["dias"]}),
                    result["origin"],
                    result["last"],
                    result["horizon"],
                    result["count"],
                    result["average"],
                    result["slope"],
                    result["intercept"],
                    result["equation"],
                    result["trend"],
                    result["trend_direction"],
                    result["near_zero"],
                    result["clipped"],
                    result["quality"],
                    result["quality_level"],
                    result["fit"]["r2"],
                    result["fit"]["mae"],
                    result["fit"]["mse"],
                    result["fit"]["rmse"],
                    result["train_count"],
                    result["test_count"],
                    evaluation.get("r2"),
                    evaluation.get("mae"),
                    evaluation.get("mse"),
                    evaluation.get("rmse"),
                    result["total"],
                    result["future_average"],
                    result["first_pred"],
                    result["last_pred"],
                ),
            )
            analysis_id = cursor.fetchone()[0]
            cursor.executemany(
                """
                INSERT INTO analysis_records (analysis_id, observation_date, quantity, source)
                VALUES (%s, %s, %s, %s)
                """,
                [(analysis_id, day, quantity, "mixto") for day, quantity in records],
            )
            cursor.executemany(
                """
                INSERT INTO analysis_predictions (analysis_id, forecast_date, raw_value, predicted_value)
                VALUES (%s, %s, %s, %s)
                """,
                [(analysis_id, day, float(raw), max(0.0, float(raw)))
                 for day, raw in result["raw_predictions"]],
            )
    return analysis_id
