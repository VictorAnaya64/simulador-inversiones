from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect

from .forms import FormularioInicioSesionConLimite


class IniciarSesionView(LoginView):
    template_name = 'usuarios/login.html'
    authentication_form = FormularioInicioSesionConLimite
    redirect_authenticated_user = True


class CerrarSesionView(LogoutView):
    next_page = 'usuarios:login'


@login_required
def redireccion_rol(request):
    usuario = request.user
    if usuario.es_profesor:
        return redirect('cursos:panel_profesor')
    if usuario.es_admin:
        return redirect('/admin/')
    return redirect('portafolios:panel_estudiante')
