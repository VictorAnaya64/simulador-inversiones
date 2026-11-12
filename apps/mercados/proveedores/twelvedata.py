"""
Adaptador para Twelve Data (https://twelvedata.com). NO IMPLEMENTADO
TODAVIA. Ver las mismas advertencias que en apps/mercados/proveedores/eodhd.py:
verificar documentacion oficial vigente, confirmar terminos de
redistribucion a estudiantes, y configurar TWELVEDATA_API_KEY por
variable de entorno (nunca en el repositorio).
"""
from .base import ProveedorCotizacionesBase


class ProveedorTwelveData(ProveedorCotizacionesBase):
    nombre_proveedor = 'TWELVEDATA'

    def obtener_precios_historicos(self, instrumento, fecha_inicio, fecha_fin):
        raise NotImplementedError(
            'Adaptador Twelve Data pendiente de implementar y verificar contra la documentacion oficial.'
        )

    def obtener_eventos_corporativos(self, instrumento, fecha_inicio, fecha_fin):
        raise NotImplementedError(
            'Adaptador Twelve Data pendiente de implementar y verificar contra la documentacion oficial.'
        )
