class EvaluationError(Exception):
    """An expected, user-facing evaluation CLI error."""


class ConfigError(EvaluationError):
    """A configuration file is missing, malformed, or invalid."""
