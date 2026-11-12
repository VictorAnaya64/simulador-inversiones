from django.core.management.base import BaseCommand
from django.db import transaction

from apps.mercados.models import Instrumento, ProveedorDatosMercado
from apps.mercados.proveedores.sintetico import BENCHMARKS_SINTETICOS, UNIVERSO_SINTETICO


class Command(BaseCommand):
    help = (
        'Crea (si no existen) el proveedor SINTETICO y los 10 instrumentos de '
        'demostracion (NYSE/NASDAQ, en USD) + 1 indice de referencia. '
        'Idempotente: se puede correr varias veces sin duplicar registros.'
    )

    @transaction.atomic
    def handle(self, *args, **options):
        proveedor, creado = ProveedorDatosMercado.objects.get_or_create(
            nombre='Datos Sinteticos de Demostracion',
            defaults={
                'tipo': ProveedorDatosMercado.Tipo.SINTETICO,
                'activo': True,
                'es_predeterminado': True,
                'notas': 'Proveedor reproducible (semilla fija); no requiere API externa.',
            },
        )
        if creado:
            self.stdout.write(self.style.SUCCESS(f'Proveedor creado: {proveedor.nombre}'))

        total_creados = 0
        for ticker, nombre, bolsa, tipo, pais, *_resto in UNIVERSO_SINTETICO + BENCHMARKS_SINTETICOS:
            _, creado = Instrumento.objects.get_or_create(
                ticker=ticker, bolsa=bolsa,
                defaults={
                    'nombre': nombre, 'tipo_instrumento': tipo,
                    'pais': pais, 'fuente_datos': proveedor, 'activo': True,
                },
            )
            if creado:
                total_creados += 1

        self.stdout.write(self.style.SUCCESS(
            f'Instrumentos nuevos creados: {total_creados} de {len(UNIVERSO_SINTETICO) + len(BENCHMARKS_SINTETICOS)} definidos.'
        ))
