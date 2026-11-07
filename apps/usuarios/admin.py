from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import RegistroAuditoria, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Datos del simulador', {
            'fields': ('rol', 'matricula', 'institucion', 'telefono', 'activo_academicamente'),
        }),
    )
    list_display = ('username', 'first_name', 'last_name', 'rol', 'matricula', 'is_active')
    list_filter = ('rol', 'is_active', 'activo_academicamente')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'matricula')


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ('creado_en', 'usuario', 'accion', 'descripcion')
    list_filter = ('accion',)
    search_fields = ('descripcion', 'usuario__username')
    readonly_fields = [f.name for f in RegistroAuditoria._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
