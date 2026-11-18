class BusBidderError(Exception):
    pass


class DataFileError(BusBidderError):
    pass


class RecordError(BusBidderError):
    category = "invalid_value"


class MissingFieldError(RecordError):
    category = "missing_value"


class InvalidFieldError(RecordError):
    category = "invalid_value"


class UnknownReferenceError(RecordError):
    category = "unknown_reference"


class InconsistentRecordError(RecordError):
    category = "inconsistent"


class DuplicateRecordError(RecordError):
    category = "duplicate"


class NoSeatsError(RecordError):
    category = "no_seats"
