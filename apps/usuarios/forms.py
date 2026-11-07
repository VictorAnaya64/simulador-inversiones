from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.core.cache import cache
from django.core.exceptions import ValidationError


def _clave_cache_intentos(username):
    return f'login_intentos:{username.lower()}'


class FormularioInicioSesionConLimite(AuthenticationForm):
    """
    Bloquea temporalmente el inicio de sesion tras demasiados intentos
    fallidos consecutivos (por nombre de usuario). Usa la cache
    configurada en settings.CACHES; ver limitacion documentada en
    docs/despliegue_cpanel.md sobre cache local por proceso.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'autofocus': True})
        self.fields['password'].widget.attrs.update({'class': 'form-control'})

    def clean(self):
        username = self.cleaned_data.get('username')
        if username:
            intentos = cache.get(_clave_cache_intentos(username), 0)
            if intentos >= settings.LOGIN_MAX_INTENTOS:
                raise ValidationError(
                    f'Demasiados intentos fallidos. Intenta de nuevo en '
                    f'{settings.LOGIN_BLOQUEO_MINUTOS} minutos.',
                    code='demasiados_intentos',
                )
        try:
            return super().clean()
        except ValidationError:
            if username:
                clave = _clave_cache_intentos(username)
                cache.set(clave, cache.get(clave, 0) + 1, timeout=settings.LOGIN_BLOQUEO_MINUTOS * 60)
            raise

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        cache.delete(_clave_cache_intentos(user.username))
