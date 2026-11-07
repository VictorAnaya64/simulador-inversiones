class ErrorPortafolio(Exception):
    """Error base para violaciones de reglas del portafolio."""


class EfectivoInsuficienteError(ErrorPortafolio):
    pass


class TitulosInsuficientesError(ErrorPortafolio):
    pass
