from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone


@pytest.fixture
def proveedor_sintetico(db):
    from apps.mercados.models import ProveedorDatosMercado
    return ProveedorDatosMercado.objects.create(
        nombre='Sintetico Demo', tipo=ProveedorDatosMercado.Tipo.SINTETICO,
        activo=True, es_predeterminado=True,
    )


@pytest.fixture
def profesor(db):
    from apps.usuarios.models import Usuario
    return Usuario.objects.create_user(username='profesor1', password='x', rol=Usuario.Rol.PROFESOR)


@pytest.fixture
def estudiante(db):
    from apps.usuarios.models import Usuario
    return Usuario.objects.create_user(username='estudiante1', password='x', rol=Usuario.Rol.ESTUDIANTE)


@pytest.fixture
def otro_estudiante(db):
    from apps.usuarios.models import Usuario
    return Usuario.objects.create_user(username='estudiante2', password='x', rol=Usuario.Rol.ESTUDIANTE)


@pytest.fixture
def curso(db, profesor):
    from apps.cursos.models import Curso
    hoy = timezone.localdate()
    return Curso.objects.create(
        nombre='Teoria de Portafolios 2026-1',
        profesor=profesor,
        fecha_inicio=hoy - timedelta(days=10),
        fecha_fin=hoy + timedelta(days=100),
        capital_inicial_usd=Decimal('1000000.00'),
        comision_operacion=Decimal('0'),
    )


@pytest.fixture
def inscripcion(db, curso, estudiante):
    from apps.cursos.models import Inscripcion
    return Inscripcion.objects.create(curso=curso, estudiante=estudiante)


@pytest.fixture
def portafolio(db, inscripcion):
    # La senal apps.portafolios.signals ya crea el portafolio automaticamente
    # al guardar la inscripcion (con el capital inicial del curso).
    from apps.portafolios.models import Portafolio
    return Portafolio.objects.get(inscripcion=inscripcion)


@pytest.fixture
def instrumento_nyse(db, proveedor_sintetico):
    from apps.mercados.models import Instrumento
    return Instrumento.objects.create(
        ticker='DEMO1', nombre='Demo NYSE 1', bolsa='NYSE',
        tipo_instrumento='ACCION', pais='Estados Unidos', fuente_datos=proveedor_sintetico,
    )


@pytest.fixture
def instrumento_nasdaq(db, proveedor_sintetico):
    from apps.mercados.models import Instrumento
    return Instrumento.objects.create(
        ticker='DEMO2', nombre='Demo NASDAQ 1', bolsa='NASDAQ',
        tipo_instrumento='ACCION', pais='Estados Unidos', fuente_datos=proveedor_sintetico,
    )


@pytest.fixture
def fabrica_precio(db):
    from apps.mercados.models import PrecioMercado

    def _crear(instrumento, fecha, cierre, volumen=1000, fuente='SINTETICO'):
        cierre = Decimal(str(cierre))
        return PrecioMercado.objects.create(
            instrumento=instrumento, fecha=fecha,
            apertura=cierre, maximo=cierre, minimo=cierre,
            cierre=cierre, cierre_ajustado=cierre,
            volumen=volumen, fuente=fuente,
        )
    return _crear
