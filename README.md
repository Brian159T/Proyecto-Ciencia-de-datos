# Proyecto-Ciencia-de-datos

Repositorio del trabajo académico **"Aplicación de regresión lineal para la predicción de la cantidad de objetos perdidos en la Universidad Privada Franz Tamayo (UNIFRANZ)"**, Facultad de Tecnología, Carrera de Ingeniería de Sistemas, Cochabamba — Bolivia, 2026.

## Contenido

| Ruta | Descripción |
| :--- | :--- |
| `perfil_de_proyecto_ciencia_de_datos.md` | Perfil del proyecto: introducción, planteamiento del problema, objetivos, alcance, metodología, tecnologías, indicadores y cronograma. |
| `Proyecto/` | Aplicación web (Flask) que entrena una regresión lineal sobre registros diarios de objetos perdidos ingresados por el usuario, calcula MAE, MSE, RMSE y R², y muestra gráficos y predicciones diarias. |

La aplicación es independiente de FindU: no usa base de datos ni guarda registros; cada análisis se procesa durante la petición con los datos ingresados.

## Ejecución

Para instalar y ejecutar la aplicación, sigue las instrucciones de [`Proyecto/README.md`](Proyecto/README.md). En resumen:

```powershell
cd Proyecto
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Luego abre **http://127.0.0.1:5000**.

## Integrantes

* Brian Ricardo Zegarra Barrientos
* David Alan Fernandez Imaca
* Raul Omar Enriquez Zuleta

**Docente:** Ing. Christian Luis Lopez Bravo
