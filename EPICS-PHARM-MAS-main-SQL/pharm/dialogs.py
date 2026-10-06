"""Prompts with the call signatures of tkinter.messagebox and tkinter.simpledialog.

When the application registers a prompt host (the desktop's work panel), each
prompt appears there as one guided step instead of a separate window, so a
sequence such as count, scan, confirm removal and confirm closure happens in
one place. Without a host, or while a step is already showing, prompts open as
themed modal windows. Either way each call blocks until it is answered, and a
barcode scan ending in Enter submits like typing.
"""
import tkinter as tk
from tkinter import ttk

from UI import theme as T
from .widgets import ScrollFrame, label

_TONES = {"info": T.ACCENT_DARK, "warning": T.WARNING, "error": T.DANGER}


class _Prompt:
    def __init__(self, parent, title, message, tone=None):
        master = (parent or tk._get_default_root("use dialogs")).winfo_toplevel()
        root = master.nametowidget(".")
        self.theme = theme = T.apply_theme(master)
        px = theme.px
        self.master, self.result = master, None
        self.done = tk.BooleanVar(master, False)
        host = getattr(root, "pharm_prompt_host", None)
        self.host = host if host is not None and master is root and host.prompt_available() else None
        if self.host:
            self.top = None
            frame = self.host.prompt_begin(self)
            pads = (px(44), px(40))
        else:
            self.top = frame = tk.Toplevel(master)
            frame.withdraw()
            frame.title(title)
            frame.configure(bg=T.SURFACE)
            frame.resizable(False, False)
            if master.winfo_viewable():
                frame.transient(master)
            pads = (px(30), px(28))
        self.body = tk.Frame(frame, bg=T.SURFACE, padx=pads[0], pady=pads[1])
        self.body.pack(fill="both", expand=True)
        self.body.columnconfigure(0, weight=1, minsize=px(460))
        context = self.host.prompt_context() if self.host else ""
        caption = f"{context}  ·  {title}" if context else title
        label(self.body, caption.upper(), "caption", _TONES.get(tone, T.ACCENT_DARK)).grid(row=0, column=0, sticky="w")
        if message:
            label(self.body, message, "prompt", wraplength=px(600)).grid(row=1, column=0, sticky="w", pady=(px(10), 0))
        self.row = 2
        self.footer = tk.Frame(self.body, bg=T.SURFACE)
        self.error = tk.StringVar()

    def add(self, widget, pady=(20, 0)):
        widget.grid(row=self.row, column=0, sticky="ew", pady=tuple(self.theme.px(p) for p in pady))
        self.row += 1
        return widget

    def error_slot(self):
        self.add(label(self.body, font="body", fg=T.DANGER, textvariable=self.error), pady=(8, 0))

    def button(self, text, command, kind="Secondary"):
        button = ttk.Button(self.footer, text=text, command=command, width=-8,
                            style=self.theme.button_style(kind, T.SURFACE, large=True))
        button.pack(side="left", padx=(0, self.theme.px(12)))
        button.bind("<Return>", lambda _: (button.invoke(), "break")[1])
        button.bind("<Escape>", lambda _: (self.close(), "break")[1])
        return button

    def close(self, result=None):
        if self.done.get():
            return
        self.result = result
        self.done.set(True)
        if self.host:
            self.host.prompt_end(self)
        else:
            self.top.grab_release()
            self.top.destroy()

    def show(self, focus):
        self.footer.grid(row=self.row, column=0, sticky="w", pady=(self.theme.px(28), 0))
        if self.host:
            focus.focus_set()
            try:
                self.master.wait_variable(self.done)
            except tk.TclError:
                pass  # The window closed while the step was showing.
            return self.result
        top, master = self.top, self.master
        top.protocol("WM_DELETE_WINDOW", self.close)
        top.bind("<Escape>", lambda _: self.close())
        top.update_idletasks()
        width, height = top.winfo_reqwidth(), top.winfo_reqheight()
        if master.winfo_viewable():
            x = master.winfo_rootx() + (master.winfo_width() - width) // 2
            y = master.winfo_rooty() + (master.winfo_height() - height) // 3
        else:
            x = (top.winfo_screenwidth() - width) // 2
            y = (top.winfo_screenheight() - height) // 3
        top.geometry(f"+{max(0, x)}+{max(0, y)}")
        top.deiconify()
        top.lift()
        try:
            top.grab_set()
        except tk.TclError:
            pass  # Another application holds the grab; the window still works.
        focus.focus_force()
        top.wait_window()
        return self.result


def _message(title, message, parent, tone):
    prompt = _Prompt(parent, title, message, tone)
    ok = prompt.button("OK", lambda: prompt.close("ok"), "Primary")
    return prompt.show(ok) or "ok"


def showinfo(title, message, parent=None):
    return _message(title, message, parent, "info")


def showwarning(title, message, parent=None):
    return _message(title, message, parent, "warning")


def showerror(title, message, parent=None):
    return _message(title, message, parent, "error")


