import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger('simulador')

from apps.analitica import services as analitica
from apps.analitica.models import MetricaPortafolio, VentanaAnalisis
from apps.mercados.models import PrecioMercado
from apps.portafolios.models import Portafolio, ValuacionPortafolio

VENTANAS_DIAS_APROX = {
    VentanaAnalisis.UN_MES: 30,
    VentanaAnalisis.TRES_MESES: 90,
    VentanaAnalisis.SEIS_MESES: 180,
    VentanaAnalisis.UN_ANIO: 365,
}


def _decimal_o_none(valor, decimales=8):
    if valor is None:
        return None
    return Decimal(str(round(valor, decimales)))


class Command(BaseCommand):
    help = (
        'Precalcula las metricas de rendimiento/riesgo/desempeno de cada '
        'portafolio (todas las ventanas) a partir de ValuacionPortafolio. '
        'El dashboard lee estos resultados en vez de recalcular series '
        'completas en cada solicitud HTTP. Idempotente para una fecha de corte '
        'dada (update_or_create). Pensado para Cron diario, despues de '
        'calcular_valuaciones.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--fecha', type=str, default=None, help='Fecha de corte AAAA-MM-DD (por defecto, hoy).')

    def handle(self, *args, **options):
        fecha_corte = date.fromisoformat(options['fecha']) if options['fecha'] else timezone.localdate()
        total = 0
        for portafolio in Portafolio.objects.select_related('inscripcion__curso').all():
            curso = portafolio.inscripcion.curso
            benchmark_cache = self._serie_benchmark(curso, fecha_corte)
            for ventana in VentanaAnalisis.values:
                try:
                    self._calcular_ventana(portafolio, curso, ventana, fecha_corte, benchmark_cache)
                    total += 1
                except InvalidOperation:
                    logger.exception(
                        'No se pudo calcular/guardar la metrica %s del portafolio %s en %s '
                        '(probable valor fuera de rango); se omite.',
                        ventana, portafolio.pk, fecha_corte,
                    )
        self.stdout.write(self.style.SUCCESS(f'Metricas calculadas: {total}.'))

    def _serie_benchmark(self, curso, fecha_corte):
        if curso.benchmark_principal_id is None:
            return {}
        precios = PrecioMercado.objects.filter(
            instrumento=curso.benchmark_principal, fecha__lte=fecha_corte,
        ).order_by('fecha').values_list('fecha', 'cierre_ajustado')
        fechas, cierres = [], []
        for fecha, cierre in precios:
            fechas.append(fecha)
            cierres.append(float(cierre))
        rendimientos_por_fecha = {}
        for i in range(1, len(fechas)):
            if cierres[i - 1] > 0:
                rendimientos_por_fecha[fechas[i]] = (cierres[i] / cierres[i - 1]) - 1
        return rendimientos_por_fecha

    def _fecha_inicio_ventana(self, curso, ventana, fecha_corte):
        if ventana == VentanaAnalisis.DESDE_INICIO:
            return curso.fecha_inicio
        dias = VENTANAS_DIAS_APROX[ventana]
        return max(curso.fecha_inicio, fecha_corte - timedelta(days=dias))

    def _calcular_ventana(self, portafolio, curso, ventana, fecha_corte, rendimientos_benchmark_por_fecha):
        fecha_inicio_ventana = self._fecha_inicio_ventana(curso, ventana, fecha_corte)
        valuaciones = list(
            ValuacionPortafolio.objects.filter(
                portafolio=portafolio, fecha__gte=fecha_inicio_ventana, fecha__lte=fecha_corte,
            ).order_by('fecha')
        )

        valores_totales = [float(v.valor_total_mxn) for v in valuaciones]
        serie_rendimientos, fechas_rendimientos = [], []
        for v in valuaciones:
            if v.rendimiento_diario is not None:
                serie_rendimientos.append(float(v.rendimiento_diario))
                fechas_rendimientos.append(v.fecha)

        numero_observaciones = len(serie_rendimientos)

        if numero_observaciones < analitica.MINIMO_OBSERVACIONES:
            MetricaPortafolio.objects.update_or_create(
                portafolio=portafolio, fecha_corte=fecha_corte, ventana=ventana,
                defaults={'observaciones_insuficientes': True, 'numero_observaciones': numero_observaciones},
            )
            return

        rendimiento_acum = analitica.rendimiento_acumulado(serie_rendimientos)
        rendimiento_anual = analitica.rendimiento_anualizado(rendimiento_acum, numero_observaciones)
        vol = analitica.volatilidad(serie_rendimientos)
        vol_anual = analitica.volatilidad_anualizada(vol)
        var_valor = analitica.varianza(serie_rendimientos)
        mdd = analitica.max_drawdown(valores_totales)
        var95 = analitica.var_historico(serie_rendimientos)
        sharpe = analitica.sharpe_ratio(rendimiento_anual, vol_anual, curso.tasa_libre_riesgo_anual)

        beta_valor = treynor = alfa = te = ir = None
        if rendimientos_benchmark_por_fecha:
            serie_bench_alineada = [
                rendimientos_benchmark_por_fecha[f] for f in fechas_rendimientos
                if f in rendimientos_benchmark_por_fecha
            ]
            serie_port_alineada = [
                r for f, r in zip(fechas_rendimientos, serie_rendimientos)
                if f in rendimientos_benchmark_por_fecha
            ]
            if len(serie_bench_alineada) >= analitica.MINIMO_OBSERVACIONES:
                beta_valor = analitica.beta(serie_port_alineada, serie_bench_alineada)
                rendimiento_acum_bench = analitica.rendimiento_acumulado(serie_bench_alineada)
                rendimiento_anual_bench = analitica.rendimiento_anualizado(rendimiento_acum_bench, len(serie_bench_alineada))
                if beta_valor is not None:
                    treynor = analitica.treynor_ratio(rendimiento_anual, beta_valor, curso.tasa_libre_riesgo_anual)
                    alfa = analitica.alfa_jensen(rendimiento_anual, rendimiento_anual_bench, beta_valor, curso.tasa_libre_riesgo_anual)
                te = analitica.tracking_error(serie_port_alineada, serie_bench_alineada)
                if te is not None:
                    ir = analitica.information_ratio(rendimiento_anual, rendimiento_anual_bench, te)

        MetricaPortafolio.objects.update_or_create(
            portafolio=portafolio, fecha_corte=fecha_corte, ventana=ventana,
            defaults={
                'rendimiento_simple': _decimal_o_none(serie_rendimientos[-1] if serie_rendimientos else None, 8),
                'rendimiento_acumulado': _decimal_o_none(rendimiento_acum, 8),
                'rendimiento_anualizado': _decimal_o_none(rendimiento_anual, 8),
                'varianza': _decimal_o_none(var_valor, 10),
                'volatilidad': _decimal_o_none(vol, 8),
                'volatilidad_anualizada': _decimal_o_none(vol_anual, 8),
                'beta': _decimal_o_none(beta_valor, 6),
                'max_drawdown': _decimal_o_none(mdd, 8),
                'var_historico_95': _decimal_o_none(var95, 8),
                'sharpe': _decimal_o_none(sharpe, 6),
                'treynor': _decimal_o_none(treynor, 6),
                'alfa_jensen': _decimal_o_none(alfa, 6),
                'information_ratio': _decimal_o_none(ir, 6),
                'tracking_error': _decimal_o_none(te, 8),
                'observaciones_insuficientes': False,
                'numero_observaciones': numero_observaciones,
            },
        )
