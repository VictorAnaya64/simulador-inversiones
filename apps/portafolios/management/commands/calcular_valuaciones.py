from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.mercados.models import PrecioMercado, TipoCambio
from apps.portafolios.models import Portafolio, ValuacionPortafolio

CENTAVO = Decimal('0.01')
OCHO_DECIMALES = Decimal('0.00000001')


def _fechas_en_rango(desde, hasta):
    fechas = []
    fecha = desde
    while fecha <= hasta:
        if fecha.weekday() < 5:
            fechas.append(fecha)
        fecha += timedelta(days=1)
    return fechas


class Command(BaseCommand):
    help = (
        'Precalcula la valuacion diaria (efectivo + posiciones a precio de '
        'mercado, en MXN) de cada portafolio, para que el dashboard no tenga '
        'que recalcularla en cada solicitud HTTP. Idempotente (update_or_create '
        'sobre la restriccion unica portafolio+fecha). Pensado para Cron diario.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--fecha', type=str, default=None, help='Fecha unica AAAA-MM-DD (por defecto, hoy).')
        parser.add_argument('--desde', type=str, default=None, help='Para recalcular un rango histórico (uso: carga de datos demo).')
        parser.add_argument('--hasta', type=str, default=None)

    def handle(self, *args, **options):
        if options['desde']:
            desde = date.fromisoformat(options['desde'])
            hasta = date.fromisoformat(options['hasta']) if options['hasta'] else timezone.localdate()
            fechas = _fechas_en_rango(desde, hasta)
        else:
            fechas = [date.fromisoformat(options['fecha'])] if options['fecha'] else [timezone.localdate()]

        portafolios = list(Portafolio.objects.select_related('inscripcion__curso').all())
        total = 0
        for fecha in fechas:
            for portafolio in portafolios:
                self._calcular_una(portafolio, fecha)
                total += 1
        self.stdout.write(self.style.SUCCESS(f'Valuaciones calculadas: {total} ({len(portafolios)} portafolios x {len(fechas)} fechas).'))

    def _calcular_una(self, portafolio, fecha):
        tipo_cambio = TipoCambio.objects.filter(par=TipoCambio.Par.USDMXN, fecha__lte=fecha).order_by('-fecha').first()
        valor_tc = tipo_cambio.valor if tipo_cambio else Decimal('1.0')

        valor_efectivo_usd_en_mxn = (portafolio.efectivo_usd * valor_tc).quantize(CENTAVO, rounding=ROUND_HALF_UP)
        valor_posiciones_mxn = Decimal('0.00')

        for posicion in portafolio.posiciones.filter(cantidad__gt=0).select_related('instrumento'):
            precio = PrecioMercado.objects.filter(
                instrumento=posicion.instrumento, fecha__lte=fecha,
            ).order_by('-fecha').first()
            if precio is None:
                continue  # Sin precio conocido aun para este instrumento: se omite del valor (documentado).
            valor_posicion = posicion.cantidad * precio.cierre
            if posicion.instrumento.moneda == 'USD':
                valor_posicion *= valor_tc
            valor_posiciones_mxn += valor_posicion

        valor_posiciones_mxn = valor_posiciones_mxn.quantize(CENTAVO, rounding=ROUND_HALF_UP)
        valor_total_mxn = portafolio.efectivo_mxn + valor_efectivo_usd_en_mxn + valor_posiciones_mxn

        anterior = ValuacionPortafolio.objects.filter(portafolio=portafolio, fecha__lt=fecha).order_by('-fecha').first()
        rendimiento_diario = None
        if anterior and anterior.valor_total_mxn > 0:
            rendimiento_diario = ((valor_total_mxn - anterior.valor_total_mxn) / anterior.valor_total_mxn).quantize(
                OCHO_DECIMALES, rounding=ROUND_HALF_UP,
            )

        capital_inicial = portafolio.inscripcion.curso.capital_inicial_mxn
        rendimiento_acumulado = None
        if capital_inicial > 0:
            rendimiento_acumulado = ((valor_total_mxn - capital_inicial) / capital_inicial).quantize(
                OCHO_DECIMALES, rounding=ROUND_HALF_UP,
            )

        ValuacionPortafolio.objects.update_or_create(
            portafolio=portafolio, fecha=fecha,
            defaults={
                'valor_efectivo_mxn': portafolio.efectivo_mxn,
                'valor_efectivo_usd_en_mxn': valor_efectivo_usd_en_mxn,
                'valor_posiciones_mxn': valor_posiciones_mxn,
                'valor_total_mxn': valor_total_mxn,
                'tipo_cambio_usado': valor_tc,
                'rendimiento_diario': rendimiento_diario,
                'rendimiento_acumulado': rendimiento_acumulado,
            },
        )
