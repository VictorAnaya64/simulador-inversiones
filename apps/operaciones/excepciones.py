class ErrorOrden(Exception):
    """Error base para violaciones de las reglas de ordenes."""


class CursoNoDisponibleError(ErrorOrden):
    pass


class InstrumentoNoPermitidoError(ErrorOrden):
    pass


class CantidadInvalidaError(ErrorOrden):
    pass


class SinPrecioReferenciaError(ErrorOrden):
    pass
