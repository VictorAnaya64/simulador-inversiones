import numpy as np
import pytest

from apps.analitica import services as analitica


def test_rendimiento_acumulado_simple():
    serie = [0.01, 0.02, -0.01]
    esperado = (1.01 * 1.02 * 0.99) - 1
    assert analitica.rendimiento_acumulado(serie) == pytest.approx(esperado)


def test_rendimiento_acumulado_serie_vacia_es_none():
    assert analitica.rendimiento_acumulado([]) is None


def test_volatilidad_y_anualizada():
    serie = [0.01, -0.01, 0.02, -0.02, 0.0]
    vol_diaria = analitica.volatilidad(serie)
    assert vol_diaria == pytest.approx(np.std(serie, ddof=1))
    vol_anual = analitica.volatilidad_anualizada(vol_diaria)
    assert vol_anual == pytest.approx(vol_diaria * (252 ** 0.5))


def test_volatilidad_con_una_sola_observacion_es_none():
    assert analitica.volatilidad([0.01]) is None


def test_max_drawdown():
    valores = [100, 110, 90, 95, 120, 80]
    # El drawdown se mide desde cada maximo acumulado: el peor es (80-120)/120.
    assert analitica.max_drawdown(valores) == pytest.approx((80 - 120) / 120)


def test_max_drawdown_serie_sin_caidas_es_cero():
    valores = [100, 101, 102, 103]
    assert analitica.max_drawdown(valores) == pytest.approx(0.0)


def test_beta_correlacion_perfecta():
    benchmark = [0.01, -0.02, 0.03, -0.01, 0.02, 0.015, -0.005]
    portafolio = [2 * r for r in benchmark]
    assert analitica.beta(portafolio, benchmark) == pytest.approx(2.0, abs=1e-6)


def test_beta_insuficientes_observaciones_es_none():
    assert analitica.beta([0.01, 0.02], [0.01, 0.02]) is None


def test_sharpe_ratio():
    assert analitica.sharpe_ratio(0.15, 0.20, 0.08) == pytest.approx((0.15 - 0.08) / 0.20)


def test_sharpe_ratio_volatilidad_cero_es_none():
    assert analitica.sharpe_ratio(0.15, 0.0, 0.08) is None


def test_treynor_ratio():
    assert analitica.treynor_ratio(0.15, 1.2, 0.08) == pytest.approx((0.15 - 0.08) / 1.2)


def test_alfa_jensen():
    # rend_p=0.15, rend_b=0.10, beta=1.1, rf=0.08
    # esperado = 0.08 + 1.1*(0.10-0.08) = 0.08 + 0.022 = 0.102
    # alfa = 0.15 - 0.102 = 0.048
    assert analitica.alfa_jensen(0.15, 0.10, 1.1, 0.08) == pytest.approx(0.048)


def test_information_ratio_y_tracking_error():
    portafolio = [0.02, -0.01, 0.015, 0.005, -0.005, 0.01]
    benchmark = [0.015, -0.005, 0.01, 0.0, 0.0, 0.008]
    te = analitica.tracking_error(portafolio, benchmark, dias_por_anio=252)
    diffs = np.array(portafolio) - np.array(benchmark)
    assert te == pytest.approx(float(np.std(diffs, ddof=1) * np.sqrt(252)))
    ir = analitica.information_ratio(0.20, 0.15, te)
    assert ir == pytest.approx((0.20 - 0.15) / te)


def test_optimizar_minima_varianza_dos_activos_anticorrelacionados():
    rendimientos_esperados = np.array([0.10, 0.10])
    sigma1, sigma2 = 0.20, 0.20
    correlacion = -1.0
    covarianza = correlacion * sigma1 * sigma2
    matriz_cov = np.array([[sigma1 ** 2, covarianza], [covarianza, sigma2 ** 2]])

    resultado = analitica.optimizar_portafolio_minima_varianza(rendimientos_esperados, matriz_cov)

    assert resultado['pesos'] == pytest.approx([0.5, 0.5], abs=0.01)
    assert resultado['volatilidad_anual'] == pytest.approx(0.0, abs=1e-6)
    assert sum(resultado['pesos']) == pytest.approx(1.0)
    assert all(0 <= p <= 1 for p in resultado['pesos'])


def test_optimizar_maximo_sharpe_pesos_validos():
    rendimientos_esperados = np.array([0.08, 0.15, 0.20])
    matriz_cov = np.array([
        [0.04, 0.01, 0.00],
        [0.01, 0.09, 0.02],
        [0.00, 0.02, 0.16],
    ])
    resultado = analitica.optimizar_portafolio_maximo_sharpe(rendimientos_esperados, matriz_cov, 0.06)
    assert sum(resultado['pesos']) == pytest.approx(1.0, abs=1e-4)
    assert all(-1e-6 <= p <= 1 + 1e-6 for p in resultado['pesos'])
    assert resultado['sharpe'] is not None


def test_frontera_eficiente_rendimientos_crecientes():
    rendimientos_esperados = np.array([0.06, 0.12, 0.18])
    matriz_cov = np.array([
        [0.03, 0.005, 0.00],
        [0.005, 0.08, 0.01],
        [0.00, 0.01, 0.15],
    ])
    puntos = analitica.calcular_frontera_eficiente(rendimientos_esperados, matriz_cov, numero_puntos=10)
    assert len(puntos) > 0
    rendimientos_calculados = [p['rendimiento'] for p in puntos]
    assert rendimientos_calculados == sorted(rendimientos_calculados)
    assert all(p['volatilidad'] >= 0 for p in puntos)
