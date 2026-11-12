import json

from django.shortcuts import render

from apps.analitica.models import MetricaPortafolio, VentanaAnalisis
from apps.usuarios.decorators import requiere_estudiante


def _inscripcion_activa(usuario):
    return usuario.inscripciones.filter(activa=True, curso__activo=True).select_related('curso', 'portafolio').first()


@requiere_estudiante
def panel_estudiante(request):
    inscripcion = _inscripcion_activa(request.user)
    if inscripcion is None:
        return render(request, 'portafolios/sin_inscripcion.html')

    portafolio = inscripcion.portafolio
    curso = inscripcion.curso

    valuaciones = list(portafolio.valuaciones.order_by('fecha'))
    ultima_valuacion = valuaciones[-1] if valuaciones else None

    posiciones = portafolio.posiciones.filter(cantidad__gt=0).select_related('instrumento')
    filas_posiciones = []
    for posicion in posiciones:
        ultimo_precio = posicion.instrumento.precios.order_by('-fecha').first()
        valor_mercado = (posicion.cantidad * ultimo_precio.cierre) if ultimo_precio else None
        filas_posiciones.append({
            'posicion': posicion, 'ultimo_precio': ultimo_precio, 'valor_mercado': valor_mercado,
        })

    metrica = MetricaPortafolio.objects.filter(
        portafolio=portafolio, ventana=VentanaAnalisis.DESDE_INICIO,
    ).order_by('-fecha_corte').first()

    return render(request, 'portafolios/panel_estudiante.html', {
        'curso': curso, 'portafolio': portafolio, 'ultima_valuacion': ultima_valuacion,
        'filas_posiciones': filas_posiciones, 'metrica': metrica,
        'fechas_json': json.dumps([v.fecha.isoformat() for v in valuaciones]),
        'valores_json': json.dumps([float(v.valor_total) for v in valuaciones]),
        'distribucion_labels_json': json.dumps([f['posicion'].instrumento.ticker for f in filas_posiciones]),
        'distribucion_valores_json': json.dumps([float(f['valor_mercado']) if f['valor_mercado'] else 0 for f in filas_posiciones]),
    })
