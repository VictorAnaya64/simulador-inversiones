from django.contrib import admin

from .models import MetricaPortafolio, ResultadoOptimizacion


@admin.register(MetricaPortafolio)
class MetricaPortafolioAdmin(admin.ModelAdmin):
    list_display = ('portafolio', 'ventana', 'fecha_corte', 'rendimiento_acumulado', 'sharpe', 'volatilidad_anualizada')
    list_filter = ('ventana', 'observaciones_insuficientes')
    date_hierarchy = 'fecha_corte'
    readonly_fields = [f.name for f in MetricaPortafolio._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(ResultadoOptimizacion)
class ResultadoOptimizacionAdmin(admin.ModelAdmin):
    list_display = ('curso', 'tipo', 'fecha_corte', 'rendimiento_esperado_anual', 'volatilidad_anual', 'sharpe')
    readonly_fields = [f.name for f in ResultadoOptimizacion._meta.fields]

    def has_add_permission(self, request):
        return False
