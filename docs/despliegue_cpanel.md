# Despliegue en cPanel

Guia paso a paso para publicar el proyecto en un hosting compartido con
cPanel que ya tiene disponible: Setup Python App, Passenger/WSGI,
MySQL/MariaDB, terminal/SSH, Cron Jobs, SSL. Ajusta nombres de dominio,
rutas y versiones segun tu proveedor especifico.

## 0. Diferencias clave entre entorno local y produccion

| | Local (desarrollo) | Produccion (cPanel) |
|---|---|---|
| `DJANGO_DEBUG` | `True` | **`False`** (obligatorio) |
| Base de datos | SQLite (`DB_ENGINE=sqlite`) | MySQL/MariaDB (`DB_ENGINE=mysql`) |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | tu dominio real |
| Servidor | `manage.py runserver` | Apache + Passenger/WSGI |
| Datos de mercado | Proveedor sintetico (por defecto) | Sintetico o un proveedor real ya verificado |
| Archivos estaticos | servidos por `runserver` | requieren `collectstatic` + configuracion en cPanel |
| Secretos | `.env` local | variables de entorno de "Setup Python App" (nunca en el repo) |

## 1. Crear el subdominio (o dominio) para la aplicacion

En cPanel &rarr; **Dominios** &rarr; crea el subdominio, por ejemplo
`simulador.tu-dominio.edu.mx`, y nota la ruta de documento raiz que
cPanel asigna (normalmente algo como
`/home/usuario/simulador.tu-dominio.edu.mx`).

## 2. Ubicacion recomendada de archivos

**No** coloques el codigo dentro de `public_html/` ni del document root
publico: ese directorio es servido directamente por Apache y cualquier
archivo ahi (incluido `.env` con secretos) podria quedar accesible por
HTTP. Clona el repositorio en una carpeta **fuera** del document root,
por ejemplo:

```
/home/usuario/simulador_inversiones/        <- codigo (fuera de public_html)
/home/usuario/simulador.tu-dominio.edu.mx/  <- document root (solo estaticos, si tu plan lo requiere)
```

Via SSH:

```bash
cd /home/usuario
git clone <url-de-tu-repositorio> simulador_inversiones
cd simulador_inversiones
```

Si no tienes acceso a `git` desde SSH, sube un ZIP via el Administrador
de Archivos de cPanel y descomprimelo en esa misma ruta.

## 3. Crear la aplicacion en "Setup Python App"

1. cPanel &rarr; **Setup Python App** &rarr; **Create Application**.
2. **Python version**: selecciona la version 3.x mas reciente
   disponible que sea compatible con Django 5.2 (3.10, 3.11 o 3.12;
   verifica en la documentacion de Django la matriz de compatibilidad
   vigente al momento del despliegue).
3. **Application root**: la ruta donde clonaste el codigo
   (`simulador_inversiones`).
4. **Application URL**: el subdominio creado en el paso 1.
5. **Application startup file**: `passenger_wsgi.py` (ya incluido en
   la raiz del proyecto).
6. **Application Entry point**: `application`.
7. Guarda. cPanel crea automaticamente un entorno virtual Python y te
   muestra el comando para activarlo por SSH (algo como
   `source /home/usuario/virtualenv/simulador_inversiones/3.12/bin/activate`).

## 4. Instalar dependencias dentro del entorno virtual de cPanel

Por SSH, activa el entorno virtual que cPanel creo (usa el comando
exacto que te mostro el panel) y luego:

```bash
cd /home/usuario/simulador_inversiones
pip install -r requirements.txt
```

**No** instales `requirements-dev.txt` en produccion (incluye Locust,
pytest y sus dependencias, innecesarias en el servidor).

## 5. Crear la base de datos MySQL y su usuario

cPanel &rarr; **MySQL Databases**:

1. Crea una base de datos, por ejemplo `usuario_simulador`.
2. Crea un usuario de base de datos con una contrasena fuerte generada
   aleatoriamente.
3. Agrega ese usuario a la base de datos con **todos los privilegios**.
4. Anota el nombre completo de la base y del usuario (cPanel suele
   anteponer el prefijo de tu cuenta, p. ej. `usuario_simulador` /
   `usuario_simdb`).

## 6. Configurar variables de entorno

En **Setup Python App**, dentro de tu aplicacion, hay una seccion para
definir variables de entorno (o, si tu plan no la ofrece, crea un
archivo `.env` en la raiz del proyecto **fuera** del document root y
asegurate de que `python-decouple` lo lea; el proyecto ya esta
preparado para ambas formas). Variables obligatorias en produccion
(ver `.env.example` para la lista completa):

