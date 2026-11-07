from django.core.validators import MinValueValidator
from django.db import models


class Bolsa(models.TextChoices):
    NYSE = 'NYSE', 'New York Stock Exchange'
    NASDAQ = 'NASDAQ', 'NASDAQ'
    BMV = 'BMV', 'Bolsa Mexicana de Valores'


class Moneda(models.TextChoices):
    MXN = 'MXN', 'Peso mexicano'
    USD = 'USD', 'Dolar estadounidense'


class TipoInstrumento(models.TextChoices):
    ACCION = 'ACCION', 'Accion'
    ETF = 'ETF', 'ETF'
    INDICE = 'INDICE', 'Indice (solo referencia / benchmark)'


class ProveedorDatosMercado(models.Model):
    """
    Catalogo de proveedores de cotizaciones. Permite cambiar de proveedor
    por configuracion sin alterar el motor de simulacion (patron
    adaptador implementado en apps/mercados/proveedores/).
    """

    class Tipo(models.TextChoices):
        SINTETICO = 'SINTETICO', 'Datos sinteticos (demostracion)'
        EODHD = 'EODHD', 'EODHD'
        TWELVEDATA = 'TWELVEDATA', 'Twelve Data'

    nombre = models.CharField(max_length=50, unique=True)
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    activo = models.BooleanField(default=False)
    es_predeterminado = models.BooleanField(default=False)
    url_base = models.URLField(blank=True, default='')
    variable_entorno_api_key = models.CharField(
        max_length=50, blank=True, default='',
        help_text='Nombre de la variable de entorno que contiene la API key (nunca se guarda la key aqui).',
    )
    notas = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'proveedor de datos de mercado'
        verbose_name_plural = 'proveedores de datos de mercado'

    def __str__(self):
        return self.nombre


