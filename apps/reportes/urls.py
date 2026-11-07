from django.urls import path

from . import views

app_name = 'reportes'

urlpatterns = [
    path('curso/<int:curso_id>/csv/', views.exportar_curso_csv, name='exportar_curso_csv'),
    path('curso/<int:curso_id>/excel/', views.exportar_curso_excel, name='exportar_curso_excel'),
]
