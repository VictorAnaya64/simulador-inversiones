# Reglas financieras y formulas

## Capital y restricciones generales

- Capital inicial por defecto: $1,000,000.00 USD (configurable por
  curso, `Curso.capital_inicial_usd`). Se asigna automaticamente al
  crear la inscripcion (senal `apps/portafolios/signals.py`). Toda la
  plataforma opera en una sola divisa (USD): no existe conversion de
  divisas ni saldos en otras monedas.
- Prohibido: apalancamiento, ventas en corto, saldos negativos, titulos
  fraccionados (v1), operaciones con dinero real.
- Todos los importes monetarios usan `Decimal` en Python y `DECIMAL` en
  la base de datos (nunca `float`), para evitar errores de redondeo
  binario. El redondeo de importes de ejecucion usa
  `ROUND_HALF_UP` a 2 decimales (centavos); ver
  `apps/operaciones/services.py`.

## Ciclo de vida de una orden

1. **Creacion** (`apps/operaciones/services.py:crear_orden`):
   valida usuario/curso vigente/`operaciones_activas`/instrumento
   permitido/cantidad entera positiva. Para una **compra**, calcula un
   importe estimado = cantidad x ultimo precio de cierre conocido, y
   reserva ese importe del efectivo disponible (nunca puede reservarse
   mas de lo disponible). Para una **venta**, reserva la cantidad de
   titulos (nunca mas de lo disponible, descontando lo ya reservado por
   otras ordenes). Si la validacion falla, **no se crea ningun
   registro** (no hay orden "rechazada" en este punto; simplemente no
   se crea).
2. **Fecha objetivo**: se calcula la siguiente sesion bursatil habil
   (`apps/mercados/calendario.py:siguiente_sesion_habil`), que es
   siempre **estrictamente posterior** a la fecha de solicitud. Nunca
   se ejecuta una orden con el precio de cierre del mismo dia en que se
   solicito, y nunca con un precio que todavia no existe en la base de
   datos (sin informacion futura).
3. **Procesamiento** (comando de cron `procesar_ordenes`, idempotente):
   para cada orden pendiente cuya `fecha_sesion_objetivo` ya llego, se
   busca el `PrecioMercado` de esa fecha exacta.
   - Si no existe (el precio aun no se ha importado/validado), la orden
     **se mantiene pendiente** sin limite de tiempo en esta primera
     version (limitacion documentada: en produccion, el cron de
     `importar_precios` debe correr todos los dias antes de
     `procesar_ordenes`, para que esto no ocurra en la practica).
   - Si existe, se calcula `importe_bruto = cantidad x precio_cierre`,
     `comision = importe_bruto x Curso.comision_operacion`, e
     `importe_neto = importe_bruto ± comision`.
4. **Politica de rechazo por movimiento de precio** (solo compras): el
   importe reservado en el paso 1 se calculo con un precio de
   *referencia* (el ultimo conocido al crear la orden), que puede ser
   distinto del precio de cierre real de la sesion objetivo. Si
   `importe_neto > monto_reservado`:
   - Si el portafolio tiene suficiente efectivo disponible **no
     reservado** para cubrir la diferencia, se reserva esa diferencia y
     la orden se ejecuta normalmente.
   - Si no alcanza, la orden se **rechaza integramente** (nunca se
     ejecuta parcialmente): se libera toda la reserva, se marca
     `estado=RECHAZADA` con un `motivo_rechazo` explicito, y **nunca**
     se genera saldo negativo.
5. **Ejecucion**: se crea un registro `Ejecucion` (inmutable), se marca
   `Orden.estado=EJECUTADA`, y se aplican los efectos sobre el
   portafolio (`apps/portafolios/services.py:aplicar_ejecucion_compra`
   / `aplicar_ejecucion_venta`), dentro de la misma transaccion
   atomica.
6. **Cancelacion**: solo ordenes `PENDIENTE` pueden cancelarse; libera
   la reserva de efectivo o de titulos correspondiente.
7. **Idempotencia**: `Orden.clave_idempotencia` es UNIQUE. Si
   `crear_orden` recibe una clave ya usada, devuelve la orden existente
   sin volver a validar ni reservar nada (protege contra doble clic y
   reintentos HTTP). El comando `procesar_ordenes` usa
   `select_for_update()` sobre cada orden y verifica su estado dentro
   de la transaccion antes de procesarla, de modo que ejecutarlo varias
   veces (o en paralelo) nunca genera dos ejecuciones de la misma orden.
8. **Ordenes pendientes al finalizar el curso**: el comando
   `procesar_ordenes` **no** verifica si el curso sigue vigente (solo
   lo verifica `crear_orden`, al momento de solicitar una orden nueva).
   Esto es deliberado: una orden ya aceptada antes de que el curso
   terminara debe poder resolverse (ejecutarse o rechazarse por falta
   de fondos) aunque el curso ya haya cerrado, para no dejar
   reservas de efectivo/titulos bloqueadas indefinidamente. El profesor
   puede revisar y cancelar manualmente ordenes pendientes residuales
   desde el admin de Django antes de dar por cerrado un curso.

## Costeo de posiciones (FIFO)

Cada compra ejecutada crea un `LoteAdquisicion` (cantidad y costo
unitario). Cada venta consume lotes en orden FIFO
(`apps/portafolios/services.py:aplicar_ejecucion_venta`): la ganancia o
perdida realizada es `importe_neto_venta - costo_de_los_lotes_consumidos`.
`Posicion.cantidad` y `Posicion.costo_promedio` son una proyeccion
cacheada de los lotes vigentes, recalculada en la misma transaccion que
los modifica (`_recalcular_cache_posicion`).

