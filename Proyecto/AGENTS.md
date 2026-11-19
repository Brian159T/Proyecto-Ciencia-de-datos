# AGENTS.md — Contexto para agentes de IA

Guía de trabajo para agentes que modifiquen este repositorio. Léela completa antes de tocar código.

## 1. Qué es el proyecto

Trabajo académico de Ciencia de Datos (UNIFRANZ, Ingeniería de Sistemas, 2026): **aplicación web que predice la cantidad diaria de objetos perdidos** mediante regresión lineal sobre registros históricos ingresados por el usuario.

- Es una app **monolítica Flask** dentro de `Proyecto/`.
- **Sin JavaScript, sin Node.js, sin base de datos, sin autenticación y sin persistencia.** Todo se procesa en memoria durante cada petición.
- Interfaz en **español** (Bolivia). Mantener ese idioma en textos, mensajes de error y documentación.
- El repositorio también contiene un `README.md` raíz con datos del trabajo (integrantes, docente) y la referencia a un perfil de proyecto.

## 2. Estructura real del repositorio

```
Proyecto Ciencia de datos/          <- raíz del repo git
├── .gitignore                      <- ignora .venv, __pycache__, .env, caches
├── README.md                       <- descripción general e integrantes
├── AGENTS.md                       <- este archivo
└── Proyecto/                       <- aplicación
    ├── app.py                      <- rutas Flask, validación y análisis
    ├── database.py                 <- guardado opcional en PostgreSQL
    ├── init_db.py                  <- crea la base y aplica schema.sql
    ├── schema.sql                  <- analyses, analysis_records, analysis_predictions
    ├── requirements.txt            <- 7 dependencias fijadas
    ├── .env.example                <- plantilla de conexión; .env real está ignorado
    ├── README.md                   <- documentación detallada de la app
    ├── datos_prueba_octubre.csv    <- 31 registros de prueba (octubre 2026)
    ├── templates/
    │   └── index.html              <- única plantilla Jinja2
    ├── static/
    │   └── css/
    │       └── styles.css          <- CSS puro (responsive + print)
    └── .venv/                      <- entorno local (ignorado por git)
```

No existen `tests/`, `pyproject.toml`, CI, linters ni Dockerfile. El `README.md` raíz menciona `perfil_de_proyecto_ciencia_de_datos.md`, que **no está en el repo**.

## 3. Stack y comandos

- Python. El `.venv` local tiene **3.10.11**; el README declara soporte 3.10–3.13.
- Dependencias fijadas en `Proyecto/requirements.txt`:
  `Flask==3.1.0`, `numpy==2.2.3`, `pandas==2.2.3`, `scikit-learn==1.6.1`, `matplotlib==3.10.1`, `openpyxl==3.1.5`, `psycopg[binary]==3.3.9`.
- **PostgreSQL 12+** es opcional: solo se usa para el botón «Guardar datos».

Ejecutar (Windows PowerShell, desde la raíz del repo):

```powershell
cd Proyecto
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python init_db.py   # opcional: crea la base y aplica schema.sql
python app.py
```

- La conexión se toma de `Proyecto/.env` (ignorado por git): `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE`, `PGPASSWORD` o una `DATABASE_URL`.
- URL: `http://127.0.0.1:5000` (host/puerto fijos en `app.py`, `debug=False`).
- Verificación disponible hoy (no hay suite de pruebas):
  - `.venv\Scripts\python.exe -m pip check`
  - `.venv\Scripts\python.exe -m compileall app.py database.py init_db.py`
  - Smoke test manual: abrir `/`, enviar `POST /predict` con ≥3 fechas distintas y comprobar 200 + 4 gráficos.
  - Guardado: `python init_db.py`, calcular, pulsar «Guardar datos» y verificar las tres tablas.
- Si agregas pruebas, usa `unittest` (librería estándar) o `pytest`; documenta el comando aquí. El README afirma que existieron 15 pruebas con `unittest` y el cliente de Flask, pero **no se versionaron**.

## 4. Arquitectura y flujo de datos

`app.py` tiene tres bloques: entrada, análisis y presentación.

1. `GET /` → `index()` → `blank_form()` (10 filas vacías, horizonte 7) → `render_template`.
2. `POST /predict` → `predict()`:
   - `read_form()`: combina tres fuentes de datos:
     - tabla HTML (`date[]`, `quantity[]`),
     - textarea `bulk` (una línea `AAAA-MM-DD,cantidad` por registro),
     - archivo `excel` (`.xlsx` o `.csv`).
   - `validate(form)`: devuelve `(records ordenados, horizon, errors)`.
   - Con errores → HTTP **422** y se re-renderiza conservando los datos.
    - `analyze(records, horizon)` → modelo, métricas, predicciones y 4 PNG Base64.
   - Excepción no controlada → **500** con mensaje genérico (stack trace solo al log).
   - `413` → archivo/petición demasiado grande.
