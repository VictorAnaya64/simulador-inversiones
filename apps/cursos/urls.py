from django.urls import path

from . import views

app_name = 'cursos'

urlpatterns = [
    path('', views.panel_profesor, name='panel_profesor'),
    path('crear/', views.crear_curso, name='crear_curso'),
    path('<int:curso_id>/', views.detalle_curso, name='detalle_curso'),
    path('<int:curso_id>/alta-estudiantes/', views.alta_estudiantes, name='alta_estudiantes'),
]
