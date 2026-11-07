import json

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.analitica.models import MetricaPortafolio, VentanaAnalisis
from apps.mercados.models import TipoCambio
from apps.usuarios.decorators import requiere_estudiante

from .excepciones import EfectivoInsuficienteError
from .forms import FormularioConversionDivisa
from .services import convertir_divisa


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

    tipo_cambio = TipoCambio.objects.filter(par=TipoCambio.Par.USDMXN, fecha__lte=timezone.localdate()).order_by('-fecha').first()

    form_conversion = FormularioConversionDivisa()
    if request.method == 'POST':
        form_conversion = FormularioConversionDivisa(request.POST)
        if form_conversion.is_valid() and tipo_cambio is not None:
            datos = form_conversion.cleaned_data
            try:
                convertir_divisa(
                    portafolio, datos['moneda_origen'], datos['moneda_destino'], datos['monto'],
                    tipo_cambio.valor, curso.spread_conversion_divisas,
                )
                messages.success(request, 'Conversion realizada correctamente.')
                return redirect('portafolios:panel_estudiante')
            except EfectivoInsuficienteError as error:
                messages.error(request, str(error))
        elif tipo_cambio is None:
            messages.error(request, 'Aun no hay tipo de cambio USD/MXN cargado; intenta mas tarde.')

    return render(request, 'portafolios/panel_estudiante.html', {
        'curso': curso, 'portafolio': portafolio, 'ultima_valuacion': ultima_valuacion,
        'filas_posiciones': filas_posiciones, 'metrica': metrica, 'tipo_cambio': tipo_cambio,
        'form_conversion': form_conversion,
        'fechas_json': json.dumps([v.fecha.isoformat() for v in valuaciones]),
        'valores_json': json.dumps([float(v.valor_total_mxn) for v in valuaciones]),
        'distribucion_labels_json': json.dumps([f['posicion'].instrumento.ticker for f in filas_posiciones]),
        'distribucion_valores_json': json.dumps([float(f['valor_mercado']) if f['valor_mercado'] else 0 for f in filas_posiciones]),
    })
