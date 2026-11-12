from django.contrib import admin

from .models import LoteAdquisicion, MovimientoEfectivo, Portafolio, Posicion, ValuacionPortafolio


class PosicionInline(admin.TabularInline):
    model = Posicion
    extra = 0
    readonly_fields = ('instrumento', 'cantidad', 'cantidad_reservada', 'costo_promedio')
    can_delete = False


@admin.register(Portafolio)
class PortafolioAdmin(admin.ModelAdmin):
    list_display = ('inscripcion', 'efectivo', 'efectivo_reservado')
    search_fields = ('inscripcion__estudiante__username', 'inscripcion__curso__nombre')
    inlines = [PosicionInline]


@admin.register(Posicion)
class PosicionAdmin(admin.ModelAdmin):
    list_display = ('portafolio', 'instrumento', 'cantidad', 'cantidad_reservada', 'costo_promedio')
    search_fields = ('portafolio__inscripcion__estudiante__username', 'instrumento__ticker')


@admin.register(LoteAdquisicion)
class LoteAdquisicionAdmin(admin.ModelAdmin):
    list_display = ('posicion', 'fecha_adquisicion', 'cantidad_original', 'cantidad_restante', 'costo_unitario')
    readonly_fields = [f.name for f in LoteAdquisicion._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(MovimientoEfectivo)
class MovimientoEfectivoAdmin(admin.ModelAdmin):
    list_display = ('portafolio', 'tipo', 'monto', 'saldo_resultante', 'fecha')
    list_filter = ('tipo',)
    date_hierarchy = 'fecha'
    readonly_fields = [f.name for f in MovimientoEfectivo._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ValuacionPortafolio)
class ValuacionPortafolioAdmin(admin.ModelAdmin):
    list_display = ('portafolio', 'fecha', 'valor_total', 'rendimiento_diario', 'rendimiento_acumulado')
    date_hierarchy = 'fecha'
    readonly_fields = [f.name for f in ValuacionPortafolio._meta.fields]

    def has_add_permission(self, request):
        return False
