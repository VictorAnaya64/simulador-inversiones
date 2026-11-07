from django.urls import path

from . import views

app_name = 'operaciones'

urlpatterns = [
    path('', views.ordenes, name='ordenes'),
    path('nueva/<int:instrumento_id>/<str:tipo>/', views.nueva_orden, name='nueva_orden'),
    path('<int:orden_id>/cancelar/', views.cancelar_orden_view, name='cancelar_orden'),
]
