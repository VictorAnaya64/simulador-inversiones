from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.cursos.models import Inscripcion
from apps.mercados.models import Instrumento, Moneda

CERO = Decimal('0')


class Portafolio(models.Model):
    """
    Un portafolio por inscripcion (estudiante x curso). Mantiene saldos
    de efectivo separados por moneda; nunca deben quedar negativos
    (enforced en el motor de ordenes/conversiones, no solo aqui).
    """

    inscripcion = models.OneToOneField(Inscripcion, on_delete=models.CASCADE, related_name='portafolio')
    efectivo_mxn = models.DecimalField(max_digits=18, decimal_places=2, default=CERO, validators=[MinValueValidator(CERO)])
    efectivo_usd = models.DecimalField(max_digits=18, decimal_places=2, default=CERO, validators=[MinValueValidator(CERO)])
    efectivo_mxn_reservado = models.DecimalField(max_digits=18, decimal_places=2, default=CERO, validators=[MinValueValidator(CERO)])
    efectivo_usd_reservado = models.DecimalField(max_digits=18, decimal_places=2, default=CERO, validators=[MinValueValidator(CERO)])
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'portafolio'
        verbose_name_plural = 'portafolios'

    def __str__(self):
        return f'Portafolio de {self.inscripcion.estudiante} - {self.inscripcion.curso}'

    def efectivo_disponible(self, moneda):
        if moneda == Moneda.MXN:
            return self.efectivo_mxn - self.efectivo_mxn_reservado
        return self.efectivo_usd - self.efectivo_usd_reservado


class Posicion(models.Model):
    """
    Posicion agregada de un instrumento dentro de un portafolio. Los
    valores de cantidad y costo_promedio son una proyeccion cacheada de
    los LotesAdquisicion (fuente de verdad para el costo FIFO); se
    recalculan siempre dentro de la misma transaccion que los modifica.
    """

    portafolio = models.ForeignKey(Portafolio, on_delete=models.CASCADE, related_name='posiciones')
    instrumento = models.ForeignKey(Instrumento, on_delete=models.PROTECT, related_name='posiciones')
    cantidad = models.DecimalField(max_digits=18, decimal_places=4, default=CERO, validators=[MinValueValidator(CERO)])
    cantidad_reservada = models.DecimalField(max_digits=18, decimal_places=4, default=CERO, validators=[MinValueValidator(CERO)])
    costo_promedio = models.DecimalField(max_digits=18, decimal_places=6, default=CERO, validators=[MinValueValidator(CERO)])
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'posicion'
        verbose_name_plural = 'posiciones'
        constraints = [
            models.UniqueConstraint(fields=['portafolio', 'instrumento'], name='uniq_posicion_portafolio_instrumento'),
        ]

    def __str__(self):
        return f'{self.portafolio} - {self.instrumento.ticker}: {self.cantidad}'

    @property
    def cantidad_disponible(self):
        return self.cantidad - self.cantidad_reservada


class LoteAdquisicion(models.Model):
    """
    Lote FIFO de adquisicion de un instrumento: cada compra ejecutada
    crea un lote con su cantidad y costo unitario. Las ventas consumen
    lotes en orden FIFO (campo cantidad_restante) para calcular la
    ganancia/perdida realizada con precision, sin depender solo del
    costo promedio agregado.
    """

    posicion = models.ForeignKey(Posicion, on_delete=models.CASCADE, related_name='lotes')
    ejecucion_compra = models.ForeignKey(
        'operaciones.Ejecucion', on_delete=models.PROTECT, related_name='lotes_generados',
    )
    fecha_adquisicion = models.DateField()
    cantidad_original = models.DecimalField(max_digits=18, decimal_places=4, validators=[MinValueValidator(Decimal('0.0001'))])
    cantidad_restante = models.DecimalField(max_digits=18, decimal_places=4, validators=[MinValueValidator(CERO)])
    costo_unitario = models.DecimalField(max_digits=18, decimal_places=6, validators=[MinValueValidator(CERO)])

    class Meta:
        verbose_name = 'lote de adquisicion'
        verbose_name_plural = 'lotes de adquisicion'
        ordering = ['fecha_adquisicion', 'id']
        indexes = [models.Index(fields=['posicion', 'cantidad_restante'])]

    def __str__(self):
        return f'Lote {self.id} {self.posicion.instrumento.ticker} {self.cantidad_restante}/{self.cantidad_original}'


