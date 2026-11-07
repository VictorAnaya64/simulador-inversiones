from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = (
        'Orquesta la carga completa de datos de demostracion: proveedor + '
        'instrumentos sinteticos, calendario de dias inhabiles, precios '
        'historicos, tipo de cambio y valuaciones retroactivas. Pensado para '
        'dejar el sistema listo para una prueba piloto sin ninguna API externa. '
        'Es seguro volver a correrlo (cada paso es idempotente).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--hasta', type=str, default=None,
            help='Fecha limite AAAA-MM-DD para precios/tipo de cambio/valuaciones (por defecto, hoy).',
        )

    def handle(self, *args, **options):
        hasta = options['hasta']
        hoy = timezone.localdate().isoformat()
        hasta = hasta or hoy

        self.stdout.write('1/5 Creando proveedor sintetico e instrumentos de demostracion...')
        call_command('poblar_instrumentos_sinteticos')

        self.stdout.write('2/5 Cargando calendario aproximado de dias inhabiles bursatiles...')
        call_command('cargar_calendario_festivos')

        self.stdout.write('3/5 Importando precios historicos y eventos corporativos...')
        call_command('importar_precios', hasta=hasta)

        self.stdout.write('4/5 Importando tipo de cambio USD/MXN...')
        call_command('actualizar_tipo_cambio', hasta=hasta)

        self.stdout.write('5/5 Aplicando eventos corporativos ya vencidos...')
        call_command('aplicar_eventos_corporativos')

        self.stdout.write(self.style.SUCCESS(
            'Datos de demostracion listos. Si ya hay cursos/estudiantes dados de '
            'alta, corre tambien "calcular_valuaciones --desde <fecha_inicio_curso>" '
            'y "calcular_metricas" para precalcular el historial de sus portafolios.'
        ))
