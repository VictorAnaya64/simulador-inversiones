# Simulador Educativo de Inversiones

Plataforma web para que estudiantes universitarios de Actuaria (materia
de Teoria de Portafolios de Inversion) administren un portafolio de
inversion con dinero ficticio, usando cotizaciones de acciones y ETF de
Mexico y Estados Unidos. Sin dinero real, sin intermediarios financieros.

## Stack

Django 5.2 LTS + MySQL/MariaDB (SQLite en desarrollo local) + Bootstrap 5
+ Plotly + NumPy/pandas/SciPy. Sin React/Vue/Node como backend, sin
Docker, sin Redis/Celery. Pensado para hosting compartido con cPanel
(Passenger/WSGI) y Cron Jobs. Ver [docs/arquitectura.md](docs/arquitectura.md).

## Instalacion local (desarrollo)

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows (Git Bash); en Linux/Mac: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env             # DB_ENGINE=sqlite por defecto, no requiere MySQL
python manage.py migrate
python manage.py poblar_datos_demo        # catalogo sintetico + precios + tipo de cambio
python manage.py crear_curso_demo --n-estudiantes 10
python manage.py createsuperuser          # cuenta de administrador general
python manage.py runserver
```

Usuario profesor de demostracion: `profesor_demo` / `Demo12345!`.
Usuarios estudiante de demostracion: `estudiante_demo_01` .. `estudiante_demo_10` / `Demo12345!`.
**Cambiar estas contrasenas antes de usar el sistema con estudiantes reales.**

## Pruebas automatizadas

```bash
pytest
```

51+ pruebas cubren el motor financiero (ordenes, ejecucion, FIFO,
idempotencia, concurrencia, conversion de divisas, splits/dividendos),
el proveedor sintetico de datos de mercado y la analitica de portafolios
(rendimiento, riesgo, Sharpe/Treynor/Jensen, optimizacion de Markowitz).

## Tareas programadas (Cron)

Ver [docs/operacion.md](docs/operacion.md) para la lista completa de
comandos `manage.py` pensados para Cron Jobs de cPanel (procesar
ordenes, importar precios, calcular valuaciones y metricas, etc.).

## Documentacion

- [docs/arquitectura.md](docs/arquitectura.md) — arquitectura y modulos.
- [docs/modelo_datos.md](docs/modelo_datos.md) — tablas y relaciones.
- [docs/reglas_financieras.md](docs/reglas_financieras.md) — reglas de simulacion y formulas.
- [docs/despliegue_cpanel.md](docs/despliegue_cpanel.md) — despliegue en cPanel paso a paso.
- [docs/operacion.md](docs/operacion.md) — cron, respaldos, mantenimiento.
- [docs/manual_profesor.md](docs/manual_profesor.md) — administracion academica.
- [docs/manual_estudiante.md](docs/manual_estudiante.md) — uso de la plataforma.
- [docs/ESTADO.md](docs/ESTADO.md) — estado del proyecto y pendientes.

## Limitaciones conocidas de esta primera version

Ver el detalle completo en cada documento de `docs/`, en particular
`docs/reglas_financieras.md` (politicas de redondeo, simplificaciones
del proveedor sintetico) y `docs/ESTADO.md` (pendientes). En resumen:
calendario de festivos aproximado (no oficial), adaptadores EODHD/Twelve
Data sin implementar (el sistema funciona sin ellos via el proveedor
sintetico), sin titulos fraccionados, un portafolio activo por
estudiante a la vez, pruebas de carga no ejecutadas aun contra un
hosting real.
