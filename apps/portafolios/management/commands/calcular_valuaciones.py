from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.mercados.models import PrecioMercado
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
        'mercado, en USD) de cada portafolio, para que el dashboard no tenga '
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
        valor_posiciones = Decimal('0.00')

        for posicion in portafolio.posiciones.filter(cantidad__gt=0).select_related('instrumento'):
            precio = PrecioMercado.objects.filter(
                instrumento=posicion.instrumento, fecha__lte=fecha,
            ).order_by('-fecha').first()
            if precio is None:
                continue  # Sin precio conocido aun para este instrumento: se omite del valor (documentado).
            valor_posiciones += posicion.cantidad * precio.cierre

        valor_posiciones = valor_posiciones.quantize(CENTAVO, rounding=ROUND_HALF_UP)
        valor_total = portafolio.efectivo + valor_posiciones

        anterior = ValuacionPortafolio.objects.filter(portafolio=portafolio, fecha__lt=fecha).order_by('-fecha').first()
        rendimiento_diario = None
        if anterior and anterior.valor_total > 0:
            rendimiento_diario = ((valor_total - anterior.valor_total) / anterior.valor_total).quantize(
                OCHO_DECIMALES, rounding=ROUND_HALF_UP,
            )

        capital_inicial = portafolio.inscripcion.curso.capital_inicial_usd
        rendimiento_acumulado = None
        if capital_inicial > 0:
            rendimiento_acumulado = ((valor_total - capital_inicial) / capital_inicial).quantize(
                OCHO_DECIMALES, rounding=ROUND_HALF_UP,
            )

        ValuacionPortafolio.objects.update_or_create(
            portafolio=portafolio, fecha=fecha,
            defaults={
                'valor_efectivo': portafolio.efectivo,
                'valor_posiciones': valor_posiciones,
                'valor_total': valor_total,
                'rendimiento_diario': rendimiento_diario,
                'rendimiento_acumulado': rendimiento_acumulado,
            },
        )
