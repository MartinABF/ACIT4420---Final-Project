from busbidder.errors import InvalidFieldError, MissingFieldError


class Bounded:
    def __init__(self, minimum, maximum, kind=float, optional=False):
        self.minimum = minimum
        self.maximum = maximum
        self.kind = kind
        self.optional = optional

    def __set_name__(self, owner, name):
        self.public_name = name
        self.private_name = f"_{name}"

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return getattr(instance, self.private_name)

    def __set__(self, instance, value):
        setattr(instance, self.private_name, self._validate(value))

    def _validate(self, value):
        name = self.public_name
        if value is None:
            if self.optional:
                return None
            raise MissingFieldError(f"{name} is required")
        allowed = int if self.kind is int else (int, float)
        if isinstance(value, bool) or not isinstance(value, allowed):
            raise InvalidFieldError(f"{name} must be a {self.kind.__name__}")
        if not self.minimum <= value <= self.maximum:
            raise InvalidFieldError(
                f"{name} must be between {self.minimum} and {self.maximum}, got {value}"
            )
        return self.kind(value)
