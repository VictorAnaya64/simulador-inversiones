"""
Funciones puras de teoria de portafolios (rendimiento, riesgo,
desempeno y optimizacion de Markowitz). Reciben datos ya alineados
(misma frecuencia, mismas fechas; todo en USD) y devuelven floats de
Python; la responsabilidad de alinear fechas/benchmarks antes de
llamar a estas funciones es del comando de cron que las usa
(apps/analitica/management/commands/calcular_metricas.py), no de estas
funciones. Ver docs/reglas_financieras.md para las formulas documentadas.

Todas las funciones devuelven None cuando no hay suficiente informacion
para un calculo confiable, en vez de devolver 0 (que seria enganoso).
"""
import numpy as np
from scipy.optimize import minimize

DIAS_POR_ANIO = 252
MINIMO_OBSERVACIONES = 5


def rendimiento_simple_periodo(valor_inicial, valor_final):
    if valor_inicial is None or valor_inicial == 0:
        return None
    return (valor_final - valor_inicial) / valor_inicial


def rendimiento_log_periodo(valor_inicial, valor_final):
    if valor_inicial is None or valor_inicial <= 0 or valor_final <= 0:
        return None
    return float(np.log(float(valor_final) / float(valor_inicial)))


def rendimiento_acumulado(serie_rendimientos_diarios):
    serie = np.asarray(serie_rendimientos_diarios, dtype=float)
    if serie.size == 0:
        return None
    return float(np.prod(1 + serie) - 1)


def rendimiento_anualizado(rendimiento_acumulado_valor, numero_dias, dias_por_anio=DIAS_POR_ANIO):
    if rendimiento_acumulado_valor is None or numero_dias <= 0:
        return None
    base = 1 + rendimiento_acumulado_valor
    if base <= 0:
        return None
    return float(base ** (dias_por_anio / numero_dias) - 1)


def volatilidad(serie_rendimientos_diarios):
    serie = np.asarray(serie_rendimientos_diarios, dtype=float)
    if serie.size < 2:
        return None
    return float(np.std(serie, ddof=1))


def volatilidad_anualizada(volatilidad_diaria, dias_por_anio=DIAS_POR_ANIO):
    if volatilidad_diaria is None:
        return None
    return float(volatilidad_diaria * np.sqrt(dias_por_anio))


def varianza(serie_rendimientos_diarios):
    vol = volatilidad(serie_rendimientos_diarios)
    return None if vol is None else float(vol ** 2)


def max_drawdown(serie_valores):
    """Recibe una serie de VALORES (no rendimientos) y devuelve la caida maxima (negativa o 0)."""
    valores = np.asarray(serie_valores, dtype=float)
    if valores.size < 2:
        return None
    maximos_acumulados = np.maximum.accumulate(valores)
    caidas = (valores - maximos_acumulados) / maximos_acumulados
    return float(np.min(caidas))


def var_historico(serie_rendimientos_diarios, nivel_confianza=0.95):
    serie = np.asarray(serie_rendimientos_diarios, dtype=float)
    if serie.size < MINIMO_OBSERVACIONES:
        return None
    percentil = (1 - nivel_confianza) * 100
    return float(np.percentile(serie, percentil))


def beta(serie_portafolio, serie_benchmark):
    p = np.asarray(serie_portafolio, dtype=float)
    b = np.asarray(serie_benchmark, dtype=float)
    if p.size < MINIMO_OBSERVACIONES or p.size != b.size:
        return None
    varianza_benchmark = np.var(b, ddof=1)
    if varianza_benchmark == 0:
        return None
    covarianza = np.cov(p, b, ddof=1)[0, 1]
    return float(covarianza / varianza_benchmark)


EPSILON_DENOMINADOR = 1e-8


def sharpe_ratio(rendimiento_anual, volatilidad_anual, tasa_libre_riesgo_anual):
    if rendimiento_anual is None or volatilidad_anual is None or abs(volatilidad_anual) < EPSILON_DENOMINADOR:
        return None
    return float((rendimiento_anual - float(tasa_libre_riesgo_anual)) / volatilidad_anual)


def treynor_ratio(rendimiento_anual, beta_valor, tasa_libre_riesgo_anual):
    if rendimiento_anual is None or beta_valor is None or abs(beta_valor) < EPSILON_DENOMINADOR:
        return None
    return float((rendimiento_anual - float(tasa_libre_riesgo_anual)) / beta_valor)


def alfa_jensen(rendimiento_anual_portafolio, rendimiento_anual_benchmark, beta_valor, tasa_libre_riesgo_anual):
    if None in (rendimiento_anual_portafolio, rendimiento_anual_benchmark, beta_valor):
        return None
    rf = float(tasa_libre_riesgo_anual)
    esperado = rf + beta_valor * (rendimiento_anual_benchmark - rf)
    return float(rendimiento_anual_portafolio - esperado)


def tracking_error(serie_portafolio, serie_benchmark, dias_por_anio=DIAS_POR_ANIO):
    p = np.asarray(serie_portafolio, dtype=float)
    b = np.asarray(serie_benchmark, dtype=float)
    if p.size < MINIMO_OBSERVACIONES or p.size != b.size:
        return None
    diferencias = p - b
    return float(np.std(diferencias, ddof=1) * np.sqrt(dias_por_anio))


def information_ratio(rendimiento_anual_portafolio, rendimiento_anual_benchmark, tracking_error_valor):
    if None in (rendimiento_anual_portafolio, rendimiento_anual_benchmark, tracking_error_valor):
        return None
    if abs(tracking_error_valor) < EPSILON_DENOMINADOR:
        return None
    return float((rendimiento_anual_portafolio - rendimiento_anual_benchmark) / tracking_error_valor)


