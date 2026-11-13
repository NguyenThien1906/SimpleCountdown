#!/usr/bin/env python3
# at top of Timer.py (first non-comment line)
from __future__ import annotations
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import List, Optional, Callable, Any
from typing import Union, Optional


DISPLAY_NAME_MAX = 20
PREVIEW_NAME_MAX = 40
RESOURCE_OPTIONS = ("Empty", "Half", "Full")
RESOURCE_LABELS = {"Empty": "Empty!!!!!!!!!!!!!!!", "Half": "Half?????", "Full": "Full"}
RESOURCE_VALUES_BY_LABEL = {label: value for value, label in RESOURCE_LABELS.items()}
RESOURCE_DISPLAY_OPTIONS = tuple(RESOURCE_LABELS[value] for value in RESOURCE_OPTIONS)


def apply_classic_widget_colors(root, dark_mode: bool, excluded=()):
    """Apply a palette to classic Tk widgets, optionally preserving subtrees."""
    excluded_paths = tuple(str(widget) for widget in excluded)
    dark_palette = {
        "background": "#333333",
        "foreground": "#f0f0f0",
        "button_background": "#444444",
        "entry_background": "#222222",
        "active_background": "#555555",
    }

    def visit(widget, excluded_parent=False):
        path = str(widget)
        is_excluded = excluded_parent or any(
            path == excluded_path or path.startswith(excluded_path + ".")
            for excluded_path in excluded_paths
        )
        if not is_excluded:
            if not hasattr(widget, "_light_mode_colors"):
                widget._light_mode_colors = {}
            if isinstance(widget, (tk.Tk, tk.Toplevel, tk.Frame, tk.LabelFrame)):
                options = ("background",)
            elif isinstance(widget, tk.Canvas):
                options = ("background",)
            elif isinstance(widget, tk.Label):
                options = ("background", "foreground")
            elif isinstance(widget, tk.Button):
                options = ("background", "foreground", "activebackground", "activeforeground")
            elif isinstance(widget, tk.Text):
                options = ("background", "foreground", "insertbackground", "selectbackground", "selectforeground")
            elif isinstance(widget, tk.Scrollbar):
                options = ("background", "troughcolor", "activebackground")
            else:
                options = ()

            values = {}
            for option in options:
                if option not in widget.configure():
                    continue
                if option not in widget._light_mode_colors:
                    widget._light_mode_colors[option] = widget.cget(option)
                original = widget._light_mode_colors[option]
                if dark_mode:
                    if option == "background":
                        value = (dark_palette["button_background"] if isinstance(widget, tk.Button)
                                 else dark_palette["entry_background"] if isinstance(widget, tk.Text)
                                 else dark_palette["background"])
                    elif option in ("foreground", "activeforeground", "insertbackground", "selectforeground"):
                        value = dark_palette["foreground"]
                    elif option in ("activebackground",):
                        value = dark_palette["active_background"]
                    elif option == "selectbackground":
                        value = "#666666"
                    elif option == "troughcolor":
                        value = dark_palette["background"]
                    else:
                        value = dark_palette["button_background"]
                else:
                    value = original
                values[option] = value
            if values:
                widget.configure(**values)

        for child in widget.winfo_children():
            visit(child, is_excluded)

    visit(root)


def _parent_dark_mode(parent) -> bool:
    current = parent
    while current is not None:
        if hasattr(current, "_dark_mode"):
            return bool(current._dark_mode)
        current = getattr(current, "master", None)
    return False


def _shorten(text: str, max_len: int) -> str:
    if text is None:
        return ""
    s = str(text)
    if len(s) <= max_len:
        return s
    if max_len <= 3:
        return s[:max_len]
    return s[: max_len - 3] + "..."

