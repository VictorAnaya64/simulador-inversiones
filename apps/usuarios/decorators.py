from django.contrib.auth.decorators import user_passes_test

requiere_profesor = user_passes_test(
    lambda u: u.is_authenticated and (u.es_profesor or u.es_admin), login_url='usuarios:login',
)
requiere_estudiante = user_passes_test(
    lambda u: u.is_authenticated and u.es_estudiante, login_url='usuarios:login',
)
