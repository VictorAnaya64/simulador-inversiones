"""
Patron adaptador para proveedores de datos de mercado. Cualquier
proveedor concreto (sintetico, EODHD, Twelve Data, etc.) implementa
esta misma interfaz, de modo que el motor de simulacion y los comandos
de cron nunca dependen de los detalles de un proveedor en particular.
"""
from abc import ABC, abstractmethod


class PrecioDiario:
    """DTO simple para un precio diario, independiente del proveedor."""

    __slots__ = ('fecha', 'apertura', 'maximo', 'minimo', 'cierre', 'cierre_ajustado', 'volumen')

    def __init__(self, fecha, apertura, maximo, minimo, cierre, cierre_ajustado, volumen):
        self.fecha = fecha
        self.apertura = apertura
        self.maximo = maximo
        self.minimo = minimo
        self.cierre = cierre
        self.cierre_ajustado = cierre_ajustado
        self.volumen = volumen


class EventoCorporativoDTO:
    """DTO simple para un split o dividendo, independiente del proveedor."""

    __slots__ = ('fecha_ex', 'tipo', 'factor_split', 'monto_dividendo_por_titulo')

    def __init__(self, fecha_ex, tipo, factor_split=None, monto_dividendo_por_titulo=None):
        self.fecha_ex = fecha_ex
        self.tipo = tipo
        self.factor_split = factor_split
        self.monto_dividendo_por_titulo = monto_dividendo_por_titulo


class ProveedorCotizacionesBase(ABC):
    """Interfaz que debe implementar cualquier adaptador de proveedor de datos de mercado."""

    nombre_proveedor = 'base'

    @abstractmethod
    def obtener_precios_historicos(self, instrumento, fecha_inicio, fecha_fin):
        """Devuelve una lista de PrecioDiario para `instrumento` entre las fechas dadas (inclusive)."""
        raise NotImplementedError

    @abstractmethod
    def obtener_eventos_corporativos(self, instrumento, fecha_inicio, fecha_fin):
        """Devuelve una lista de EventoCorporativoDTO para `instrumento` entre las fechas dadas."""
        raise NotImplementedError
