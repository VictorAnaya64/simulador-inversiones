from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Usuario(AbstractUser):
    """
    Modelo de usuario personalizado desde el inicio del proyecto para
    evitar una migracion dolorosa mas adelante. El rol determina el
    conjunto de permisos funcionales (no reemplaza los permisos nativos
    de Django, que se siguen usando para el admin de Django).
    """

    class Rol(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrador'
        PROFESOR = 'PROFESOR', 'Profesor'
        ESTUDIANTE = 'ESTUDIANTE', 'Estudiante'

    rol = models.CharField(max_length=12, choices=Rol.choices, default=Rol.ESTUDIANTE)
    matricula = models.CharField(max_length=30, blank=True, default='')
    institucion = models.CharField(max_length=150, blank=True, default='')
    telefono = models.CharField(max_length=30, blank=True, default='')
    activo_academicamente = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.get_rol_display()})'

    @property
    def es_admin(self):
        return self.rol == self.Rol.ADMIN or self.is_superuser

    @property
    def es_profesor(self):
        return self.rol == self.Rol.PROFESOR

    @property
    def es_estudiante(self):
        return self.rol == self.Rol.ESTUDIANTE


class RegistroAuditoria(models.Model):
    """
    Bitacora generica de acciones relevantes del sistema (altas, bajas,
    cambios de configuracion, correcciones administrativas, etc.).
    Se usa GenericForeignKey para poder referenciar cualquier modelo sin
    acoplar esta app a todas las demas.
    """

    class Accion(models.TextChoices):
        CREACION = 'CREACION', 'Creacion'
        MODIFICACION = 'MODIFICACION', 'Modificacion'
        ELIMINACION = 'ELIMINACION', 'Eliminacion'
        CORRECCION = 'CORRECCION', 'Correccion administrativa'
        REINICIO_SIMULACION = 'REINICIO_SIMULACION', 'Reinicio de simulacion'
        OTRO = 'OTRO', 'Otro'

    usuario = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='acciones_auditadas',
    )
    accion = models.CharField(max_length=25, choices=Accion.choices)
    descripcion = models.TextField()
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.CharField(max_length=64, null=True, blank=True)
    objeto_relacionado = GenericForeignKey('content_type', 'object_id')
    datos_adicionales = models.JSONField(default=dict, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'registro de auditoria'
        verbose_name_plural = 'registros de auditoria'
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['-creado_en']),
        ]

    def __str__(self):
        return f'[{self.creado_en:%Y-%m-%d %H:%M}] {self.get_accion_display()} - {self.usuario}'
