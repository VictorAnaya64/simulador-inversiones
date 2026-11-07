from django.contrib import admin

from .models import Curso, Inscripcion


class InscripcionInline(admin.TabularInline):
    model = Inscripcion
    extra = 0
    autocomplete_fields = ['estudiante']


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'profesor', 'fecha_inicio', 'fecha_fin', 'capital_inicial_mxn', 'operaciones_activas', 'activo')
    list_filter = ('activo', 'operaciones_activas')
    search_fields = ('nombre', 'profesor__username')
    filter_horizontal = ('instrumentos_permitidos',)
    inlines = [InscripcionInline]


@admin.register(Inscripcion)
class InscripcionAdmin(admin.ModelAdmin):
    list_display = ('curso', 'estudiante', 'fecha_inscripcion', 'activa')
    list_filter = ('activa', 'curso')
    search_fields = ('estudiante__username', 'curso__nombre')
