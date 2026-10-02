"""
widgets.py - Pieces every screen reuses: colours, tables, forms, messages.
Owner: Person 1

Writing these once keeps each tab short and makes every screen look the same.
"""

import tkinter as tk
from tkinter import font as tkfont, messagebox, ttk

from utils.validator import (ValidationError, parse_date, parse_day,
                             parse_float, parse_gender, parse_int, parse_phone,
                             parse_text, parse_time)

# --------------------------------------------------------------- appearance
INK = "#1f2933"
MUTED = "#6b7785"
PRIMARY = "#1f3864"
PRIMARY_LIGHT = "#dce6f5"
SURFACE = "#ffffff"
BACKGROUND = "#eef1f5"
DANGER = "#b3261e"
SUCCESS = "#1b5e20"
BORDER = "#c7cdd6"


def apply_theme(root):
    """One place for fonts, colours and widget styling."""
    for name, size, weight in (("TkDefaultFont", 10, "normal"),
                               ("TkTextFont", 10, "normal"),
                               ("TkHeadingFont", 10, "bold")):
        try:
            tkfont.nametofont(name).configure(size=size, weight=weight)
        except Exception:
            pass

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure(".", background=BACKGROUND, foreground=INK)
    style.configure("TFrame", background=BACKGROUND)
    style.configure("Card.TFrame", background=SURFACE, relief="flat")
    style.configure("TLabel", background=BACKGROUND, foreground=INK)
    style.configure("Card.TLabel", background=SURFACE, foreground=INK)
    style.configure("Title.TLabel", background=BACKGROUND, foreground=PRIMARY,
                    font=("TkDefaultFont", 16, "bold"))
    style.configure("Heading.TLabel", background=SURFACE, foreground=PRIMARY,
                    font=("TkDefaultFont", 12, "bold"))
    style.configure("Muted.TLabel", background=SURFACE, foreground=MUTED)
    style.configure("Stat.TLabel", background=SURFACE, foreground=PRIMARY,
                    font=("TkDefaultFont", 20, "bold"))
    style.configure("Status.TLabel", background=PRIMARY, foreground="#ffffff")
    style.configure("TButton", padding=(12, 6))
    style.configure("Primary.TButton", background=PRIMARY, foreground="#ffffff",
                    padding=(14, 7))
    style.map("Primary.TButton", background=[("active", "#2d4a7c")])
    style.configure("Danger.TButton", background=DANGER, foreground="#ffffff",
                    padding=(12, 6))
    style.map("Danger.TButton", background=[("active", "#8c1d18")])
    style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE,
                    rowheight=26, borderwidth=0)
    style.configure("Treeview.Heading", background=PRIMARY_LIGHT,
                    foreground=PRIMARY, font=("TkDefaultFont", 10, "bold"))
    style.configure("TNotebook", background=BACKGROUND, borderwidth=0)
    style.configure("TNotebook.Tab", padding=(18, 9))
    style.map("TNotebook.Tab",
              background=[("selected", SURFACE), ("!selected", BACKGROUND)],
              foreground=[("selected", PRIMARY), ("!selected", MUTED)])
    root.configure(background=BACKGROUND)
    return style


# ------------------------------------------------------------- small helpers
def info(message, title="Done"):
    messagebox.showinfo(title, message)


def error(message, title="Cannot do that"):
    messagebox.showerror(title, message)


def ask(message, title="Please confirm"):
    return messagebox.askyesno(title, message)


def money(value):
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "-"


class Toolbar(ttk.Frame):
    """A row of buttons above a table."""

    def __init__(self, master, buttons, **kwargs):
        super().__init__(master, style="Card.TFrame", **kwargs)
        for label, command, kind in buttons:
            style = {"primary": "Primary.TButton",
                     "danger": "Danger.TButton"}.get(kind, "TButton")
            ttk.Button(self, text=label, command=command, style=style).pack(
                side="left", padx=(0, 8), pady=8)