class MovimientoEfectivo(models.Model):
    """Libro de movimientos de efectivo. Es historico: nunca se edita, solo se agregan registros nuevos."""

    class Tipo(models.TextChoices):
        DEPOSITO_INICIAL = 'DEPOSITO_INICIAL', 'Deposito inicial'
        COMPRA = 'COMPRA', 'Compra de instrumento'
        VENTA = 'VENTA', 'Venta de instrumento'
        COMISION = 'COMISION', 'Comision'
        DIVIDENDO = 'DIVIDENDO', 'Dividendo recibido'
        CONVERSION_ENTRADA = 'CONVERSION_ENTRADA', 'Entrada por conversion de divisa'
        CONVERSION_SALIDA = 'CONVERSION_SALIDA', 'Salida por conversion de divisa'
        AJUSTE_ADMINISTRATIVO = 'AJUSTE_ADMINISTRATIVO', 'Ajuste administrativo (compensatorio)'

    portafolio = models.ForeignKey(Portafolio, on_delete=models.CASCADE, related_name='movimientos_efectivo')
    moneda = models.CharField(max_length=3, choices=Moneda.choices)
    tipo = models.CharField(max_length=25, choices=Tipo.choices)
    monto = models.DecimalField(max_digits=18, decimal_places=2, help_text='Positivo = entrada, negativo = salida.')
    saldo_resultante = models.DecimalField(max_digits=18, decimal_places=2)
    fecha = models.DateTimeField()
    referencia_tipo = models.CharField(max_length=30, blank=True, default='')
    referencia_id = models.CharField(max_length=40, blank=True, default='')
    descripcion = models.CharField(max_length=255, blank=True, default='')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'movimiento de efectivo'
        verbose_name_plural = 'movimientos de efectivo'
        ordering = ['portafolio', 'fecha', 'id']
        indexes = [models.Index(fields=['portafolio', '-fecha'])]

    def __str__(self):
        return f'{self.portafolio} {self.tipo} {self.monto} {self.moneda}'


class ConversionDivisa(models.Model):
    """Conversion simulada de efectivo entre MXN y USD dentro de un portafolio."""

    portafolio = models.ForeignKey(Portafolio, on_delete=models.CASCADE, related_name='conversiones_divisa')
    fecha = models.DateTimeField()
    moneda_origen = models.CharField(max_length=3, choices=Moneda.choices)
    moneda_destino = models.CharField(max_length=3, choices=Moneda.choices)
    monto_origen = models.DecimalField(max_digits=18, decimal_places=2)
    tipo_cambio_base = models.DecimalField(max_digits=12, decimal_places=6)
    spread_aplicado = models.DecimalField(max_digits=6, decimal_places=5)
    tipo_cambio_efectivo = models.DecimalField(max_digits=12, decimal_places=6)
    monto_destino = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        verbose_name = 'conversion de divisa'
        verbose_name_plural = 'conversiones de divisa'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.portafolio} {self.moneda_origen}->{self.moneda_destino} {self.monto_origen}'


class ValuacionPortafolio(models.Model):
    """
    Valuacion diaria precalculada de un portafolio (corrida por el
    comando de cron `calcular_valuaciones`). El dashboard lee de aqui en
    vez de recalcular en cada solicitud HTTP.
    """

    portafolio = models.ForeignKey(Portafolio, on_delete=models.CASCADE, related_name='valuaciones')
    fecha = models.DateField()
    valor_efectivo_mxn = models.DecimalField(max_digits=18, decimal_places=2)
    valor_efectivo_usd_en_mxn = models.DecimalField(max_digits=18, decimal_places=2)
    valor_posiciones_mxn = models.DecimalField(max_digits=18, decimal_places=2)
    valor_total_mxn = models.DecimalField(max_digits=18, decimal_places=2)
    tipo_cambio_usado = models.DecimalField(max_digits=12, decimal_places=6)
    rendimiento_diario = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)
    rendimiento_acumulado = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)

    class Meta:
        verbose_name = 'valuacion de portafolio'
        verbose_name_plural = 'valuaciones de portafolio'
        constraints = [
            models.UniqueConstraint(fields=['portafolio', 'fecha'], name='uniq_valuacion_portafolio_fecha'),
        ]
        indexes = [models.Index(fields=['portafolio', '-fecha'])]
        ordering = ['portafolio', 'fecha']

    def __str__(self):
        return f'{self.portafolio} {self.fecha} total={self.valor_total_mxn}'
