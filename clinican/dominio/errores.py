"""Errores del negocio. Sus mensajes se muestran tal cual a la persona usuaria."""


class ErrorClinican(Exception):
    """Error esperado con un mensaje claro en español."""


class PermisoDenegado(ErrorClinican):
    pass


class DatoInvalido(ErrorClinican):
    pass


class CredencialesInvalidas(ErrorClinican):
    pass


class NoEncontrado(ErrorClinican):
    pass
