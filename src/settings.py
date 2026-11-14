import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional


class _ToggleSwitch(tk.Canvas):
    def __init__(self, master: tk.Misc, variable: tk.BooleanVar) -> None:
        background = ttk.Style(master).lookup("TFrame", "background")
        super().__init__(
            master,
            width=44,
            height=26,
            background=background or "SystemButtonFace",
            borderwidth=0,
            highlightthickness=0,
            takefocus=True,
            cursor="hand2",
        )
        self.variable = variable
        self.variable.trace_add("write", self._draw)
        self.bind("<Button-1>", self._toggle)
        self.bind("<space>", self._toggle)
        self.bind("<Return>", self._toggle)
        self.bind("<FocusIn>", self._draw)
        self.bind("<FocusOut>", self._draw)
        self._draw()

    def _toggle(self, _event: Optional[tk.Event] = None) -> str:
        self.focus_set()
        self.variable.set(not self.variable.get())
        return "break"

    def _draw(self, *_args: str) -> None:
        self.delete("all")
        enabled = self.variable.get()
        track_color = "#2563eb" if enabled else "#94a3b8"
        self.create_rectangle(
            12, 2, 32, 22, fill=track_color, outline=track_color
        )
        self.create_oval(2, 2, 22, 22, fill=track_color, outline=track_color)
        self.create_oval(22, 2, 42, 22, fill=track_color, outline=track_color)
        knob_x = 24 if enabled else 4
        self.create_oval(knob_x, 4, knob_x + 16, 20, fill="#ffffff", outline="")
        if self.focus_get() is self:
            self.create_rectangle(0, 0, 43, 25, outline="#1d4ed8", width=1)


class SettingsDialog(tk.Toplevel):
    """Dialog for application settings."""

    def __init__(
        self,
        master: tk.Misc,
        low_power_mode: bool = False,
        on_low_power_mode_changed: Optional[Callable[[bool], None]] = None,
    ) -> None:
        super().__init__(master)
        self.title("Settings")
        self.transient(master.winfo_toplevel())
        self.resizable(False, False)
        self.bind("<Escape>", lambda _event: self.destroy())

        content = ttk.Frame(self, padding=18)
        content.grid(row=0, column=0, sticky="nsew")
        ttk.Label(content, text="Low-power Mode").grid(
            row=0, column=0, sticky="w", padx=(0, 16)
        )
        self.low_power_mode_var = tk.BooleanVar(self, value=low_power_mode)
        if on_low_power_mode_changed is not None:
            self.low_power_mode_var.trace_add(
                "write",
                lambda *_args: on_low_power_mode_changed(
                    self.low_power_mode_var.get()
                ),
            )
        _ToggleSwitch(content, self.low_power_mode_var).grid(row=0, column=1)

        self.geometry("320x180")
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        self.grab_set()