3. `analyze(records, horizon)` (`app.py:227`):
   - `X` = días naturales transcurridos desde la primera fecha (no hay relleno de días faltantes).
   - `Y` = cantidad registrada.
   - Si `n >= 10`: split cronológico 80/20, entrena un modelo aparte y calcula métricas de **evaluación** sobre las últimas fechas.
   - Modelo final: `LinearRegression` entrenado con **todo** el historial.
   - Predice **todos los días naturales** posteriores al último registro (incluye fines de semana y feriados).
   - Recorta predicciones negativas a 0 (`np.maximum(0, ...)`) y marca `clipped`.
   - `near_zero` (tendencia despreciable): `|pendiente| * días_historial < 1% * max(promedio, 1)`.
   - R² se omite (`None`) si `Y` es constante (`np.ptp == 0`).
4. `graphs()` (`app.py:191`): genera 4 figuras con backend `Agg` y las serializa a Base64 con `PLOT_LOCK`.
   - Dispersión + regresión.
   - Historial + proyección con línea de corte.
   - Barras reales vs ajustadas.
   - Torta con la proporción de objetos registrados por día de la semana (suma histórica; sin datos positivos muestra un aviso).
5. La plantilla `templates/index.html` renderiza todo en la misma página (contexto, formulario, resultados, gráficos, resumen). No hay rutas AJAX.
6. `POST /save` (botón «Guardar datos»): recibe el campo compacto `records` (`AAAA-MM-DD,cantidad;...`) y `horizon`, los revalida, reanaliza y llama a `database.save_analysis()`. Inserta en `analyses`, `analysis_records` y `analysis_predictions` dentro de una transacción. El botón solo se habilita si `database.is_configured()` (hay `PGPASSWORD` o `DATABASE_URL`); si no, queda deshabilitado y la ruta responde 503.

## 5. Reglas de negocio e invariantes (no romper)

- **Mínimo 3 registros** con fechas distintas.
- **Máximo 2 000 registros** por análisis (`MAX_RECORDS`).
- **Máximo 365 días** de horizonte (`MAX_HORIZON`).
- Fechas en formato **`AAAA-MM-DD`** (ISO). Se rechazan campos incompletos y fechas inválidas. Un duplicado con la misma cantidad se omite y se conserva el primero; un duplicado con cantidad distinta es error.
- Cantidades: **enteros** entre 0 y 1 000 000. Los ceros son válidos.
- Horizonte permitido: `7`, `14`, `30` o `custom` (1–365).
- Límite de petición: `MAX_CONTENT_LENGTH = 3 MB` (`app.py:21`); el mensaje del handler 413 también indica 3 MB.
- Archivos: Excel `.xlsx` (primera hoja) o CSV `.csv`, columna A = fecha, columna B = cantidad, encabezado opcional. El CSV admite coma, punto y coma o tabulador y codificación UTF-8 o cp1252. `read_excel` no cierra el workbook si hay excepción antes de `close()`.
- Datos de referencia («110 objetos en agosto 2026», «~5 por día») son **solo informativos** y **nunca** entran al entrenamiento.
- Por defecto no se guardan datos, modelos ni imágenes entre peticiones. **Excepción explícita:** al pulsar «Guardar datos» se insertan en PostgreSQL la cabecera (`analyses`), las observaciones (`analysis_records`) y las predicciones (`analysis_predictions`). No se guardan imágenes ni modelos.
- `analysis_records.source` se escribe como `mixto`; el `CHECK` del esquema admite `tabla`, `texto`, `excel`, `csv` y `mixto`.
- `.env` está ignorado por git y contiene la contraseña; nunca debe versionarse. `.env.example` sí se versiona.

## 6. Convenciones de código y UI

- Python: nombres en `snake_case`, funciones pequeñas, sin comentarios salvo aclaraciones matemáticas. El código actual es directo, sin capas ni clases.
- No agregar JavaScript sin justificación: la ausencia de JS es una decisión de diseño documentada.
- El CSS es puro, con variables en `:root` y media queries en **1000 px** y **720 px**. Mantener la paleta (`--navy #12243c`, `--blue #3269e8`, `--teal #0b9e91`).
- Accesibilidad ya presente: `aria-*`, `sr-only`, `scope`, `role="alert"`. Conservarla.
- Jinja: escapar siempre (autoescape activo). Las variables del formulario deben tolerar `None` (ver cambio pendiente en `index.html`).
- Mensajes al usuario en español, tono claro y sin prometer precisión estadística.