# --- Optimizacion de Markowitz -------------------------------------------------

def matriz_covarianza_anualizada(matriz_rendimientos_diarios, dias_por_anio=DIAS_POR_ANIO):
    """`matriz_rendimientos_diarios`: array (n_obs, n_activos)."""
    datos = np.asarray(matriz_rendimientos_diarios, dtype=float)
    return np.cov(datos, rowvar=False, ddof=1) * dias_por_anio


def rendimientos_esperados_anualizados(matriz_rendimientos_diarios, dias_por_anio=DIAS_POR_ANIO):
    datos = np.asarray(matriz_rendimientos_diarios, dtype=float)
    return np.mean(datos, axis=0) * dias_por_anio


def _rendimiento_portafolio(pesos, rendimientos_esperados):
    return float(np.dot(pesos, rendimientos_esperados))


def _volatilidad_portafolio(pesos, matriz_covarianza):
    return float(np.sqrt(np.dot(pesos, np.dot(matriz_covarianza, pesos))))


def _resolver_pesos_optimos(rendimientos_esperados, matriz_covarianza, objetivo):
    """
    objetivo: 'MIN_VAR' minimiza varianza; 'MAX_SHARPE' maximiza (rend-rf)/vol
    requiere rf en kwargs via closure (ver optimizar_markowitz).
    Restricciones: pesos en [0,1], suma de pesos = 1 (sin apalancamiento, sin cortos).
    """
    n = len(rendimientos_esperados)
    pesos_iniciales = np.repeat(1.0 / n, n)
    restricciones = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]
    limites = [(0.0, 1.0)] * n

    if objetivo == 'MIN_VAR':
        funcion_objetivo = lambda w: _volatilidad_portafolio(w, matriz_covarianza)
    else:
        raise ValueError('Usar _maximizar_sharpe para MAX_SHARPE (requiere tasa libre de riesgo).')

    resultado = minimize(
        funcion_objetivo, pesos_iniciales, method='SLSQP',
        bounds=limites, constraints=restricciones,
    )
    return resultado.x if resultado.success else pesos_iniciales


def _maximizar_sharpe(rendimientos_esperados, matriz_covarianza, tasa_libre_riesgo_anual):
    n = len(rendimientos_esperados)
    pesos_iniciales = np.repeat(1.0 / n, n)
    restricciones = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]
    limites = [(0.0, 1.0)] * n

    def sharpe_negativo(w):
        rend = _rendimiento_portafolio(w, rendimientos_esperados)
        vol = _volatilidad_portafolio(w, matriz_covarianza)
        if vol == 0:
            return 0.0
        return -(rend - float(tasa_libre_riesgo_anual)) / vol

    resultado = minimize(
        sharpe_negativo, pesos_iniciales, method='SLSQP',
        bounds=limites, constraints=restricciones,
    )
    return resultado.x if resultado.success else pesos_iniciales


def optimizar_portafolio_minima_varianza(rendimientos_esperados, matriz_covarianza):
    pesos = _resolver_pesos_optimos(rendimientos_esperados, matriz_covarianza, 'MIN_VAR')
    return {
        'pesos': pesos,
        'rendimiento_esperado_anual': _rendimiento_portafolio(pesos, rendimientos_esperados),
        'volatilidad_anual': _volatilidad_portafolio(pesos, matriz_covarianza),
    }


def optimizar_portafolio_maximo_sharpe(rendimientos_esperados, matriz_covarianza, tasa_libre_riesgo_anual):
    pesos = _maximizar_sharpe(rendimientos_esperados, matriz_covarianza, tasa_libre_riesgo_anual)
    rend = _rendimiento_portafolio(pesos, rendimientos_esperados)
    vol = _volatilidad_portafolio(pesos, matriz_covarianza)
    return {
        'pesos': pesos,
        'rendimiento_esperado_anual': rend,
        'volatilidad_anual': vol,
        'sharpe': sharpe_ratio(rend, vol, tasa_libre_riesgo_anual),
    }


def calcular_frontera_eficiente(rendimientos_esperados, matriz_covarianza, numero_puntos=20):
    """
    Para cada nivel objetivo de rendimiento entre el minimo y el maximo de los
    activos, minimiza la varianza sujeta a alcanzar ese rendimiento. Devuelve
    una lista de puntos {rendimiento, volatilidad} ordenada por rendimiento.
    """
    n = len(rendimientos_esperados)
    rendimiento_min = float(np.min(rendimientos_esperados))
    rendimiento_max = float(np.max(rendimientos_esperados))
    objetivos = np.linspace(rendimiento_min, rendimiento_max, numero_puntos)

    puntos = []
    for objetivo_rendimiento in objetivos:
        pesos_iniciales = np.repeat(1.0 / n, n)
        restricciones = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},
            {'type': 'eq', 'fun': lambda w, r=objetivo_rendimiento: _rendimiento_portafolio(w, rendimientos_esperados) - r},
        ]
        limites = [(0.0, 1.0)] * n
        resultado = minimize(
            lambda w: _volatilidad_portafolio(w, matriz_covarianza), pesos_iniciales,
            method='SLSQP', bounds=limites, constraints=restricciones,
        )
        if resultado.success:
            puntos.append({
                'rendimiento': float(objetivo_rendimiento),
                'volatilidad': _volatilidad_portafolio(resultado.x, matriz_covarianza),
            })
    return puntos
