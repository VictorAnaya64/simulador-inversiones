from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.mercados.models import Instrumento, Moneda
from apps.portafolios.models import Portafolio


class Orden(models.Model):
    """
    Orden de compra/venta. El `clave_idempotencia` es la defensa contra
    doble clic, reintentos HTTP o reprocesamiento de cron: dos solicitudes
    con la misma clave nunca generan dos ordenes (UNIQUE a nivel de base
    de datos + validacion en el servicio).

    Regla de ejecucion (v1): precios de cierre diario unicamente. Una
    orden se ejecuta, como minimo, al cierre de la siguiente sesion
    bursatil elegible para el instrumento (ver apps/mercados calendario).
    """

    class Tipo(models.TextChoices):
        COMPRA = 'COMPRA', 'Compra'
        VENTA = 'VENTA', 'Venta'

    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        EJECUTADA = 'EJECUTADA', 'Ejecutada'
        CANCELADA = 'CANCELADA', 'Cancelada'
        RECHAZADA = 'RECHAZADA', 'Rechazada'

    portafolio = models.ForeignKey(Portafolio, on_delete=models.CASCADE, related_name='ordenes')
    instrumento = models.ForeignKey(Instrumento, on_delete=models.PROTECT, related_name='ordenes')
    tipo = models.CharField(max_length=6, choices=Tipo.choices)
    cantidad = models.DecimalField(max_digits=18, decimal_places=4, validators=[MinValueValidator(Decimal('0.0001'))])
    moneda = models.CharField(max_length=3, choices=Moneda.choices)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    clave_idempotencia = models.CharField(max_length=80, unique=True)
    precio_referencia = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True,
        help_text='Ultimo precio de cierre conocido al momento de crear la orden; solo informativo/para reserva estimada.',
    )
    monto_efectivo_reservado = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True,
        help_text='Solo para compras: importe exacto reservado en el efectivo del portafolio al crear la orden.',
    )
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_sesion_objetivo = models.DateField(
        help_text='Primera sesion bursatil elegible para ejecutar esta orden (>= fecha_solicitud, siguiente dia habil).',
    )
    motivo_rechazo = models.CharField(max_length=255, blank=True, default='')
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='ordenes_creadas')
    cancelada_en = models.DateTimeField(null=True, blank=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'orden'
        verbose_name_plural = 'ordenes'
        ordering = ['-fecha_solicitud']
        indexes = [
            models.Index(fields=['portafolio', 'estado']),
            models.Index(fields=['estado', 'fecha_sesion_objetivo']),
        ]

    def __str__(self):
        return f'Orden#{self.id} {self.tipo} {self.cantidad} {self.instrumento.ticker} [{self.estado}]'

    @property
    def es_compra(self):
        return self.tipo == self.Tipo.COMPRA


class Ejecucion(models.Model):
    """
    Ejecucion de una orden. Relacion 1:1 con Orden en esta primera
    version (no se modela ejecucion parcial). Una vez creada, no se
    modifica: cualquier correccion se hace mediante una operacion
    compensatoria registrada aparte.
    """

    orden = models.OneToOneField(Orden, on_delete=models.PROTECT, related_name='ejecucion')
    fecha_sesion = models.DateField(help_text='Fecha bursatil cuyo precio de cierre se uso.')
    fecha_ejecucion = models.DateTimeField()
    precio_ejecucion = models.DecimalField(max_digits=18, decimal_places=6)
    cantidad = models.DecimalField(max_digits=18, decimal_places=4)
    importe_bruto = models.DecimalField(max_digits=18, decimal_places=2)
    comision = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    importe_neto = models.DecimalField(max_digits=18, decimal_places=2)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'ejecucion'
        verbose_name_plural = 'ejecuciones'
        ordering = ['-fecha_ejecucion']

    def __str__(self):
        return f'Ejecucion orden#{self.orden_id} @ {self.precio_ejecucion} ({self.fecha_sesion})'
