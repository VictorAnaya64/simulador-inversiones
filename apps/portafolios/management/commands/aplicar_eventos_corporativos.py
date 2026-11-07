from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.mercados.models import EventoCorporativo
from apps.portafolios import services


class Command(BaseCommand):
    help = (
        'Aplica a las posiciones de los estudiantes los splits y dividendos '
        'cuya fecha ex ya llego y que aun no han sido aplicados. Idempotente: '
        'un evento con aplicado=True nunca se vuelve a procesar.'
    )

    def handle(self, *args, **options):
        hoy = timezone.localdate()
        ids_pendientes = list(
            EventoCorporativo.objects.filter(aplicado=False, fecha_ex__lte=hoy)
            .values_list('id', flat=True)
        )
        aplicados, omitidos = 0, 0
        for evento_id in ids_pendientes:
            if self._aplicar_uno(evento_id):
                aplicados += 1
            else:
                omitidos += 1
        self.stdout.write(self.style.SUCCESS(
            f'Eventos corporativos aplicados: {aplicados}. Ya procesados (omitidos): {omitidos}.'
        ))

    @transaction.atomic
    def _aplicar_uno(self, evento_id):
        evento = EventoCorporativo.objects.select_for_update().select_related('instrumento').get(pk=evento_id)
        if evento.aplicado:
            return False
        if evento.tipo == EventoCorporativo.Tipo.SPLIT:
            services.aplicar_split(evento)
        else:
            services.aplicar_dividendo(evento)
        evento.aplicado = True
        evento.fecha_aplicacion = timezone.now()
        evento.save(update_fields=['aplicado', 'fecha_aplicacion'])
        return True
