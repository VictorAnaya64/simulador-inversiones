import json

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import Instrumento


@login_required
def buscador(request):
    query = request.GET.get('q', '').strip()
    instrumentos = Instrumento.objects.filter(activo=True).exclude(tipo_instrumento='INDICE')
    if query:
        instrumentos = instrumentos.filter(Q(ticker__icontains=query) | Q(nombre__icontains=query))
    instrumentos = instrumentos.order_by('bolsa', 'ticker')

    filas = [{'instrumento': i, 'precio': i.precios.order_by('-fecha').first()} for i in instrumentos]

    return render(request, 'mercados/buscador.html', {'filas': filas, 'query': query})


@login_required
def detalle_instrumento(request, instrumento_id):
    instrumento = get_object_or_404(Instrumento, pk=instrumento_id)
    precios = list(instrumento.precios.order_by('-fecha')[:500])
    precios.reverse()

    return render(request, 'mercados/detalle_instrumento.html', {
        'instrumento': instrumento,
        'ultimo_precio': precios[-1] if precios else None,
        'fechas_json': json.dumps([p.fecha.isoformat() for p in precios]),
        'cierres_json': json.dumps([float(p.cierre_ajustado) for p in precios]),
    })
