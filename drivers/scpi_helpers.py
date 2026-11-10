"""Helpers for building validated, typed SCPI properties on instrument drivers."""


class Choice:
    """Validates a SCPI keyword argument and normalizes it to its long form.

    Keywords use the SCPI manual notation, where the upper-case letters are the short
    form: "PERiod" accepts "PER" or "PERIOD" in any case, and both become "PERIOD".
    """

    def __init__(self, *keywords):
        self._long_forms = {}
        for keyword in keywords:
            long_form = keyword.upper()
            short_form = "".join(c for c in keyword if c.isupper() or c.isdigit())
            self._long_forms[long_form] = long_form
            self._long_forms[short_form] = long_form

    def __call__(self, value):
        key = str(value).strip().strip('"').upper()
        if key not in self._long_forms:
            raise ValueError(f"must be one of {sorted(set(self._long_forms.values()))}, got {value!r}")
        return self._long_forms[key]


def to_number(value):
    """Validates a number and formats it for a SCPI read command."""
    return str(float(value))


def to_integer(value):
    """Validates a whole number and formats it for a SCPI command."""
    if int(value) != value:
        raise ValueError(f"must be a whole number, got {value!r}")
    return str(int(value))


def to_on_off(value):
    """Formats a truth value as a SCPI ON or OFF."""
    return "ON" if value else "OFF"


def parse_bool(response):
    """Parses a SCPI boolean reply: 1 or ON is True, anything else is False."""
    return response.strip().upper() in ("1", "ON")


def parse_integer(response):
    """Parses a SCPI whole-number reply, which may be formatted like "3.0"."""
    return int(float(response))


def scpi_property(command, doc, to_scpi, from_scpi):
    """Builds a property that sends "<command> <value>" and queries "<command>?"."""

    def getter(self):
        return from_scpi(self.query(f"{command}?"))

    def setter(self, value):
        self.write(f"{command} {to_scpi(value)}")

    return property(getter, setter, doc=doc)
