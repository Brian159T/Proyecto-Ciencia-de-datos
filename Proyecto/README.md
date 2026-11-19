# Sistema de Predicción de Objetos Perdidos — UNIFRANZ

Aplicación independiente en la carpeta **Proyecto**, con un único servidor Flask. HTML5, Jinja2 y CSS puro; Python, NumPy, Pandas, Scikit-learn y Matplotlib. Sin JavaScript, Node.js ni autenticación. Usa PostgreSQL de forma opcional para guardar las predicciones que el usuario decida almacenar.

## Instalación y ejecución en Windows

Usa **Python 3.10 a 3.13** (entorno local verificado: Python 3.10.11). Requiere **PostgreSQL 12 o superior** solo si vas a guardar predicciones.

Desde el directorio que contiene Proyecto:

~~~powershell
cd Proyecto
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
~~~

En CMD, activa con .venv\Scripts\activate.bat. Si PowerShell restringe la activación, puedes ejecutar directamente:

~~~powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
~~~

Abre **http://127.0.0.1:5000**. Para detener el servidor pulsa Ctrl+C. No necesitas un servidor adicional para la interfaz.

## Uso

1. Introduce fechas y cantidades diarias reales en las 10 filas editables. Deja completamente vacías las filas que no necesites.
2. Opcionalmente pega más registros en el campo de texto, con una línea por registro: AAAA-MM-DD,cantidad. No incluyas encabezado. También puedes cargar un archivo `.xlsx` o `.csv` con dos columnas (fecha, cantidad); en Excel se usa la primera hoja, el encabezado es opcional y el CSV admite coma, punto y coma o tabulador. Los datos de la tabla, el texto y el archivo se combinan. Si una fecha se repite con la misma cantidad, se omite la repetición y se conserva el primer valor; si la cantidad es distinta, se muestra un error.
3. Selecciona 7, 14 o 30 días; para otra cantidad elige Personalizado y completa el número (1 a 365).
4. Pulsa **Calcular regresión**. Los resultados, cuatro gráficos y la tabla de predicciones aparecen en la misma página. Los datos introducidos permanecen visibles para modificarlos y recalcular.
5. Pulsa **Limpiar formulario** para regresar a la página inicial vacía.

Se requieren al menos 3 fechas distintas. Se recomiendan 14 o más observaciones reales. Se admiten cantidades enteras de 0 a 1 000 000 y hasta 2 000 registros por petición (máximo 3 MB). No se admiten fechas inválidas, campos incompletos, valores negativos ni no numéricos. Los duplicados con la misma cantidad se omiten; los duplicados con cantidad distinta se rechazan. Los ceros son válidos; los días sin observación no se completan automáticamente. En archivos, las fechas se aceptan como AAAA-MM-DD, AAAA/MM/DD, dd/mm/aaaa, dd-mm-aaaa o dd.mm.aaaa.

## Modelo y métricas

Los registros se ordenan por fecha. X representa días naturales transcurridos desde la primera fecha y Y, los objetos recibidos ese día. Se entrena sklearn.linear_model.LinearRegression y se muestra Y = mX + b con sus parámetros reales.

- **Ajuste**: MAE, MSE, RMSE y R² corresponden al modelo final entrenado con todo el historial. Describen cómo se ajusta a esos datos, no su capacidad futura.
- **Evaluación**: con 10 o más observaciones, un modelo independiente utiliza las primeras floor(0.8 × n) fechas para entrenar y las restantes para evaluar, sin mezclar registros. Después se ajusta el modelo final con todo el historial para generar las predicciones. La evaluación cronológica es pequeña y orientativa.
- R² se omite cuando la cantidad observada es constante, incluido el conjunto reservado si fuera constante. R² de evaluación puede ser negativo. MAE y RMSE tienen unidades de objetos; MSE, objetos al cuadrado.
- Las métricas y los gráficos de ajuste utilizan las salidas lineales originales. Las cantidades futuras mostradas se limitan a cero; el total y promedio futuros utilizan esos valores limitados, sin redondeo previo. La tabla se redondea a dos decimales, así que pueden existir diferencias pequeñas al sumar valores visibles.
- Se predicen todos los días naturales siguientes al último registro, incluidos fines de semana. No se modelan feriados, calendario universitario ni estacionalidad.
- Se considera una tendencia cercana a cero cuando el cambio absoluto del modelo durante el historial es menor al 1 % de max(promedio real, 1). Este criterio descriptivo no es una prueba de significancia estadística.
- El gráfico de torta muestra qué porcentaje del total registrado corresponde a cada día de la semana. Agrupa todos los registros históricos; no es una predicción ni corrige semanas con distinta cantidad de cada día.

El promedio histórico corresponde únicamente a los días registrados. Una tendencia histórica no garantiza el comportamiento futuro; las estimaciones pueden contener decimales y no constituyen conteos observados ni intervalos de confianza.

