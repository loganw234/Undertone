"""The one way the reference model says no.

Every operation has two outcomes: the right answer, or a Refusal that names
what is wrong. The names are the definition's (`spec/undertone.toml`,
`[refusals]`), so a refusal cannot carry a name nobody declared.
"""
from spec import constants as C


class Refusal(Exception):
    """A named refusal. `name` is one of `spec.constants.REFUSALS`."""

    def __init__(self, name, detail=""):
        if name not in C.REFUSALS:
            raise ValueError("not a declared refusal name: %r" % (name,))
        self.name = name
        self.detail = detail
        super().__init__("%s: %s" % (name, detail) if detail else name)
