"""
Prueba de carga con Locust. NO ejecutar contra el hosting de produccion
sin autorizacion explicita del administrador del cPanel: una prueba de
carga mal dimensionada puede saturar un plan de hosting compartido.

Ejecutar SIEMPRE desde una maquina distinta al hosting (tu laptop, un
runner de CI, etc.), nunca desde dentro del propio cPanel.

Uso (interfaz web, recomendado para elegir el numero de usuarios):
    locust -f locustfile.py --host https://tu-dominio-de-prueba.ejemplo

Uso (modo headless, un escenario fijo, ejemplo con 50 usuarios):
    locust -f locustfile.py --host https://tu-dominio-de-prueba.ejemplo \
        --headless --users 50 --spawn-rate 5 --run-time 5m \
        --csv locust_reports/escenario_50

Escenarios sugeridos (ver docs/arquitectura.md, seccion de rendimiento):
    5, 20, 50 y 100 usuarios concurrentes. Objetivos: P95 de consultas
    ordinarias <= 2s, P95 de envio de ordenes <= 3s, cero errores 5xx/508,
    cero errores de integridad financiera.

Requiere credenciales de estudiantes de demostracion ya creadas en el
ambiente de prueba (por ejemplo via `manage.py crear_curso_demo
--n-estudiantes 100`). NUNCA correr esta prueba contra una base de datos
de produccion con estudiantes reales.
"""
import random

from locust import HttpUser, between, task


class EstudianteSimulado(HttpUser):
    wait_time = between(2, 6)

    def on_start(self):
        numero = random.randint(1, 100)
        self.username = f'estudiante_demo_{numero:02d}'
        self.password = 'Demo12345!'
        self._iniciar_sesion()

    def _iniciar_sesion(self):
        pagina_login = self.client.get('/cuentas/login/')
        csrftoken = pagina_login.cookies.get('csrftoken')
        self.client.post(
            '/cuentas/login/',
            data={'username': self.username, 'password': self.password, 'csrfmiddlewaretoken': csrftoken},
            headers={'Referer': f'{self.client.base_url}/cuentas/login/'},
        )

    @task(5)
    def consultar_panel(self):
        self.client.get('/panel/')

    @task(3)
    def consultar_mercado(self):
        self.client.get('/mercado/')

    @task(2)
    def consultar_analisis(self):
        self.client.get('/analisis/')

    @task(2)
    def consultar_operaciones(self):
        self.client.get('/operaciones/')

    @task(1)
    def enviar_orden(self):
        # Ajustar el id de instrumento al catalogo real del ambiente de prueba.
        instrumento_id = random.randint(1, 20)
        pagina = self.client.get(f'/operaciones/nueva/{instrumento_id}/COMPRA/')
        if pagina.status_code != 200:
            return
        import re
        coincidencia = re.search(r'name="clave_idempotencia" value="([a-f0-9]+)"', pagina.text)
        if not coincidencia:
            return
        csrftoken = pagina.cookies.get('csrftoken')
        self.client.post(
            f'/operaciones/nueva/{instrumento_id}/COMPRA/',
            data={
                'cantidad': random.randint(1, 5),
                'clave_idempotencia': coincidencia.group(1),
                'csrfmiddlewaretoken': csrftoken,
            },
            headers={'Referer': f'{self.client.base_url}/operaciones/nueva/{instrumento_id}/COMPRA/'},
        )
