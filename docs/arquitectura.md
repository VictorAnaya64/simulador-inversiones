# Arquitectura

## Principios

- **Parsimonia**: Django + MySQL/MariaDB + Bootstrap 5 + Plotly. Sin
  React/Vue/Angular, sin Node como backend, sin Docker, sin
  Redis/Celery/Kubernetes ni microservicios. No hay procesos Python
  permanentemente activos ni WebSockets: todo corre dentro del ciclo
  request/response de Django o de comandos `manage.py` disparados por
  Cron.
- **Separacion de responsabilidades**: la logica financiera vive en
  modulos `services.py` dentro de cada app, completamente desacoplada
  de las vistas web. Las vistas solo orquestan: validan permisos,
  llaman al servicio correspondiente y renderizan el resultado.
- **Idempotencia**: cualquier operacion que pueda repetirse (una orden
  reenviada, un comando de cron ejecutado dos veces) debe producir el
  mismo resultado que ejecutarse una sola vez. Ver
  `docs/reglas_financieras.md`.

## Apps Django y dependencias

```
usuarios     (sin dependencias de otras apps del proyecto)
cursos       -> mercados
mercados     (sin dependencias de otras apps del proyecto)
portafolios  -> cursos, mercados
operaciones  -> mercados, portafolios
analitica    -> portafolios, cursos
reportes     -> cursos, analitica, usuarios
```

La flecha `A -> B` significa "A importa modelos de B". Este orden es
deliberado: `mercados` y `usuarios` son las apps de mas bajo nivel y no
dependen de nada del proyecto; `operaciones` (el motor de compraventa)
depende de `portafolios` y `mercados` pero ninguna app de bajo nivel
depende de `operaciones`, lo que evita importaciones circulares. Cuando
se necesita una referencia en sentido contrario (p. ej. `portafolios`
necesita crear un `LoteAdquisicion` ligado a una `Ejecucion` de
`operaciones`), se usa una referencia de modelo en string
(`'operaciones.Ejecucion'`), que Django resuelve de forma perezosa sin
crear un import circular en tiempo de carga.

## Capas dentro de cada app

- `models.py` — esquema de datos (Django ORM).
- `services.py` — logica de negocio reutilizable (motor financiero,
  analitica, etc.), funciones puras o transaccionales, sin tocar
  `request`/`response`.
- `views.py` + `forms.py` — capa web (Bootstrap 5 + Django Templates).
- `management/commands/` — comandos ejecutables por Cron.
- `admin.py` — panel de administracion de Django (usado por el rol
  Administrador y, para algunas tablas de solo lectura, por consulta
  directa cuando no hay una vista dedicada).

## Patron adaptador para datos de mercado

`apps/mercados/proveedores/` define `ProveedorCotizacionesBase` (precios
historicos y eventos corporativos) y una fabrica
(`factory.obtener_proveedor_activo()`) que lee la configuracion
`SIMULADOR['PROVEEDOR_DATOS_MERCADO']` y devuelve la implementacion
concreta: `ProveedorSintetico` (por defecto, no requiere API externa),
o los adaptadores `EODHD`/`TwelveData` (sin implementar todavia; ver
advertencias en esos archivos). El motor de simulacion y los comandos de
cron solo conocen la interfaz base, nunca el proveedor concreto.

## Por que PyMySQL en vez de mysqlclient

`mysqlclient` requiere compilar una extension C contra los headers de
desarrollo de MySQL, que no siempre estan disponibles (o son dificiles
de instalar) en un hosting compartido con cPanel. `PyMySQL` es una
implementacion pura en Python del protocolo de MySQL; es mas lenta que
`mysqlclient` bajo carga muy alta, pero para la carga objetivo de este
proyecto (100 estudiantes) la diferencia es irrelevante y la
portabilidad gana. Se activa en `config/__init__.py` con
`pymysql.install_as_MySQLdb()`.

## Rendimiento en hosting compartido

- Los calculos costosos (metricas de riesgo/rendimiento, valuacion
  diaria de cada portafolio) se precalculan por Cron
  (`calcular_valuaciones`, `calcular_metricas`) y se leen desde tablas
  normales en las vistas; nunca se recalculan series completas dentro
  de una solicitud HTTP.
- La optimizacion de Markowitz (frontera eficiente, maximo Sharpe) SI
  se calcula en la vista `analitica:analisis` porque usa pocos activos
  (hasta `LIMITE_INSTRUMENTOS_OPTIMIZACION = 12`) y `scipy.optimize`
  con `SLSQP` resuelve ese tamano en milisegundos; si en el futuro se
  permiten mas instrumentos por curso, esto deberia moverse a un
  resultado cacheado en `ResultadoOptimizacion` (el modelo ya existe
  para ese fin).
- Los comandos de cron usan `select_for_update()` y actualizaciones
  idempotentes (`update_or_create`), nunca recrean toda la tabla.
- No se hacen llamadas a APIs externas durante una solicitud HTTP: toda
  descarga de datos de mercado ocurre en comandos de cron.
- **Limites reales de CPU/RAM/Entry Processes del hosting**: no
  identificados todavia (ver seccion 3 del prompt original). Antes de
  la prueba piloto con 100 estudiantes, ejecutar las pruebas de carga
  de `locustfile.py` desde una maquina externa contra un ambiente de
  staging en el mismo plan de hosting, y documentar los resultados en
  `docs/operacion.md`.
