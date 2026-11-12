"""
Proveedor de datos sinteticos. Permite que todo el sistema funcione sin
contratar ni configurar ninguna API financiera real. Genera un universo
fijo de 10 instrumentos listados en NYSE/NASDAQ (todos cotizados en
USD; la plataforma no modela otras divisas ni otras bolsas) mas 1
indice de referencia, con precios diarios desde 2022-01-03 hasta
2027-12-31, correlaciones realistas entre instrumentos (modelo de un
factor global + un factor de mercado + ruido idiosincratico),
distintos niveles de volatilidad, y algunos splits y dividendos de
ejemplo. Todo es reproducible: la misma semilla siempre genera
exactamente los mismos datos.

Simplificacion documentada (ver docs/reglas_financieras.md): los
dividendos no provocan una caida mecanica del precio crudo en la
caminata aleatoria (se modelan como una distribucion de efectivo pura);
el precio de cierre ajustado si incorpora retroactivamente tanto splits
como dividendos, siguiendo el metodo estandar de ajuste hacia atras.
"""
import math
from datetime import date, timedelta
from decimal import Decimal

import numpy as np

from .base import EventoCorporativoDTO, PrecioDiario, ProveedorCotizacionesBase

FECHA_INICIO_UNIVERSO = date(2022, 1, 3)
FECHA_FIN_UNIVERSO = date(2027, 12, 31)
DIAS_POR_ANIO = 252

# ticker, nombre, bolsa, tipo, pais, precio_inicial, drift_anual, sigma_anual, beta_mercado
UNIVERSO_SINTETICO = [
    ('STEC01', 'Tecnologia Sintetico Inc.', 'NASDAQ', 'ACCION', 'Estados Unidos', 150.0, 0.14, 0.38, 0.85),
    ('STEC02', 'Software Sintetico Inc.', 'NASDAQ', 'ACCION', 'Estados Unidos', 95.0, 0.12, 0.34, 0.80),
    ('SBIO01', 'Biotecnologia Sintetico Inc.', 'NASDAQ', 'ACCION', 'Estados Unidos', 40.0, 0.10, 0.45, 0.50),
    ('SCON01', 'Consumo Sintetico Corp.', 'NYSE', 'ACCION', 'Estados Unidos', 70.0, 0.08, 0.22, 0.65),
    ('SIND01', 'Industrial Sintetico Corp.', 'NYSE', 'ACCION', 'Estados Unidos', 110.0, 0.07, 0.24, 0.70),
    ('SFIN01', 'Financiero Sintetico Corp.', 'NYSE', 'ACCION', 'Estados Unidos', 130.0, 0.09, 0.28, 0.85),
    ('SENE01', 'Energia Sintetico Corp.', 'NYSE', 'ACCION', 'Estados Unidos', 85.0, 0.08, 0.32, 0.75),
    ('SMAT01', 'Materiales Sintetico Corp.', 'NYSE', 'ACCION', 'Estados Unidos', 55.0, 0.06, 0.26, 0.60),
    ('SETFUS1', 'ETF Sintetico S&P Amplio', 'NYSE', 'ETF', 'Estados Unidos', 400.0, 0.10, 0.17, 0.98),
    ('SETFUS2', 'ETF Sintetico Nasdaq 100', 'NASDAQ', 'ETF', 'Estados Unidos', 350.0, 0.13, 0.20, 0.95),
]

BENCHMARKS_SINTETICOS = [
    ('SIDXUS', 'Indice Sintetico EUA', 'NASDAQ', 'INDICE', 'Estados Unidos', 1000.0, 0.10, 0.17, 1.0),
]

SIGMA_GLOBAL_ANUAL = 0.08
SIGMA_MERCADO_ANUAL = 0.18
BETA_GLOBAL = 0.3


def _generar_fechas_habiles(fecha_inicio, fecha_fin):
    fechas = []
    fecha = fecha_inicio
    while fecha <= fecha_fin:
        if fecha.weekday() < 5:
            fechas.append(fecha)
        fecha += timedelta(days=1)
    return fechas


