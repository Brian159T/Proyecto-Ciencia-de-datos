"""Dashboard UNIFRANZ: datos y modelos temporales por petición."""
import base64
import csv
import math
import re
from datetime import date, datetime, timedelta
from io import BytesIO, StringIO
from threading import Lock

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
from openpyxl import load_workbook
from flask import Flask, render_template, request
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

import database

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024
PLOT_LOCK = Lock()
MAX_RECORDS = 2000
MAX_HORIZON = 365


def blank_form():
    return {"rows": [("", "") for _ in range(10)], "bulk": "", "horizon": "7", "custom": "",
            "excel": [], "excel_name": "", "excel_errors": []}


def form_from_compact(raw, raw_horizon):
    """Reconstruye un formulario a partir de los registros ya validados."""
    rows = []
    for chunk in (raw or "").split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "," in chunk:
            day, quantity = chunk.rsplit(",", 1)
            rows.append((day.strip(), quantity.strip()))
        else:
            rows.append((chunk, ""))
    raw_horizon = (raw_horizon or "").strip()
    horizon = raw_horizon if raw_horizon in ("7", "14", "30") else "custom"
    custom = "" if horizon != "custom" else raw_horizon
    return {"rows": rows, "bulk": "", "horizon": horizon, "custom": custom,
            "excel": [], "excel_name": "", "excel_errors": [], "table_overflow": False}


def render_page(form, errors, result=None, status=200, save_message=None, save_error=None):
    return render_template("index.html", form=form, errors=errors, result=result,
                           save_enabled=database.is_configured(),
                           save_message=save_message, save_error=save_error), status


