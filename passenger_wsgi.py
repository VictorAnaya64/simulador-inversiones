"""
Punto de entrada que Phusion Passenger (usado por "Setup Python App" de
cPanel) busca por convencion en la raiz de la aplicacion. Simplemente
delega en config/wsgi.py; no agregar logica de negocio aqui.

cPanel ejecuta este archivo con el interprete Python del entorno virtual
que "Setup Python App" crea y activa automaticamente (ver
docs/despliegue_cpanel.md); no es necesario activar el venv manualmente
en este archivo.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from config.wsgi import application  # noqa: E402
