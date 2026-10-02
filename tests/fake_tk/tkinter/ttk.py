"""ttk stand-in: the themed widgets, plus a Treeview that really holds rows."""

from tkinter import Widget, _uid


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


class Combobox(Widget):
    def set(self, value):
        self.kwargs["value"] = value

    def get(self):
        return self.kwargs.get("value", "")

    def current(self, index=None):
        return 0


class Notebook(Widget):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.tabs_added = []

    def add(self, child, text="", **kwargs):
        self.tabs_added.append((text, child))

    def select(self, tab=None):
        return None


class Scrollbar(Widget):
    def set(self, *args):
        return None


class Separator(Widget):
    pass


class Progressbar(Widget):
    pass


class Treeview(Widget):
    """Holds inserted rows so the table code can be exercised for real."""

    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.rows = {}
        self.order = []
        self._selection = ()
        self.headings = {}

    def heading(self, column, text="", **kwargs):
        self.headings[column] = text

    def column(self, column, **kwargs):
        return None

    def insert(self, parent, index, values=(), tags=(), **kwargs):
        item = _uid("R")
        self.rows[item] = list(values)
        self.order.append(item)
        return item

    def get_children(self, item=""):
        return tuple(self.order)

    def delete(self, *items):
        for item in items:
            self.rows.pop(item, None)
            if item in self.order:
                self.order.remove(item)

    def selection(self):
        return self._selection

    def selection_set(self, item):
        self._selection = (item,)

    def select_first(self):
        """Test helper: highlight the first row."""
        if self.order:
            self._selection = (self.order[0],)
        return self._selection

    def tag_configure(self, name, **kwargs):
        return None

    def yview(self, *args):
        return None

    def xview(self, *args):
        return None


class Style(Widget):
    def __init__(self, master=None):
        super().__init__(master)
        self.settings = {}

    def theme_use(self, name=None):
        return "clam"

    def configure(self, style="", **kwargs):
        self.settings[style] = kwargs
        return None

    def map(self, style="", **kwargs):
        return None