```
DJANGO_SECRET_KEY=<genera una clave nueva y unica, nunca reutilices la de desarrollo>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=simulador.tu-dominio.edu.mx
DJANGO_CSRF_TRUSTED_ORIGINS=https://simulador.tu-dominio.edu.mx
DB_ENGINE=mysql
DB_NAME=usuario_simulador
DB_USER=usuario_simdb
DB_PASSWORD=<la contrasena creada en el paso 5>
DB_HOST=localhost
DB_PORT=3306
```

Genera `DJANGO_SECRET_KEY` con:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**Nunca** subas `.env` con secretos reales al repositorio (ya esta en
`.gitignore`).

## 7. Migraciones de Django

Con el entorno virtual activado:

```bash
python manage.py migrate
```

## 8. Crear superusuario (rol Administrador)

```bash
python manage.py createsuperuser
```

Este usuario puede entrar a `/admin/` y tambien se trata como
Administrador en las vistas propias del sistema (`Usuario.es_admin`
es `True` para cualquier `is_superuser`).

## 9. Poblar datos de demostracion (opcional, recomendado para la primera prueba piloto)

```bash
python manage.py poblar_datos_demo
python manage.py crear_curso_demo --n-estudiantes 10
```

Esto NO requiere ninguna API externa (usa el proveedor sintetico). Para
produccion real con datos de mercado reales, ver la seccion "Activar un
proveedor de datos real" mas abajo.

## 10. Configuracion de Passenger/WSGI

Passenger detecta automaticamente `passenger_wsgi.py` en la raiz del
"Application root" configurado en el paso 3; no se requiere
configuracion adicional salvo asegurarse de que el archivo exista (ya
viene en el repositorio) y que `Application Entry point = application`.

## 11. Archivos estaticos

```bash
python manage.py collectstatic --noinput
```

Esto copia todo a `STATIC_ROOT` (`staticfiles/`, ver `settings.py`).
Dependiendo de tu plan de cPanel, puede ser necesario:

- Configurar un alias en Apache (via `.htaccess` en el document root
  publico) que mapee `/static/` hacia la carpeta `staticfiles/` del
  Application root, **o**
- Copiar manualmente `staticfiles/` dentro del document root publico
  bajo una ruta `static/` (nunca copies el resto del proyecto, solo
  esta carpeta de estaticos ya compilados, que no contiene secretos).

Los templates usan Bootstrap 5 y Plotly desde CDN (no requieren
`collectstatic` para esas librerias), solo el CSS propio
(`static/css/simulador.css`) pasa por este paso.

## 12. Configuracion SSL

