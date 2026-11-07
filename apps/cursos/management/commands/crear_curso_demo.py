from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.cursos.models import Curso, Inscripcion
from apps.mercados.models import Instrumento

Usuario = get_user_model()


class Command(BaseCommand):
    help = (
        'Crea un profesor, N estudiantes y un curso de demostracion ya '
        'inscrito (para probar la plataforma sin capturar datos a mano). '
        'Las contrasenas de demostracion deben cambiarse antes de produccion. '
        'Idempotente: usa get_or_create para usuarios/curso/inscripciones.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--n-estudiantes', type=int, default=10)
        parser.add_argument('--nombre-curso', type=str, default='Teoria de Portafolios - Grupo Demo')
        parser.add_argument('--password', type=str, default='Demo12345!')

    @transaction.atomic
    def handle(self, *args, **options):
        n_estudiantes = options['n_estudiantes']
        password = options['password']
        hoy = timezone.localdate()

        profesor, creado = Usuario.objects.get_or_create(
            username='profesor_demo',
            defaults={'rol': Usuario.Rol.PROFESOR, 'first_name': 'Profesor', 'last_name': 'Demo', 'is_staff': True},
        )
        if creado:
            profesor.set_password(password)
            profesor.save()
            self.stdout.write(self.style.SUCCESS(f'Profesor creado: {profesor.username} / {password}'))

        benchmark = Instrumento.objects.filter(ticker='SIDXBMV', tipo_instrumento='INDICE').first()

        curso, creado = Curso.objects.get_or_create(
            nombre=options['nombre_curso'],
            defaults={
                'profesor': profesor,
                'fecha_inicio': hoy - timedelta(days=15),
                'fecha_fin': hoy + timedelta(days=105),
                'benchmark_principal': benchmark,
            },
        )
        if creado:
            self.stdout.write(self.style.SUCCESS(f'Curso creado: {curso.nombre}'))

        total_nuevos = 0
        for i in range(1, n_estudiantes + 1):
            username = f'estudiante_demo_{i:02d}'
            estudiante, creado = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    'rol': Usuario.Rol.ESTUDIANTE, 'matricula': f'DEMO{i:03d}',
                    'first_name': 'Estudiante', 'last_name': f'Demo {i:02d}',
                },
            )
            if creado:
                estudiante.set_password(password)
                estudiante.save()
                total_nuevos += 1
            Inscripcion.objects.get_or_create(curso=curso, estudiante=estudiante)

        self.stdout.write(self.style.SUCCESS(
            f'Estudiantes nuevos creados: {total_nuevos} de {n_estudiantes} solicitados '
            f'(password de demostracion: {password}). Todos inscritos en "{curso.nombre}".'
        ))
