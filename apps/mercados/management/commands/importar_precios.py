from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.mercados.models import EventoCorporativo, Instrumento, PrecioMercado
from apps.mercados.proveedores.factory import obtener_proveedor_activo


class Command(BaseCommand):
    help = (
        'Descarga (del proveedor de datos de mercado activo) y guarda en MySQL '
        'los precios historicos y eventos corporativos de todos los instrumentos '
        'activos, hasta la fecha indicada (por defecto, hoy). Idempotente: usa '
        'update_or_create sobre la restriccion unica (instrumento, fecha).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--hasta', type=str, default=None, help='Fecha limite AAAA-MM-DD (por defecto, hoy).')
        parser.add_argument('--desde', type=str, default=None, help='Fecha inicial AAAA-MM-DD (por defecto, toda la historia disponible).')

    def handle(self, *args, **options):
        hasta = date.fromisoformat(options['hasta']) if options['hasta'] else timezone.localdate()
        desde = date.fromisoformat(options['desde']) if options['desde'] else date(2022, 1, 1)

        proveedor = obtener_proveedor_activo()
        total_precios, total_eventos = 0, 0

        for instrumento in Instrumento.objects.filter(activo=True):
            precios = proveedor.obtener_precios_historicos(instrumento, desde, hasta)
            with transaction.atomic():
                for precio in precios:
                    PrecioMercado.objects.update_or_create(
                        instrumento=instrumento, fecha=precio.fecha,
                        defaults={
                            'apertura': precio.apertura, 'maximo': precio.maximo, 'minimo': precio.minimo,
                            'cierre': precio.cierre, 'cierre_ajustado': precio.cierre_ajustado,
                            'volumen': precio.volumen, 'fuente': proveedor.nombre_proveedor,
                        },
                    )
            total_precios += len(precios)

            eventos = proveedor.obtener_eventos_corporativos(instrumento, desde, hasta)
            with transaction.atomic():
                for evento in eventos:
                    _, creado = EventoCorporativo.objects.get_or_create(
                        instrumento=instrumento, fecha_ex=evento.fecha_ex, tipo=evento.tipo,
                        defaults={
                            'factor_split': evento.factor_split,
                            'monto_dividendo_por_titulo': evento.monto_dividendo_por_titulo,
                            'fuente': proveedor.nombre_proveedor,
                        },
                    )
                    if creado:
                        total_eventos += 1

        self.stdout.write(self.style.SUCCESS(
            f'Precios importados/actualizados: {total_precios}. Eventos corporativos nuevos: {total_eventos}.'
        ))
