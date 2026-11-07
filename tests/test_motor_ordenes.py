from decimal import Decimal

import pytest
from django.utils import timezone

from apps.mercados.calendario import siguiente_sesion_habil
from apps.operaciones.excepciones import (
    CantidadInvalidaError,
    InstrumentoNoPermitidoError,
    SinPrecioReferenciaError,
)
from apps.operaciones.models import Ejecucion, Orden
from apps.operaciones.services import cancelar_orden, crear_orden, procesar_ordenes_pendientes
from apps.portafolios.excepciones import EfectivoInsuficienteError, TitulosInsuficientesError
from apps.portafolios.models import MovimientoEfectivo, Posicion


@pytest.mark.django_db
def test_crear_orden_compra_sin_precio_referencia_rechaza(portafolio, instrumento_bmv, estudiante):
    with pytest.raises(SinPrecioReferenciaError):
        crear_orden(
            portafolio=portafolio, instrumento=instrumento_bmv, tipo=Orden.Tipo.COMPRA,
            cantidad=10, usuario=estudiante, clave_idempotencia='k1',
        )
    assert Orden.objects.count() == 0


@pytest.mark.django_db
def test_crear_orden_compra_reserva_efectivo(portafolio, instrumento_bmv, estudiante, fabrica_precio):
    hoy = timezone.localdate()
    fabrica_precio(instrumento_bmv, hoy, '100.00')

    orden = crear_orden(
        portafolio=portafolio, instrumento=instrumento_bmv, tipo=Orden.Tipo.COMPRA,
        cantidad=50, usuario=estudiante, clave_idempotencia='compra-1',
    )

    portafolio.refresh_from_db()
    assert orden.monto_efectivo_reservado == Decimal('5000.00')
    assert portafolio.efectivo_mxn_reservado == Decimal('5000.00')
    assert portafolio.efectivo_disponible('MXN') == portafolio.efectivo_mxn - Decimal('5000.00')
    assert orden.fecha_sesion_objetivo == siguiente_sesion_habil('BMV', hoy)
    assert orden.fecha_sesion_objetivo > hoy


@pytest.mark.django_db
def test_crear_orden_compra_efectivo_insuficiente(portafolio, instrumento_bmv, estudiante, fabrica_precio):
    hoy = timezone.localdate()
    fabrica_precio(instrumento_bmv, hoy, '1000000.00')  # 1 titulo ya cuesta mas que todo el capital

    with pytest.raises(EfectivoInsuficienteError):
        crear_orden(
            portafolio=portafolio, instrumento=instrumento_bmv, tipo=Orden.Tipo.COMPRA,
            cantidad=2, usuario=estudiante, clave_idempotencia='compra-insuf',
        )
    assert Orden.objects.count() == 0
    portafolio.refresh_from_db()
    assert portafolio.efectivo_mxn_reservado == Decimal('0.00')


@pytest.mark.django_db
def test_crear_orden_cantidad_fraccionada_rechazada(portafolio, instrumento_bmv, estudiante, fabrica_precio):
    fabrica_precio(instrumento_bmv, timezone.localdate(), '100.00')
    with pytest.raises(CantidadInvalidaError):
        crear_orden(
            portafolio=portafolio, instrumento=instrumento_bmv, tipo=Orden.Tipo.COMPRA,
            cantidad=Decimal('1.5'), usuario=estudiante, clave_idempotencia='frac-1',
        )


@pytest.mark.django_db
def test_crear_orden_instrumento_no_permitido(portafolio, instrumento_bmv, estudiante, fabrica_precio):
    fabrica_precio(instrumento_bmv, timezone.localdate(), '100.00')
    curso = portafolio.inscripcion.curso
    curso.instrumentos_permitidos.set([])  # vacio -> permite todos activos
    instrumento_bmv.activo = False
    instrumento_bmv.save()
    with pytest.raises(InstrumentoNoPermitidoError):
        crear_orden(
            portafolio=portafolio, instrumento=instrumento_bmv, tipo=Orden.Tipo.COMPRA,
            cantidad=1, usuario=estudiante, clave_idempotencia='noperm-1',
        )


@pytest.mark.django_db
def test_crear_orden_venta_sin_titulos(portafolio, instrumento_bmv, estudiante):
    with pytest.raises(TitulosInsuficientesError):
        crear_orden(
            portafolio=portafolio, instrumento=instrumento_bmv, tipo=Orden.Tipo.VENTA,
            cantidad=10, usuario=estudiante, clave_idempotencia='venta-1',
        )


