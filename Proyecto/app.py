"""Dashboard UNIFRANZ: datos y modelos temporales por petición."""
import base64
import math
import re
from datetime import date, timedelta
from io import BytesIO
from threading import Lock

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
from flask import Flask, render_template, request
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
PLOT_LOCK = Lock()
MAX_RECORDS = 2000
MAX_HORIZON = 365


def blank_form():
    return {"rows": [("", "") for _ in range(10)], "bulk": "", "horizon": "7", "custom": ""}


def read_form():
    dates = request.form.getlist("date")
    counts = request.form.getlist("quantity")
    size = max(len(dates), len(counts), 10)
    rows = [(dates[i] if i < len(dates) else "", counts[i] if i < len(counts) else "") for i in range(min(size, MAX_RECORDS))]
    return {"rows": rows, "bulk": request.form.get("bulk", ""),
            "horizon": request.form.get("horizon", "7"), "custom": request.form.get("custom", ""),
            "table_overflow": max(len(dates), len(counts)) > MAX_RECORDS}


def validate(form):
    errors, records, seen = [], [], set()
    if form.get("table_overflow"):
        errors.append(f"Se admiten hasta {MAX_RECORDS} filas de tabla; reduce los registros enviados.")

    def add(raw_date, raw_count, label):
        raw_date, raw_count = raw_date.strip(), raw_count.strip()
        if not raw_date and not raw_count:
            return
        if not raw_date or not raw_count:
            errors.append(f"{label}: completa la fecha y la cantidad.")
            return
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date):
                raise ValueError
            day = date.fromisoformat(raw_date)
        except ValueError:
            errors.append(f"{label}: fecha inválida; utiliza AAAA-MM-DD.")
            return
        if not re.fullmatch(r"[0-9]+", raw_count):
            errors.append(f"{label}: la cantidad debe ser un número entero no negativo.")
            return
        # Evitar conversiones de enteros gigantes y modelos numéricamente inestables.
        if len(raw_count) > 7 or int(raw_count) > 1000000:
            errors.append(f"{label}: la cantidad máxima admitida es 1 000 000.")
            return
        if day in seen:
            errors.append(f"{label}: la fecha {raw_date} está duplicada en los datos ingresados.")
            return
        seen.add(day)
        records.append((day, int(raw_count)))

    for i, (day, count) in enumerate(form["rows"], 1):
        add(day, count, f"Fila {i}")
    for i, line in enumerate(form["bulk"].splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split(",")
        if len(parts) != 2:
            errors.append(f"Texto, línea {i}: utiliza AAAA-MM-DD,cantidad.")
        else:
            add(*parts, f"Texto, línea {i}")
    if len(records) < 3:
        errors.append("Ingresa al menos 3 registros válidos en fechas diferentes.")
    if len(records) > MAX_RECORDS:
        errors.append(f"Se admiten hasta {MAX_RECORDS} registros por análisis.")
    horizon = None
    if form["horizon"] not in ("7", "14", "30", "custom"):
        errors.append("Selecciona un horizonte válido: 7, 14, 30 o personalizado.")
    else:
        raw = form["custom"].strip() if form["horizon"] == "custom" else form["horizon"]
        if not re.fullmatch(r"[0-9]{1,3}", raw) or not 1 <= int(raw) <= MAX_HORIZON:
            errors.append("El horizonte debe ser un número entero entre 1 y 365 días.")
        else:
            horizon = int(raw)
    if records and horizon:
        try:
            max(day for day, _ in records) + timedelta(days=horizon)
        except OverflowError:
            errors.append("Las fechas futuras exceden el calendario admitido; reduce la fecha o el horizonte.")
    return sorted(records), horizon, errors[:50]


def metrics(actual, predicted):
    mse = float(mean_squared_error(actual, predicted))
    # R² no se interpreta si el objetivo observado es constante.
    r2 = float(r2_score(actual, predicted)) if len(actual) >= 2 and np.ptp(actual) > 0 else None
    return {"mae": float(mean_absolute_error(actual, predicted)), "mse": mse,
            "rmse": math.sqrt(mse), "r2": r2}


def figure_image(fig):
    with BytesIO() as buffer:
        fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight", facecolor="white")
        return base64.b64encode(buffer.getvalue()).decode("ascii")


def chart_axis(title, xlabel):
    fig = Figure(figsize=(10, 4.6), layout="constrained")
    ax = fig.subplots()
    ax.set_title(title, loc="left", fontsize=14, fontweight="bold", color="#12243c", pad=18)
    ax.set_xlabel(xlabel, color="#52647b")
    ax.set_ylabel("Objetos perdidos", color="#52647b")
    ax.set_facecolor("#f8fafc")
    ax.grid(axis="y", color="#dfe7ef", linewidth=.7)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color("#dfe7ef")
    ax.tick_params(colors="#52647b", labelsize=9)
    return fig, ax


def graphs(days, y, fitted, dates, future_dates, future):
    blue, teal, navy = "#3269e8", "#0b9e91", "#12243c"
    with PLOT_LOCK:
        fig, ax = chart_axis("Historial y ajuste lineal", "Días desde la primera fecha registrada")
        ax.scatter(days, y, c=blue, s=38, label="Registros reales", zorder=3)
        ax.plot(days, fitted, color=teal, linewidth=2.2, label="Regresión lineal (sin limitar)")
        ax.legend(frameon=False)
        first = figure_image(fig)

        fig, ax = chart_axis("Proyección de objetos perdidos", "Fecha")
        ax.scatter(dates, y, color=blue, s=30, label="Historial real", zorder=3)
        ax.plot(dates, fitted, color=navy, linewidth=1.7, label="Tendencia histórica (sin limitar)")
        ax.plot(future_dates, future, color=teal, marker="." if len(future) <= 30 else None,
                linewidth=2.2, linestyle="--", label="Estimación futura (mínimo 0)")
        boundary = mdates.date2num(dates[-1]) + .5
        ax.axvline(boundary, color="#8192a7", linestyle=":", label="Fin del historial")
        ax.axvspan(boundary, mdates.date2num(future_dates[-1]), color=teal, alpha=.06)
        locator = mdates.AutoDateLocator(minticks=3, maxticks=7)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        ax.legend(frameon=False, fontsize=9)
        second = figure_image(fig)

        # Se representan todas las observaciones; solo se reducen las etiquetas del eje.
        fig, ax = chart_axis("Valores reales frente a valores ajustados", "Fecha del registro")
        positions = np.arange(len(y))
        width = .4
        ax.bar(positions - width/2, y, width, color=blue, label="Cantidad real")
        ax.bar(positions + width/2, fitted, width, color=teal, label="Ajuste lineal (sin limitar)")
        ticks = np.unique(np.linspace(0, len(y)-1, min(len(y), 10), dtype=int))
        ax.set_xticks(ticks, [dates[i].strftime("%d/%m/%Y") for i in ticks], rotation=30, ha="right")
        ax.legend(frameon=False)
        third = figure_image(fig)
    return [first, second, third]


def analyze(records, horizon):
    frame = pd.DataFrame(records, columns=["date", "quantity"])
    dates = frame["date"].tolist()
    days = np.array([(day - dates[0]).days for day in dates], dtype=float)
    x = days.reshape(-1, 1)
    y = frame["quantity"].to_numpy(dtype=float)
    evaluation, split = None, None
    if len(y) >= 10:
        split = int(len(y) * .8)
        evaluation_model = LinearRegression().fit(x[:split], y[:split])
        evaluation = metrics(y[split:], evaluation_model.predict(x[split:]))
    # Tras evaluar el modelo temporal, ajustar el modelo final con todo el historial.
    model = LinearRegression().fit(x, y)
    fitted = model.predict(x)
    future_dates = [dates[-1] + timedelta(days=i) for i in range(1, horizon+1)]
    future_x = np.array([(day-dates[0]).days for day in future_dates], dtype=float).reshape(-1, 1)
    raw_future = model.predict(future_x)
    future = np.maximum(0, raw_future)
    if not np.all(np.isfinite(future)):
        raise ValueError("El modelo produjo valores no finitos.")
    slope, intercept = float(model.coef_[0]), float(model.intercept_)
    # Umbral explícito: cambio menor al 1 % de max(promedio, 1) durante el historial.
    near_zero = abs(slope) * max(days[-1], 1) < .01 * max(float(y.mean()), 1)
    trend = "No se observa una tendencia lineal importante" if near_zero else (
        "El modelo muestra una tendencia creciente" if slope > 0 else "El modelo muestra una tendencia decreciente")
    return {"count": len(y), "average": float(y.mean()), "slope": slope, "intercept": intercept,
            "equation": f"Y = {slope:.6g}X {'+' if intercept >= 0 else '−'} {abs(intercept):.6g}",
            "fit": metrics(y, fitted), "evaluation": evaluation, "train_count": split,
            "test_count": len(y)-split if split else None, "origin": dates[0], "last": dates[-1],
            "horizon": horizon, "total": float(future.sum()), "future_average": float(future.mean()),
            "predictions": list(zip(future_dates, future.tolist())), "trend": trend,
            "clipped": bool(np.any(raw_future < 0)),
            "charts": graphs(days, y, fitted, dates, future_dates, future)}


@app.get("/")
def index():
    return render_template("index.html", form=blank_form(), errors=[], result=None)


@app.post("/predict")
def predict():
    form = read_form()
    records, horizon, errors = validate(form)
    if errors:
        return render_template("index.html", form=form, errors=errors, result=None), 422
    try:
        result = analyze(records, horizon)
    except Exception:
        app.logger.exception("No se pudo realizar el análisis")
        return render_template("index.html", form=form, result=None,
            errors=["No se pudo completar el análisis. Revisa los datos e intenta nuevamente."]), 500
    return render_template("index.html", form=form, errors=[], result=result)


@app.errorhandler(413)
def too_large(error):
    return render_template("index.html", form=blank_form(), result=None,
        errors=["La solicitud es demasiado grande. Se admite hasta 1 MB y 2 000 registros."]), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