def _simular_ruta_precio(rng, num_dias, precio_inicial, drift_anual, sigma_anual, beta_mercado, componente_global, componente_mercado):
    sigma_total_diaria = sigma_anual / math.sqrt(DIAS_POR_ANIO)
    sigma_global_diaria = SIGMA_GLOBAL_ANUAL / math.sqrt(DIAS_POR_ANIO)
    sigma_mercado_diaria = componente_mercado['sigma_anual'] / math.sqrt(DIAS_POR_ANIO)

    varianza_explicada = (BETA_GLOBAL * sigma_global_diaria) ** 2 + (beta_mercado * sigma_mercado_diaria) ** 2
    piso_varianza_idiosincratica = (0.05 / math.sqrt(DIAS_POR_ANIO)) ** 2
    varianza_idiosincratica = max(sigma_total_diaria ** 2 - varianza_explicada, piso_varianza_idiosincratica)
    sigma_idiosincratica_diaria = math.sqrt(varianza_idiosincratica)

    ruido_idiosincratico = rng.standard_normal(num_dias) * sigma_idiosincratica_diaria
    mu_diaria = drift_anual / DIAS_POR_ANIO

    rendimientos_log = (
        mu_diaria - 0.5 * sigma_total_diaria ** 2
        + BETA_GLOBAL * componente_global
        + beta_mercado * componente_mercado['serie']
        + ruido_idiosincratico
    )
    log_precio = math.log(precio_inicial) + np.cumsum(rendimientos_log)
    return np.exp(log_precio)


def _decidir_eventos_corporativos(rng, ticker, tipo_instrumento, fechas):
    """
    Asigna deterministicamente algunos splits/dividendos de ejemplo.
    Usa el indice del ticker dentro del universo (ya fijo) para decidir
    quien recibe eventos, y el rng (ya sembrado) para variar montos.
    """
    eventos = []
    indice_ticker = next((i for i, t in enumerate(UNIVERSO_SINTETICO) if t[0] == ticker), None)
    if indice_ticker is None:
        return eventos

    if tipo_instrumento == 'ACCION' and indice_ticker % 3 == 0:
        # Dividendo semestral aproximado (indices de dias de pago fijos y deterministicos).
        for offset in range(180, len(fechas), 180):
            fecha_ex = fechas[offset]
            monto = Decimal(str(round(float(rng.uniform(0.3, 1.2)), 4)))
            eventos.append(EventoCorporativoDTO(fecha_ex=fecha_ex, tipo='DIVIDENDO', monto_dividendo_por_titulo=monto))

    if tipo_instrumento == 'ACCION' and indice_ticker % 7 == 0:
        offset_split = min(500, len(fechas) - 1)
        fecha_ex = fechas[offset_split]
        eventos.append(EventoCorporativoDTO(fecha_ex=fecha_ex, tipo='SPLIT', factor_split=Decimal('2.0')))

    return eventos


def _aplicar_splits_y_calcular_ajustado(precio_suave, fechas, eventos):
    """
    `precio_suave` es la ruta continua (sin reflejar splits todavia).
    Devuelve (cierre_crudo, cierre_ajustado) aplicando el split hacia
    adelante sobre el precio crudo y el ajuste estandar hacia atras
    (splits + dividendos) sobre el precio ajustado.
    """
    num_dias = len(fechas)
    indice_por_fecha = {f: i for i, f in enumerate(fechas)}

    divisor_split_acumulado = np.ones(num_dias)
    divisor_actual = 1.0
    for evento in sorted((e for e in eventos if e.tipo == 'SPLIT'), key=lambda e: e.fecha_ex):
        idx_ex = indice_por_fecha.get(evento.fecha_ex)
        if idx_ex is None:
            continue
        divisor_actual *= float(evento.factor_split)
        divisor_split_acumulado[idx_ex:] = divisor_actual

    cierre_crudo = precio_suave / divisor_split_acumulado

    eventos_por_fecha = {}
    for evento in eventos:
        eventos_por_fecha.setdefault(evento.fecha_ex, []).append(evento)

    cierre_ajustado = np.empty(num_dias)
    multiplicador = 1.0
    for i in range(num_dias - 1, -1, -1):
        cierre_ajustado[i] = cierre_crudo[i] * multiplicador
        for evento in eventos_por_fecha.get(fechas[i], []):
            if evento.tipo == 'SPLIT':
                multiplicador *= 1.0 / float(evento.factor_split)
            elif evento.tipo == 'DIVIDENDO':
                referencia = cierre_crudo[i] if cierre_crudo[i] > 0 else 1.0
                factor = max(0.01, 1 - float(evento.monto_dividendo_por_titulo) / referencia)
                multiplicador *= factor

    return cierre_crudo, cierre_ajustado


