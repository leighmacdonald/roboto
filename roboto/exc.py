class RobotoException(Exception):
    pass


class ValidationError(RobotoException):
    pass


class InvalidArgument(ValidationError):
    pass
