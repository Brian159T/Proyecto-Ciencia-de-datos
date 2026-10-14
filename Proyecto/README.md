# Sistema de Predicción de Objetos Perdidos — UNIFRANZ

Aplicación independiente en la carpeta **Proyecto**, con un único servidor Flask. HTML5, Jinja2 y CSS puro; Python, NumPy, Pandas, Scikit-learn y Matplotlib. Sin JavaScript, Node.js, autenticación ni base de datos.

## Instalación y ejecución en Windows

Usa **Python 3.10 a 3.13** (verificación local con Python 3.10.11).

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
2. Opcionalmente pega más registros en el campo de texto, con una línea por registro: AAAA-MM-DD,cantidad. No incluyas encabezado. Los datos de la tabla y el texto se combinan y se rechazan las fechas repetidas entre ambas entradas.
3. Selecciona 7, 14 o 30 días; para otra cantidad elige Personalizado y completa el número (1 a 365).
4. Pulsa **Calcular regresión**. Los resultados, tres gráficos y la tabla de predicciones aparecen en la misma página. Los datos introducidos permanecen visibles para modificarlos y recalcular.
5. Pulsa **Limpiar formulario** para regresar a la página inicial vacía.

Se requieren al menos 3 fechas distintas. Se recomiendan 14 o más observaciones reales. Se admiten cantidades enteras de 0 a 1 000 000 y hasta 2 000 registros por petición (máximo 1 MB). No se admiten fechas inválidas, campos incompletos, valores negativos, no numéricos o duplicados. Los ceros son válidos; los días sin observación no se completan automáticamente.

## Modelo y métricas

Los registros se ordenan por fecha. X representa días naturales transcurridos desde la primera fecha y Y, los objetos recibidos ese día. Se entrena sklearn.linear_model.LinearRegression y se muestra Y = mX + b con sus parámetros reales.

- **Ajuste**: MAE, MSE, RMSE y R² corresponden al modelo final entrenado con todo el historial. Describen cómo se ajusta a esos datos, no su capacidad futura.
- **Evaluación**: con 10 o más observaciones, un modelo independiente utiliza las primeras floor(0.8 × n) fechas para entrenar y las restantes para evaluar, sin mezclar registros. Después se ajusta el modelo final con todo el historial para generar las predicciones. La evaluación cronológica es pequeña y orientativa.
- R² se omite cuando la cantidad observada es constante, incluido el conjunto reservado si fuera constante. R² de evaluación puede ser negativo. MAE y RMSE tienen unidades de objetos; MSE, objetos al cuadrado.
- Las métricas y los gráficos de ajuste utilizan las salidas lineales originales. Las cantidades futuras mostradas se limitan a cero; el total y promedio futuros utilizan esos valores limitados, sin redondeo previo. La tabla se redondea a dos decimales, así que pueden existir diferencias pequeñas al sumar valores visibles.
- Se predicen todos los días naturales siguientes al último registro, incluidos fines de semana. No se modelan feriados, calendario universitario ni estacionalidad.
- Se considera una tendencia cercana a cero cuando el cambio absoluto del modelo durante el historial es menor al 1 % de max(promedio real, 1). Este criterio descriptivo no es una prueba de significancia estadística.

El promedio histórico corresponde únicamente a los días registrados. Una tendencia histórica no garantiza el comportamiento futuro; las estimaciones pueden contener decimales y no constituyen conteos observados ni intervalos de confianza.

Los **110 objetos de agosto (año sin confirmar)** y los **aproximadamente 5 diarios** de la entrevista se muestran como referencia y nunca se incorporan al entrenamiento. No hay observaciones ficticias precargadas.

## Archivos y flujo

~~~text
Proyecto/
├── app.py
├── requirements.txt
├── README.md
├── templates/
│   └── index.html
└── static/
    └── css/
        └── styles.css
~~~

GET / renderiza el formulario vacío. POST /predict valida, entrena, calcula métricas y predicciones, genera gráficos PNG en BytesIO y los codifica en Base64. render_template envía los resultados a index.html, que enlaza CSS con url_for('static', filename='css/styles.css'). Las entradas inválidas devuelven HTTP 422 con errores visibles; una petición demasiado grande devuelve 413.

No se guardan registros, modelos ni imágenes de gráficos. Toda la información se procesa temporalmente durante cada petición. El CSS incluye diseños para escritorio y móvil, tablas con desplazamiento horizontal y etiquetas accesibles.

## Dependencias

Las cinco dependencias directas tienen versiones fijadas en requirements.txt. Sus dependencias transitivas (por ejemplo SciPy y Jinja2) se instalan automáticamente, pues son necesarias para estas bibliotecas.

Versiones contrastadas con las fichas oficiales de [Flask](https://pypi.org/project/Flask/3.1.0/), [NumPy](https://pypi.org/project/numpy/2.2.3/), [Pandas](https://pypi.org/project/pandas/2.2.3/), [Scikit-learn](https://pypi.org/project/scikit-learn/1.6.1/) y [Matplotlib](https://pypi.org/project/matplotlib/3.10.1/).


## Comprobaciones realizadas

Se ejecutaron 15 pruebas automatizadas con unittest y el cliente de Flask: plantilla y CSS, formulario POST, fechas y cantidades inválidas, duplicados, horizontes, preservación de entradas, entrenamiento real, cambios de predicciones, métricas contrastadas con cálculos manuales, separación cronológica, series constantes, límite cero y tres PNG Base64 válidos. Todas pasaron. Los datos sintéticos de prueba existieron únicamente en memoria y no están precargados en la aplicación.

La comprobación de dependencias con python -m pip check pasó. También se inició python app.py y se comprobó una respuesta HTTP 200 en http://127.0.0.1:5000.

El diseño incluye reglas responsive a 1 000 y 720 píxeles y contenedores de tablas desplazables. No se pudo realizar una revisión visual en escritorio/móvil porque el entorno no dispone de un navegador conectado. Esa comprobación visual queda pendiente.
