"""
Servicios reutilizables sobre portafolios: reservas de efectivo y
titulos, conversion de divisas y aplicacion de ejecuciones (compra y
venta) con costeo FIFO. Toda funcion que modifica saldos debe llamarse
dentro de una transaccion atomica que ya tenga bloqueado (select_for_update)
el portafolio/posicion relevante, para evitar condiciones de carrera
entre operaciones concurrentes del mismo estudiante.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.mercados.models import Moneda

from .excepciones import EfectivoInsuficienteError, TitulosInsuficientesError
from .models import ConversionDivisa, LoteAdquisicion, MovimientoEfectivo, Posicion

CERO = Decimal('0.00')
CENTAVO = Decimal('0.01')


def bloquear_portafolio(portafolio):
    """Devuelve el portafolio bloqueado (SELECT ... FOR UPDATE). Debe llamarse dentro de atomic()."""
    from .models import Portafolio
    return Portafolio.objects.select_for_update().get(pk=portafolio.pk)


def _campo_efectivo(moneda):
    return 'efectivo_mxn' if moneda == Moneda.MXN else 'efectivo_usd'


def _campo_reservado(moneda):
    return 'efectivo_mxn_reservado' if moneda == Moneda.MXN else 'efectivo_usd_reservado'


def registrar_movimiento_efectivo(portafolio, moneda, tipo, monto, descripcion='', referencia_tipo='', referencia_id='', fecha=None):
    """
    Aplica `monto` (positivo=entrada, negativo=salida) al efectivo del
    portafolio (bloqueado por el llamador) y registra el movimiento.
    Nunca permite que el saldo quede negativo.
    """
    campo = _campo_efectivo(moneda)
    saldo_actual = getattr(portafolio, campo)
    nuevo_saldo = saldo_actual + monto
    if nuevo_saldo < CERO:
        raise EfectivoInsuficienteError(
            f'El movimiento dejaria saldo negativo en {moneda}: {saldo_actual} + {monto} = {nuevo_saldo}'
        )
    setattr(portafolio, campo, nuevo_saldo)
    portafolio.save(update_fields=[campo, 'actualizado_en'])
    return MovimientoEfectivo.objects.create(
        portafolio=portafolio,
        moneda=moneda,
        tipo=tipo,
        monto=monto,
        saldo_resultante=nuevo_saldo,
        fecha=fecha or timezone.now(),
        referencia_tipo=referencia_tipo,
        referencia_id=str(referencia_id),
        descripcion=descripcion,
    )


def reservar_efectivo(portafolio, moneda, monto):
    """Reserva `monto` del efectivo disponible (no afecta el efectivo total, solo el reservado)."""
    disponible = portafolio.efectivo_disponible(moneda)
    if monto > disponible:
        raise EfectivoInsuficienteError(
            f'Efectivo disponible insuficiente en {moneda}: disponible={disponible}, solicitado={monto}'
        )
    campo = _campo_reservado(moneda)
    setattr(portafolio, campo, getattr(portafolio, campo) + monto)
    portafolio.save(update_fields=[campo, 'actualizado_en'])


def liberar_efectivo(portafolio, moneda, monto):
    """Libera `monto` previamente reservado (nunca deja el reservado negativo)."""
    campo = _campo_reservado(moneda)
    nuevo_valor = max(CERO, getattr(portafolio, campo) - monto)
    setattr(portafolio, campo, nuevo_valor)
    portafolio.save(update_fields=[campo, 'actualizado_en'])


def obtener_o_crear_posicion(portafolio, instrumento):
    posicion, _ = Posicion.objects.get_or_create(portafolio=portafolio, instrumento=instrumento)
    return posicion


def bloquear_posicion(posicion):
    return Posicion.objects.select_for_update().get(pk=posicion.pk)


def reservar_titulos(posicion, cantidad):
    if cantidad > posicion.cantidad_disponible:
        raise TitulosInsuficientesError(
            f'Titulos disponibles insuficientes de {posicion.instrumento.ticker}: '
            f'disponible={posicion.cantidad_disponible}, solicitado={cantidad}'
        )
    posicion.cantidad_reservada += cantidad
    posicion.save(update_fields=['cantidad_reservada', 'actualizado_en'])


def liberar_titulos(posicion, cantidad):
    posicion.cantidad_reservada = max(CERO, posicion.cantidad_reservada - cantidad)
    posicion.save(update_fields=['cantidad_reservada', 'actualizado_en'])


@transaction.atomic
def aplicar_ejecucion_compra(ejecucion):
    """
    Aplica los efectos de una compra ejecutada: ajusta el efectivo
    (usa lo reservado; si el costo real excede lo reservado, intenta
    tomar la diferencia del efectivo disponible no reservado; si no
    alcanza, el llamador debe haber rechazado la orden antes de llegar
    aqui), crea el lote de adquisicion FIFO y actualiza la posicion.
    """
    orden = ejecucion.orden
    portafolio = bloquear_portafolio(orden.portafolio)
    moneda = orden.moneda
    monto_reservado = orden.monto_efectivo_reservado or CERO

    liberar_efectivo(portafolio, moneda, monto_reservado)
    registrar_movimiento_efectivo(
        portafolio, moneda, MovimientoEfectivo.Tipo.COMPRA, -ejecucion.importe_neto,
        descripcion=f'Compra {orden.cantidad} {orden.instrumento.ticker} @ {ejecucion.precio_ejecucion}',
        referencia_tipo='Ejecucion', referencia_id=ejecucion.pk, fecha=ejecucion.fecha_ejecucion,
    )

    posicion = obtener_o_crear_posicion(portafolio, orden.instrumento)
    posicion = bloquear_posicion(posicion)
    LoteAdquisicion.objects.create(
        posicion=posicion,
        ejecucion_compra=ejecucion,
        fecha_adquisicion=ejecucion.fecha_sesion,
        cantidad_original=ejecucion.cantidad,
        cantidad_restante=ejecucion.cantidad,
        costo_unitario=ejecucion.importe_neto / ejecucion.cantidad,
    )
    _recalcular_cache_posicion(posicion)


@transaction.atomic
def aplicar_ejecucion_venta(ejecucion):
    """
    Aplica los efectos de una venta ejecutada: consume lotes FIFO para
    determinar el costo de lo vendido (ganancia/perdida realizada),
    libera los titulos reservados, reduce la posicion y acredita el
    efectivo neto.
    """
    orden = ejecucion.orden
    portafolio = bloquear_portafolio(orden.portafolio)
    posicion = bloquear_posicion(obtener_o_crear_posicion(portafolio, orden.instrumento))

    cantidad_por_consumir = ejecucion.cantidad
    costo_total = CERO
    lotes = list(LoteAdquisicion.objects.select_for_update().filter(
        posicion=posicion, cantidad_restante__gt=0,
    ).order_by('fecha_adquisicion', 'id'))
    for lote in lotes:
        if cantidad_por_consumir <= 0:
            break
        consumo = min(lote.cantidad_restante, cantidad_por_consumir)
        costo_total += consumo * lote.costo_unitario
        lote.cantidad_restante -= consumo
        lote.save(update_fields=['cantidad_restante'])
        cantidad_por_consumir -= consumo

    ganancia_realizada = ejecucion.importe_neto - costo_total

    posicion.cantidad -= ejecucion.cantidad
    liberar_titulos(posicion, ejecucion.cantidad)
    _recalcular_cache_posicion(posicion, cantidad_ya_actualizada=True)

    registrar_movimiento_efectivo(
        portafolio, orden.moneda, MovimientoEfectivo.Tipo.VENTA, ejecucion.importe_neto,
        descripcion=(
            f'Venta {orden.cantidad} {orden.instrumento.ticker} @ {ejecucion.precio_ejecucion} '
            f'(G/P realizada: {ganancia_realizada})'
        ),
        referencia_tipo='Ejecucion', referencia_id=ejecucion.pk, fecha=ejecucion.fecha_ejecucion,
    )
    return ganancia_realizada


def _recalcular_cache_posicion(posicion, cantidad_ya_actualizada=False):
    """Recalcula cantidad (si no se actualizo ya) y costo_promedio a partir de los lotes vigentes."""
    lotes_vigentes = posicion.lotes.filter(cantidad_restante__gt=0)
    cantidad_total = sum((l.cantidad_restante for l in lotes_vigentes), CERO)
    costo_total = sum((l.cantidad_restante * l.costo_unitario for l in lotes_vigentes), CERO)
    if not cantidad_ya_actualizada:
        posicion.cantidad = cantidad_total
    posicion.costo_promedio = (costo_total / cantidad_total) if cantidad_total > 0 else CERO
    posicion.save(update_fields=['cantidad', 'costo_promedio', 'actualizado_en'])


@transaction.atomic
def convertir_divisa(portafolio, moneda_origen, moneda_destino, monto_origen, tipo_cambio_base, spread):
    """
    Convierte efectivo entre MXN y USD aplicando un spread contra el
    estudiante (comprar la divisa extranjera siempre cuesta un poco mas
    que el tipo de cambio base; venderla rinde un poco menos).
    """
    if moneda_origen == moneda_destino:
        raise ValueError('La conversion requiere monedas distintas.')

    portafolio = bloquear_portafolio(portafolio)
    disponible = portafolio.efectivo_disponible(moneda_origen)
    if monto_origen > disponible:
        raise EfectivoInsuficienteError(
            f'Efectivo disponible insuficiente en {moneda_origen} para convertir: '
            f'disponible={disponible}, solicitado={monto_origen}'
        )

    if moneda_origen == Moneda.MXN and moneda_destino == Moneda.USD:
        # Comprar USD: el estudiante recibe menos USD por cada MXN (tipo de cambio efectivo mas alto).
        tipo_cambio_efectivo = tipo_cambio_base * (Decimal('1') + spread)
        monto_destino = (monto_origen / tipo_cambio_efectivo).quantize(Decimal('0.01'))
    else:
        # Vender USD: el estudiante recibe menos MXN por cada USD (tipo de cambio efectivo mas bajo).
        tipo_cambio_efectivo = tipo_cambio_base * (Decimal('1') - spread)
        monto_destino = (monto_origen * tipo_cambio_efectivo).quantize(Decimal('0.01'))

    registrar_movimiento_efectivo(
        portafolio, moneda_origen, MovimientoEfectivo.Tipo.CONVERSION_SALIDA, -monto_origen,
        descripcion=f'Conversion {moneda_origen}->{moneda_destino}',
    )
    registrar_movimiento_efectivo(
        portafolio, moneda_destino, MovimientoEfectivo.Tipo.CONVERSION_ENTRADA, monto_destino,
        descripcion=f'Conversion {moneda_origen}->{moneda_destino}',
    )
    return ConversionDivisa.objects.create(
        portafolio=portafolio,
        fecha=timezone.now(),
        moneda_origen=moneda_origen,
        moneda_destino=moneda_destino,
        monto_origen=monto_origen,
        tipo_cambio_base=tipo_cambio_base,
        spread_aplicado=spread,
        tipo_cambio_efectivo=tipo_cambio_efectivo,
        monto_destino=monto_destino,
    )


@transaction.atomic
def aplicar_split(evento):
    """
    Multiplica cantidades (posicion y lotes) por el factor de split y
    divide los costos unitarios por el mismo factor, de modo que el
    valor total de la posicion (cantidad * costo) no cambia. Debe
    llamarse exactamente una vez por evento (el llamador es responsable
    de marcar `evento.aplicado = True` dentro de la misma transaccion
    para garantizar la idempotencia).
    """
    factor = evento.factor_split
    posiciones = Posicion.objects.select_for_update().filter(instrumento=evento.instrumento, cantidad__gt=0)
    for posicion in posiciones:
        posicion.cantidad *= factor
        posicion.cantidad_reservada *= factor
        if posicion.costo_promedio:
            posicion.costo_promedio = posicion.costo_promedio / factor
        posicion.save(update_fields=['cantidad', 'cantidad_reservada', 'costo_promedio', 'actualizado_en'])
        for lote in posicion.lotes.select_for_update().filter(cantidad_restante__gt=0):
            lote.cantidad_original *= factor
            lote.cantidad_restante *= factor
            lote.costo_unitario = lote.costo_unitario / factor
            lote.save(update_fields=['cantidad_original', 'cantidad_restante', 'costo_unitario'])


@transaction.atomic
def aplicar_dividendo(evento):
    """
    Acredita en efectivo, a cada portafolio que tenga posicion vigente
    en el instrumento, `cantidad * monto_dividendo_por_titulo`. Debe
    llamarse exactamente una vez por evento (idempotencia a cargo del
    llamador, igual que `aplicar_split`).
    """
    monto_por_titulo = evento.monto_dividendo_por_titulo
    posiciones = Posicion.objects.select_for_update().filter(instrumento=evento.instrumento, cantidad__gt=0)
    for posicion in posiciones:
        portafolio = bloquear_portafolio(posicion.portafolio)
        monto_total = (posicion.cantidad * monto_por_titulo).quantize(CENTAVO)
        if monto_total <= 0:
            continue
        registrar_movimiento_efectivo(
            portafolio, evento.instrumento.moneda, MovimientoEfectivo.Tipo.DIVIDENDO, monto_total,
            descripcion=f'Dividendo {evento.instrumento.ticker} ex-fecha {evento.fecha_ex}',
            referencia_tipo='EventoCorporativo', referencia_id=evento.pk, fecha=timezone.now(),
        )
