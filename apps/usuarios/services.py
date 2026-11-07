from .models import RegistroAuditoria


def registrar_auditoria(usuario, accion, descripcion, objeto=None, **datos_adicionales):
    """Crea una entrada de auditoria. Uso transversal desde cualquier app."""
    registro = RegistroAuditoria(
        usuario=usuario,
        accion=accion,
        descripcion=descripcion,
        datos_adicionales=datos_adicionales,
    )
    if objeto is not None:
        registro.objeto_relacionado = objeto
    registro.save()
    return registro