## 7. Estado del repositorio y trampas conocidas

- Hay cambios **sin commitear** en `app.py`, `templates/index.html`, `static/css/styles.css` y `requirements.txt`, además de archivos nuevos (`database.py`, `init_db.py`, `schema.sql`, `.env.example`, `AGENTS.md`, `datos_prueba_octubre.csv`). No revertirlos.
- Ya corregidos: la etiqueta de tendencia usa `trend_direction` calculado en Python (evita que «decreciente» se muestre como «creciente»); el límite de 3 MB es coherente; el README ya indica 7 dependencias, 3 MB y Python 3.10.11.
- `Proyecto/.env` está configurado localmente con `PGPORT=5432` y la contraseña de PostgreSQL; el botón «Guardar datos» se habilita cuando `database.is_configured()` detecta esas credenciales. Nunca versionar `.env`.
- El guardado se probó con un PostgreSQL 17 temporal en el puerto 5433. La instancia real del usuario está en 5432 y requiere la contraseña para ejecutar `init_db.py`.
- `excel_date` interpreta fechas de texto como `aaaa-mm-dd`, `aaaa/mm/dd`, `aaaa.mm.dd`, `dd/mm/aaaa`, `dd-mm-aaaa` o `dd.mm.aaaa`. Las celdas de fecha nativas de Excel sí funcionan. El CSV detecta el separador con `csv.Sniffer` (coma, punto y coma o tabulador).
- `graphs()` no cierra las figuras de Matplotlib; en un uso prolongado conviene `fig.clear()`/`plt.close(fig)`.
- No hay protección CSRF (aceptable en local, riesgoso si se expone), ni cabeceras de seguridad, ni límite de tasa.
- El servidor de desarrollo (`app.run`) no debe usarse en producción.
- Codificación: los archivos son UTF-8; en PowerShell antiguo los acentos pueden verse mal, no «corregirlos» con reescrituras ANSI.

## 8. Checklist antes de dar una tarea por terminada

1. `python -m compileall app.py database.py init_db.py` sin errores.
2. `pip check` sin conflictos.
3. Smoke test de `/` y `/predict` (caso válido, caso inválido, Excel, CSV, horizonte personalizado).
4. Si tocas el modelo: verificar que métricas de ajuste usan el modelo final, las de evaluación usan el holdout cronológico, y que las predicciones se recortan a 0 solo para mostrar/totalizar.
5. Si tocas la plantilla: comprobar que los formularios conservan datos tras un 422 y que `None` no se imprime como `"None"`.
6. Si tocas el guardado: ejecutar `python init_db.py`, calcular, pulsar «Guardar datos» y verificar `analyses`, `analysis_records` y `analysis_predictions`.
7. Actualizar `README.md` (app y raíz) cuando cambien límites, dependencias o comandos.
8. No hacer commit salvo que se pida explícitamente.

## 9. Mejoras pendientes (priorizadas)

1. **Versionar la suite de pruebas** (`tests/`, `pytest` o `unittest`) y añadir CI (GitHub Actions: instalar, `pip check`, pruebas, `compileall`).
2. **Extraer el análisis** a `analysis.py` con funciones puras y tipos, dejando `app.py` como capa web; **cerrar las figuras de Matplotlib** para evitar crecimiento de memoria.
3. **Endurecer la entrada**: CSRF, cabeceras de seguridad, validación del contenido real del `.xlsx`/`.csv`, límite por archivo y límite de tasa.
4. **Mejorar el modelo y el rigor estadístico**: intervalos de confianza, diagnóstico de residuos, comparación con media móvil/Holt-Winters, tratamiento opcional de fines de semana/feriados y advertencia explícita de que 3 puntos no permiten inferencia.
5. **Mejorar UX**: exportar predicciones a CSV, vista previa del Excel/CSV antes de calcular, conservar resultados al recargar y revisión visual real en móvil/escritorio.
6. **Empaquetado y operación**: `pyproject.toml` con configuración de `ruff`/`pytest`, lockfile, host/puerto por variables de entorno y `Dockerfile` opcional.
7. **Repositorio**: agregar `perfil_de_proyecto_ciencia_de_datos.md` o eliminar la referencia en el `README.md` raíz.
