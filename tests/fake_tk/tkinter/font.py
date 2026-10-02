"""font stand-in."""


class Font:
    def __init__(self, *args, **kwargs):
        self.settings = dict(kwargs)

    def configure(self, **kwargs):
        self.settings.update(kwargs)

    def actual(self, option=None):
        return self.settings


_named = {}


def nametofont(name):
    return _named.setdefault(name, Font())


def families(root=None):
    return ("Helvetica", "Courier New")
