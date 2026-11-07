from django.db import models

from apps.portafolios.models import Portafolio


class VentanaAnalisis(models.TextChoices):
    UN_MES = '1M', '1 mes'
    TRES_MESES = '3M', '3 meses'
    SEIS_MESES = '6M', '6 meses'
    UN_ANIO = '1A', '1 anio'
    DESDE_INICIO = 'TODO', 'Desde el inicio del curso'


class MetricaPortafolio(models.Model):
    """
    Metricas de rendimiento/riesgo/desempeno precalculadas por el
    comando de cron `calcular_metricas`. El dashboard las lee en lugar
    de recalcular series completas en cada solicitud HTTP.

    Un campo numerico se deja en NULL cuando no hay suficiente historia
    para calcularlo de forma confiable (p. ej. Sharpe con menos de 2
    observaciones); la vista debe explicar la razon, no mostrar un 0.
    """

    portafolio = models.ForeignKey(Portafolio, on_delete=models.CASCADE, related_name='metricas')
    fecha_corte = models.DateField()
    ventana = models.CharField(max_length=5, choices=VentanaAnalisis.choices)

    rendimiento_simple = models.DecimalField(max_digits=14, decimal_places=8, null=True, blank=True)
    rendimiento_log = models.DecimalField(max_digits=14, decimal_places=8, null=True, blank=True)
    rendimiento_acumulado = models.DecimalField(max_digits=14, decimal_places=8, null=True, blank=True)
    rendimiento_anualizado = models.DecimalField(max_digits=14, decimal_places=8, null=True, blank=True)

    varianza = models.DecimalField(max_digits=18, decimal_places=10, null=True, blank=True)
    volatilidad = models.DecimalField(max_digits=14, decimal_places=8, null=True, blank=True)
    volatilidad_anualizada = models.DecimalField(max_digits=14, decimal_places=8, null=True, blank=True)
    beta = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    max_drawdown = models.DecimalField(max_digits=14, decimal_places=8, null=True, blank=True)
    var_historico_95 = models.DecimalField(max_digits=14, decimal_places=8, null=True, blank=True)

    sharpe = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    treynor = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    alfa_jensen = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    information_ratio = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    tracking_error = models.DecimalField(max_digits=14, decimal_places=8, null=True, blank=True)

    observaciones_insuficientes = models.BooleanField(
        default=False, help_text='True si no hubo suficiente historia para calcular la ventana completa.',
    )
    numero_observaciones = models.IntegerField(default=0)
    calculado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'metrica de portafolio'
        verbose_name_plural = 'metricas de portafolio'
        constraints = [
            models.UniqueConstraint(fields=['portafolio', 'fecha_corte', 'ventana'], name='uniq_metrica_portafolio_fecha_ventana'),
        ]
        indexes = [models.Index(fields=['portafolio', 'ventana', '-fecha_corte'])]
        ordering = ['portafolio', '-fecha_corte']

    def __str__(self):
        return f'{self.portafolio} {self.ventana} @ {self.fecha_corte}'


class ResultadoOptimizacion(models.Model):
    """
    Resultado cacheado de un calculo de frontera eficiente / portafolio
    optimo de Markowitz para un curso en una fecha de corte, para no
    repetir la optimizacion (costosa) en cada carga de pantalla.
    """

    class Tipo(models.TextChoices):
        MINIMA_VARIANZA = 'MIN_VAR', 'Minima varianza'
        MAXIMO_SHARPE = 'MAX_SHARPE', 'Maximo Sharpe'

    curso = models.ForeignKey('cursos.Curso', on_delete=models.CASCADE, related_name='resultados_optimizacion')
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    fecha_corte = models.DateField()
    pesos = models.JSONField(help_text='Mapa {instrumento_id: peso} con suma 1.0 y pesos en [0,1].')
    rendimiento_esperado_anual = models.DecimalField(max_digits=10, decimal_places=6)
    volatilidad_anual = models.DecimalField(max_digits=10, decimal_places=6)
    sharpe = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    frontera_eficiente = models.JSONField(
        default=list, blank=True,
        help_text='Lista de puntos [{rendimiento, volatilidad}] de la frontera eficiente.',
    )
    calculado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'resultado de optimizacion'
        verbose_name_plural = 'resultados de optimizacion'
        constraints = [
            models.UniqueConstraint(fields=['curso', 'tipo', 'fecha_corte'], name='uniq_resultadoopt_curso_tipo_fecha'),
        ]
        ordering = ['-fecha_corte']

    def __str__(self):
        return f'{self.curso} {self.tipo} @ {self.fecha_corte}'
