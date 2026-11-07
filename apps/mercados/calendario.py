"""
Calendario bursatil simplificado. Un dia es habil para una bolsa si no
es sabado/domingo y no esta registrado como DiaInhabilBursatil (festivos
oficiales de México/EUA segun la bolsa). Ver docs/reglas_financieras.md.
"""
from datetime import timedelta

from .models import DiaInhabilBursatil


def es_dia_habil(bolsa, fecha):
    if fecha.weekday() >= 5:  # 5=sabado, 6=domingo
        return False
    return not DiaInhabilBursatil.objects.filter(bolsa=bolsa, fecha=fecha).exists()


def siguiente_sesion_habil(bolsa, desde_fecha):
    """Primera fecha estrictamente posterior a `desde_fecha` que es sesion habil para `bolsa`."""
    fecha = desde_fecha + timedelta(days=1)
    while not es_dia_habil(bolsa, fecha):
        fecha += timedelta(days=1)
    return fecha
