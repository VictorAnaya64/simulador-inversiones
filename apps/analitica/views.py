import json

import numpy as np
import pandas as pd
from django.shortcuts import render

from apps.mercados.models import Instrumento, PrecioMercado
from apps.portafolios.models import ValuacionPortafolio
from apps.usuarios.decorators import requiere_estudiante

from . import services as analitica
from .models import MetricaPortafolio, VentanaAnalisis

LIMITE_INSTRUMENTOS_OPTIMIZACION = 12


def _inscripcion_activa(usuario):
    return usuario.inscripciones.filter(activa=True, curso__activo=True).select_related('curso', 'portafolio').first()


def _matriz_rendimientos(instrumentos, dias=252):
    series = {}
    for instrumento in instrumentos:
        precios = instrumento.precios.order_by('-fecha')[:dias + 1]
        datos = {p.fecha: float(p.cierre_ajustado) for p in precios}
        series[instrumento.ticker] = pd.Series(datos)
    df_precios = pd.DataFrame(series).sort_index().dropna()
    return df_precios.pct_change().dropna()


@requiere_estudiante
def analisis(request):
    inscripcion = _inscripcion_activa(request.user)
    if inscripcion is None:
        return render(request, 'portafolios/sin_inscripcion.html')

    portafolio = inscripcion.portafolio
    curso = inscripcion.curso

    ultima_fecha_corte = (
        MetricaPortafolio.objects.filter(portafolio=portafolio).order_by('-fecha_corte').values_list('fecha_corte', flat=True).first()
    )
    metricas = []
    if ultima_fecha_corte:
        orden_ventanas = {v: i for i, v in enumerate(VentanaAnalisis.values)}
        metricas = sorted(
            MetricaPortafolio.objects.filter(portafolio=portafolio, fecha_corte=ultima_fecha_corte),
            key=lambda m: orden_ventanas.get(m.ventana, 99),
        )

    instrumentos = list(curso.instrumentos_permitidos.filter(activo=True).exclude(tipo_instrumento='INDICE'))
    if not instrumentos:
        instrumentos = list(Instrumento.objects.filter(activo=True).exclude(tipo_instrumento='INDICE')[:LIMITE_INSTRUMENTOS_OPTIMIZACION])
    instrumentos = instrumentos[:LIMITE_INSTRUMENTOS_OPTIMIZACION]

    correlacion_tickers, correlacion_matriz = [], []
    frontera, optimo_min_var, optimo_max_sharpe = [], None, None

    if len(instrumentos) >= 2:
        df_rendimientos = _matriz_rendimientos(instrumentos)
        if len(df_rendimientos) >= analitica.MINIMO_OBSERVACIONES:
            correlacion = df_rendimientos.corr()
            correlacion_tickers = list(correlacion.columns)
            correlacion_matriz = correlacion.round(3).values.tolist()

            rendimientos_esperados = analitica.rendimientos_esperados_anualizados(df_rendimientos.values)
            matriz_cov = analitica.matriz_covarianza_anualizada(df_rendimientos.values)

            optimo_min_var = analitica.optimizar_portafolio_minima_varianza(rendimientos_esperados, matriz_cov)
            optimo_max_sharpe = analitica.optimizar_portafolio_maximo_sharpe(
                rendimientos_esperados, matriz_cov, curso.tasa_libre_riesgo_anual,
            )
            frontera = analitica.calcular_frontera_eficiente(rendimientos_esperados, matriz_cov, numero_puntos=15)

    valuaciones = list(portafolio.valuaciones.order_by('fecha'))
    benchmark_fechas, benchmark_valores, portafolio_valores_norm = [], [], []
    if curso.benchmark_principal_id and valuaciones:
        precios_benchmark = {
            p.fecha: float(p.cierre_ajustado)
            for p in PrecioMercado.objects.filter(
                instrumento=curso.benchmark_principal, fecha__gte=valuaciones[0].fecha, fecha__lte=valuaciones[-1].fecha,
            )
        }
        primer_valor_portafolio = float(valuaciones[0].valor_total)
        primer_precio_benchmark = None
        for v in valuaciones:
            precio_b = precios_benchmark.get(v.fecha)
            if precio_b is None:
                continue
            if primer_precio_benchmark is None:
                primer_precio_benchmark = precio_b
            benchmark_fechas.append(v.fecha.isoformat())
            benchmark_valores.append(100 * precio_b / primer_precio_benchmark)
            portafolio_valores_norm.append(100 * float(v.valor_total) / primer_valor_portafolio)

    tickers_optimizacion = [i.ticker for i in instrumentos]
    pesos_min_var = list(zip(tickers_optimizacion, optimo_min_var['pesos'])) if optimo_min_var else []
    pesos_max_sharpe = list(zip(tickers_optimizacion, optimo_max_sharpe['pesos'])) if optimo_max_sharpe else []

    return render(request, 'analitica/analisis.html', {
        'curso': curso, 'metricas': metricas,
        'correlacion_tickers_json': json.dumps(correlacion_tickers),
        'correlacion_matriz_json': json.dumps(correlacion_matriz),
        'frontera_json': json.dumps(frontera),
        'optimo_min_var': optimo_min_var,
        'optimo_max_sharpe': optimo_max_sharpe,
        'pesos_min_var': pesos_min_var,
        'pesos_max_sharpe': pesos_max_sharpe,
        'instrumentos_optimizacion': instrumentos,
        'benchmark_fechas_json': json.dumps(benchmark_fechas),
        'benchmark_valores_json': json.dumps(benchmark_valores),
        'portafolio_valores_norm_json': json.dumps(portafolio_valores_norm),
        'tiene_benchmark': bool(curso.benchmark_principal_id),
    })