def _center_window(win: tk.Toplevel | tk.Tk | tk.Widget, width: Optional[int] = None, height: Optional[int] = None):
    """
    Cross-platform center helper. If width/height are None we use current widget size.
    Call after widgets are laid out (use update_idletasks()).
    """
    try:
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        if width is None:
            width = win.winfo_width()
            if width <= 1:
                width = win.winfo_reqwidth()
        if height is None:
            height = win.winfo_height()
            if height <= 1:
                height = win.winfo_reqheight()
        x = max((sw - width) // 2, 0)
        y = max((sh - height) // 2, 0)
        win.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        # Fallback: ignore centering failure (shouldn't be fatal)
        pass

class AddNameDialog(simpledialog.Dialog):
    """Simple dialog to enter a new name (single-line)."""
    def __init__(self, parent, title="Add Name"):
        self.result_text: Optional[str] = None
        super().__init__(parent, title)

    def buttonbox(self):
        super().buttonbox()
        apply_classic_widget_colors(self, _parent_dark_mode(self.master))

    def body(self, master):
        ttk.Label(master, text="New name:").grid(row=0, column=0, sticky="w", pady=(4,4))
        self.entry = ttk.Entry(master, width=30)
        self.entry.grid(row=1, column=0, padx=4, pady=(0,8))
        # center this dialog on screen (dialog is already created at this point)
        _center_window(self)
        return self.entry

    def validate(self):
        txt = self.entry.get().strip()
        if not txt:
            messagebox.showwarning("Empty", "Please enter a non-empty name.")
            return False
        self.result_text = txt
        return True

    def apply(self):
        # result_text is already set in validate
        pass

class _ScrollableNames(ttk.Frame):
    """
    Scrollable list helper used by the NameChooser.

    Key points:
    - Uses a Canvas + inner tk.Frame to host items.
    - Has its own dedicated vertical scrollbar so A and B each
      have a separate visible vertical bar.
    - Binds mouse-wheel events to both canvas and inner so scrolling is independent
      when the mouse is over either widget.
    - Uses grid layout internally to avoid accidental covering of the scrollbar.
    """
    def __init__(self, parent, height: int = 200):
        super().__init__(parent)

        # Canvas that holds the inner frame
        self.canvas = tk.Canvas(self, height=height, highlightthickness=0)
        # Use a tk.Scrollbar (always visible). ttk.Scrollbar can be used if preferred.
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview, width=12)

        # Inner container for items. Use tk.Frame for consistent event behavior.
        self.inner = tk.Frame(self.canvas)

        # Create window inside canvas
        self.inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        # Configure yscroll
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Layout using grid to ensure the scrollbar isn't overlapped
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        # keep scroll region updated
        self.inner.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self._bind_mousewheel_tree(self.canvas)

        # ensure scrollbar sits above other widgets
        try:
            self.scrollbar.lift()
        except Exception:
            pass

    def _on_frame_configure(self, event=None):
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass

    def _on_canvas_configure(self, event):
        try:
            # ensure inner frame width follows canvas width
            self.canvas.itemconfigure(self.inner_id, width=event.width)
        except Exception:
            pass

    def _bind_mousewheel_tree(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        widget.bind("<Button-4>", self._on_mousewheel, add="+")
        widget.bind("<Button-5>", self._on_mousewheel, add="+")
        for child in widget.winfo_children():
            self._bind_mousewheel_tree(child)

    def _on_mousewheel(self, event):
        if not self.canvas.winfo_exists():
            return

        toplevel = self.canvas.winfo_toplevel()
        focused = toplevel.focus_displayof()
        if focused is None or focused.winfo_toplevel() != toplevel:
            return

        bbox = self.canvas.bbox("all")
        if not bbox:
            return

        content_height = bbox[3] - bbox[1]
        try:
            ch = self.canvas.winfo_height()
        except Exception:
            ch = 0
        if content_height <= ch:
            return  # nothing to scroll

        # event.num is for Button-4/5 on X11, event.delta used on Windows/macOS
        num = getattr(event, "num", None)
        delta_attr = getattr(event, "delta", 0)
        if num == 4:
            delta = -1
        elif num == 5:
            delta = 1
        else:
            # normalize typical MouseWheel delta (120 per notch on Windows)
            try:
                delta = -int(delta_attr) // 120
            except Exception:
                delta = 0

        if delta:
            self.canvas.yview_scroll(int(delta), "units")

class NameChooser(tk.Toplevel):
    """
    Pop-up to choose Name, Upgrade, and Type components from mutable lists.
    Supports adding names (plus) and removing names (trash).
    - Displays truncated names (DISPLAY_NAME_MAX) in buttons.
    - Preview (Selected:) truncated to PREVIEW_NAME_MAX.
    - Fixed window size with internal vertical scrollbars.
    - Edit mode supports dragging items to reorder and shows Add/Trash controls in the list.
    """
    def __init__(self, parent, list_a: List[str], list_b: List[str], list_type: List[str],
                 initial_name: Optional[str] = None):
        super().__init__(parent)
        self.title("Choose Name (Name - Upgrade - Type)")
        self.transient(parent)
        # fixed window size
        win_w = 840
        win_h = 400

        # center in a cross-platform way
        self.geometry(f"{win_w}x{win_h}")
        self.resizable(False, False)
        _center_window(self, win_w, win_h)
        self.grab_set()

        # references to shared lists (mutated in-place)
        self.list_a = list_a
        self.list_b = list_b
        self.list_type = list_type

        self.selected_a: Optional[str] = None
        self.selected_b: Optional[str] = None
        self.selected_type: Optional[str] = None
        self.result: Optional[str] = None
        if initial_name:
            name_parts = str(initial_name).split(" - ", 2)
            self.selected_a = name_parts[0].strip()
            if len(name_parts) >= 2:
                self.selected_b = name_parts[1].strip()
                for timer_type in self.list_type:
                    suffix = f" ({timer_type})"
                    if self.selected_b.endswith(suffix):
                        self.selected_b = self.selected_b[:-len(suffix)].strip()
                        self.selected_type = timer_type
                        break
            if len(name_parts) == 3:
                self.selected_type = name_parts[2].strip()

        # removal mode flags (when True show per-item trash)
        self.remove_mode_a = False
        self.remove_mode_b = False
        self.remove_mode_type = False

        # drag state
        self._drag_data: Optional[dict] = None  # {'which': 'a'|'b'|'type', 'index': int}

        frame = ttk.Frame(self, padding=8)
        frame.pack(fill="both", expand=True)

        a_frame = ttk.LabelFrame(frame, text="Name", width=260, height=260)
        a_frame.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")
        b_frame = ttk.LabelFrame(frame, text="Upgrade", width=260, height=260)
        b_frame.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")
        type_frame = ttk.LabelFrame(frame, text="Type", width=260, height=260)
        type_frame.grid(row=0, column=2, padx=6, pady=6, sticky="nsew")

        # Make grid expand correctly
        for column in range(3):
            frame.columnconfigure(column, weight=1)
        frame.rowconfigure(0, weight=1)

        # Scrollable areas (fixed height) inside each label frame.
        # Use a height that comfortably shows ~10 items depending on font.
        scroll_height = 200
        self.a_scroll = _ScrollableNames(a_frame, height=scroll_height)
        self.a_scroll.pack(fill="both", expand=True, padx=4, pady=(4, 2))
        self.b_scroll = _ScrollableNames(b_frame, height=scroll_height)
        self.b_scroll.pack(fill="both", expand=True, padx=4, pady=(4, 2))
        self.type_scroll = _ScrollableNames(type_frame, height=scroll_height)
        self.type_scroll.pack(fill="both", expand=True, padx=4, pady=(4, 2))

        # selection label and controls
        sel_frame = ttk.Frame(frame)
        sel_frame.grid(row=1, column=0, columnspan=3, pady=(8, 0), sticky="ew")
        sel_frame.columnconfigure(0, weight=1)
        self.sel_lbl = ttk.Label(sel_frame, text="Selected: (none)", anchor="w")
        self.sel_lbl.grid(row=0, column=0, sticky="w", padx=(2,8))
        ok_btn = ttk.Button(sel_frame, text="OK", command=self._on_ok)
        ok_btn.grid(row=0, column=1, sticky="e", padx=4)
        cancel_btn = ttk.Button(sel_frame, text="Cancel", command=self._on_cancel)
        cancel_btn.grid(row=0, column=2, sticky="e", padx=4)

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # initial build
        self._rebuild_a()
        self._rebuild_b()
        self._rebuild_type()
        # ensure the selectable preview uses truncation
        self._update_label()
        apply_classic_widget_colors(self, _parent_dark_mode(parent))

    # ---- add/remove handlers ----
    def _add_name_a(self):
        dlg = AddNameDialog(self, title="Add Name")
        if getattr(dlg, "result_text", None):
            self.list_a.append(dlg.result_text)
            self._rebuild_a()

    def _add_name_b(self):
        dlg = AddNameDialog(self, title="Add Upgrade")
        if getattr(dlg, "result_text", None):
            self.list_b.append(dlg.result_text)
            self._rebuild_b()

    def _toggle_remove_a(self):
        self.remove_mode_a = not self.remove_mode_a
        # rebuild so per-item trash appears/disappears
        self._rebuild_a()

    def _toggle_remove_b(self):
        self.remove_mode_b = not self.remove_mode_b
        self._rebuild_b()

    def _add_name_type(self):
        dlg = AddNameDialog(self, title="Add Type")
        if getattr(dlg, "result_text", None):
            self.list_type.append(dlg.result_text)
            self._rebuild_type()

    def _toggle_remove_type(self):
        self.remove_mode_type = not self.remove_mode_type
        self._rebuild_type()

    def _rebuild_a(self):
        # clear
        for w in self.a_scroll.inner.winfo_children():
            w.destroy()

        # header with Add / Edit toggle inside the list (so controls are in main list)
        hdr = ttk.Frame(self.a_scroll.inner)
        hdr.pack(fill="x", pady=(0,4))
        ttk.Label(hdr, text="Items:").pack(side="left")
        ttk.Button(hdr, text="+", width=3, command=self._add_name_a).pack(side="right", padx=(4,0))
        ttk.Button(hdr, text="🗑", width=3, command=self._toggle_remove_a).pack(side="right")
        self.a_scroll._bind_mousewheel_tree(hdr)

        # recreate buttons, truncating visible text, with drag handle and optional trash
        for i, a in enumerate(self.list_a):
            display = _shorten(a, DISPLAY_NAME_MAX)
            item_fr = ttk.Frame(self.a_scroll.inner)
            item_fr.pack(fill="x", pady=2)

            # drag handle
            handle = ttk.Label(item_fr, text="≡", width=2, anchor="center", cursor="hand2")
            handle.pack(side="left", padx=(0,4))
            # bind drag events (press/release)
            handle.bind("<ButtonPress-1>", lambda e, which="a", idx=i: self._start_drag(e, which, idx))
            handle.bind("<ButtonRelease-1>", lambda e, which="a", idx=i: self._end_drag(e, which, idx))
            # optional motion for visual effect (not required)
            handle.bind("<B1-Motion>", lambda e: None)

            btn = ttk.Button(item_fr, text=display, command=lambda v=a: self._on_click_a(v))
            btn.pack(side="left", fill="x", expand=True)

            if self.remove_mode_a:
                trash = ttk.Button(item_fr, text="🗑", width=3, command=lambda v=a: self._confirm_remove_a(v))
                trash.pack(side="right", padx=(4,0))
            self.a_scroll._bind_mousewheel_tree(item_fr)

        # if previously selected was removed externally, clear it
        if self.selected_a is not None and self.selected_a not in self.list_a:
            self.selected_a = None
            self._update_label()

    def _rebuild_b(self):
        for w in self.b_scroll.inner.winfo_children():
            w.destroy()

        hdr = ttk.Frame(self.b_scroll.inner)
        hdr.pack(fill="x", pady=(0,4))
        ttk.Label(hdr, text="Items:").pack(side="left")
        ttk.Button(hdr, text="+", width=3, command=self._add_name_b).pack(side="right", padx=(4,0))
        ttk.Button(hdr, text="🗑", width=3, command=self._toggle_remove_b).pack(side="right")
        self.b_scroll._bind_mousewheel_tree(hdr)

        for i, b in enumerate(self.list_b):
            display = _shorten(b, DISPLAY_NAME_MAX)
            item_fr = ttk.Frame(self.b_scroll.inner)
            item_fr.pack(fill="x", pady=2)

            handle = ttk.Label(item_fr, text="≡", width=2, anchor="center", cursor="hand2")
            handle.pack(side="left", padx=(0,4))
            handle.bind("<ButtonPress-1>", lambda e, which="b", idx=i: self._start_drag(e, which, idx))
            handle.bind("<ButtonRelease-1>", lambda e, which="b", idx=i: self._end_drag(e, which, idx))
            handle.bind("<B1-Motion>", lambda e: None)

            btn = ttk.Button(item_fr, text=display, command=lambda v=b: self._on_click_b(v))
            btn.pack(side="left", fill="x", expand=True)

            if self.remove_mode_b:
                trash = ttk.Button(item_fr, text="🗑", width=3, command=lambda v=b: self._confirm_remove_b(v))
                trash.pack(side="right", padx=(4,0))
            self.b_scroll._bind_mousewheel_tree(item_fr)

        if self.selected_b is not None and self.selected_b not in self.list_b:
            self.selected_b = None
            self._update_label()

    def _rebuild_type(self):
        for widget in self.type_scroll.inner.winfo_children():
            widget.destroy()

        header = ttk.Frame(self.type_scroll.inner)
        header.pack(fill="x", pady=(0, 4))
        ttk.Label(header, text="Items:").pack(side="left")
        ttk.Button(header, text="+", width=3, command=self._add_name_type).pack(side="right", padx=(4, 0))
        ttk.Button(header, text="🗑", width=3, command=self._toggle_remove_type).pack(side="right")
        self.type_scroll._bind_mousewheel_tree(header)

        for index, value in enumerate(self.list_type):
            item_frame = ttk.Frame(self.type_scroll.inner)
            item_frame.pack(fill="x", pady=2)
            handle = ttk.Label(item_frame, text="≡", width=2, anchor="center", cursor="hand2")
            handle.pack(side="left", padx=(0, 4))
            handle.bind("<ButtonPress-1>", lambda event, idx=index: self._start_drag(event, "type", idx))
            handle.bind("<ButtonRelease-1>", lambda event, idx=index: self._end_drag(event, "type", idx))
            handle.bind("<B1-Motion>", lambda event: None)
            button = ttk.Button(item_frame, text=_shorten(value, DISPLAY_NAME_MAX),
                                command=lambda selected=value: self._on_click_type(selected))
            button.pack(side="left", fill="x", expand=True)
            if self.remove_mode_type:
                ttk.Button(item_frame, text="🗑", width=3,
                           command=lambda selected=value: self._confirm_remove_type(selected)).pack(side="right", padx=(4, 0))
            self.type_scroll._bind_mousewheel_tree(item_frame)

        if self.selected_type is not None and self.selected_type not in self.list_type:
            self.selected_type = None
            self._update_label()

    def _confirm_remove_a(self, val: str):
        # keep confirmation for list changes
        if messagebox.askyesno("Confirm remove", f"Remove '{val}' from the Name list?"):
            try:
                self.list_a.remove(val)
            except ValueError:
                pass
            self.remove_mode_a = False
            self._rebuild_a()

    def _confirm_remove_b(self, val: str):
        if messagebox.askyesno("Confirm remove", f"Remove '{val}' from the Upgrade list?"):
            try:
                self.list_b.remove(val)
            except ValueError:
                pass
            self.remove_mode_b = False
            self._rebuild_b()

    def _confirm_remove_type(self, val: str):
        if messagebox.askyesno("Confirm remove", f"Remove '{val}' from the Type list?"):
            try:
                self.list_type.remove(val)
            except ValueError:
                pass
            self.remove_mode_type = False
            self._rebuild_type()

    def _on_click_a(self, val: str):
        # normal: select (store full value)
        self.selected_a = val
        self._update_label()

    def _on_click_b(self, val: str):
        self.selected_b = val
        self._update_label()

    def _on_click_type(self, val: str):
        self.selected_type = val
        self._update_label()

    def _update_label(self):
        name = self.selected_a or "(none)"
        upgrade = self.selected_b or "(none)"
        timer_type = self.selected_type or "(none)"
        combined = f"{name} - {upgrade} - {timer_type}"
        self.sel_lbl.config(text=f"Selected: {_shorten(combined, PREVIEW_NAME_MAX)}")

    def _on_ok(self):
        if not self.selected_a or not self.selected_b or not self.selected_type:
            messagebox.showwarning("Incomplete", "Please select a Name, Upgrade, and Type before pressing OK.")
            return
        self.result = f"{self.selected_a} - {self.selected_b} - {self.selected_type}"
        self.grab_release()
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()

    # ---- drag helpers ----
    def _start_drag(self, event, which: str, index: int):
        # store which list and original index
        self._drag_data = {"which": which, "index": index}
        # give visual feedback by setting the cursor (optional)
        try:
            event.widget.configure(cursor="fleur")
        except Exception:
            pass

    def _end_drag(self, event, which: str, index: int):
        if not self._drag_data:
            return
        src = self._drag_data
        # identify target index by y position within the appropriate inner frame
        if src["which"] == "a":
            inner = self.a_scroll.inner
            list_ref = self.list_a
        elif src["which"] == "b":
            inner = self.b_scroll.inner
            list_ref = self.list_b
        else:
            inner = self.type_scroll.inner
            list_ref = self.list_type
        items = [w for w in inner.winfo_children() if isinstance(w, ttk.Frame)][1:]

        # pointer y relative to inner
        try:
            y = inner.winfo_pointery() - inner.winfo_rooty()
        except Exception:
            y = 0

        target_idx = len(items)  # default append
        for idx, fr in enumerate(items):
            fr_top = fr.winfo_y()
            fr_h = fr.winfo_height() or 1
            mid = fr_top + fr_h // 2
            if y < mid:
                target_idx = idx
                break

        old_idx = src["index"]
        # normalize indices (if header present the items list index matches logical index)
        if old_idx < 0 or old_idx >= len(list_ref):
            self._drag_data = None
            return

        # no-op if same position
        if target_idx == old_idx or target_idx == old_idx + 1:
            # still rebuild to normalize UI
            self._drag_data = None
            self._rebuild_list(src["which"])
            return

        try:
            val = list_ref.pop(old_idx)
            if target_idx > len(list_ref):
                target_idx = len(list_ref)
            list_ref.insert(target_idx, val)
        except Exception:
            pass

        self._drag_data = None
        self._rebuild_list(src["which"])

    def _rebuild_list(self, which: str):
        if which == "a":
            self._rebuild_a()
        elif which == "b":
            self._rebuild_b()
        else:
            self._rebuild_type()

class AddTimerDialog(tk.Toplevel):
    """
    Dialog to create a new timer:
     - Name: built from current app lists via NameChooser
     - Timer: D HH:MM:SS via four numeric entries
     - Note: optional plain text
    """
    def __init__(self, parent, on_add_callback: Callable[[str, int, str], None],
                 list_a: List[str], list_b: List[str], list_type: List[str]):
        super().__init__(parent)
        self.title("Add Timer")
        self.transient(parent)
        self.resizable(False, False)
        self.grab_set()

        self.on_add_callback = on_add_callback
        self.chosen_name: Optional[str] = None
        self.list_a = list_a
        self.list_b = list_b
        self.list_type = list_type

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)

        # Name row with button to open NameChooser
        name_row = ttk.Frame(frame)
        name_row.pack(fill="x", pady=4)
        ttk.Label(name_row, text="Name:", width=8).pack(side="left")
        self.name_var = tk.StringVar(value="(none)")
        ttk.Label(name_row, textvariable=self.name_var).pack(side="left", padx=(4, 8))
        choose_btn = ttk.Button(name_row, text="Choose Name...", command=self._open_name_chooser)
        choose_btn.pack(side="right")

        # Timer input D HH:MM:SS
        time_row = ttk.Frame(frame)
        time_row.pack(fill="x", pady=4)
        ttk.Label(time_row, text="Timer (D HH:MM:SS):", width=18).pack(side="left")
        self.dd = tk.StringVar(value="0")
        self.hh = tk.StringVar(value="00")
        self.mm = tk.StringVar(value="00")
        self.ss = tk.StringVar(value="00")

        time_inputs = ttk.Frame(time_row)
        time_inputs.pack(side="right")
        dd_entry = ttk.Entry(time_inputs, width=4, textvariable=self.dd, justify="center")
        hh_entry = ttk.Entry(time_inputs, width=4, textvariable=self.hh, justify="center")
        mm_entry = ttk.Entry(time_inputs, width=4, textvariable=self.mm, justify="center")
        ss_entry = ttk.Entry(time_inputs, width=4, textvariable=self.ss, justify="center")

        # keep references for keyboard navigation & selection
        self.dd_entry = dd_entry
        self.hh_entry = hh_entry
        self.mm_entry = mm_entry
        self.ss_entry = ss_entry

        dd_entry.pack(side="left", padx=(0, 4))
        ttk.Label(time_inputs, text="d").pack(side="left")
        hh_entry.pack(side="left", padx=(4, 4))
        ttk.Label(time_inputs, text=":").pack(side="left")
        mm_entry.pack(side="left", padx=4)
        ttk.Label(time_inputs, text=":").pack(side="left")
        ss_entry.pack(side="left", padx=(4, 0))

        note_frame = ttk.LabelFrame(frame, text="Note")
        note_frame.pack(fill="both", expand=True, pady=4)
        self.note_text = tk.Text(note_frame, width=40, height=4, wrap="word")
        self.note_text.pack(fill="both", expand=True, padx=4, pady=4)

        # Bind focus/click to select all and left/right arrow navigation
        for w in (self.dd_entry, self.hh_entry, self.mm_entry, self.ss_entry):
            w.bind("<FocusIn>", lambda e: e.widget.select_range(0, "end"))
            # ensure click selects all (after focus)
            w.bind("<Button-1>", lambda e: (e.widget.after(1, lambda: e.widget.focus_set()),
                                            e.widget.after(2, lambda: e.widget.select_range(0, "end"))))
        # left/right navigation
        self.dd_entry.bind("<Right>", lambda e: (self.hh_entry.focus_set(), self.hh_entry.select_range(0, "end")))
        self.hh_entry.bind("<Left>", lambda e: (self.dd_entry.focus_set(), self.dd_entry.select_range(0, "end")))
        self.hh_entry.bind("<Right>", lambda e: (self.mm_entry.focus_set(), self.mm_entry.select_range(0, "end")))
        self.mm_entry.bind("<Left>", lambda e: (self.hh_entry.focus_set(), self.hh_entry.select_range(0, "end")))
        self.mm_entry.bind("<Right>", lambda e: (self.ss_entry.focus_set(), self.ss_entry.select_range(0, "end")))
        self.ss_entry.bind("<Left>", lambda e: (self.mm_entry.focus_set(), self.mm_entry.select_range(0, "end")))

        # Actions -- swap positions so Cancel is rightmost (per requested change)
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(8, 0))
        # pack Cancel first on the right, then Add to its left
        cancel_btn = ttk.Button(actions, text="Cancel", command=self._on_cancel)
        cancel_btn.pack(side="right")
        add_btn = ttk.Button(actions, text="Add Timer", command=self._on_add)
        add_btn.pack(side="right", padx=4)

        # Window size & center
        self.update_idletasks()
        width  = self.winfo_width()
        height = self.winfo_height()
        self.geometry(f"{width}x{height}")
        _center_window(self, width, height)

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.bind("<Return>", lambda event: self._on_add())
        apply_classic_widget_colors(self, _parent_dark_mode(parent))

    def _open_name_chooser(self):
        chooser = NameChooser(self, self.list_a, self.list_b, self.list_type)
        self.wait_window(chooser)
        if getattr(chooser, "result", None):
            self.chosen_name = chooser.result
            self.name_var.set(_shorten(self.chosen_name, PREVIEW_NAME_MAX))

    def _parse_dhms(self) -> Optional[int]:
        try:
            dd = int(self.dd.get())
            hh = int(self.hh.get())
            mm = int(self.mm.get())
            ss = int(self.ss.get())
        except ValueError:
            return None
        if dd < 0 or hh < 0 or mm < 0 or ss < 0:
            return None
        if hh >= 24 or mm >= 60 or ss >= 60:
            return None
        return dd * 86400 + hh * 3600 + mm * 60 + ss

    def _on_add(self):
        if not self.chosen_name:
            messagebox.showwarning("Missing name", "Please choose a Name, Upgrade, and Type.")
            return
        secs = self._parse_dhms()
        if secs is None or secs <= 0:
            messagebox.showwarning("Invalid time", "Please enter a valid D HH:MM:SS (positive, HH in 0-23, MM and SS in 0-59).")
            return
        note = self.note_text.get("1.0", "end-1c")
        try:
            if callable(self.on_add_callback):
                self.on_add_callback(self.chosen_name, secs, note)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add timer: {e}")
        finally:
            self.grab_release()
            self.destroy()

    def _on_cancel(self):
        self.grab_release()
        self.destroy()

