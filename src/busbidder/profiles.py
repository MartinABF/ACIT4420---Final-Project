import json
from dataclasses import dataclass, replace

from busbidder.errors import ConfigError
from busbidder.scoring import validate_weights
from busbidder.travel import PERIODS

REQUIREMENTS = {"max_transfers", "require_changeable", "require_refundable"}


@dataclass(frozen=True)
class Profile:
    name: str
    description: str
    weights: dict
    preferred_period: str
    requirements: dict

    def apply(self, request, period=None):
        changes = {"preferred_period": period or self.preferred_period}
        for key, value in self.requirements.items():
            current = getattr(request, key)
            if isinstance(value, bool):
                changes[key] = current or value
            else:
                changes[key] = value if current is None else min(current, value)
        return replace(request, **changes)


def _parse_profile(name, data):
    try:
        requirements = data.get("requirements", {})
        unknown = set(requirements) - REQUIREMENTS
        if unknown:
            raise ConfigError(f"profile {name} has unknown requirements: {sorted(unknown)}")
        period = data["preferred_period"]
        if period not in PERIODS:
            raise ConfigError(f"profile {name} has unknown period: {period}")
        weights = validate_weights(data["weights"])
        return Profile(name, data["description"], weights, period, requirements)
    except (KeyError, TypeError, AttributeError) as error:
        raise ConfigError(f"profile {name} is incomplete: {error}") from error


def load_profiles(path):
    try:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as error:
        raise ConfigError(f"profile file not found: {path}") from error
    except (OSError, ValueError) as error:
        raise ConfigError(f"could not read {path}: {error}") from error
    if not isinstance(data, dict) or len(data) < 3:
        raise ConfigError("the profile file must define at least three profiles")
    return {name: _parse_profile(name, values) for name, values in data.items()}


def parse_weights(text):
    try:
        pairs = (part.split("=") for part in text.split(","))
        return {name.strip(): float(value) / 100 for name, value in pairs}
    except ValueError as error:
        raise ConfigError("write weights like price=40,duration=25") from error