## Splits y dividendos

- Un `EventoCorporativo` se aplica **exactamente una vez**: el comando
  `aplicar_eventos_corporativos` usa `select_for_update()` sobre el
  evento y verifica `aplicado=False` dentro de la transaccion antes de
  procesarlo.
- **Split** (factor F): multiplica `cantidad` (posicion, reservas y
  lotes) por F y divide `costo_unitario`/`costo_promedio` por F, de
  modo que el valor total de la posicion no cambia.
- **Dividendo** (monto por titulo): acredita en efectivo
  `cantidad_en_la_fecha_ex x monto_por_titulo` a cada portafolio con
  posicion vigente; no modifica cantidades ni costos.
- **Precios originales vs. ajustados**: `PrecioMercado.cierre` es el
  precio crudo (incluye la caida visible de un split en su fecha
  ex-date); `PrecioMercado.cierre_ajustado` incorpora retroactivamente
  splits y dividendos (metodo estandar de ajuste hacia atras), de modo
  que nunca se "re-aplica" un ajuste sobre un precio que ya lo
  incorpora. Las metricas de rendimiento/riesgo usan siempre
  `cierre_ajustado`.
- **Simplificacion documentada**: en el proveedor sintetico, los
  dividendos no provocan una caida mecanica del precio crudo en la
  caminata aleatoria (se modelan como una distribucion de efectivo
  pura); solo los splits generan una caida visible en el precio crudo.
  Esto es razonable para fines didacticos pero no replica al 100% la
  convencion de algunos proveedores de datos reales.

## Divisa unica

- Todos los instrumentos cotizan en NYSE o NASDAQ y estan denominados
  en USD; cada portafolio mantiene un unico saldo de efectivo
  (`Portafolio.efectivo`) tambien en USD. No existe conversion de
  divisas, tipo de cambio, ni saldos en otras monedas: esto es
  deliberado para mantener el modelo simple para el curso.
- El valor consolidado del portafolio (`ValuacionPortafolio`) es
  simplemente `efectivo + valor_de_mercado_de_las_posiciones`, sin
  ningun ajuste cambiario.

## Metricas de teoria de portafolios (`apps/analitica/services.py`)

Todas las funciones devuelven `None` (no `0`) cuando no hay suficiente
informacion (`MINIMO_OBSERVACIONES = 5` observaciones por defecto); la
vista debe mostrar "informacion insuficiente", nunca un numero
enganoso.

- **Rendimiento simple de un periodo**: `(V_f - V_i) / V_i`.
- **Rendimiento acumulado** sobre una serie de rendimientos diarios
  `r_t`: `∏(1 + r_t) - 1`.
- **Rendimiento anualizado**: `(1 + rendimiento_acumulado)^(252/n) - 1`,
  con `n` = numero de observaciones.
- **Volatilidad**: desviacion estandar muestral (`ddof=1`) de los
  rendimientos diarios; **anualizada**: `volatilidad_diaria x sqrt(252)`.
- **Maximo drawdown**: minima caida `(V_t - max(V_0..V_t)) / max(V_0..V_t)`
  sobre la serie de valores del portafolio (no de rendimientos).
- **VaR historico (95%)**: percentil 5 de la serie de rendimientos
  diarios (simulacion historica, sin asumir normalidad).
- **Beta**: `cov(r_portafolio, r_benchmark) / var(r_benchmark)`.
- **Sharpe**: `(rendimiento_anual - r_f) / volatilidad_anual`.
- **Treynor**: `(rendimiento_anual - r_f) / beta`.
- **Alfa de Jensen**: `rendimiento_anual - (r_f + beta x
  (rendimiento_anual_benchmark - r_f))`.
- **Tracking error**: desviacion estandar de `(r_portafolio -
  r_benchmark)`, anualizada.
- **Information ratio**: `(rendimiento_anual_portafolio -
  rendimiento_anual_benchmark) / tracking_error`.
- Todas las razones que dividen entre volatilidad/beta/tracking error
  devuelven `None` si el denominador es menor a `1e-8` en valor
  absoluto (evita valores absurdos por division entre (casi) cero, que
  ademas pueden desbordar la precision de las columnas `DECIMAL` en
  MySQL).
- La **tasa libre de riesgo** es configurable por curso
  (`Curso.tasa_libre_riesgo_anual`).
- Antes de calcular cualquier metrica contra un benchmark, las series
  se alinean por fecha exacta (interseccion de fechas disponibles en
  ambas series); fechas sin dato en una de las dos series se excluyen
  de ambas.

## Optimizacion de Markowitz

- Restricciones siempre aplicadas: pesos en `[0, 1]` (sin
  apalancamiento, sin ventas en corto), suma de pesos = 1.
- **Minima varianza**: minimiza la volatilidad del portafolio sujeta a
  esas restricciones (`scipy.optimize.minimize`, metodo `SLSQP`).
- **Maximo Sharpe**: maximiza `(rendimiento - r_f) / volatilidad` bajo
  las mismas restricciones.
- **Frontera eficiente**: para cada nivel de rendimiento objetivo entre
  el minimo y el maximo de los activos considerados, minimiza la
  volatilidad sujeta a alcanzar ese rendimiento exacto.
- Se calcula sobre, como maximo, los instrumentos permitidos en el
  curso (o los primeros 12 instrumentos activos si el curso no
  restringe el catalogo) y sobre los rendimientos diarios de hasta 252
  sesiones; ver `docs/arquitectura.md` para la justificacion de por que
  esto se calcula en la vista (no en un cron) en esta version.
