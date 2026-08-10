from enum import StrEnum

########################################################################################


class BadRequestErrorTypes(StrEnum):
    FAILED_VALIDATION = "Uno o más campos no se pudieron validar."
    INCORRECT_TYPE = "Uno o más argumentos son del tipo incorrecto."
    MISSING_FIELDS = "No se recibieron todos los argumentos necesarios."


########################################################################################


class ConflictErrorTypes(StrEnum):
    CHECK = "Uno o más campos no cumplen con las restricciones."
    BAD_FOREIGN = "Una de las llaves foráneas no corresponde a un registro relacionado."
    LOCKED = "El recurso está siendo modificado por otra solicitud."
    NULL = "Uno o más campos no pueden ser nulos."
    RESTRICT = "No se puede eliminar un recurso con referencias externas."
    UNIQUE = "No se puede crear un registro duplicado."


########################################################################################


class ContentTooLargeErrorTypes(StrEnum):
    BODY = "El cuerpo de la solicitud excede el tamaño máximo permitido."
    FIELDS = "La solicitud contiene más campos de los permitidos."
    FILES = "La solicitud contiene más archivos de los permitidos."


########################################################################################


class UnsupportedMediaErrorTypes(StrEnum):
    UNSUPPORTED_ENCODING = "El cuerpo de la solicitud debe estar codificado en UTF-8."
    UNSUPPORTED_FILES = "El tipo de contenido enviado no permite el envío de archivos."
    UNSUPPORTED_MEDIA = "El tipo de contenido especificado no es soportado."


########################################################################################


class RequestScopes(StrEnum):
    BODY = "body"
    COOKIES = "cookies"
    FILES = "files"
    HEADERS = "headers"
    PATH = "path"
    QUERY = "query"
