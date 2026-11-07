import secrets
import string

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import models
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.analitica.models import MetricaPortafolio, VentanaAnalisis
from apps.usuarios.decorators import requiere_profesor
from apps.usuarios.models import RegistroAuditoria
from apps.usuarios.services import registrar_auditoria

from .forms import FormularioAltaEstudiante, FormularioAltaEstudiantesCSV, FormularioCurso
from .models import Curso, Inscripcion

Usuario = get_user_model()


def _generar_password():
    alfabeto = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alfabeto) for _ in range(10)) + '!1'


def _verificar_propietario(request, curso):
    return request.user.es_admin or curso.profesor_id == request.user.id


@requiere_profesor
def panel_profesor(request):
    if request.user.es_admin:
        cursos = Curso.objects.all()
    else:
        cursos = Curso.objects.filter(profesor=request.user)
    cursos = cursos.annotate(num_estudiantes=models.Count('inscripciones', distinct=True)).order_by('-fecha_inicio')
    return render(request, 'cursos/panel_profesor.html', {'cursos': cursos})


@requiere_profesor
def crear_curso(request):
    if request.method == 'POST':
        form = FormularioCurso(request.POST)
        if form.is_valid():
            curso = form.save(commit=False)
            curso.profesor = request.user
            curso.save()
            form.save_m2m()
            registrar_auditoria(request.user, RegistroAuditoria.Accion.CREACION, f'Curso creado: {curso.nombre}', objeto=curso)
            messages.success(request, f'Curso "{curso.nombre}" creado correctamente.')
            return redirect('cursos:detalle_curso', curso_id=curso.id)
    else:
        form = FormularioCurso()
    return render(request, 'cursos/formulario_curso.html', {'form': form, 'modo': 'crear'})


@requiere_profesor
def detalle_curso(request, curso_id):
    curso = get_object_or_404(Curso, pk=curso_id)
    if not _verificar_propietario(request, curso):
        return HttpResponseForbidden('No tienes permiso sobre este curso.')

    orden_ranking = request.GET.get('orden', 'rendimiento')
    inscripciones = curso.inscripciones.select_related('estudiante', 'portafolio').filter(activa=True)

    filas = []
    for inscripcion in inscripciones:
        portafolio = getattr(inscripcion, 'portafolio', None)
        metrica = None
        if portafolio is not None:
            metrica = MetricaPortafolio.objects.filter(
                portafolio=portafolio, ventana=VentanaAnalisis.DESDE_INICIO,
            ).order_by('-fecha_corte').first()
        filas.append({'estudiante': inscripcion.estudiante, 'portafolio': portafolio, 'metrica': metrica})

    def clave_orden(fila):
        metrica = fila['metrica']
        if metrica is None or metrica.observaciones_insuficientes:
            return float('-inf')
        if orden_ranking == 'sharpe':
            valor = metrica.sharpe
        else:
            valor = metrica.rendimiento_acumulado
        return float(valor) if valor is not None else float('-inf')

    filas.sort(key=clave_orden, reverse=True)

    return render(request, 'cursos/detalle_curso.html', {
        'curso': curso, 'filas': filas, 'orden_ranking': orden_ranking,
    })


@requiere_profesor
def alta_estudiantes(request, curso_id):
    curso = get_object_or_404(Curso, pk=curso_id)
    if not _verificar_propietario(request, curso):
        return HttpResponseForbidden('No tienes permiso sobre este curso.')

    form_individual = FormularioAltaEstudiante(prefix='individual')
    form_csv = FormularioAltaEstudiantesCSV(prefix='csv')
    creados = []

    if request.method == 'POST' and 'individual-username' in request.POST:
        form_individual = FormularioAltaEstudiante(request.POST, prefix='individual')
        if form_individual.is_valid():
            datos = form_individual.cleaned_data
            password = _generar_password()
            estudiante = Usuario.objects.create_user(
                username=datos['username'], password=password, rol=Usuario.Rol.ESTUDIANTE,
                first_name=datos['first_name'], last_name=datos['last_name'],
                matricula=datos['matricula'], email=datos['email'],
            )
            Inscripcion.objects.get_or_create(curso=curso, estudiante=estudiante)
            registrar_auditoria(
                request.user, RegistroAuditoria.Accion.CREACION,
                f'Alta de estudiante {estudiante.username} en {curso.nombre}',
            )
            creados.append({'username': estudiante.username, 'password': password})
            messages.success(request, f'Estudiante {estudiante.username} creado e inscrito.')
            form_individual = FormularioAltaEstudiante(prefix='individual')

    elif request.method == 'POST' and 'csv-archivo_csv' in request.FILES:
        form_csv = FormularioAltaEstudiantesCSV(request.POST, request.FILES, prefix='csv')
        if form_csv.is_valid():
            filas_validas, errores = form_csv.limpiar_filas()
            for fila in filas_validas:
                password = _generar_password()
                estudiante = Usuario.objects.create_user(
                    username=fila['username'], password=password, rol=Usuario.Rol.ESTUDIANTE,
                    first_name=fila['first_name'], last_name=fila['last_name'],
                    matricula=fila['matricula'], email=fila['email'],
                )
                Inscripcion.objects.get_or_create(curso=curso, estudiante=estudiante)
                creados.append({'username': estudiante.username, 'password': password})
            if filas_validas:
                registrar_auditoria(
                    request.user, RegistroAuditoria.Accion.CREACION,
                    f'Alta masiva de {len(filas_validas)} estudiantes en {curso.nombre} via CSV',
                )
                messages.success(request, f'{len(filas_validas)} estudiantes creados e inscritos.')
            for error in errores:
                messages.warning(request, error)
            form_csv = FormularioAltaEstudiantesCSV(prefix='csv')

    return render(request, 'cursos/alta_estudiantes.html', {
        'curso': curso, 'form_individual': form_individual, 'form_csv': form_csv, 'creados': creados,
    })
