from django.urls import path

from . import views

app_name = 'mercados'

urlpatterns = [
    path('', views.buscador, name='buscador'),
    path('<int:instrumento_id>/', views.detalle_instrumento, name='detalle_instrumento'),
]