@pytest.mark.django_db
def test_idempotencia_doble_clic_no_duplica(portafolio, instrumento_bmv, estudiante, fabrica_precio):
    fabrica_precio(instrumento_bmv, timezone.localdate(), '100.00')
    orden1 = crear_orden(
        portafolio=portafolio, instrumento=instrumento_bmv, tipo=Orden.Tipo.COMPRA,
        cantidad=10, usuario=estudiante, clave_idempotencia='misma-clave',
    )
    orden2 = crear_orden(
        portafolio=portafolio, instrumento=instrumento_bmv, tipo=Orden.Tipo.COMPRA,
        cantidad=10, usuario=estudiante, clave_idempotencia='misma-clave',
    )
    assert orden1.pk == orden2.pk
    assert Orden.objects.count() == 1
    portafolio.refresh_from_db()
    # Solo se reservo efectivo una vez.
    assert portafolio.efectivo_mxn_reservado == Decimal('1000.00')


@pytest.mark.django_db
def test_cancelar_orden_libera_reserva(portafolio, instrumento_bmv, estudiante, fabrica_precio):
    fabrica_precio(instrumento_bmv, timezone.localdate(), '100.00')
    orden = crear_orden(
        portafolio=portafolio, instrumento=instrumento_bmv, tipo=Orden.Tipo.COMPRA,
        cantidad=10, usuario=estudiante, clave_idempotencia='cancelar-1',
    )
    cancelar_orden(orden)
    orden.refresh_from_db()
    portafolio.refresh_from_db()
    assert orden.estado == Orden.Estado.CANCELADA
    assert portafolio.efectivo_mxn_reservado == Decimal('0.00')


@pytest.mark.django_db
def test_ejecucion_compra_actualiza_posicion_y_efectivo(portafolio, instrumento_bmv, estudiante, fabrica_precio):
    hoy = timezone.localdate()
    fabrica_precio(instrumento_bmv, hoy, '100.00')
    orden = crear_orden(
        portafolio=portafolio, instrumento=instrumento_bmv, tipo=Orden.Tipo.COMPRA,
        cantidad=10, usuario=estudiante, clave_idempotencia='ejec-compra-1',
    )
    # El precio de cierre de la sesion objetivo (igual al de referencia en este caso).
    fabrica_precio(instrumento_bmv, orden.fecha_sesion_objetivo, '100.00')

    resultado = procesar_ordenes_pendientes(hasta_fecha=orden.fecha_sesion_objetivo)
    assert resultado['ejecutadas'] == 1

    orden.refresh_from_db()
    portafolio.refresh_from_db()
    posicion = Posicion.objects.get(portafolio=portafolio, instrumento=instrumento_bmv)

    assert orden.estado == Orden.Estado.EJECUTADA
    assert posicion.cantidad == Decimal('10')
    assert posicion.costo_promedio == Decimal('100.00')
    capital_inicial = portafolio.inscripcion.curso.capital_inicial_mxn
    assert portafolio.efectivo_mxn == capital_inicial - Decimal('1000.00')
    assert portafolio.efectivo_mxn_reservado == Decimal('0.00')
    assert MovimientoEfectivo.objects.filter(portafolio=portafolio, tipo=MovimientoEfectivo.Tipo.COMPRA).count() == 1


@pytest.mark.django_db
def test_ejecucion_sin_precio_queda_pendiente(portafolio, instrumento_bmv, estudiante, fabrica_precio):
    fabrica_precio(instrumento_bmv, timezone.localdate(), '100.00')
    orden = crear_orden(
        portafolio=portafolio, instrumento=instrumento_bmv, tipo=Orden.Tipo.COMPRA,
        cantidad=10, usuario=estudiante, clave_idempotencia='sinprecio-1',
    )
    # No se crea precio para fecha_sesion_objetivo.
    resultado = procesar_ordenes_pendientes(hasta_fecha=orden.fecha_sesion_objetivo)
    assert resultado['sin_precio'] == 1
    orden.refresh_from_db()
    assert orden.estado == Orden.Estado.PENDIENTE


@pytest.mark.django_db
def test_reprocesamiento_no_duplica_ejecucion(portafolio, instrumento_bmv, estudiante, fabrica_precio):
    hoy = timezone.localdate()
    fabrica_precio(instrumento_bmv, hoy, '100.00')
    orden = crear_orden(
        portafolio=portafolio, instrumento=instrumento_bmv, tipo=Orden.Tipo.COMPRA,
        cantidad=10, usuario=estudiante, clave_idempotencia='reproceso-1',
    )
    fabrica_precio(instrumento_bmv, orden.fecha_sesion_objetivo, '100.00')

    procesar_ordenes_pendientes(hasta_fecha=orden.fecha_sesion_objetivo)
    resultado2 = procesar_ordenes_pendientes(hasta_fecha=orden.fecha_sesion_objetivo)

    assert resultado2['ejecutadas'] == 0
    assert Ejecucion.objects.filter(orden=orden).count() == 1


