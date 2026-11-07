from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.mercados.models import Instrumento


class Curso(models.Model):
    """
    Un curso agrupa a un profesor, un grupo de estudiantes y las reglas
    de la simulacion (capital inicial, instrumentos permitidos, fechas,
    comisiones, etc.). Las reglas se consultan desde el motor financiero
    en el momento de validar cada orden.
    """

    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, default='')
    profesor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='cursos_impartidos',
        limit_choices_to={'rol': 'PROFESOR'},
    )
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    capital_inicial_mxn = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal('1000000.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    tasa_libre_riesgo_anual = models.DecimalField(
        max_digits=8, decimal_places=5, default=Decimal('0.10'),
        help_text='Tasa libre de riesgo anualizada usada en Sharpe/Treynor/Jensen para este curso.',
    )
    spread_conversion_divisas = models.DecimalField(
        max_digits=6, decimal_places=5, default=Decimal('0.005'),
        help_text='Spread aplicado a conversiones MXN<->USD, como fraccion (0.005 = 0.5%).',
    )
    comision_operacion = models.DecimalField(
        max_digits=6, decimal_places=5, default=Decimal('0.00'),
        help_text='Comision por operacion de compra/venta, como fraccion del importe.',
    )
    instrumentos_permitidos = models.ManyToManyField(
        Instrumento, blank=True, related_name='cursos_que_lo_permiten',
        help_text='Si se deja vacio, se permiten todos los instrumentos activos.',
    )
    operaciones_activas = models.BooleanField(
        default=True, help_text='Interruptor general para suspender compras/ventas en este curso.',
    )
    benchmark_principal = models.ForeignKey(
        Instrumento, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cursos_benchmark',
        limit_choices_to={'tipo_instrumento': 'INDICE'},
    )
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'curso'
        verbose_name_plural = 'cursos'
        ordering = ['-fecha_inicio']

    def __str__(self):
        return f'{self.nombre} ({self.fecha_inicio:%Y-%m} - {self.fecha_fin:%Y-%m})'

    def permite_instrumento(self, instrumento):
        if not self.instrumentos_permitidos.exists():
            return instrumento.activo
        return instrumento.activo and self.instrumentos_permitidos.filter(pk=instrumento.pk).exists()

    def esta_en_periodo_vigente(self, fecha):
        return self.fecha_inicio <= fecha <= self.fecha_fin


class Inscripcion(models.Model):
    """Relacion estudiante-curso. Un portafolio (apps.portafolios) se crea 1:1 con cada inscripcion."""

    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='inscripciones')
    estudiante = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inscripciones',
        limit_choices_to={'rol': 'ESTUDIANTE'},
    )
    fecha_inscripcion = models.DateTimeField(auto_now_add=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'inscripcion'
        verbose_name_plural = 'inscripciones'
        constraints = [
            models.UniqueConstraint(fields=['curso', 'estudiante'], name='uniq_inscripcion_curso_estudiante'),
        ]

    def __str__(self):
        return f'{self.estudiante} en {self.curso}'
