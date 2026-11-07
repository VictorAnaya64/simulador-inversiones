from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.mercados.models import TipoCambio
from apps.mercados.proveedores.factory import obtener_proveedor_activo


class Command(BaseCommand):
    help = 'Descarga y guarda el tipo de cambio USD/MXN hasta la fecha indicada (por defecto, hoy). Idempotente.'

    def add_arguments(self, parser):
        parser.add_argument('--hasta', type=str, default=None)
        parser.add_argument('--desde', type=str, default=None)

    def handle(self, *args, **options):
        hasta = date.fromisoformat(options['hasta']) if options['hasta'] else timezone.localdate()
        desde = date.fromisoformat(options['desde']) if options['desde'] else date(2022, 1, 1)

        proveedor = obtener_proveedor_activo()
        pares = proveedor.obtener_tipo_cambio_usdmxn(desde, hasta)
        total = 0
        for fecha, valor in pares:
            TipoCambio.objects.update_or_create(
                par=TipoCambio.Par.USDMXN, fecha=fecha,
                defaults={'valor': valor, 'fuente': proveedor.nombre_proveedor},
            )
            total += 1
        self.stdout.write(self.style.SUCCESS(f'Tipos de cambio importados/actualizados: {total}.'))
