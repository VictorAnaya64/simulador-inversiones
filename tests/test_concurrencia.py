"""
Pruebas de integridad bajo concurrencia: dos ordenes de compra que
compiten por el mismo efectivo disponible nunca deben, en conjunto,
reservar mas de lo que el portafolio tiene disponible (lo que
provocaria, mas adelante, un saldo negativo).

Limitacion conocida de SQLite (solo aplica en desarrollo/pruebas
locales, documentada en docs/operacion.md): SQLite admite un unico
escritor a la vez y no implementa bloqueo de filas real, por lo que
`select_for_update()` no bloquea lecturas concurrentes como si lo hace
MySQL/InnoDB en produccion. Bajo SQLite, una de las dos transacciones
concurrentes puede fallar con "database is locked" en lugar de con la
excepcion de negocio `EfectivoInsuficienteError`; en ambos casos la
orden correspondiente NO queda registrada ni reserva efectivo, que es
la propiedad que esta prueba verifica. El comportamiento con bloqueo de
filas real debe validarse en MySQL antes de salir a produccion.
"""
from decimal import Decimal
from threading import Thread

import pytest
from django.db import OperationalError, connection
from django.utils import timezone

from apps.operaciones.models import Orden
from apps.operaciones.services import crear_orden
from apps.portafolios.excepciones import EfectivoInsuficienteError


@pytest.mark.django_db(transaction=True)
def test_dos_compras_concurrentes_no_exceden_el_efectivo_disponible(
    portafolio, instrumento_nyse, estudiante, fabrica_precio,
):
    hoy = timezone.localdate()
    # Precio tal que cada orden individualmente cabe en el capital, pero las dos juntas no.
    fabrica_precio(instrumento_nyse, hoy, '700000.00')

    resultados = {}

    def intentar_compra(etiqueta, clave):
        try:
            crear_orden(
                portafolio=portafolio, instrumento=instrumento_nyse, tipo=Orden.Tipo.COMPRA,
                cantidad=1, usuario=estudiante, clave_idempotencia=clave,
            )
            resultados[etiqueta] = 'ok'
        except EfectivoInsuficienteError:
            resultados[etiqueta] = 'rechazada'
        except OperationalError:
            # Contencion de SQLite (ver docstring del modulo); no aplica en MySQL/InnoDB.
            resultados[etiqueta] = 'lock_error_sqlite'
        finally:
            connection.close()

    hilo1 = Thread(target=intentar_compra, args=('h1', 'conc-1'))
    hilo2 = Thread(target=intentar_compra, args=('h2', 'conc-2'))
    hilo1.start()
    hilo2.start()
    hilo1.join()
    hilo2.join()

    exitosas = [v for v in resultados.values() if v == 'ok']
    # Nunca pueden tener exito las dos (juntas exceden el capital inicial de 1,000,000).
    assert len(exitosas) <= 1

    portafolio.refresh_from_db()
    # Invariante financiera central: lo reservado nunca excede el efectivo total,
    # y el disponible nunca queda negativo, sin importar cuantas ordenes tuvieron exito.
    assert portafolio.efectivo_reservado == Decimal('700000.00') * len(exitosas)
    assert portafolio.efectivo_disponible() >= Decimal('0.00')
    assert Orden.objects.count() == len(exitosas)