cPanel &rarr; **SSL/TLS Status** &rarr; activa AutoSSL (Let's Encrypt)
para el subdominio creado en el paso 1. Una vez activo, confirma en
`.env`:

```
DJANGO_SECURE_SSL_REDIRECT=True
```

(Ya es el valor por defecto cuando `DJANGO_DEBUG=False`.)

## 13. Configuracion de Cron Jobs

cPanel &rarr; **Cron Jobs**. Cada entrada debe activar el entorno
virtual antes de llamar a `manage.py` (sustituye las rutas por las
reales de tu cuenta):

```bash
# Importar precios y eventos corporativos — todos los dias a las 20:30 (tras el cierre de mercados EUA)
30 20 * * 1-5 /home/usuario/virtualenv/simulador_inversiones/3.12/bin/python /home/usuario/simulador_inversiones/manage.py importar_precios >> /home/usuario/simulador_inversiones/logs/cron_importar_precios.log 2>&1

# Aplicar splits/dividendos pendientes — todos los dias a las 20:40
40 20 * * 1-5 /home/usuario/virtualenv/.../bin/python /home/usuario/simulador_inversiones/manage.py aplicar_eventos_corporativos >> /home/usuario/simulador_inversiones/logs/cron_eventos.log 2>&1

# Procesar ordenes pendientes — todos los dias a las 20:45 (idempotente; se puede correr varias veces al dia)
45 20 * * 1-5 /home/usuario/virtualenv/.../bin/python /home/usuario/simulador_inversiones/manage.py procesar_ordenes >> /home/usuario/simulador_inversiones/logs/cron_ordenes.log 2>&1

# Calcular valuaciones diarias — todos los dias a las 20:50
50 20 * * 1-5 /home/usuario/virtualenv/.../bin/python /home/usuario/simulador_inversiones/manage.py calcular_valuaciones >> /home/usuario/simulador_inversiones/logs/cron_valuaciones.log 2>&1

# Calcular metricas — todos los dias a las 20:55
55 20 * * 1-5 /home/usuario/virtualenv/.../bin/python /home/usuario/simulador_inversiones/manage.py calcular_metricas >> /home/usuario/simulador_inversiones/logs/cron_metricas.log 2>&1
```

El orden importa: precios/eventos deben correr **antes** de procesar
ordenes, y procesar ordenes debe correr **antes** de calcular
valuaciones y metricas. Revisa `docs/operacion.md` para el detalle de
cada comando y sus argumentos.

## 14. Verificaciones de seguridad antes de anunciar la URL a los estudiantes

```bash
python manage.py check --deploy
```

Revisa cada advertencia. Como minimo, confirma:

- `DJANGO_DEBUG=False`.
- `DJANGO_ALLOWED_HOSTS` solo incluye tu dominio real.
- El superusuario tiene una contrasena fuerte (no la de demostracion).
- Las contrasenas de demostracion de `crear_curso_demo` fueron
  cambiadas o esos usuarios de demo fueron eliminados si no se van a
  usar.
- `.env` no esta dentro de un directorio servido publicamente.

## 15. Reinicio controlado de la aplicacion

Tras cualquier cambio de codigo o variables de entorno, en **Setup
Python App** usa el boton **Restart** de tu aplicacion (esto reinicia
el proceso Passenger). Alternativamente, por SSH:

```bash
touch /home/usuario/simulador_inversiones/tmp/restart.txt
```

(si tu configuracion de Passenger lo soporta; confirma con tu proveedor
de hosting el mecanismo exacto).

## 16. Diagnostico de errores frecuentes

| Sintoma | Causa probable | Solucion |
|---|---|---|
| Error 500 generico | `DJANGO_DEBUG=False` oculta el detalle | Revisa `logs/simulador.log` (o el log de Passenger/Apache de cPanel) |
| `DisallowedHost` | Falta el dominio en `DJANGO_ALLOWED_HOSTS` | Agregalo y reinicia |
| No se aplican estilos/Bootstrap | Falta `collectstatic` o el alias de `/static/` | Repite el paso 11 |
| `OperationalError: (2002, ...)` al conectar a MySQL | Credenciales o host de BD incorrectos | Revisa `DB_*` en las variables de entorno |
| Ordenes nunca se ejecutan | Los Cron Jobs no estan corriendo o el orden de ejecucion es incorrecto | Revisa los logs de cada cron y el orden del paso 13 |
| `ModuleNotFoundError` tras un despliegue nuevo | No se corrio `pip install -r requirements.txt` dentro del venv correcto | Repite el paso 4 |

## 17. Respaldos y restauracion

- **Base de datos**: cPanel &rarr; **Backup** &rarr; programa un
  respaldo automatico de la base MySQL (diario o semanal segun el plan
  del hosting), o usa `mysqldump` por cron hacia un archivo fuera del
  document root:
  ```bash
  mysqldump -u usuario_simdb -p usuario_simulador > /home/usuario/respaldos/simulador_$(date +%Y%m%d).sql
  ```
- **Codigo**: al estar en control de versiones (Git), el respaldo es
  el propio repositorio remoto; no depende del hosting.
- **Restauracion**:
  ```bash
  mysql -u usuario_simdb -p usuario_simulador < /home/usuario/respaldos/simulador_AAAAMMDD.sql
  ```
  Antes de restaurar sobre una base con datos reales de estudiantes,
  confirma con el profesor/administrador: es una operacion destructiva
  sobre el estado actual.

## Activar un proveedor de datos real (EODHD / Twelve Data)

Los adaptadores en `apps/mercados/proveedores/eodhd.py` y
`twelvedata.py` estan **sin implementar** deliberadamente: antes de
activarlos hay que (1) verificar los endpoints vigentes en la
documentacion oficial del proveedor, (2) confirmar en los terminos de
la suscripcion si esta permitido redistribuir los datos a un grupo de
estudiantes, y (3) implementar y probar el adaptador. Mientras tanto,
`PROVEEDOR_DATOS_MERCADO=sintetico` (valor por defecto) mantiene el
sistema funcionando sin ninguna API externa.