Los **110 objetos de agosto de 2026** y los **aproximadamente 5 diarios** de la entrevista se muestran como referencia y nunca se incorporan al entrenamiento. No hay observaciones ficticias precargadas.

## Archivos y flujo

~~~text
Proyecto/
├── app.py
├── database.py
├── init_db.py
├── schema.sql
├── requirements.txt
├── README.md
├── .env.example
├── templates/
│   └── index.html
└── static/
    └── css/
        └── styles.css
~~~

GET / renderiza el formulario vacío. POST /predict lee la tabla, el texto pegado y el archivo `.xlsx` o `.csv`; valida, entrena, calcula métricas y predicciones, genera gráficos PNG en BytesIO y los codifica en Base64. render_template envía los resultados a index.html, que enlaza CSS con url_for('static', filename='css/styles.css'). Las entradas inválidas devuelven HTTP 422 con errores visibles; una petición demasiado grande devuelve 413.

El botón **Guardar datos** envía los registros ya validados a POST /save. Esa ruta vuelve a calcular el análisis y, en una sola transacción, inserta la cabecera en `analyses`, las observaciones en `analysis_records` y las predicciones diarias en `analysis_predictions`. Si no hay conexión configurada, el botón aparece deshabilitado.

Por defecto no se guardan registros, modelos ni imágenes: todo se procesa en memoria durante cada petición. Solo si el usuario pulsa **Guardar datos** se almacenan los datos en PostgreSQL. El CSS incluye diseños para escritorio y móvil, tablas con desplazamiento horizontal y etiquetas accesibles.

## Base de datos PostgreSQL (opcional)

1. Copia `.env.example` como `.env` y completa `PGPASSWORD` (o define `DATABASE_URL`). El archivo `.env` está en `.gitignore` y no se sube a GitHub.
2. Inicializa la base de datos y el esquema:

~~~powershell
.venv\Scripts\python.exe init_db.py
~~~

El script crea la base `objetos_perdidos` si no existe y aplica `schema.sql`. También puedes hacerlo manualmente con `createdb` y `psql`.
3. Inicia `python app.py`, calcula una regresión y pulsa **Guardar datos**.

| Objeto | Contenido |
| :--- | :--- |
| `analyses` | Cabecera de cada análisis guardado: fechas, horizonte, ecuación, tendencia, métricas y totales. |
| `analysis_records` | Observaciones históricas (fecha y cantidad) usadas por ese análisis. |
| `analysis_predictions` | Predicción diaria; guarda el valor lineal original y el valor recortado a cero. |
| `v_analysis_summary` | Vista de resumen con el número de predicciones por análisis. |

Si no hay conexión configurada, la aplicación funciona normalmente y el botón de guardado aparece deshabilitado.

## Dependencias

Las siete dependencias directas tienen versiones fijadas en requirements.txt. Sus dependencias transitivas (por ejemplo SciPy y Jinja2) se instalan automáticamente, pues son necesarias para estas bibliotecas.

Versiones contrastadas con las fichas oficiales de [Flask](https://pypi.org/project/Flask/3.1.0/), [NumPy](https://pypi.org/project/numpy/2.2.3/), [Pandas](https://pypi.org/project/pandas/2.2.3/), [Scikit-learn](https://pypi.org/project/scikit-learn/1.6.1/), [Matplotlib](https://pypi.org/project/matplotlib/3.10.1/), [openpyxl](https://pypi.org/project/openpyxl/3.1.5/) y [psycopg](https://pypi.org/project/psycopg/3.3.9/).


## Comprobaciones realizadas

Se ejecutaron pruebas automatizadas con unittest y el cliente de Flask: plantilla y CSS, formulario POST, fechas y cantidades inválidas, duplicados, horizontes, preservación de entradas, carga de archivos Excel y CSV, entrenamiento real, cambios de predicciones, métricas contrastadas con cálculos manuales, separación cronológica, series constantes, límite cero y tres PNG Base64 válidos. Todas pasaron. Los archivos de pruebas no forman parte de este repositorio; solo se incluyen la aplicación, la plantilla y los estilos. Los datos sintéticos de prueba existieron únicamente en memoria y no están precargados en la aplicación.

La comprobación de dependencias con python -m pip check pasó. También se inició python app.py y se comprobó una respuesta HTTP 200 en http://127.0.0.1:5000.

El guardado se verificó contra una instancia temporal de PostgreSQL 17: se insertaron un análisis, 31 observaciones y 7 predicciones, y se comprobó que `predicted_value` siempre es `GREATEST(raw_value, 0)`. El botón permanece deshabilitado si no hay conexión configurada.

El diseño incluye reglas responsive a 1 000 y 720 píxeles y contenedores de tablas desplazables. No se pudo realizar una revisión visual en escritorio/móvil porque el entorno no dispone de un navegador conectado. Esa comprobación visual queda pendiente.