class SearchBar(ttk.Frame):
    """A search box that calls back on Enter or on the button."""

    def __init__(self, master, on_search, on_clear=None, placeholder="Search..."):
        super().__init__(master, style="Card.TFrame")
        self.var = tk.StringVar()
        ttk.Label(self, text=placeholder, style="Muted.TLabel").pack(
            side="left", padx=(0, 6))
        entry = ttk.Entry(self, textvariable=self.var, width=28)
        entry.pack(side="left", padx=(0, 6), pady=8)
        entry.bind("<Return>", lambda event: on_search(self.var.get().strip()))
        ttk.Button(self, text="Search",
                   command=lambda: on_search(self.var.get().strip())).pack(side="left")
        if on_clear:
            ttk.Button(self, text="Show all",
                       command=lambda: (self.var.set(""), on_clear())).pack(
                side="left", padx=(6, 0))


class DataTable(ttk.Frame):
    """A Treeview with scrollbars that takes a list of dictionaries.

    columns is a list of (key, heading, width) tuples.
    """

    def __init__(self, master, columns, on_double_click=None, height=14):
        super().__init__(master, style="Card.TFrame")
        self.columns = columns
        self._rows = {}

        keys = [c[0] for c in columns]
        self.tree = ttk.Treeview(self, columns=keys, show="headings", height=height)
        for key, heading, width in columns:
            self.tree.heading(key, text=heading)
            anchor = "e" if heading in ("Fee", "Total", "Amount", "Income",
                                        "Price", "Stock", "Visits", "Qty") else "w"
            self.tree.column(key, width=width, anchor=anchor, stretch=True)

        vertical = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.tree.tag_configure("odd", background="#f7f9fc")
        if on_double_click:
            self.tree.bind("<Double-1>", lambda event: on_double_click())

    def set_rows(self, rows, formatter=None):
        """Fill the table. formatter(row) may return a dict of display values."""
        self.tree.delete(*self.tree.get_children())
        self._rows = {}
        for index, row in enumerate(rows or []):
            display = formatter(row) if formatter else row
            values = [self._value(display, key) for key, _, _ in self.columns]
            item = self.tree.insert("", "end", values=values,
                                    tags=("odd",) if index % 2 else ())
            self._rows[item] = row
        return len(rows or [])

    @staticmethod
    def _value(row, key):
        if isinstance(row, dict):
            value = row.get(key)
        else:
            value = getattr(row, key, None)
        return "" if value is None else value

    def selected(self):
        """The original row behind the highlighted line, or None."""
        chosen = self.tree.selection()
        return self._rows.get(chosen[0]) if chosen else None

    def selected_value(self, key):
        row = self.selected()
        if row is None:
            return None
        return self._value(row, key)

    def clear(self):
        self.tree.delete(*self.tree.get_children())
        self._rows = {}


