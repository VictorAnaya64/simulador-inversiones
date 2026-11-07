from django.core.management.base import BaseCommand

from apps.operaciones.services import procesar_ordenes_pendientes


class Command(BaseCommand):
    help = (
        'Ejecuta/rechaza las ordenes pendientes cuya sesion objetivo ya llego y '
        'para las que ya hay un precio de cierre validado. Pensado para Cron '
        '(correr varias veces al dia es seguro: es completamente idempotente).'
    )

    def handle(self, *args, **options):
        resultado = procesar_ordenes_pendientes()
        self.stdout.write(self.style.SUCCESS(
            f"Ejecutadas: {resultado['ejecutadas']}, Rechazadas: {resultado['rechazadas']}, "
            f"Sin precio (siguen pendientes): {resultado['sin_precio']}, "
            f"Ya procesadas (omitidas): {resultado['ya_procesadas']}."
        ))