class ProveedorSintetico(ProveedorCotizacionesBase):
    nombre_proveedor = 'SINTETICO'
    SEMILLA_DEFAULT = 42

    def __init__(self, semilla=None):
        self.semilla = self.SEMILLA_DEFAULT if semilla is None else semilla
        self._cache = None

    def _construir_universo(self):
        if self._cache is not None:
            return self._cache

        rng = np.random.default_rng(self.semilla)
        fechas = _generar_fechas_habiles(FECHA_INICIO_UNIVERSO, FECHA_FIN_UNIVERSO)
        num_dias = len(fechas)

        global_serie = rng.standard_normal(num_dias) * (SIGMA_GLOBAL_ANUAL / math.sqrt(DIAS_POR_ANIO))
        mercado_serie = rng.standard_normal(num_dias) * (SIGMA_MERCADO_ANUAL / math.sqrt(DIAS_POR_ANIO))
        componente_mercado = {'serie': mercado_serie, 'sigma_anual': SIGMA_MERCADO_ANUAL}

        instrumentos = {}
        for ticker, nombre, bolsa, tipo, pais, p0, drift, sigma, beta in (
            UNIVERSO_SINTETICO + BENCHMARKS_SINTETICOS
        ):
            precio_suave = _simular_ruta_precio(
                rng, num_dias, p0, drift, sigma, beta, global_serie, componente_mercado,
            )
            eventos = [] if tipo == 'INDICE' else _decidir_eventos_corporativos(rng, ticker, tipo, fechas)
            cierre_crudo, cierre_ajustado = _aplicar_splits_y_calcular_ajustado(precio_suave, fechas, eventos)

            apertura = np.empty(num_dias)
            apertura[0] = cierre_crudo[0]
            apertura[1:] = cierre_crudo[:-1] * (1 + rng.standard_normal(num_dias - 1) * 0.002)
            rango_intradia = np.abs(rng.standard_normal(num_dias)) * (sigma / math.sqrt(DIAS_POR_ANIO)) * cierre_crudo
            maximo = np.maximum(apertura, cierre_crudo) + rango_intradia * 0.5
            minimo = np.maximum(np.minimum(apertura, cierre_crudo) - rango_intradia * 0.5, 0.01)
            volumen_base = 2_000_000 if tipo == 'ETF' else 500_000
            volumen = (volumen_base * np.exp(rng.standard_normal(num_dias) * 0.3)).astype(int)

            instrumentos[ticker] = {
                'nombre': nombre, 'bolsa': bolsa, 'tipo': tipo, 'pais': pais,
                'fechas': fechas, 'apertura': apertura, 'maximo': maximo, 'minimo': minimo,
                'cierre': cierre_crudo, 'cierre_ajustado': cierre_ajustado, 'volumen': volumen,
                'eventos': eventos,
            }

        self._cache = {'fechas': fechas, 'instrumentos': instrumentos}
        return self._cache

    def obtener_precios_historicos(self, instrumento, fecha_inicio, fecha_fin):
        universo = self._construir_universo()
        datos = universo['instrumentos'].get(instrumento.ticker)
        if datos is None:
            return []
        resultado = []
        for i, fecha in enumerate(datos['fechas']):
            if fecha_inicio <= fecha <= fecha_fin:
                resultado.append(PrecioDiario(
                    fecha=fecha,
                    apertura=Decimal(str(round(float(datos['apertura'][i]), 6))),
                    maximo=Decimal(str(round(float(datos['maximo'][i]), 6))),
                    minimo=Decimal(str(round(float(datos['minimo'][i]), 6))),
                    cierre=Decimal(str(round(float(datos['cierre'][i]), 6))),
                    cierre_ajustado=Decimal(str(round(float(datos['cierre_ajustado'][i]), 6))),
                    volumen=int(datos['volumen'][i]),
                ))
        return resultado

    def obtener_eventos_corporativos(self, instrumento, fecha_inicio, fecha_fin):
        universo = self._construir_universo()
        datos = universo['instrumentos'].get(instrumento.ticker)
        if datos is None:
            return []
        return [e for e in datos['eventos'] if fecha_inicio <= e.fecha_ex <= fecha_fin]

    def listar_tickers_universo(self):
        return [t[0] for t in UNIVERSO_SINTETICO]

    def listar_tickers_benchmarks(self):
        return [t[0] for t in BENCHMARKS_SINTETICOS]
