# Operacion y mantenimiento

## Comandos de gestion (`manage.py`)

Todos son idempotentes: correrlos dos veces (o que se superpongan por
un reintento de Cron) nunca duplica datos ni reprocesa lo ya hecho.

| Comando | Que hace | Cuando correrlo |
|---|---|---|
| `poblar_instrumentos_sinteticos` | Crea el proveedor SINTETICO y los 20 instrumentos + 2 indices de demostracion | Una vez, al preparar el ambiente |
| `cargar_calendario_festivos` | Carga un calendario **aproximado** de dias inhabiles BMV/NYSE/NASDAQ 2022-2028 | Una vez, y revisar/corregir cada semestre |
| `importar_precios [--desde] [--hasta]` | Descarga (del proveedor activo) y guarda precios + eventos corporativos | Diario, antes de `procesar_ordenes` |
| `actualizar_tipo_cambio [--desde] [--hasta]` | Descarga y guarda el tipo de cambio USD/MXN | Diario, antes de `calcular_valuaciones` |
| `aplicar_eventos_corporativos` | Aplica splits/dividendos vencidos a las posiciones | Diario, antes de `procesar_ordenes` |
| `procesar_ordenes` | Ejecuta o rechaza ordenes pendientes cuya sesion ya llego | Diario (se puede correr varias veces al dia sin riesgo) |
| `calcular_valuaciones [--fecha] [--desde --hasta]` | Precalcula la valuacion diaria de cada portafolio | Diario, despues de `procesar_ordenes` |
| `calcular_metricas [--fecha]` | Precalcula rendimiento/riesgo/desempeno por ventana | Diario, despues de `calcular_valuaciones` |
| `poblar_datos_demo [--hasta]` | Orquesta los primeros 5 comandos de esta tabla para un ambiente de demostracion | Al preparar un ambiente nuevo |
| `crear_curso_demo [--n-estudiantes] [--password]` | Crea profesor, N estudiantes y un curso ya inscrito | Al preparar un ambiente de prueba |

Ver `docs/despliegue_cpanel.md` seccion 13 para el orden exacto y los
horarios sugeridos en Cron Jobs de cPanel.

## Revisiones de integridad sugeridas

No hay (todavia) un comando dedicado de "revision de integridad"; las
invariantes centrales ya estan protegidas por el motor (nunca saldo
negativo, nunca doble ejecucion, FIFO consistente) y cubiertas por
pruebas automatizadas (`pytest`). Para una auditoria manual rapida
desde `manage.py shell`:

```python
from apps.portafolios.models import Portafolio
from django.db.models import F
# Ningun portafolio deberia tener efectivo reservado mayor al efectivo total.
list(Portafolio.objects.filter(efectivo_mxn_reservado__gt=F('efectivo_mxn')))
list(Portafolio.objects.filter(efectivo_usd_reservado__gt=F('efectivo_usd')))
```

Si esas consultas devuelven algo, es un bug: reportarlo con el id del
portafolio antes de que el curso continue.

## Respaldos

Ver `docs/despliegue_cpanel.md` seccion 17 (mysqldump + backup nativo
de cPanel). Frecuencia recomendada para una prueba piloto: diario,
retenidos al menos 2 semanas.

## Pruebas de carga (Locust)

`locustfile.py` en la raiz del proyecto. **Nunca** correrlo contra
produccion sin autorizacion explicita del administrador del hosting, y
**siempre** desde una maquina distinta al propio cPanel:

```bash
pip install -r requirements-dev.txt   # incluye locust
locust -f locustfile.py --host https://simulador-staging.tu-dominio.edu.mx
```

Escenarios objetivo: 5, 20, 50 y 100 usuarios concurrentes. Metas: P95
de consultas ordinarias <= 2s, P95 de envio de ordenes <= 3s, cero
errores 5xx/508, cero errores de integridad financiera. **Estos
numeros no se han validado todavia contra un hosting real** — esta
seccion debe actualizarse con los resultados reales antes de anunciar
que el sistema "soporta 100 usuarios".

## Limitaciones operativas conocidas

- **Cache y bloqueo de intentos de login**: usa
  `django.core.cache.backends.locmem.LocMemCache`, que vive en la
  memoria de cada proceso Python. Si Passenger llega a correr multiples
  procesos de la aplicacion simultaneamente, el contador de intentos
  fallidos de login se mantiene por proceso, no globalmente — una
  mitigacion razonable pero no perfecta contra fuerza bruta. Si el
  hosting ejecuta multiples procesos y se requiere un limite estricto
  global, migrar a una cache compartida (p. ej. una tabla de base de
  datos via `django.core.cache.backends.db.DatabaseCache`) sin agregar
  Redis/Memcached.
- **Calendario de festivos**: `cargar_calendario_festivos` genera un
  calendario *aproximado* (reglas generales + Viernes Santo calculado),
  no una fuente oficial. Revisar contra BMV y NYSE/NASDAQ antes de cada
  semestre; no modela cierres anticipados.
- **Adaptadores EODHD/Twelve Data**: sin implementar (ver
  `docs/despliegue_cpanel.md`, seccion final).
- **Un curso activo por estudiante a la vez**: las vistas de estudiante
  (`apps/portafolios/views.py`, `apps/operaciones/views.py`) toman la
  primera inscripcion activa del usuario. Si un estudiante llegara a
  inscribirse en mas de un curso activo simultaneamente, solo vera el
  primero; esto no esta prohibido a nivel de modelo (se permite
  multiples inscripciones) pero la UI actual no lo soporta bien. Para
  la prueba piloto (un curso por semestre) no es un problema.
