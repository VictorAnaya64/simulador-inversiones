from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.cursos.models import Inscripcion

from .models import Portafolio


@receiver(post_save, sender=Inscripcion)
def crear_portafolio_al_inscribir(sender, instance, created, **kwargs):
    """Cada inscripcion recibe automaticamente un portafolio con el capital inicial del curso."""
    if created:
        Portafolio.objects.get_or_create(
            inscripcion=instance,
            defaults={'efectivo_mxn': instance.curso.capital_inicial_mxn},
        )
