import uuid

from django.contrib import messages
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.mercados.models import Instrumento
from apps.portafolios.excepciones import EfectivoInsuficienteError, TitulosInsuficientesError
from apps.usuarios.decorators import requiere_estudiante

from .excepciones import (
    CantidadInvalidaError,
    CursoNoDisponibleError,
    InstrumentoNoPermitidoError,
    SinPrecioReferenciaError,
)
from .forms import FormularioOrden
from .models import Orden
from .services import cancelar_orden, crear_orden


def _inscripcion_activa(usuario):
    return usuario.inscripciones.filter(activa=True, curso__activo=True).select_related('curso', 'portafolio').first()


@requiere_estudiante
def nueva_orden(request, instrumento_id, tipo):
    tipo = tipo.upper()
    if tipo not in (Orden.Tipo.COMPRA, Orden.Tipo.VENTA):
        raise Http404('Tipo de orden invalido.')

    instrumento = get_object_or_404(Instrumento, pk=instrumento_id)
    inscripcion = _inscripcion_activa(request.user)
    if inscripcion is None:
        messages.error(request, 'No tienes una inscripcion activa en ningun curso.')
        return redirect('mercados:buscador')
    portafolio = inscripcion.portafolio

    if request.method == 'POST':
        form = FormularioOrden(request.POST)
        if form.is_valid():
            try:
                crear_orden(
                    portafolio=portafolio, instrumento=instrumento, tipo=tipo,
                    cantidad=form.cleaned_data['cantidad'], usuario=request.user,
                    clave_idempotencia=form.cleaned_data['clave_idempotencia'],
                )
                messages.success(request, 'Orden registrada. Se ejecutara al cierre de la siguiente sesion bursatil disponible.')
                return redirect('operaciones:ordenes')
            except (CantidadInvalidaError, CursoNoDisponibleError, InstrumentoNoPermitidoError, SinPrecioReferenciaError) as error:
                messages.error(request, str(error))
            except (EfectivoInsuficienteError, TitulosInsuficientesError) as error:
                messages.error(request, str(error))
    else:
        form = FormularioOrden(initial={'clave_idempotencia': uuid.uuid4().hex})

    posicion = portafolio.posiciones.filter(instrumento=instrumento).first()
    return render(request, 'operaciones/nueva_orden.html', {
        'form': form, 'instrumento': instrumento, 'tipo': tipo, 'portafolio': portafolio, 'posicion': posicion,
    })


@requiere_estudiante
def ordenes(request):
    ordenes_qs = Orden.objects.filter(
        portafolio__inscripcion__estudiante=request.user,
    ).select_related('instrumento', 'portafolio').order_by('-fecha_solicitud')
    return render(request, 'operaciones/ordenes.html', {'ordenes': ordenes_qs})


@requiere_estudiante
def cancelar_orden_view(request, orden_id):
    orden = get_object_or_404(Orden, pk=orden_id)
    if orden.portafolio.inscripcion.estudiante_id != request.user.id:
        return HttpResponseForbidden('No puedes cancelar la orden de otro estudiante.')
    if request.method == 'POST':
        try:
            cancelar_orden(orden, usuario=request.user)
            messages.success(request, 'Orden cancelada; el efectivo o los titulos reservados fueron liberados.')
        except ValueError as error:
            messages.error(request, str(error))
    return redirect('operaciones:ordenes')
