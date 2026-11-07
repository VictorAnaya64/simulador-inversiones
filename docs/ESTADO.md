# Estado del proyecto

_Ultima actualizacion: 2026-11-07._

## Resumen

Primera version funcional completa: motor financiero, datos sinteticos,
aplicacion web (estudiante + profesor), analitica de portafolios,
reportes, pruebas automatizadas y documentacion de despliegue. El
sistema corre localmente con SQLite sin ninguna API externa y esta
preparado para MySQL + cPanel por configuracion (`.env`), sin cambios
de codigo.

## Fases completadas (ver seccion 21 del prompt original)

- **Fase 1 — Infraestructura y modelos**: proyecto Django 5.2,
  7 apps (`usuarios, cursos, mercados, operaciones, portafolios,
  analitica, reportes`), modelo de usuario personalizado con roles,
  todos los modelos de datos, migraciones, admin de Django para cada
  modelo. ✅
- **Fase 2 — Motor financiero**: ordenes, ejecuciones a precio de
  cierre T+1 bursatil, reservas de efectivo/titulos, idempotencia,
  costeo FIFO, movimientos de efectivo, conversion de divisas,
  splits/dividendos. ✅ (23+ pruebas dedicadas)
- **Fase 3 — Datos bursatiles**: proveedor sintetico reproducible (20
  instrumentos + 2 indices, 6 anios de historia, correlaciones,
  splits/dividendos de ejemplo, tipo de cambio simulado), adaptador
  patron para proveedores reales (EODHD/Twelve Data, sin implementar
  a proposito — ver `docs/despliegue_cpanel.md`), comandos de
  importacion idempotentes, calendario bursatil aproximado. ✅
- **Fase 4 — Aplicacion web**: login con bloqueo por intentos
  fallidos, dashboard de estudiante (Plotly: evolucion + distribucion),
  buscador y detalle de instrumentos, formulario de compra/venta con
  idempotencia por token de formulario, historial de ordenes con
  cancelacion, panel de profesor con ranking y alta de estudiantes
  (individual + CSV). ✅
- **Fase 5 — Analitica**: rendimiento, riesgo (volatilidad, max
  drawdown, VaR historico), Sharpe/Treynor/Jensen, tracking
  error/information ratio, matriz de correlacion, optimizacion de
  Markowitz (minima varianza, maximo Sharpe, frontera eficiente),
  comparacion contra benchmark. ✅ (16 pruebas dedicadas a las
  formulas + pruebas de integracion del comando `calcular_metricas`)
- **Fase 6 — Calidad y despliegue**: 51 pruebas automatizadas (pytest,
  todas pasando), documentacion completa en `docs/`, `locustfile.py`
  preparado (no ejecutado contra un hosting real todavia),
  `passenger_wsgi.py`, variables de entorno documentadas en
  `.env.example`. 🟡 Parcial — ver pendientes.

## Pruebas automatizadas: estado actual

```
pytest
51 passed
```

Cobertura: calendario bursatil, motor de ordenes (creacion, validacion,
idempotencia, cancelacion, ejecucion, rechazo por movimiento de precio,
reprocesamiento, FIFO), concurrencia (dos compras simultaneas sobre el
mismo saldo), conversion de divisas, eventos corporativos (splits y
dividendos, incluyendo no-reprocesamiento), proveedor sintetico
(reproducibilidad, universo, splits), analitica (todas las formulas +
optimizacion de Markowitz), comando `calcular_metricas` end-to-end.

**No cubierto todavia por pruebas automatizadas** (verificado
manualmente via `Client` de Django, ver mas abajo): vistas web
(login, dashboards, formularios, exportaciones). Serian el siguiente
paso natural (pruebas de vista con `django.test.TestCase` /
`pytest-django`'s `client` fixture).

## Verificacion manual end-to-end realizada en esta sesion

1. `poblar_datos_demo` + `crear_curso_demo --n-estudiantes 5`: OK.
2. Creacion de una orden de compra real via `crear_orden`, importacion
   de precios futuros (dentro del horizonte sintetico) y ejecucion via
   `procesar_ordenes_pendientes`: OK.
3. `calcular_valuaciones` + `calcular_metricas` sobre datos reales del
   curso de demostracion: valores numericos revisados y consistentes.
4. Smoke test de las vistas web (`django.test.Client`) como estudiante
   (panel, mercado, analisis, operaciones, detalle de instrumento,
   crear orden via formulario) y como profesor (panel, detalle de
   curso, exportar CSV, exportar Excel): **todas las paginas
   responden 200/302 sin excepciones**.

No se abrio un navegador real (no hay esa herramienta disponible en
este entorno); lo anterior prueba que las vistas renderizan y los
flujos no truenan, pero no sustituye una revision visual/UX manual en
un navegador antes de la prueba piloto.

## Pendientes / siguientes pasos recomendados

1. **Revision visual en navegador real** de los templates (diseno
   responsivo en telefono, accesibilidad basica) antes de la prueba
   piloto — no verificado en esta sesion.
2. **Pruebas de carga reales** (`locustfile.py`) contra un ambiente de
   staging en el mismo plan de hosting que se usara en produccion;
   los objetivos de P95 en `docs/operacion.md` son metas, no
   resultados medidos.
3. **Calendario de festivos**: revisar/corregir
   `cargar_calendario_festivos` contra las fuentes oficiales de BMV y
   NYSE/NASDAQ antes de cada semestre (es una aproximacion).
4. **Adaptadores EODHD / Twelve Data**: implementar solo si se decide
   usar datos de mercado reales; requiere verificar la documentacion
   oficial vigente y los terminos de redistribucion de datos a
   estudiantes (ver `docs/despliegue_cpanel.md`).
5. **Pruebas automatizadas de vistas**: agregar pruebas con
   `django.test.Client` (ya se verifico manualmente que funcionan; falta
   formalizarlas como suite de regresion).
6. **Exportacion a nivel administrador general**: hoy solo el profesor
   puede exportar los resultados de sus propios cursos; si el
   administrador necesita una vista consolidada de todos los cursos,
   se puede extender `apps/reportes` facilmente (los servicios ya
   estan generalizados por curso).
7. **Multiples cursos activos simultaneos por estudiante**: soportado
   a nivel de modelo pero no en la UI actual (ver limitacion en
   `docs/operacion.md`).

## Como continuar si se interrumpe la sesion

El proyecto es un repositorio Git normal (`git init` pendiente si aun
no se ha hecho — este entorno no inicializo Git automaticamente).
Todo el estado relevante esta en:

- Codigo: `apps/`, `config/`, `templates/`, `static/`.
- Esquema de datos: migraciones ya generadas y aplicadas en SQLite
  local (`db.sqlite3`, ignorado por git).
- Documentacion: `docs/` (este archivo incluido).
- Dependencias: `requirements.txt` (produccion) y
  `requirements-dev.txt` (desarrollo/pruebas/carga).

Para retomar: `pip install -r requirements-dev.txt`, `python manage.py
migrate`, `python manage.py poblar_datos_demo`, `pytest`.