class FormDialog(tk.Toplevel):
    """A modal form built from a list of field definitions.

    Each field is a dict:
        {"key": "name", "label": "Full name", "kind": "text",
         "default": "", "options": [...], "required": True}

    kind is one of: text, int, float, phone, gender, date, time, day, choice.
    The dialog validates with the same rules the command line version uses and
    stays open, showing the message, until every value is acceptable.
    """

    KINDS_WITH_OPTIONS = ("choice", "gender", "day")

    def __init__(self, master, title, fields, submit_label="Save", intro=None):
        super().__init__(master)
        self.title(title)
        self.result = None
        self.fields = fields
        self.vars = {}

        self.transient(master)
        self.resizable(False, False)
        self.configure(background=SURFACE)

        body = ttk.Frame(self, style="Card.TFrame", padding=18)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text=title, style="Heading.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        row_index = 1
        if intro:
            ttk.Label(body, text=intro, style="Muted.TLabel",
                      wraplength=380, justify="left").grid(
                row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))
            row_index = 2

        for field in fields:
            label = field["label"]
            if not field.get("required", True):
                label += "  (optional)"
            ttk.Label(body, text=label, style="Card.TLabel").grid(
                row=row_index, column=0, sticky="w", pady=6, padx=(0, 12))

            variable = tk.StringVar(value=str(field.get("default", "") or ""))
            self.vars[field["key"]] = variable

            if field.get("kind") in self.KINDS_WITH_OPTIONS or field.get("options"):
                options = field.get("options") or (["M", "F"] if field["kind"] == "gender" else [])
                widget = ttk.Combobox(body, textvariable=variable, values=list(options),
                                      state="readonly" if field.get("strict", True) else "normal",
                                      width=28)
            else:
                widget = ttk.Entry(body, textvariable=variable, width=30,
                                   show="*" if field.get("secret") else "")
            widget.grid(row=row_index, column=1, sticky="ew", pady=6)
            row_index += 1

        self.message = ttk.Label(body, text="", foreground=DANGER,
                                 style="Card.TLabel", wraplength=380)
        self.message.grid(row=row_index, column=0, columnspan=2, sticky="w", pady=(8, 0))

        buttons = ttk.Frame(body, style="Card.TFrame")
        buttons.grid(row=row_index + 1, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", command=self._cancel).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text=submit_label, command=self._submit,
                   style="Primary.TButton").pack(side="right")

        body.grid_columnconfigure(1, weight=1)
        self.bind("<Return>", lambda event: self._submit())
        self.bind("<Escape>", lambda event: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _collect(self):
        """Read every field, converting and checking as the CLI does."""
        values = {}
        for field in self.fields:
            raw = self.vars[field["key"]].get()
            kind = field.get("kind", "text")
            label = field["label"]
            optional = not field.get("required", True)
            if kind == "int":
                values[field["key"]] = parse_int(raw, label, field.get("minimum"),
                                                 field.get("maximum"), optional)
            elif kind == "float":
                values[field["key"]] = parse_float(raw, label,
                                                   field.get("minimum", 0.0), optional)
            elif kind == "phone":
                values[field["key"]] = parse_phone(raw, label, optional)
            elif kind == "gender":
                values[field["key"]] = parse_gender(raw, label)
            elif kind == "date":
                values[field["key"]] = parse_date(raw, label,
                                                  field.get("no_past", False), optional)
            elif kind == "time":
                values[field["key"]] = parse_time(raw, label, optional)
            elif kind == "day":
                values[field["key"]] = parse_day(raw, label)
            elif kind == "choice":
                value = (raw or "").strip()
                if not value and not optional:
                    raise ValidationError(f"{label} must be chosen.")
                values[field["key"]] = value
            else:
                values[field["key"]] = parse_text(raw, label, optional,
                                                  field.get("max_len", 120))
        return values

    def _submit(self):
        try:
            self.result = self._collect()
        except ValidationError as e:
            self.message.configure(text=str(e))
            return
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()

    @classmethod
    def open(cls, master, title, fields, submit_label="Save", intro=None):
        """Show the form and return the values, or None if it was cancelled."""
        dialog = cls(master, title, fields, submit_label, intro)
        dialog.grab_set()
        master.wait_window(dialog)
        return dialog.result


class TextWindow(tk.Toplevel):
    """A read-only window for a receipt or any block of fixed-width text."""

    def __init__(self, master, title, content, on_save=None):
        super().__init__(master)
        self.title(title)
        self.configure(background=SURFACE)
        frame = ttk.Frame(self, style="Card.TFrame", padding=14)
        frame.pack(fill="both", expand=True)

        box = tk.Text(frame, width=56, height=28, font=("Courier New", 10),
                      background="#fbfbfd", relief="flat", borderwidth=1)
        box.insert("1.0", content)
        box.configure(state="disabled")
        box.pack(fill="both", expand=True)

        buttons = ttk.Frame(frame, style="Card.TFrame")
        buttons.pack(fill="x", pady=(10, 0))
        if on_save:
            ttk.Button(buttons, text="Save to file", command=on_save,
                       style="Primary.TButton").pack(side="left")
        ttk.Button(buttons, text="Close", command=self.destroy).pack(side="right")