def excel_date(value):
    """Convierte una fecha de Excel o CSV a AAAA-MM-DD (o texto original si no se reconoce)."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    match = re.fullmatch(r"(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})", text)
    if match:
        return f"{match[1]}-{int(match[2]):02d}-{int(match[3]):02d}"
    match = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", text)
    if match:
        return f"{match[3]}-{int(match[2]):02d}-{int(match[1]):02d}"
    return text


def excel_count(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    match = re.fullmatch(r"(\d+)\.0+", text)
    return match.group(1) if match else text


def read_excel(upload):
    """Lee la primera hoja (columna A: fecha, columna B: cantidad). Devuelve (filas, errores)."""
    name = upload.filename or ""
    if not name.lower().endswith(".xlsx"):
        return [], ["El archivo debe tener formato Excel .xlsx."]
    rows = []
    try:
        upload.stream.seek(0)
        workbook = load_workbook(BytesIO(upload.stream.read()), read_only=True, data_only=True)
        sheet = workbook.worksheets[0]
        for row in sheet.iter_rows(min_row=1, max_col=2, values_only=True):
            first, second = (list(row) + [None, None])[:2]
            if first is None and second is None:
                continue
            if not rows and isinstance(first, str) and first.strip() and not re.search(r"\d", first):
                continue  # encabezado de columnas
            if len(rows) >= MAX_RECORDS + 1:
                return rows, [f"El archivo supera el máximo de {MAX_RECORDS} registros."]
            rows.append((excel_date(first) if first is not None else "",
                         excel_count(second) if second is not None else ""))
        workbook.close()
    except Exception:
        return [], ["No se pudo leer el archivo Excel. Verifica que sea un .xlsx válido."]
    if not rows:
        return [], ["El archivo Excel no contiene datos en las columnas A (fecha) y B (cantidad)."]
    return rows, []


def read_csv(upload):
    """Lee un CSV (columna A: fecha, columna B: cantidad). Devuelve (filas, errores)."""
    try:
        raw = upload.stream.read()
    except Exception:
        return [], ["No se pudo leer el archivo CSV."]
    text = None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        return [], ["No se pudo leer el archivo CSV. Guarda el archivo en UTF-8."]
    sample = text[:4096]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except csv.Error:
        delimiter = ","
    rows = []
    try:
        for row in csv.reader(StringIO(text), delimiter=delimiter):
            first = row[0] if len(row) > 0 else ""
            second = row[1] if len(row) > 1 else ""
            if not first.strip() and not second.strip():
                continue
            if not rows and first.strip() and not re.search(r"\d", first):
                continue  # encabezado de columnas
            if len(rows) >= MAX_RECORDS + 1:
                return rows, [f"El archivo supera el máximo de {MAX_RECORDS} registros."]
            rows.append((excel_date(first), excel_count(second)))
    except csv.Error:
        return [], ["No se pudo interpretar el archivo CSV. Verifica el formato."]
    if not rows:
        return [], ["El archivo CSV no contiene datos en las columnas A (fecha) y B (cantidad)."]
    return rows, []


def read_upload(upload):
    """Lee un .xlsx o .csv y devuelve (filas, errores)."""
    name = (upload.filename or "").lower()
    if name.endswith(".csv"):
        return read_csv(upload)
    if name.endswith(".xlsx"):
        return read_excel(upload)
    return [], ["El archivo debe ser Excel .xlsx o CSV .csv."]


def read_form():
    dates = request.form.getlist("date")
    counts = request.form.getlist("quantity")
    size = max(len(dates), len(counts), 10)
    rows = [(dates[i] if i < len(dates) else "", counts[i] if i < len(counts) else "") for i in range(min(size, MAX_RECORDS))]
    excel, excel_errors, excel_name = [], [], ""
    upload = request.files.get("excel")
    if upload and upload.filename:
        excel_name = upload.filename
        excel, excel_errors = read_upload(upload)
    return {"rows": rows, "bulk": request.form.get("bulk", ""),
            "horizon": request.form.get("horizon", "7"), "custom": request.form.get("custom", ""),
            "excel": excel, "excel_name": excel_name, "excel_errors": excel_errors,
            "table_overflow": max(len(dates), len(counts)) > MAX_RECORDS}


def validate(form):
    errors, records, seen, duplicates = [], [], {}, []
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
        quantity = int(raw_count)
        if day in seen:
            origin_label, origin_quantity = seen[day]
            if quantity != origin_quantity:
                errors.append(f"{label}: la fecha {raw_date} ya está registrada en {origin_label} "
                              f"con otra cantidad ({origin_quantity}).")
            else:
                duplicates.append(raw_date)
            return
        seen[day] = (label, quantity)
        records.append((day, quantity))

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
    errors.extend(form.get("excel_errors", []))
    file_label = "CSV" if form.get("excel_name", "").lower().endswith(".csv") else "Excel"
    for i, (raw_date, raw_count) in enumerate(form.get("excel", []), 1):
        add(raw_date, raw_count, f"{file_label}, fila {i}")
    if duplicates:
        total = len(duplicates)
        form["duplicate_notice"] = (
            f"Se omitió 1 fecha duplicada en los datos ingresados; se conservó el primer valor."
            if total == 1 else
            f"Se omitieron {total} fechas duplicadas en los datos ingresados; se conservó el primer valor."
        )
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
    if near_zero:
        trend_direction = "estable"
        trend = "No se observa una tendencia lineal importante"
    elif slope > 0:
        trend_direction = "creciente"
        trend = "El modelo muestra una tendencia creciente"
    else:
        trend_direction = "decreciente"
        trend = "El modelo muestra una tendencia decreciente"
    r2 = metrics(y, fitted)["r2"]
    quality = ("Sin variación para evaluar", "neutral") if r2 is None else (
        ("Ajuste fuerte", "good") if r2 >= .7 else ("Ajuste moderado", "mid") if r2 >= .4 else ("Ajuste débil", "low"))
    return {"quality": quality[0], "quality_level": quality[1], "count": len(y), "average": float(y.mean()), "slope": slope, "intercept": intercept,
            "equation": f"Y = {slope:.6g}X {'+' if intercept >= 0 else '−'} {abs(intercept):.6g}",
            "fit": metrics(y, fitted), "evaluation": evaluation, "train_count": split,
            "test_count": len(y)-split if split else None, "origin": dates[0], "last": dates[-1],
            "horizon": horizon, "total": float(future.sum()), "future_average": float(future.mean()),
            "predictions": list(zip(future_dates, future.tolist())), "trend": trend,
            "trend_direction": trend_direction, "near_zero": near_zero,
            "raw_predictions": list(zip(future_dates, raw_future.tolist())),
            "records_compact": ";".join(f"{day.isoformat()},{quantity}" for day, quantity in records),
            "peak": float(y.max()), "peak_date": dates[int(y.argmax())], "first_pred": float(future[0]),
            "last_pred": float(future[-1]), "daily_change": slope,
            "clipped": bool(np.any(raw_future < 0)),
            "charts": graphs(days, y, fitted, dates, future_dates, future)}


@app.get("/")
def index():
    return render_page(blank_form(), [])


@app.post("/predict")
def predict():
    form = read_form()
    records, horizon, errors = validate(form)
    if errors:
        return render_page(form, errors, status=422)
    try:
        result = analyze(records, horizon)
    except Exception:
        app.logger.exception("No se pudo realizar el análisis")
        return render_page(form, ["No se pudo completar el análisis. Revisa los datos e intenta nuevamente."], status=500)
    return render_page(form, [], result)


@app.post("/save")
def save_prediction():
    form = form_from_compact(request.form.get("records", ""), request.form.get("horizon", "7"))
    records, horizon, errors = validate(form)
    if errors:
        return render_page(form, errors, status=422)
    try:
        result = analyze(records, horizon)
    except Exception:
        app.logger.exception("No se pudo recalcular el análisis antes de guardar")
        return render_page(form, ["No se pudo preparar la predicción para guardar. Intenta nuevamente."], status=500)
    try:
        analysis_id = database.save_analysis(records, result)
    except RuntimeError as error:
        return render_page(form, [], result, status=503, save_error=str(error))
    except Exception:
        app.logger.exception("No se pudo guardar el análisis en PostgreSQL")
        return render_page(form, [], result, status=503,
            save_error="No se pudo guardar la predicción en la base de datos. Revisa la conexión e intenta nuevamente.")
    return render_page(form, [], result,
        save_message=(f"Identificador #{analysis_id}. Se almacenaron {result['count']} observaciones "
                      f"históricas y {result['horizon']} días de proyección en PostgreSQL."))


@app.errorhandler(413)
def too_large(error):
    return render_page(blank_form(),
        ["La solicitud es demasiado grande. Se admiten hasta 3 MB y 2 000 registros."], status=413)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