class Instrumento(models.Model):
    """
    Catalogo de instrumentos financieros. El ticker NO es llave unica
    global: la llave logica es (ticker, bolsa), porque el mismo ticker
    puede existir en mercados distintos (p. ej. acciones listadas en
    EUA vs. valores operados via SIC en Mexico, que NO deben confundirse).
    """

    ticker = models.CharField(max_length=15)
    nombre = models.CharField(max_length=150)
    bolsa = models.CharField(max_length=10, choices=Bolsa.choices)
    moneda = models.CharField(max_length=3, choices=Moneda.choices)
    tipo_instrumento = models.CharField(max_length=10, choices=TipoInstrumento.choices)
    pais = models.CharField(max_length=60)
    activo = models.BooleanField(default=True)
    fuente_datos = models.ForeignKey(
        ProveedorDatosMercado, on_delete=models.PROTECT, related_name='instrumentos',
    )
    identificador_proveedor = models.CharField(
        max_length=50, blank=True, default='',
        help_text='Identificador/simbolo usado por el proveedor de datos, si difiere del ticker.',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'instrumento'
        verbose_name_plural = 'instrumentos'
        constraints = [
            models.UniqueConstraint(fields=['ticker', 'bolsa'], name='uniq_ticker_bolsa'),
        ]
        indexes = [
            models.Index(fields=['ticker']),
            models.Index(fields=['bolsa', 'activo']),
        ]
        ordering = ['ticker']

    def __str__(self):
        return f'{self.ticker} ({self.bolsa})'

    @property
    def clave(self):
        return f'{self.bolsa}:{self.ticker}'


class PrecioMercado(models.Model):
    """
    Precio diario de un instrumento. cierre_ajustado incorpora splits y
    dividendos acumulados; cierre es el precio historico original. Nunca
    se vuelve a aplicar un evento corporativo sobre un registro que ya
    lo incorpora (ver CorporateAction / EventoCorporativo).
    """

    instrumento = models.ForeignKey(Instrumento, on_delete=models.CASCADE, related_name='precios')
    fecha = models.DateField()
    apertura = models.DecimalField(max_digits=18, decimal_places=6)
    maximo = models.DecimalField(max_digits=18, decimal_places=6)
    minimo = models.DecimalField(max_digits=18, decimal_places=6)
    cierre = models.DecimalField(max_digits=18, decimal_places=6)
    cierre_ajustado = models.DecimalField(max_digits=18, decimal_places=6)
    volumen = models.BigIntegerField(validators=[MinValueValidator(0)], default=0)
    fuente = models.CharField(max_length=20)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'precio de mercado'
        verbose_name_plural = 'precios de mercado'
        constraints = [
            models.UniqueConstraint(fields=['instrumento', 'fecha'], name='uniq_precio_instrumento_fecha'),
        ]
        indexes = [
            models.Index(fields=['instrumento', '-fecha']),
        ]
        ordering = ['instrumento', 'fecha']

    def __str__(self):
        return f'{self.instrumento.ticker} {self.fecha} close={self.cierre}'


class TipoCambio(models.Model):
    """Tipo de cambio diario. Por ahora solo se modela el par USD/MXN."""

    class Par(models.TextChoices):
        USDMXN = 'USDMXN', 'USD/MXN'

    par = models.CharField(max_length=10, choices=Par.choices, default=Par.USDMXN)
    fecha = models.DateField()
    valor = models.DecimalField(max_digits=12, decimal_places=6, help_text='Unidades de MXN por 1 USD.')
    fuente = models.CharField(max_length=20)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'tipo de cambio'
        verbose_name_plural = 'tipos de cambio'
        constraints = [
            models.UniqueConstraint(fields=['par', 'fecha'], name='uniq_tipocambio_par_fecha'),
        ]
        indexes = [models.Index(fields=['par', '-fecha'])]
        ordering = ['fecha']

    def __str__(self):
        return f'{self.par} {self.fecha} = {self.valor}'


class EventoCorporativo(models.Model):
    """
    Split o dividendo de un instrumento. El campo `aplicado` evita que un
    proceso programado reprocese el mismo evento dos veces sobre las
    posiciones de los estudiantes.
    """

    class Tipo(models.TextChoices):
        SPLIT = 'SPLIT', 'Split'
        DIVIDENDO = 'DIVIDENDO', 'Dividendo'

    instrumento = models.ForeignKey(Instrumento, on_delete=models.CASCADE, related_name='eventos_corporativos')
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    fecha_ex = models.DateField(help_text='Fecha ex-derecho/ex-split.')
    factor_split = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True,
        help_text='Para splits: nuevas acciones por cada accion anterior (p. ej. 2.0 en un split 2x1).',
    )
    monto_dividendo_por_titulo = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True,
        help_text='Para dividendos: monto por titulo en la moneda de cotizacion del instrumento.',
    )
    aplicado = models.BooleanField(default=False)
    fecha_aplicacion = models.DateTimeField(null=True, blank=True)
    fuente = models.CharField(max_length=20, blank=True, default='')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'evento corporativo'
        verbose_name_plural = 'eventos corporativos'
        constraints = [
            models.UniqueConstraint(fields=['instrumento', 'fecha_ex', 'tipo'], name='uniq_evento_instrumento_fecha_tipo'),
        ]
        ordering = ['fecha_ex']

    def __str__(self):
        return f'{self.instrumento.ticker} {self.get_tipo_display()} {self.fecha_ex}'


class DiaInhabilBursatil(models.Model):
    """Calendario de dias sin sesion bursatil, por mercado."""

    bolsa = models.CharField(max_length=10, choices=Bolsa.choices)
    fecha = models.DateField()
    descripcion = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        verbose_name = 'dia inhabil bursatil'
        verbose_name_plural = 'dias inhabiles bursatiles'
        constraints = [
            models.UniqueConstraint(fields=['bolsa', 'fecha'], name='uniq_diainhabil_bolsa_fecha'),
        ]
        ordering = ['fecha']

    def __str__(self):
        return f'{self.bolsa} {self.fecha} {self.descripcion}'
