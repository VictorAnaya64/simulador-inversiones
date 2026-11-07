from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.mercados.models import EventoCorporativo
from apps.operaciones.models import Orden
from apps.operaciones.services import crear_orden, procesar_ordenes_pendientes
from apps.portafolios.models import MovimientoEfectivo, Posicion


def _comprar_y_ejecutar(portafolio, instrumento, estudiante, fabrica_precio, cantidad, precio, clave):
    hoy = timezone.localdate()
    if not instrumento.precios.filter(fecha=hoy).exists():
        fabrica_precio(instrumento, hoy, precio)
    orden = crear_orden(
        portafolio=portafolio, instrumento=instrumento, tipo=Orden.Tipo.COMPRA,
        cantidad=cantidad, usuario=estudiante, clave_idempotencia=clave,
    )
    fabrica_precio(instrumento, orden.fecha_sesion_objetivo, precio)
    procesar_ordenes_pendientes(hasta_fecha=orden.fecha_sesion_objetivo)
    return orden


@pytest.mark.django_db
def test_split_duplica_cantidad_y_divide_costo(portafolio, instrumento_bmv, estudiante, fabrica_precio):
    _comprar_y_ejecutar(portafolio, instrumento_bmv, estudiante, fabrica_precio, 10, '100.00', 'split-compra-1')
    posicion = Posicion.objects.get(portafolio=portafolio, instrumento=instrumento_bmv)
    assert posicion.cantidad == Decimal('10')
    assert posicion.costo_promedio == Decimal('100.00')

    EventoCorporativo.objects.create(
        instrumento=instrumento_bmv, tipo=EventoCorporativo.Tipo.SPLIT,
        fecha_ex=timezone.localdate(), factor_split=Decimal('2.0'),
    )

    call_command('aplicar_eventos_corporativos')

    posicion.refresh_from_db()
    assert posicion.cantidad == Decimal('20')
    assert posicion.costo_promedio == Decimal('50.00')
    lote = posicion.lotes.get()
    assert lote.cantidad_restante == Decimal('20')
    assert lote.costo_unitario == Decimal('50.00')


@pytest.mark.django_db
def test_split_no_se_reaplica_al_correr_el_comando_dos_veces(portafolio, instrumento_bmv, estudiante, fabrica_precio):
    _comprar_y_ejecutar(portafolio, instrumento_bmv, estudiante, fabrica_precio, 10, '100.00', 'split-compra-2')
    EventoCorporativo.objects.create(
        instrumento=instrumento_bmv, tipo=EventoCorporativo.Tipo.SPLIT,
        fecha_ex=timezone.localdate(), factor_split=Decimal('2.0'),
    )
    call_command('aplicar_eventos_corporativos')
    call_command('aplicar_eventos_corporativos')

    posicion = Posicion.objects.get(portafolio=portafolio, instrumento=instrumento_bmv)
    assert posicion.cantidad == Decimal('20')  # no se duplico una segunda vez


@pytest.mark.django_db
def test_dividendo_acredita_efectivo_proporcional_a_cantidad(portafolio, instrumento_bmv, estudiante, fabrica_precio):
    _comprar_y_ejecutar(portafolio, instrumento_bmv, estudiante, fabrica_precio, 100, '50.00', 'div-compra-1')
    efectivo_antes = portafolio.efectivo_mxn
    portafolio.refresh_from_db()
    efectivo_antes = portafolio.efectivo_mxn

    EventoCorporativo.objects.create(
        instrumento=instrumento_bmv, tipo=EventoCorporativo.Tipo.DIVIDENDO,
        fecha_ex=timezone.localdate(), monto_dividendo_por_titulo=Decimal('2.50'),
    )
    call_command('aplicar_eventos_corporativos')

    portafolio.refresh_from_db()
    assert portafolio.efectivo_mxn == efectivo_antes + Decimal('250.00')
    assert MovimientoEfectivo.objects.filter(portafolio=portafolio, tipo=MovimientoEfectivo.Tipo.DIVIDENDO).count() == 1


@pytest.mark.django_db
def test_dividendo_no_se_reprocesa_al_correr_el_comando_dos_veces(portafolio, instrumento_bmv, estudiante, fabrica_precio):
    _comprar_y_ejecutar(portafolio, instrumento_bmv, estudiante, fabrica_precio, 100, '50.00', 'div-compra-2')
    portafolio.refresh_from_db()
    efectivo_antes = portafolio.efectivo_mxn

    EventoCorporativo.objects.create(
        instrumento=instrumento_bmv, tipo=EventoCorporativo.Tipo.DIVIDENDO,
        fecha_ex=timezone.localdate(), monto_dividendo_por_titulo=Decimal('2.50'),
    )
    call_command('aplicar_eventos_corporativos')
    call_command('aplicar_eventos_corporativos')

    portafolio.refresh_from_db()
    assert portafolio.efectivo_mxn == efectivo_antes + Decimal('250.00')
    assert MovimientoEfectivo.objects.filter(portafolio=portafolio, tipo=MovimientoEfectivo.Tipo.DIVIDENDO).count() == 1
