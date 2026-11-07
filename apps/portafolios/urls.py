from django.urls import path

from . import views

app_name = 'portafolios'

urlpatterns = [
    path('', views.panel_estudiante, name='panel_estudiante'),
]
