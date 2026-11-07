from django.contrib import admin

from .models import (
    DiaInhabilBursatil,
    EventoCorporativo,
    Instrumento,
    PrecioMercado,
    ProveedorDatosMercado,
    TipoCambio,
)


@admin.register(ProveedorDatosMercado)
class ProveedorDatosMercadoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'activo', 'es_predeterminado')
    list_filter = ('tipo', 'activo')


@admin.register(Instrumento)
class InstrumentoAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'bolsa', 'nombre', 'moneda', 'tipo_instrumento', 'pais', 'activo')
    list_filter = ('bolsa', 'moneda', 'tipo_instrumento', 'activo')
    search_fields = ('ticker', 'nombre')


@admin.register(PrecioMercado)
class PrecioMercadoAdmin(admin.ModelAdmin):
    list_display = ('instrumento', 'fecha', 'cierre', 'cierre_ajustado', 'volumen', 'fuente')
    list_filter = ('fuente',)
    search_fields = ('instrumento__ticker',)
    date_hierarchy = 'fecha'


@admin.register(TipoCambio)
class TipoCambioAdmin(admin.ModelAdmin):
    list_display = ('par', 'fecha', 'valor', 'fuente')
    date_hierarchy = 'fecha'


@admin.register(EventoCorporativo)
class EventoCorporativoAdmin(admin.ModelAdmin):
    list_display = ('instrumento', 'tipo', 'fecha_ex', 'factor_split', 'monto_dividendo_por_titulo', 'aplicado')
    list_filter = ('tipo', 'aplicado')
    search_fields = ('instrumento__ticker',)


@admin.register(DiaInhabilBursatil)
class DiaInhabilBursatilAdmin(admin.ModelAdmin):
    list_display = ('bolsa', 'fecha', 'descripcion')
    list_filter = ('bolsa',)
    date_hierarchy = 'fecha'
