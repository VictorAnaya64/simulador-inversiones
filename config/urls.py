from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(pattern_name='usuarios:redireccion_rol'), name='inicio'),
    path('cuentas/', include('apps.usuarios.urls')),
    path('cursos/', include('apps.cursos.urls')),
    path('mercado/', include('apps.mercados.urls')),
    path('operaciones/', include('apps.operaciones.urls')),
    path('panel/', include('apps.portafolios.urls')),
    path('analisis/', include('apps.analitica.urls')),
    path('reportes/', include('apps.reportes.urls')),
]
