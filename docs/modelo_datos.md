# Modelo de datos

Generado y versionado via Django ORM (`python manage.py makemigrations`
/ `migrate`). Este documento resume las tablas principales; el detalle
exacto de columnas, tipos y restricciones esta en cada `models.py`.

## apps.usuarios

- **Usuario** (extiende `AbstractUser`): `rol` (ADMIN/PROFESOR/ESTUDIANTE),
  `matricula`, `institucion`, `telefono`, `activo_academicamente`.
  Es el modelo de usuario del proyecto desde el inicio
  (`AUTH_USER_MODEL = 'usuarios.Usuario'`) para evitar una migracion
  de usuario a mitad de semestre.
- **RegistroAuditoria**: bitacora generica (GenericForeignKey) de
  creaciones, modificaciones, eliminaciones, correcciones
  administrativas y reinicios de simulacion. `usuario`, `accion`,
  `descripcion`, `datos_adicionales` (JSON), `creado_en`.

## apps.cursos

- **Curso**: `nombre`, `profesor` (FK Usuario), `fecha_inicio`,
  `fecha_fin`, `capital_inicial_usd`, `tasa_libre_riesgo_anual`,
  `comision_operacion`, `instrumentos_permitidos` (M2M a Instrumento;
  vacio = todos los activos), `benchmark_principal` (FK Instrumento
  tipo INDICE), `operaciones_activas`, `activo`.
- **Inscripcion**: `curso`, `estudiante`, `fecha_inscripcion`, `activa`.
  UNIQUE (curso, estudiante). Al crearse, una senal
  (`apps/portafolios/signals.py`) crea automaticamente el `Portafolio`
  del estudiante con el capital inicial del curso.

## apps.mercados

- **ProveedorDatosMercado**: catalogo de proveedores (`SINTETICO`,
  `EODHD`, `TWELVEDATA`), `activo`, `es_predeterminado`.
- **Instrumento**: `ticker`, `nombre`, `bolsa` (NYSE/NASDAQ),
  `tipo_instrumento` (ACCION/ETF/INDICE), `pais`, `activo`,
  `fuente_datos` (FK ProveedorDatosMercado). UNIQUE (ticker, bolsa) —
  el ticker **no** es llave unica global, para no confundir
  instrumentos homonimos listados en bolsas distintas. Todos los
  instrumentos cotizan en USD (la plataforma no modela otras divisas).
- **PrecioMercado**: `instrumento`, `fecha`, OHLC, `cierre_ajustado`,
  `volumen`, `fuente`. UNIQUE (instrumento, fecha) — importacion
  idempotente (`update_or_create`).
- **EventoCorporativo**: `instrumento`, `tipo` (SPLIT/DIVIDENDO),
  `fecha_ex`, `factor_split`, `monto_dividendo_por_titulo`, `aplicado`,
  `fecha_aplicacion`. UNIQUE (instrumento, fecha_ex, tipo) — un evento
  nunca se aplica dos veces (`aplicado=True` es la guarda de
  idempotencia que usa el comando `aplicar_eventos_corporativos`).
- **DiaInhabilBursatil**: `bolsa`, `fecha`, `descripcion`. UNIQUE
  (bolsa, fecha).

## apps.operaciones

- **Orden**: `portafolio`, `instrumento`, `tipo` (COMPRA/VENTA),
  `cantidad`, `estado` (PENDIENTE/EJECUTADA/CANCELADA/
  RECHAZADA), `clave_idempotencia` (UNIQUE — defensa contra doble
  clic/reintento), `precio_referencia`, `monto_efectivo_reservado`
  (solo compras), `fecha_solicitud`, `fecha_sesion_objetivo`,
  `motivo_rechazo`, `creado_por`.
- **Ejecucion**: `orden` (OneToOne), `fecha_sesion`, `fecha_ejecucion`,
  `precio_ejecucion`, `cantidad`, `importe_bruto`, `comision`,
  `importe_neto`. Inmutable una vez creada.

## apps.portafolios

- **Portafolio**: `inscripcion` (OneToOne), `efectivo` (USD),
  `efectivo_reservado` (USD).
- **Posicion**: `portafolio`, `instrumento`, `cantidad`,
  `cantidad_reservada`, `costo_promedio` (cache derivada de los lotes).
  UNIQUE (portafolio, instrumento).
- **LoteAdquisicion**: `posicion`, `ejecucion_compra`,
  `fecha_adquisicion`, `cantidad_original`, `cantidad_restante`,
  `costo_unitario`. Fuente de verdad para el costeo FIFO de ventas.
- **MovimientoEfectivo**: libro historico e inmutable de movimientos de
  efectivo (`tipo`, `monto`, `saldo_resultante`, `fecha`, referencia a
  la orden/ejecucion/evento que lo origino).
- **ValuacionPortafolio**: valuacion diaria precalculada (`fecha`,
  `valor_efectivo`, `valor_posiciones`, `valor_total`,
  `rendimiento_diario`, `rendimiento_acumulado`). UNIQUE (portafolio,
  fecha).

## apps.analitica

- **MetricaPortafolio**: metricas precalculadas por ventana (1M, 3M,
  6M, 1A, TODO) y fecha de corte: rendimientos, varianza/volatilidad
  (diaria y anualizada), beta, max drawdown, VaR historico 95%, Sharpe,
  Treynor, alfa de Jensen, tracking error, information ratio.
  `observaciones_insuficientes` + `numero_observaciones` documentan
  cuando NO hay suficiente historia (la vista nunca muestra un numero
  enganoso en ese caso). UNIQUE (portafolio, fecha_corte, ventana).
- **ResultadoOptimizacion**: cache opcional de un resultado de
  Markowitz por curso/tipo/fecha de corte (pesos, rendimiento esperado,
  volatilidad, Sharpe, puntos de la frontera eficiente en JSON).

## apps.reportes

Sin modelos propios: genera exportaciones CSV/Excel a partir de los
modelos de `cursos`, `portafolios` y `analitica` (ver `views.py`).

## Indices y restricciones unicas relevantes para el rendimiento

- `Instrumento(ticker, bolsa)`, `PrecioMercado(instrumento, fecha)`,
  `EventoCorporativo(instrumento, fecha_ex, tipo)`,
  `Orden.clave_idempotencia`, `Posicion(portafolio, instrumento)`,
  `ValuacionPortafolio(portafolio, fecha)`,
  `MetricaPortafolio(portafolio, fecha_corte, ventana)`.
- Indices adicionales en `Orden(portafolio, estado)`,
  `Orden(estado, fecha_sesion_objetivo)` (usado por el cron de
  procesamiento), `LoteAdquisicion(posicion, cantidad_restante)`
  (consumo FIFO), `ValuacionPortafolio(portafolio, -fecha)` y
  `MetricaPortafolio(portafolio, ventana, -fecha_corte)` (lectura del
  dashboard).
