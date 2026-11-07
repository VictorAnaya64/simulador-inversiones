"""
Motor de compraventa. Reglas (ver docs/reglas_financieras.md):

- Solo ejecucion a precio de cierre diario; una orden se ejecuta, como
  minimo, al cierre de la siguiente sesion bursatil elegible tras la
  fecha de solicitud (nunca el mismo dia, nunca con informacion futura).
- Sin apalancamiento, sin ventas en corto, sin saldos negativos, sin
  titulos fraccionados.
- Idempotencia: `clave_idempotencia` evita que un doble clic o un
  reintento HTTP genere dos ordenes; volver a invocar `crear_orden` con
  la misma clave devuelve la orden ya existente.
- Si al momento de ejecutar el importe neto excede el efectivo
  reservado, se intenta cubrir la diferencia con efectivo disponible no
  reservado; si no alcanza, la orden se RECHAZA integramente (nunca se
  ejecuta parcialmente ni se genera saldo negativo).
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.mercados.calendario import siguiente_sesion_habil
from apps.mercados.models import PrecioMercado
from apps.portafolios import services as portafolios_services

from .excepciones import (
    CantidadInvalidaError,
    CursoNoDisponibleError,
    InstrumentoNoPermitidoError,
    SinPrecioReferenciaError,
)
from .models import Ejecucion, Orden

CERO = Decimal('0.00')
CENTAVO = Decimal('0.01')


def _ultimo_precio_cierre(instrumento, hasta_fecha=None):
    qs = PrecioMercado.objects.filter(instrumento=instrumento)
    if hasta_fecha is not None:
        qs = qs.filter(fecha__lte=hasta_fecha)
    precio = qs.order_by('-fecha').first()
    return precio


@transaction.atomic
def crear_orden(*, portafolio, instrumento, tipo, cantidad, usuario, clave_idempotencia):
    """
    Crea una orden de compra o venta. Lanza una excepcion (y no crea
    ningun registro) si alguna validacion falla; la unica excepcion es
    cuando `clave_idempotencia` ya existe, en cuyo caso se devuelve la
    orden existente sin volver a validar nada (comportamiento idempotente).
    """
    existente = Orden.objects.filter(clave_idempotencia=clave_idempotencia).first()
    if existente is not None:
        return existente

    cantidad = Decimal(cantidad)
    if cantidad <= 0 or cantidad != cantidad.to_integral_value():
        raise CantidadInvalidaError('La cantidad debe ser un entero positivo (no se permiten titulos fraccionados).')

    curso = portafolio.inscripcion.curso
    hoy = timezone.localdate()
    if not curso.operaciones_activas:
        raise CursoNoDisponibleError('Las operaciones estan desactivadas para este curso.')
    if not curso.esta_en_periodo_vigente(hoy):
        raise CursoNoDisponibleError('El curso no esta vigente (fuera del periodo de inicio/fin).')
    if not curso.permite_instrumento(instrumento):
        raise InstrumentoNoPermitidoError(f'El instrumento {instrumento.clave} no esta permitido en este curso.')

    moneda = instrumento.moneda
    precio_obj = _ultimo_precio_cierre(instrumento, hasta_fecha=hoy)
    fecha_sesion_objetivo = siguiente_sesion_habil(instrumento.bolsa, hoy)

    portafolio_bloqueado = portafolios_services.bloquear_portafolio(portafolio)

    monto_reservado = None
    if tipo == Orden.Tipo.COMPRA:
        if precio_obj is None:
            raise SinPrecioReferenciaError(
                f'No hay precio de referencia disponible para {instrumento.clave}; no se puede validar poder de compra.'
            )
        monto_reservado = (cantidad * precio_obj.cierre).quantize(CENTAVO, rounding=ROUND_HALF_UP)
        portafolios_services.reservar_efectivo(portafolio_bloqueado, moneda, monto_reservado)
    else:
        posicion = portafolios_services.bloquear_posicion(
            portafolios_services.obtener_o_crear_posicion(portafolio_bloqueado, instrumento)
        )
        portafolios_services.reservar_titulos(posicion, cantidad)

    orden = Orden.objects.create(
        portafolio=portafolio_bloqueado,
        instrumento=instrumento,
        tipo=tipo,
        cantidad=cantidad,
        moneda=moneda,
        clave_idempotencia=clave_idempotencia,
        precio_referencia=precio_obj.cierre if precio_obj else None,
        monto_efectivo_reservado=monto_reservado,
        fecha_sesion_objetivo=fecha_sesion_objetivo,
        creado_por=usuario,
    )
    return orden


@transaction.atomic
def cancelar_orden(orden, usuario=None):
    orden = Orden.objects.select_for_update().get(pk=orden.pk)
    if orden.estado != Orden.Estado.PENDIENTE:
        raise ValueError('Solo se pueden cancelar ordenes pendientes.')

    portafolio = portafolios_services.bloquear_portafolio(orden.portafolio)
    if orden.es_compra:
        portafolios_services.liberar_efectivo(portafolio, orden.moneda, orden.monto_efectivo_reservado or CERO)
    else:
        posicion = portafolios_services.bloquear_posicion(
            portafolios_services.obtener_o_crear_posicion(portafolio, orden.instrumento)
        )
        portafolios_services.liberar_titulos(posicion, orden.cantidad)

    orden.estado = Orden.Estado.CANCELADA
    orden.cancelada_en = timezone.now()
    orden.save(update_fields=['estado', 'cancelada_en', 'actualizada_en'])
    return orden


def procesar_ordenes_pendientes(hasta_fecha=None):
    """
    Punto de entrada idempotente para el comando de cron. Recorre las
    ordenes pendientes cuya sesion objetivo ya llego y, si hay un precio
    de cierre validado para esa fecha exacta, las ejecuta o rechaza
    segun la politica documentada; si no hay precio, se dejan pendientes.
    """
    hasta_fecha = hasta_fecha or timezone.localdate()
    resultados = {'ejecutadas': 0, 'rechazadas': 0, 'sin_precio': 0, 'ya_procesadas': 0}
    ids_pendientes = list(
        Orden.objects.filter(estado=Orden.Estado.PENDIENTE, fecha_sesion_objetivo__lte=hasta_fecha)
        .values_list('id', flat=True)
    )
    for orden_id in ids_pendientes:
        resultado = _procesar_una_orden(orden_id)
        resultados[resultado] += 1
    return resultados


@transaction.atomic
def _procesar_una_orden(orden_id):
    orden = Orden.objects.select_for_update().select_related('instrumento', 'portafolio').get(pk=orden_id)
    if orden.estado != Orden.Estado.PENDIENTE:
        return 'ya_procesadas'

    precio_obj = PrecioMercado.objects.filter(
        instrumento=orden.instrumento, fecha=orden.fecha_sesion_objetivo,
    ).first()
    if precio_obj is None:
        return 'sin_precio'

    precio = precio_obj.cierre
    importe_bruto = (orden.cantidad * precio).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    tasa_comision = orden.portafolio.inscripcion.curso.comision_operacion
    comision = (importe_bruto * tasa_comision).quantize(CENTAVO, rounding=ROUND_HALF_UP)

    if orden.es_compra:
        importe_neto = importe_bruto + comision
        reservado = orden.monto_efectivo_reservado or CERO
        faltante = importe_neto - reservado
        portafolio = portafolios_services.bloquear_portafolio(orden.portafolio)
        if faltante > 0:
            disponible_extra = portafolio.efectivo_disponible(orden.moneda)
            if faltante > disponible_extra:
                portafolios_services.liberar_efectivo(portafolio, orden.moneda, reservado)
                orden.estado = Orden.Estado.RECHAZADA
                orden.motivo_rechazo = (
                    f'Efectivo insuficiente al momento de ejecucion: requerido={importe_neto}, '
                    f'reservado={reservado}, disponible_adicional={disponible_extra}'
                )
                orden.save(update_fields=['estado', 'motivo_rechazo', 'actualizada_en'])
                return 'rechazadas'
            portafolios_services.reservar_efectivo(portafolio, orden.moneda, faltante)
            orden.monto_efectivo_reservado = reservado + faltante
    else:
        importe_neto = importe_bruto - comision

    ejecucion = Ejecucion.objects.create(
        orden=orden,
        fecha_sesion=orden.fecha_sesion_objetivo,
        fecha_ejecucion=timezone.now(),
        precio_ejecucion=precio,
        cantidad=orden.cantidad,
        importe_bruto=importe_bruto,
        comision=comision,
        importe_neto=importe_neto,
    )
    orden.estado = Orden.Estado.EJECUTADA
    campos = ['estado', 'actualizada_en']
    if orden.es_compra:
        campos.append('monto_efectivo_reservado')
    orden.save(update_fields=campos)

    if orden.es_compra:
        portafolios_services.aplicar_ejecucion_compra(ejecucion)
    else:
        portafolios_services.aplicar_ejecucion_venta(ejecucion)

    return 'ejecutadas'
