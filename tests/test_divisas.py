from decimal import Decimal

import pytest

from apps.portafolios.excepciones import EfectivoInsuficienteError
from apps.portafolios.models import ConversionDivisa, MovimientoEfectivo
from apps.portafolios.services import convertir_divisa


@pytest.mark.django_db
def test_conversion_mxn_a_usd_aplica_spread_contra_el_estudiante(portafolio):
    tipo_cambio_base = Decimal('20.00')
    spread = Decimal('0.01')  # 1%

    conversion = convertir_divisa(
        portafolio, 'MXN', 'USD', Decimal('2000.00'), tipo_cambio_base, spread,
    )

    tipo_cambio_efectivo_esperado = tipo_cambio_base * Decimal('1.01')
    monto_destino_esperado = (Decimal('2000.00') / tipo_cambio_efectivo_esperado).quantize(Decimal('0.01'))

    assert conversion.tipo_cambio_efectivo == tipo_cambio_efectivo_esperado
    assert conversion.monto_destino == monto_destino_esperado
    # El tipo de cambio efectivo para comprar USD es mas alto que el base (perjudica al estudiante).
    assert conversion.tipo_cambio_efectivo > tipo_cambio_base

    portafolio.refresh_from_db()
    assert portafolio.efectivo_mxn == portafolio.inscripcion.curso.capital_inicial_mxn - Decimal('2000.00')
    assert portafolio.efectivo_usd == monto_destino_esperado


@pytest.mark.django_db
def test_conversion_usd_a_mxn_aplica_spread_contra_el_estudiante(portafolio):
    portafolio.efectivo_usd = Decimal('1000.00')
    portafolio.save()

    tipo_cambio_base = Decimal('20.00')
    spread = Decimal('0.01')

    conversion = convertir_divisa(portafolio, 'USD', 'MXN', Decimal('500.00'), tipo_cambio_base, spread)

    tipo_cambio_efectivo_esperado = tipo_cambio_base * Decimal('0.99')
    assert conversion.tipo_cambio_efectivo == tipo_cambio_efectivo_esperado
    assert conversion.tipo_cambio_efectivo < tipo_cambio_base  # recibe menos MXN por USD

    portafolio.refresh_from_db()
    assert portafolio.efectivo_usd == Decimal('500.00')


@pytest.mark.django_db
def test_conversion_efectivo_insuficiente_no_modifica_saldos(portafolio):
    saldo_previo = portafolio.efectivo_mxn
    with pytest.raises(EfectivoInsuficienteError):
        convertir_divisa(
            portafolio, 'MXN', 'USD', saldo_previo + Decimal('1.00'), Decimal('20.00'), Decimal('0.01'),
        )
    portafolio.refresh_from_db()
    assert portafolio.efectivo_mxn == saldo_previo
    assert portafolio.efectivo_usd == Decimal('0.00')
    assert not ConversionDivisa.objects.exists()


@pytest.mark.django_db
def test_conversion_registra_movimientos_de_entrada_y_salida(portafolio):
    convertir_divisa(portafolio, 'MXN', 'USD', Decimal('1000.00'), Decimal('20.00'), Decimal('0.0'))
    movimientos = MovimientoEfectivo.objects.filter(portafolio=portafolio).order_by('id')
    tipos = list(movimientos.values_list('tipo', flat=True))
    assert MovimientoEfectivo.Tipo.CONVERSION_SALIDA in tipos
    assert MovimientoEfectivo.Tipo.CONVERSION_ENTRADA in tipos
