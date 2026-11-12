from datetime import date

import pytest

from apps.mercados.calendario import es_dia_habil, siguiente_sesion_habil
from apps.mercados.models import DiaInhabilBursatil


@pytest.mark.django_db
def test_fin_de_semana_no_es_habil():
    sabado = date(2026, 1, 3)
    domingo = date(2026, 1, 4)
    assert not es_dia_habil('NYSE', sabado)
    assert not es_dia_habil('NYSE', domingo)


@pytest.mark.django_db
def test_dia_festivo_registrado_no_es_habil():
    festivo = date(2026, 1, 1)
    DiaInhabilBursatil.objects.create(bolsa='NYSE', fecha=festivo, descripcion='Ano Nuevo')
    assert not es_dia_habil('NYSE', festivo)
    # El calendario es por bolsa: un festivo registrado solo para NYSE no afecta a NASDAQ.
    assert es_dia_habil('NASDAQ', festivo)


@pytest.mark.django_db
def test_siguiente_sesion_habil_salta_fin_de_semana():
    viernes = date(2026, 1, 2)  # viernes
    siguiente = siguiente_sesion_habil('NYSE', viernes)
    assert siguiente == date(2026, 1, 5)  # lunes


@pytest.mark.django_db
def test_siguiente_sesion_habil_salta_festivo_consecutivo():
    DiaInhabilBursatil.objects.create(bolsa='NYSE', fecha=date(2026, 1, 6), descripcion='Festivo local')
    martes = date(2026, 1, 5)
    siguiente = siguiente_sesion_habil('NYSE', martes)
    assert siguiente == date(2026, 1, 7)


@pytest.mark.django_db
def test_siguiente_sesion_nunca_es_el_mismo_dia():
    hoy = date(2026, 3, 10)  # martes
    siguiente = siguiente_sesion_habil('NASDAQ', hoy)
    assert siguiente > hoy
