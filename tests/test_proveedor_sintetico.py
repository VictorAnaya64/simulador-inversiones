from datetime import date
from decimal import Decimal

from apps.mercados.proveedores.sintetico import (
    FECHA_FIN_UNIVERSO,
    FECHA_INICIO_UNIVERSO,
    UNIVERSO_SINTETICO,
    ProveedorSintetico,
)


class _InstrumentoFalso:
    """Objeto minimo con el atributo `ticker` que espera el proveedor, sin tocar la base de datos."""
    def __init__(self, ticker):
        self.ticker = ticker


def test_universo_tiene_al_menos_10_instrumentos():
    assert len(UNIVERSO_SINTETICO) >= 10


def test_misma_semilla_genera_los_mismos_precios():
    proveedor1 = ProveedorSintetico(semilla=42)
    proveedor2 = ProveedorSintetico(semilla=42)
    instrumento = _InstrumentoFalso('STEC01')

    precios1 = proveedor1.obtener_precios_historicos(instrumento, date(2023, 1, 1), date(2023, 3, 1))
    precios2 = proveedor2.obtener_precios_historicos(instrumento, date(2023, 1, 1), date(2023, 3, 1))

    assert len(precios1) == len(precios2)
    assert len(precios1) > 0
    for p1, p2 in zip(precios1, precios2):
        assert p1.fecha == p2.fecha
        assert p1.cierre == p2.cierre
        assert p1.cierre_ajustado == p2.cierre_ajustado


def test_semillas_distintas_generan_precios_distintos():
    proveedor1 = ProveedorSintetico(semilla=1)
    proveedor2 = ProveedorSintetico(semilla=2)
    instrumento = _InstrumentoFalso('STEC01')

    precios1 = proveedor1.obtener_precios_historicos(instrumento, date(2023, 1, 1), date(2023, 6, 1))
    precios2 = proveedor2.obtener_precios_historicos(instrumento, date(2023, 1, 1), date(2023, 6, 1))

    assert [p.cierre for p in precios1] != [p.cierre for p in precios2]


def test_precios_siempre_positivos_en_todo_el_universo():
    proveedor = ProveedorSintetico(semilla=42)
    for ticker, *_resto in UNIVERSO_SINTETICO:
        precios = proveedor.obtener_precios_historicos(
            _InstrumentoFalso(ticker), FECHA_INICIO_UNIVERSO, FECHA_FIN_UNIVERSO,
        )
        assert all(p.cierre > 0 for p in precios), f'{ticker} tiene precios no positivos'
        assert all(p.cierre_ajustado > 0 for p in precios), f'{ticker} tiene precios ajustados no positivos'


def test_split_genera_caida_visible_en_precio_crudo_pero_no_en_ajustado():
    proveedor = ProveedorSintetico(semilla=42)
    ticker_con_split = next(
        t[0] for i, t in enumerate(UNIVERSO_SINTETICO)
        if t[3] == 'ACCION' and i % 7 == 0
    )
    instrumento = _InstrumentoFalso(ticker_con_split)
    eventos = proveedor.obtener_eventos_corporativos(instrumento, FECHA_INICIO_UNIVERSO, FECHA_FIN_UNIVERSO)
    splits = [e for e in eventos if e.tipo == 'SPLIT']
    assert len(splits) == 1

    fecha_split = splits[0].factor_split and splits[0].fecha_ex
    precios = proveedor.obtener_precios_historicos(instrumento, FECHA_INICIO_UNIVERSO, FECHA_FIN_UNIVERSO)
    por_fecha = {p.fecha: p for p in precios}
    idx_fechas = list(por_fecha.keys())
    pos_split = idx_fechas.index(fecha_split)

    precio_crudo_antes = por_fecha[idx_fechas[pos_split - 1]].cierre
    precio_crudo_despues = por_fecha[idx_fechas[pos_split]].cierre
    # El precio crudo cae aproximadamente a la mitad justo en el split (factor 2.0);
    # se tolera hasta 65% del precio previo para dar margen al ruido diario normal.
    assert precio_crudo_despues < precio_crudo_antes * Decimal('0.65')

    precio_ajustado_antes = por_fecha[idx_fechas[pos_split - 1]].cierre_ajustado
    precio_ajustado_despues = por_fecha[idx_fechas[pos_split]].cierre_ajustado
    # El precio ajustado es continuo: el cambio relativo debe ser pequeno (ruido diario normal).
    cambio_relativo_ajustado = abs(precio_ajustado_despues - precio_ajustado_antes) / precio_ajustado_antes
    assert cambio_relativo_ajustado < Decimal('0.15')