class EditTimerDialog(tk.Toplevel):
    """
    Dialog to edit an existing timer's name and remaining time.
    - Name: choose via NameChooser (shared lists) and Save Name (separate button)
    - Remaining time: DD:HH:MM:SS entries and Save Time (separate button)
    - Disabled state: toggle with the Disable timer checkbox
    """
    def __init__(self, parent, timer: Any, list_a: List[str], list_b: List[str], list_type: List[str],
                 on_update: Optional[Callable[[], None]] = None,
                 on_resource_update: Optional[Callable[[str], None]] = None):
        """
        timer: object with attributes `name` and `end_ts` and a method `remaining_seconds()` expected.
        list_a/list_b/list_type: name pools passed to NameChooser so modifications persist.
        on_update: optional callback invoked after a successful save (name or time).
        on_resource_update: optional resource-specific callback.
        """
        super().__init__(parent)
        self.title("Edit Timer")
        self.transient(parent)
        self.resizable(False, False)
        self.grab_set()

        self.timer = timer
        self.list_a = list_a
        self.list_b = list_b
        self.list_type = list_type
        self.on_update = on_update
        self.on_resource_update = on_resource_update

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)

        # --- Name section ---
        name_frame = ttk.LabelFrame(frame, text="Name")
        name_frame.pack(fill="x", pady=(0, 8))

        self.current_name_var = tk.StringVar(value=str(getattr(self.timer, "name", "(none)")))
        ttk.Label(name_frame, text="Current:").grid(row=0, column=0, sticky="w", padx=6, pady=(6,2))
        ttk.Label(name_frame, textvariable=self.current_name_var).grid(row=0, column=1, sticky="w", padx=6, pady=(6,2))

        choose_btn = ttk.Button(name_frame, text="Choose Name...", command=self._open_name_chooser)
        choose_btn.grid(row=1, column=0, sticky="w", padx=6, pady=(2,6))

        self.chosen_name_var = tk.StringVar(value=str(getattr(self.timer, "name", "")))
        ttk.Label(name_frame, textvariable=self.chosen_name_var).grid(row=1, column=1, sticky="w", padx=6, pady=(2,6))

        save_name_btn = ttk.Button(name_frame, text="Save Name", command=self._save_name)
        save_name_btn.grid(row=2, column=0, columnspan=2, sticky="e", padx=6, pady=(0,6))

        # --- Remaining time section ---
        time_frame = ttk.LabelFrame(frame, text="Remaining Time (D HH:MM:SS)")
        time_frame.pack(fill="x", pady=(0, 8))

        rem = getattr(self.timer, "remaining_seconds", lambda: 0)()
        days, rem = divmod(int(rem), 86400)
        hh, rem = divmod(rem, 3600)
        mm, ss = divmod(rem, 60)

        self.dd_var = tk.StringVar(value=f"{days}")
        self.hh_var = tk.StringVar(value=f"{hh:02}")
        self.mm_var = tk.StringVar(value=f"{mm:02}")
        self.ss_var = tk.StringVar(value=f"{ss:02}")

        dd_entry = ttk.Entry(time_frame, width=4, textvariable=self.dd_var, justify="center")
        hh_entry = ttk.Entry(time_frame, width=4, textvariable=self.hh_var, justify="center")
        mm_entry = ttk.Entry(time_frame, width=4, textvariable=self.mm_var, justify="center")
        ss_entry = ttk.Entry(time_frame, width=4, textvariable=self.ss_var, justify="center")

        dd_entry.grid(row=0, column=0, padx=(6,2), pady=6)
        ttk.Label(time_frame, text="d").grid(row=0, column=1, padx=(0,6), pady=6)
        hh_entry.grid(row=0, column=2, padx=(0,2), pady=6)
        ttk.Label(time_frame, text=":").grid(row=0, column=3, padx=0, pady=6)
        mm_entry.grid(row=0, column=4, padx=2, pady=6)
        ttk.Label(time_frame, text=":").grid(row=0, column=5, padx=0, pady=6)
        ss_entry.grid(row=0, column=6, padx=(2,6), pady=6)

        ttk.Label(time_frame, text="Subtract (HH:MM:SS) x").grid(
            row=1, column=0, columnspan=2, sticky="w", padx=(6,2), pady=6
        )
        self.subtract_hh_var = tk.StringVar(value="00")
        self.subtract_mm_var = tk.StringVar(value="00")
        self.subtract_ss_var = tk.StringVar(value="00")
        self.subtract_multiplier_var = tk.StringVar(value="1")
        ttk.Entry(time_frame, width=4, textvariable=self.subtract_hh_var, justify="center").grid(
            row=1, column=2, padx=(0,2), pady=6
        )
        ttk.Label(time_frame, text=":").grid(row=1, column=3, padx=0, pady=6)
        ttk.Entry(time_frame, width=4, textvariable=self.subtract_mm_var, justify="center").grid(
            row=1, column=4, padx=2, pady=6
        )
        ttk.Label(time_frame, text=":").grid(row=1, column=5, padx=0, pady=6)
        ttk.Entry(time_frame, width=4, textvariable=self.subtract_ss_var, justify="center").grid(
            row=1, column=6, padx=(2,6), pady=6
        )
        ttk.Label(time_frame, text="Multiplier:").grid(row=2, column=0, sticky="w", padx=6, pady=(0,6))
        ttk.Entry(time_frame, width=6, textvariable=self.subtract_multiplier_var, justify="center").grid(
            row=2, column=1, padx=2, pady=(0,6)
        )

        self.time_status_label = ttk.Label(time_frame, text="", style="InvalidTime.TLabel")
        self.time_status_label.grid(row=3, column=0, columnspan=7, sticky="w", padx=6, pady=(0,4))
        ttk.Style(self).configure("InvalidTime.TLabel", foreground="red")

        self.save_time_btn = ttk.Button(time_frame, text="Save Time", command=self._save_time)
        self.save_time_btn.grid(row=4, column=0, columnspan=7, sticky="e", padx=6, pady=(0,6))
        for variable in (
            self.dd_var,
            self.hh_var,
            self.mm_var,
            self.ss_var,
            self.subtract_hh_var,
            self.subtract_mm_var,
            self.subtract_ss_var,
            self.subtract_multiplier_var,
        ):
            variable.trace_add("write", self._update_time_preview)
        self._update_time_preview()

        resource_frame = ttk.LabelFrame(frame, text="Resource")
        resource_frame.pack(fill="x", pady=(0, 8))
        resource = str(getattr(self.timer, "resource", "Empty"))
        if resource not in RESOURCE_OPTIONS:
            resource = "Empty"
        self.resource_var = tk.StringVar(value=RESOURCE_LABELS[resource])
        resource_combo = ttk.Combobox(
            resource_frame,
            state="readonly",
            values=RESOURCE_DISPLAY_OPTIONS,
            textvariable=self.resource_var,
            width=12
        )
        resource_combo.pack(anchor="w", padx=6, pady=6)
        resource_combo.bind("<<ComboboxSelected>>", lambda event: self._save_resource())

        note_frame = ttk.LabelFrame(frame, text="Note")
        note_frame.pack(fill="both", expand=True, pady=(0, 8))
        self.note_text = tk.Text(note_frame, width=40, height=4, wrap="word")
        self.note_text.pack(fill="both", expand=True, padx=4, pady=4)
        self.note_text.insert("1.0", str(getattr(self.timer, "note", "")))
        save_note_btn = ttk.Button(note_frame, text="Save Note", command=self._save_note)
        save_note_btn.pack(anchor="e", padx=6, pady=(0, 6))

        self.disabled_var = tk.BooleanVar(value=bool(getattr(self.timer, "disabled", False)))
        disabled_check = ttk.Checkbutton(
            frame,
            text="Disable timer",
            variable=self.disabled_var,
            command=self._save_disabled
        )
        disabled_check.pack(anchor="w", padx=6, pady=(0, 8))

        # Close / Cancel
        close_btn = ttk.Button(frame, text="Close", command=self._on_close)
        close_btn.pack(anchor="e", pady=(0,4), padx=6)

        # center this dialog
        self.update_idletasks()
        _center_window(self)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Return>", lambda event: self._save_time())
        apply_classic_widget_colors(self, _parent_dark_mode(parent))

    def _open_name_chooser(self):
        chooser = NameChooser(
            self, self.list_a, self.list_b, self.list_type,
            initial_name=str(getattr(self.timer, "name", ""))
        )
        self.wait_window(chooser)
        if getattr(chooser, "result", None):
            self.chosen_name_var.set(chooser.result)

    def _save_name(self):
        new_name = self.chosen_name_var.get().strip()
        if not new_name:
            messagebox.showwarning("No name", "Choose a name first using Choose Name...")
            return
        # apply change to timer object without extra confirmation pop-up
        try:
            setattr(self.timer, "name", new_name)
            self.current_name_var.set(new_name)
            if self.on_update:
                self.on_update()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save name: {e}")

    def _calculate_adjusted_time(self):
        try:
            dd = int(self.dd_var.get())
            hh = int(self.hh_var.get())
            mm = int(self.mm_var.get())
            ss = int(self.ss_var.get())
            subtract_hh = int(self.subtract_hh_var.get())
            subtract_mm = int(self.subtract_mm_var.get())
            subtract_ss = int(self.subtract_ss_var.get())
            multiplier = int(self.subtract_multiplier_var.get())
        except ValueError:
            return None, "All time values and the multiplier must be integers."

        if min(dd, hh, mm, ss, subtract_hh, subtract_mm, subtract_ss, multiplier) < 0:
            return None, "Values and multiplier must be non-negative."
        if hh >= 24 or subtract_hh >= 24:
            return None, "Hours must be in 0-23. Use the days field for larger durations."
        if mm >= 60 or ss >= 60 or subtract_mm >= 60 or subtract_ss >= 60:
            return None, "Minutes and seconds must be in 0-59."

        total = dd * 86400 + hh * 3600 + mm * 60 + ss
        subtraction = (subtract_hh * 3600 + subtract_mm * 60 + subtract_ss) * multiplier
        return total - subtraction, None

    def _update_time_preview(self, *_):
        total, error = self._calculate_adjusted_time()
        if error:
            self.time_status_label.configure(text=error)
            self.save_time_btn.configure(state="disabled")
        elif total <= 0:
            self.time_status_label.configure(text="Total time must be greater than 0.")
            self.save_time_btn.configure(state="disabled")
        else:
            self.time_status_label.configure(text="")
            self.save_time_btn.configure(state="normal")

    def _save_time(self):
        total, error = self._calculate_adjusted_time()
        if error:
            messagebox.showwarning("Invalid time", error)
            return
        if total <= 0:
            self._update_time_preview()
            return
        try:
            # set end timestamp relative to now without showing a confirmation pop-up
            setattr(self.timer, "end_ts", int(time.time()) + total)
            if self.on_update:
                self.on_update()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save time: {e}")

    def _save_resource(self):
        try:
            resource = RESOURCE_VALUES_BY_LABEL[self.resource_var.get()]
            setattr(self.timer, "resource", resource)
            if self.on_resource_update:
                self.on_resource_update(resource)
            elif self.on_update:
                self.on_update()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save resource: {e}")

    def _save_note(self):
        try:
            setattr(self.timer, "note", self.note_text.get("1.0", "end-1c"))
            if self.on_update:
                self.on_update()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save note: {e}")

    def _save_disabled(self):
        try:
            setattr(self.timer, "disabled", bool(self.disabled_var.get()))
            if self.on_update:
                self.on_update()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update timer state: {e}")

    def _on_close(self):
        self.grab_release()
        self.destroy()