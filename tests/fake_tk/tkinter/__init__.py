"""
A stand-in for tkinter, used only by tests/gui_smoke.py.

It lets the whole interface be built and driven on a machine with no
tkinter installed and no screen attached, which is how the GUI was checked
for import errors, wiring mistakes and broken data flow. It draws nothing.
Delete this folder and the real tkinter is used; nothing in the application
imports it.
"""

_counter = [0]


def _uid(prefix="I"):
    _counter[0] += 1
    return f"{prefix}{_counter[0]:04d}"


class Variable:
    def __init__(self, master=None, value=None, name=None):
        self._value = "" if value is None else value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


StringVar = IntVar = DoubleVar = BooleanVar = Variable


class Widget:
    """Accepts anything, records children, and answers unknown calls quietly."""

    def __init__(self, master=None, **kwargs):
        self.master = master
        self.kwargs = dict(kwargs)
        self.children = []
        self.bindings = {}
        self._destroyed = False
        if isinstance(master, Widget):
            master.children.append(self)

    # --- geometry and configuration ---
    def pack(self, **kwargs):
        return self

    def grid(self, **kwargs):
        return self

    def place(self, **kwargs):
        return self

    def configure(self, **kwargs):
        self.kwargs.update(kwargs)
        return self

    config = configure

    def cget(self, key):
        return self.kwargs.get(key)

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback

    def winfo_children(self):
        return list(self.children)

    def destroy(self):
        self._destroyed = True
        if isinstance(self.master, Widget) and self in self.master.children:
            self.master.children.remove(self)

    def __getattr__(self, name):
        """Any other tkinter call does nothing and returns a safe value."""
        def anything(*args, **kwargs):
            if name.startswith("winfo_"):
                return 800
            return None
        return anything


class Misc(Widget):
    pass


class Tk(Widget):
    def mainloop(self, n=0):
        return None

    def wait_window(self, window=None):
        return None

    def update_idletasks(self):
        return None


class Toplevel(Tk):
    pass


class Frame(Widget):
    pass


class Label(Widget):
    pass


class Button(Widget):
    def invoke(self):
        command = self.kwargs.get("command")
        return command() if command else None


class Entry(Widget):
    pass


class Text(Widget):
    def insert(self, index, text):
        self.kwargs["text"] = self.kwargs.get("text", "") + str(text)

    def get(self, start="1.0", end="end"):
        return self.kwargs.get("text", "")


class Canvas(Widget):
    pass


class Menu(Widget):
    pass


class PhotoImage(Widget):
    pass


END = "end"
LEFT = "left"
RIGHT = "right"
TOP = "top"
BOTTOM = "bottom"
BOTH = "both"
X = "x"
Y = "y"
W = "w"
E = "e"
NSEW = "nsew"
