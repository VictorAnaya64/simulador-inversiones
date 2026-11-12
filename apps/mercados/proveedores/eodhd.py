"""
Adaptador para EODHD (https://eodhd.com). NO IMPLEMENTADO TODAVIA.

Antes de implementar las llamadas reales a la API:
1. Verificar en la documentacion oficial vigente de EODHD los endpoints
   exactos de precios historicos EOD, splits y dividendos, y sus
   formatos de respuesta (pueden cambiar entre planes).
2. Confirmar en los terminos de la suscripcion si esta permitido
   redistribuir los datos a los estudiantes (uso educativo en grupo),
   ya que una suscripcion personal no necesariamente lo autoriza.
3. Definir la variable de entorno EODHD_API_KEY (ver .env.example) y
   jamas registrarla en el repositorio ni en los logs.

Mientras esto no se complete, el sistema debe seguir funcionando con
ProveedorSintetico (proveedor por defecto, no requiere API externa).
"""
from .base import ProveedorCotizacionesBase


class ProveedorEODHD(ProveedorCotizacionesBase):
    nombre_proveedor = 'EODHD'

    def obtener_precios_historicos(self, instrumento, fecha_inicio, fecha_fin):
        raise NotImplementedError(
            'Adaptador EODHD pendiente de implementar y verificar contra la documentacion oficial.'
        )

    def obtener_eventos_corporativos(self, instrumento, fecha_inicio, fecha_fin):
        raise NotImplementedError(
            'Adaptador EODHD pendiente de implementar y verificar contra la documentacion oficial.'
        )
