from django.urls import path

from . import views

app_name = 'analitica'

urlpatterns = [
    path('', views.analisis, name='analisis'),
]
