"""
Fabrica de proveedores: traduce el valor de configuracion
`SIMULADOR['PROVEEDOR_DATOS_MERCADO']` (o el registro activo en
ProveedorDatosMercado) en una instancia concreta que implemente
ProveedorCotizacionesBase. Permite cambiar de proveedor sin tocar el
motor de simulacion ni los comandos de cron.
"""
from django.conf import settings

from .sintetico import ProveedorSintetico


def obtener_proveedor_activo():
    clave = settings.SIMULADOR.get('PROVEEDOR_DATOS_MERCADO', 'sintetico').lower()
    if clave == 'sintetico':
        return ProveedorSintetico()
    if clave == 'eodhd':
        from .eodhd import ProveedorEODHD
        return ProveedorEODHD()
    if clave == 'twelvedata':
        from .twelvedata import ProveedorTwelveData
        return ProveedorTwelveData()
    raise ValueError(f'Proveedor de datos de mercado no reconocido: {clave}')
