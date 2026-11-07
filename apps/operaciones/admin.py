from django.contrib import admin

from .models import Ejecucion, Orden


@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ('id', 'portafolio', 'tipo', 'instrumento', 'cantidad', 'estado', 'fecha_solicitud', 'fecha_sesion_objetivo')
    list_filter = ('estado', 'tipo')
    search_fields = ('portafolio__inscripcion__estudiante__username', 'instrumento__ticker', 'clave_idempotencia')
    date_hierarchy = 'fecha_solicitud'


@admin.register(Ejecucion)
class EjecucionAdmin(admin.ModelAdmin):
    list_display = ('orden', 'fecha_sesion', 'precio_ejecucion', 'cantidad', 'importe_neto')
    readonly_fields = [f.name for f in Ejecucion._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