@pytest.mark.django_db
def test_rechazo_por_alza_de_precio_entre_creacion_y_ejecucion(portafolio, instrumento_bmv, estudiante, fabrica_precio):
    """
    El estudiante reserva efectivo justo para su capital disponible al
    precio de referencia; si el precio de cierre real sube lo suficiente
    y no queda efectivo adicional disponible, la orden se rechaza
    integramente (nunca se ejecuta parcialmente ni se genera saldo negativo).
    """
    hoy = timezone.localdate()
    fabrica_precio(instrumento_bmv, hoy, '100000.00')  # 10 titulos = 1,000,000 = todo el capital
    orden = crear_orden(
        portafolio=portafolio, instrumento=instrumento_bmv, tipo=Orden.Tipo.COMPRA,
        cantidad=10, usuario=estudiante, clave_idempotencia='alza-1',
    )
    # El precio de cierre real de la sesion objetivo sube.
    fabrica_precio(instrumento_bmv, orden.fecha_sesion_objetivo, '150000.00')

    resultado = procesar_ordenes_pendientes(hasta_fecha=orden.fecha_sesion_objetivo)
    assert resultado['rechazadas'] == 1

    orden.refresh_from_db()
    portafolio.refresh_from_db()
    assert orden.estado == Orden.Estado.RECHAZADA
    assert orden.motivo_rechazo != ''
    assert portafolio.efectivo_mxn_reservado == Decimal('0.00')
    assert portafolio.efectivo_mxn == portafolio.inscripcion.curso.capital_inicial_mxn
    assert not Ejecucion.objects.filter(orden=orden).exists()


@pytest.mark.django_db
def test_venta_consume_lotes_fifo_y_calcula_ganancia(
    portafolio, instrumento_bmv, estudiante, fabrica_precio, monkeypatch,
):
    import apps.operaciones.services as ops_services

    hoy = timezone.localdate()

    # Primera compra a 100 (creada "hoy").
    fabrica_precio(instrumento_bmv, hoy, '100.00')
    orden1 = crear_orden(
        portafolio=portafolio, instrumento=instrumento_bmv, tipo=Orden.Tipo.COMPRA,
        cantidad=10, usuario=estudiante, clave_idempotencia='fifo-compra-1',
    )
    fabrica_precio(instrumento_bmv, orden1.fecha_sesion_objetivo, '100.00')
    procesar_ordenes_pendientes(hasta_fecha=orden1.fecha_sesion_objetivo)

    # Segunda compra a 120: se simula que se crea un dia despues (cuando ya
    # llego la sesion de la primera compra), para que su propia sesion
    # objetivo sea una fecha distinta y posterior.
    dia1 = orden1.fecha_sesion_objetivo
    monkeypatch.setattr(ops_services.timezone, 'localdate', lambda: dia1)
    orden2 = crear_orden(
        portafolio=portafolio, instrumento=instrumento_bmv, tipo=Orden.Tipo.COMPRA,
        cantidad=10, usuario=estudiante, clave_idempotencia='fifo-compra-2',
    )
    assert orden2.fecha_sesion_objetivo > dia1
    fabrica_precio(instrumento_bmv, orden2.fecha_sesion_objetivo, '120.00')
    procesar_ordenes_pendientes(hasta_fecha=orden2.fecha_sesion_objetivo)

    posicion = Posicion.objects.get(portafolio=portafolio, instrumento=instrumento_bmv)
    assert posicion.cantidad == Decimal('20')

    # Vender 12 titulos: deben consumirse los 10 del primer lote (costo 100)
    # y 2 del segundo lote (costo 120) -> costo total = 1000 + 240 = 1240.
    dia2 = orden2.fecha_sesion_objetivo
    monkeypatch.setattr(ops_services.timezone, 'localdate', lambda: dia2)
    orden_venta = crear_orden(
        portafolio=portafolio, instrumento=instrumento_bmv, tipo=Orden.Tipo.VENTA,
        cantidad=12, usuario=estudiante, clave_idempotencia='fifo-venta-1',
    )
    assert orden_venta.fecha_sesion_objetivo > dia2
    fabrica_precio(instrumento_bmv, orden_venta.fecha_sesion_objetivo, '130.00')
    procesar_ordenes_pendientes(hasta_fecha=orden_venta.fecha_sesion_objetivo)

    orden_venta.refresh_from_db()
    assert orden_venta.estado == Orden.Estado.EJECUTADA
    ejecucion_venta = Ejecucion.objects.get(orden=orden_venta)
    importe_bruto_esperado = Decimal('12') * Decimal('130.00')
    assert ejecucion_venta.importe_bruto == importe_bruto_esperado

    movimiento_venta = MovimientoEfectivo.objects.filter(
        portafolio=portafolio, tipo=MovimientoEfectivo.Tipo.VENTA,
    ).latest('creado_en')
    ganancia_esperada = importe_bruto_esperado - Decimal('1240.00')
    assert f'{ganancia_esperada}' in movimiento_venta.descripcion

    posicion.refresh_from_db()
    assert posicion.cantidad == Decimal('8')
    # Quedan 8 titulos del segundo lote (costo 120) -> costo promedio 120.
    assert posicion.costo_promedio == Decimal('120.00')
