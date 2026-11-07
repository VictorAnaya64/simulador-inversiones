"""
Carga un calendario aproximado de dias inhabiles bursatiles para BMV,
NYSE y NASDAQ entre 2022 y 2028. Se basa en reglas generales (feriados
fijos y de "enesimo lunes del mes") y en el algoritmo estandar de
Computus para calcular Viernes Santo. Es una aproximacion razonable
para fines didacticos, NO una fuente oficial: antes de cada semestre,
el administrador debe revisar y corregir este calendario con las
fechas publicadas por la BMV (https://www.bmv.com.mx) y por NYSE/NASDAQ
(https://www.nyse.com/markets/hours-calendars), incluyendo cierres
anticipados que este comando no modela.
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from apps.mercados.models import DiaInhabilBursatil


def _enesimo_lunes(anio, mes, n):
    fecha = date(anio, mes, 1)
    lunes_encontrados = 0
    while True:
        if fecha.weekday() == 0:
            lunes_encontrados += 1
            if lunes_encontrados == n:
                return fecha
        fecha += timedelta(days=1)


def _ultimo_lunes(anio, mes):
    if mes == 12:
        fecha = date(anio + 1, 1, 1) - timedelta(days=1)
    else:
        fecha = date(anio, mes + 1, 1) - timedelta(days=1)
    while fecha.weekday() != 0:
        fecha -= timedelta(days=1)
    return fecha


def _viernes_santo(anio):
    # Algoritmo de Computus (Anonymous Gregorian algorithm) para Domingo de Pascua.
    a = anio % 19
    b = anio // 100
    c = anio % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    domingo_pascua = date(anio, mes, dia)
    return domingo_pascua - timedelta(days=2)


def _festivos_mexico(anio):
    festivos = [
        (date(anio, 1, 1), 'Ano Nuevo'),
        (_enesimo_lunes(anio, 2, 1), 'Dia de la Constitucion (observado)'),
        (_enesimo_lunes(anio, 3, 3), 'Natalicio de Benito Juarez (observado)'),
        (date(anio, 5, 1), 'Dia del Trabajo'),
        (date(anio, 9, 16), 'Dia de la Independencia'),
        (_enesimo_lunes(anio, 11, 3), 'Dia de la Revolucion (observado)'),
        (date(anio, 12, 25), 'Navidad'),
    ]
    return festivos


def _festivos_eua(anio):
    festivos = [
        (date(anio, 1, 1), "New Year's Day"),
        (_enesimo_lunes(anio, 1, 3), 'Martin Luther King Jr. Day'),
        (_enesimo_lunes(anio, 2, 3), "Washington's Birthday (Presidents Day)"),
        (_viernes_santo(anio), 'Good Friday'),
        (_ultimo_lunes(anio, 5), 'Memorial Day'),
        (date(anio, 6, 19), 'Juneteenth'),
        (date(anio, 7, 4), 'Independence Day'),
        (_enesimo_lunes(anio, 9, 1), 'Labor Day'),
        (_enesimo_lunes(anio, 11, 4) + timedelta(days=3), 'Thanksgiving Day'),
        (date(anio, 12, 25), 'Christmas Day'),
    ]
    return festivos


class Command(BaseCommand):
    help = 'Carga un calendario aproximado de dias inhabiles bursatiles 2022-2028 para BMV, NYSE y NASDAQ. Idempotente.'

    def handle(self, *args, **options):
        total = 0
        for anio in range(2022, 2029):
            for fecha, descripcion in _festivos_mexico(anio):
                _, creado = DiaInhabilBursatil.objects.get_or_create(
                    bolsa='BMV', fecha=fecha, defaults={'descripcion': descripcion},
                )
                total += int(creado)
            for fecha, descripcion in _festivos_eua(anio):
                for bolsa in ('NYSE', 'NASDAQ'):
                    _, creado = DiaInhabilBursatil.objects.get_or_create(
                        bolsa=bolsa, fecha=fecha, defaults={'descripcion': descripcion},
                    )
                    total += int(creado)
        self.stdout.write(self.style.SUCCESS(f'Dias inhabiles nuevos registrados: {total}.'))
        self.stdout.write(self.style.WARNING(
            'Calendario aproximado: verificar contra las fuentes oficiales de BMV y NYSE/NASDAQ antes de cada semestre.'
        ))
