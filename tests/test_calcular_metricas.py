from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.analitica.models import MetricaPortafolio, VentanaAnalisis
from apps.portafolios.models import ValuacionPortafolio


def _crear_valuaciones(portafolio, dias, rendimiento_diario_constante):
    """Crea una serie de valuaciones con un rendimiento diario constante conocido, para poder predecir las metricas."""
    hoy = timezone.localdate()
    valor = portafolio.inscripcion.curso.capital_inicial_mxn
    valuaciones = []
    for offset in range(dias, -1, -1):
        fecha = hoy - timedelta(days=offset)
        if offset != dias:
            valor = valor * (Decimal('1') + rendimiento_diario_constante)
        valuaciones.append(ValuacionPortafolio(
            portafolio=portafolio, fecha=fecha,
            valor_efectivo_mxn=valor, valor_efectivo_usd_en_mxn=Decimal('0'),
            valor_posiciones_mxn=Decimal('0'), valor_total_mxn=valor,
            tipo_cambio_usado=Decimal('18.0'),
            rendimiento_diario=None if offset == dias else rendimiento_diario_constante,
            rendimiento_acumulado=(valor / portafolio.inscripcion.curso.capital_inicial_mxn) - 1,
        ))
    ValuacionPortafolio.objects.bulk_create(valuaciones)


@pytest.mark.django_db
def test_calcular_metricas_con_rendimiento_constante(portafolio):
    curso = portafolio.inscripcion.curso
    curso.fecha_inicio = timezone.localdate() - timedelta(days=60)
    curso.save()
    _crear_valuaciones(portafolio, dias=40, rendimiento_diario_constante=Decimal('0.001'))

    call_command('calcular_metricas')

    metrica = MetricaPortafolio.objects.get(portafolio=portafolio, ventana=VentanaAnalisis.DESDE_INICIO)
    assert metrica.observaciones_insuficientes is False
    assert metrica.numero_observaciones == 40
    # Con rendimiento diario constante, la volatilidad diaria debe ser ~0.
    assert abs(metrica.volatilidad) < Decimal('0.0001')
    assert metrica.rendimiento_acumulado > 0
    assert metrica.max_drawdown == Decimal('0E-8') or metrica.max_drawdown == 0


@pytest.mark.django_db
def test_calcular_metricas_observaciones_insuficientes(portafolio):
    curso = portafolio.inscripcion.curso
    curso.fecha_inicio = timezone.localdate() - timedelta(days=5)
    curso.save()
    _crear_valuaciones(portafolio, dias=2, rendimiento_diario_constante=Decimal('0.001'))

    call_command('calcular_metricas')

    metrica = MetricaPortafolio.objects.get(portafolio=portafolio, ventana=VentanaAnalisis.DESDE_INICIO)
    assert metrica.observaciones_insuficientes is True
    assert metrica.sharpe is None
    assert metrica.rendimiento_acumulado is None


@pytest.mark.django_db
def test_calcular_metricas_es_idempotente_en_reprocesamiento(portafolio):
    curso = portafolio.inscripcion.curso
    curso.fecha_inicio = timezone.localdate() - timedelta(days=60)
    curso.save()
    _crear_valuaciones(portafolio, dias=40, rendimiento_diario_constante=Decimal('0.001'))

    call_command('calcular_metricas')
    call_command('calcular_metricas')

    assert MetricaPortafolio.objects.filter(
        portafolio=portafolio, ventana=VentanaAnalisis.DESDE_INICIO,
    ).count() == 1
