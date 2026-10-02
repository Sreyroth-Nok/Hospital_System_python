"""messagebox stand-in. Records what would have been shown; answers yes."""

shown = []
answer = True


def showinfo(title="", message="", **kwargs):
    shown.append(("info", title, message))
    return "ok"


def showerror(title="", message="", **kwargs):
    shown.append(("error", title, message))
    return "ok"


def showwarning(title="", message="", **kwargs):
    shown.append(("warning", title, message))
    return "ok"


def askyesno(title="", message="", **kwargs):
    shown.append(("ask", title, message))
    return answer