def askyesno(title, message, parent=None, yes="Yes", no="No", danger=False):
    prompt = _Prompt(parent, title, message, "warning" if danger else None)
    accept = prompt.button(yes, lambda: prompt.close(True), "Danger" if danger else "Primary")
    prompt.button(no, lambda: prompt.close(False))
    return bool(prompt.show(accept))


def _ask(title, text, parent, initialvalue, convert, scan=False, confirm="Continue"):
    prompt = _Prompt(parent, title, text)
    entry = prompt.add(ttk.Entry(prompt.body, font=prompt.theme.font("scan" if scan else "input")))
    if initialvalue is not None:
        entry.insert(0, str(initialvalue))
        entry.select_range(0, "end")
    prompt.error_slot()

    def submit(_event=None):
        try:
            prompt.close(convert(entry.get()))
        except ValueError as exc:
            prompt.error.set(str(exc))
            entry.focus_set()
            entry.select_range(0, "end")
        return "break"
    prompt.button(confirm, submit, "Primary")
    prompt.button("Cancel", prompt.close)
    entry.bind("<Return>", submit)
    entry.bind("<Escape>", lambda _: (prompt.close(), "break")[1])
    return prompt.show(entry)


def askinteger(title, prompt, parent=None, minvalue=None, maxvalue=None, initialvalue=None):
    def convert(text):
        try:
            value = int(text.strip())
        except ValueError:
            raise ValueError("Enter a whole number.") from None
        if (minvalue is not None and value < minvalue) or (maxvalue is not None and value > maxvalue):
            if minvalue is not None and maxvalue is not None:
                raise ValueError(f"Enter a whole number from {minvalue} to {maxvalue}.")
            raise ValueError(f"Enter a whole number of at least {minvalue}." if minvalue is not None
                             else f"Enter a whole number no greater than {maxvalue}.")
        return value
    return _ask(title, prompt, parent, initialvalue, convert)


def askstring(title, prompt, parent=None, initialvalue=None, scan=False):
    """Returns the text, possibly empty, or None when cancelled."""
    return _ask(title, prompt, parent, initialvalue, lambda text: text, scan=scan,
                confirm="Submit scan" if scan else "Continue")


def askchoices(title, prompt, options, parent=None):
    """Checklist; returns the selected option indexes, or None when cancelled."""
    dialog = _Prompt(parent, title, prompt)
    px = dialog.theme.px
    toolbar = dialog.add(tk.Frame(dialog.body, bg=T.SURFACE), pady=(20, 6))
    count = tk.StringVar()
    label(toolbar, font="strong", fg=T.TEXT_SOFT, textvariable=count).pack(side="left")
    frame = tk.Frame(dialog.body, bg=T.SURFACE, highlightthickness=1, highlightbackground=T.BORDER)
    dialog.add(frame, pady=(0, 0))
    area = ScrollFrame(frame, bg=T.SURFACE)
    area.canvas.configure(width=px(560), height=px(min(len(options), 6) * 44 + 12))
    area.pack(fill="both", expand=True)
    variables = []

    def recount():
        count.set(f"{sum(v.get() for v in variables)} of {len(options)} selected")
    for text in options:
        variable = tk.BooleanVar(value=False)
        variables.append(variable)
        ttk.Checkbutton(area.body, text=text, variable=variable, style="Check.TCheckbutton",
                        command=recount).pack(anchor="w", padx=px(14))
    recount()

    def every(value):
        for variable in variables:
            variable.set(value)
        recount()
    for text, value in (("Clear", False), ("Select all", True)):
        ttk.Button(toolbar, text=text, style=dialog.theme.button_style("Ghost"),
                   command=lambda v=value: every(v)).pack(side="right")
    accept = dialog.button("Continue", lambda: dialog.close([i for i, v in enumerate(variables) if v.get()]), "Primary")
    dialog.button("Cancel", dialog.close)
    return dialog.show(accept)


def showimage(title, message, image, parent=None):
    prompt = _Prompt(parent, title, message)
    prompt.add(tk.Label(prompt.body, image=image, bg=T.SURFACE, bd=0, anchor="w"))
    close = prompt.button("Close", prompt.close, "Primary")
    return prompt.show(close)


def showrecords(title, columns, rows, parent=None, message=None):
    prompt = _Prompt(parent, title, message)
    px = prompt.theme.px
    if rows:
        frame = prompt.add(tk.Frame(prompt.body, bg=T.SURFACE))
        table = ttk.Treeview(frame, columns=columns, show="headings", style="Records.Treeview",
                             height=min(len(rows), 9), selectmode="browse")
        for column in columns:
            table.heading(column, text=column.upper(), anchor="w")
            table.column(column, width=px(170), anchor="w")
        for row in rows:
            table.insert("", "end", values=row)
        table.pack(side="left", fill="both", expand=True)
        if len(rows) > 9:
            bar = ttk.Scrollbar(frame, orient="vertical", style=prompt.theme.scrollbar_style(T.SURFACE),
                                command=table.yview)
            table.configure(yscrollcommand=bar.set)
            bar.pack(side="right", fill="y")
    else:
        prompt.add(label(prompt.body, "No box records.", fg=T.MUTED))
    close = prompt.button("Close", prompt.close, "Primary")
    return prompt.show(close)
