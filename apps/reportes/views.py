import csv
import io

from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from openpyxl import Workbook

from apps.analitica.models import MetricaPortafolio, VentanaAnalisis
from apps.cursos.models import Curso
from apps.usuarios.decorators import requiere_profesor
from apps.usuarios.models import RegistroAuditoria
from apps.usuarios.services import registrar_auditoria

ENCABEZADOS = [
    'Estudiante', 'Usuario', 'Matricula', 'Efectivo (USD)',
    'Rendimiento acumulado', 'Volatilidad anualizada', 'Sharpe', 'Max drawdown', 'Numero de operaciones',
]


def _verificar_propietario(request, curso):
    return request.user.es_admin or curso.profesor_id == request.user.id


def _filas_curso(curso):
    filas = []
    for inscripcion in curso.inscripciones.select_related('estudiante', 'portafolio').filter(activa=True):
        portafolio = getattr(inscripcion, 'portafolio', None)
        metrica = None
        num_operaciones = 0
        if portafolio is not None:
            metrica = MetricaPortafolio.objects.filter(
                portafolio=portafolio, ventana=VentanaAnalisis.DESDE_INICIO,
            ).order_by('-fecha_corte').first()
            num_operaciones = portafolio.ordenes.filter(estado='EJECUTADA').count()
        filas.append([
            inscripcion.estudiante.get_full_name() or inscripcion.estudiante.username,
            inscripcion.estudiante.username,
            inscripcion.estudiante.matricula,
            float(portafolio.efectivo) if portafolio else None,
            float(metrica.rendimiento_acumulado) if metrica and metrica.rendimiento_acumulado is not None else None,
            float(metrica.volatilidad_anualizada) if metrica and metrica.volatilidad_anualizada is not None else None,
            float(metrica.sharpe) if metrica and metrica.sharpe is not None else None,
            float(metrica.max_drawdown) if metrica and metrica.max_drawdown is not None else None,
            num_operaciones,
        ])
    return filas


@requiere_profesor
def exportar_curso_csv(request, curso_id):
    curso = get_object_or_404(Curso, pk=curso_id)
    if not _verificar_propietario(request, curso):
        return HttpResponseForbidden('No tienes permiso sobre este curso.')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{curso.nombre}.csv"'
    writer = csv.writer(response)
    writer.writerow(ENCABEZADOS)
    for fila in _filas_curso(curso):
        writer.writerow(fila)

    registrar_auditoria(request.user, RegistroAuditoria.Accion.OTRO, f'Exportacion CSV del curso {curso.nombre}')
    return response


@requiere_profesor
def exportar_curso_excel(request, curso_id):
    curso = get_object_or_404(Curso, pk=curso_id)
    if not _verificar_propietario(request, curso):
        return HttpResponseForbidden('No tienes permiso sobre este curso.')

    libro = Workbook()
    hoja = libro.active
    hoja.title = 'Resultados'
    hoja.append(ENCABEZADOS)
    for fila in _filas_curso(curso):
        hoja.append(fila)

    buffer = io.BytesIO()
    libro.save(buffer)
    buffer.seek(0)

    response = HttpResponse(buffer.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{curso.nombre}.xlsx"'

    registrar_auditoria(request.user, RegistroAuditoria.Accion.OTRO, f'Exportacion Excel del curso {curso.nombre}')
    return response
