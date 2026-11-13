#!/usr/bin/env python3
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont
from typing import List, Optional

from Timer import (
    AddTimerDialog,
    EditTimerDialog,
    RESOURCE_LABELS,
    RESOURCE_OPTIONS,
    apply_classic_widget_colors,
)  # dialogs live in Timer.py
import Save

class CountdownTimer:
    def __init__(self, name: str, seconds: int, disabled: bool = False, note: str = "", resource: str = "Empty"):
        """
        name: display name of the timer
        seconds: initial countdown length in seconds
        disabled: whether the timer is disabled
        note: plain-text note associated with the timer
        resource: resource level, one of Empty, Half, or Full
        """
        self.name = name
        self.disabled = bool(disabled)
        self.note = str(note)
        self.resource = resource if resource in RESOURCE_OPTIONS else "Empty"
        self.start_ts = int(time.time())
        self.end_ts = self.start_ts + int(seconds)

    def remaining_seconds(self) -> int:
        return max(0, int(self.end_ts - int(time.time())))

    def is_finished(self) -> bool:
        return not self.disabled and self.remaining_seconds() == 0

    def remaining_str(self) -> str:
        if self.disabled:
            return "--:--:--"
        remaining = self.remaining_seconds()
        if remaining >= 86400:
            days, remainder = divmod(remaining, 86400)
            hours = remainder // 3600
            return f"{days}d{hours}h"
        if remaining >= 3600:
            hours, remainder = divmod(remaining, 3600)
            minutes = remainder // 60
            return f"{hours}h{minutes}m"
        minutes, remainder = divmod(remaining, 60)
        return f"{minutes}m{remainder}s"

def unix_to_local_str(unix_ts: int) -> str:
    """
    Convert an integer UNIX timestamp (seconds) to a local datetime string.
    Format: MM-DD HH:MM
    """
    return datetime.fromtimestamp(int(unix_ts)).strftime("%m-%d %H:%M")

class ScrollableFrame(ttk.Frame):
    """A vertical scrollable frame using a canvas."""
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.vscroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        # Use a classic tk.Frame so cget("background") is available
        self.inner = tk.Frame(self.canvas)

        self.inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vscroll.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.vscroll.pack(side="right", fill="y")

        # update scrollregion when inner frame changes size
        self.inner.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self._bind_mousewheel_tree(self.canvas)

    def _on_frame_configure(self, event=None):
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass

    def _on_canvas_configure(self, event):
        # make inner frame the same width as canvas
        canvas_width = event.width
        try:
            self.canvas.itemconfigure(self.inner_id, width=canvas_width)
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

        # cross-platform scrolling
        num = getattr(event, "num", None)
        delta_attr = getattr(event, "delta", 0)
        if num == 4:
            delta = -1
        elif num == 5:
            delta = 1
        else:
            try:
                delta = -1 * (int(delta_attr) // 120)
            except Exception:
                delta = 0

        if not self.canvas.winfo_exists():
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
            return

        if delta:
            self.canvas.yview_scroll(int(delta), "units")

class SimpleCountdownApp:
    UPDATE_INTERVAL_MS = 1000
    LOW_POWER_BATCH_COUNT = 10
    BUTTON_FONT = ("Courier", 10)

    def __init__(self, root: tk.Tk, timers: List[CountdownTimer],
                 visible_rows: int = 10,
                 name_list_a: Optional[List[str]] = None,
                 name_list_b: Optional[List[str]] = None,
                 name_list_type: Optional[List[str]] = None):
        self.root = root
        self.root.title("Simple Countdown List")
        self.timers = timers
        self.visible_rows = visible_rows
        self._dark_mode = False
        self._timer_text_font = tkfont.Font(root=root, font=self.BUTTON_FONT)
        self._light_root_background = self.root.cget("background")
        self.root._dark_mode = False
        self.style = ttk.Style(self.root)
        self._light_theme = self.style.theme_use()

        # Persistent Name, Upgrade, and Type lists are shared with dialogs in Timer.py.
        if name_list_a is not None:
            self.name_list_a = name_list_a
        else:
            self.name_list_a = ["Alpha", "Beta", "Gamma", "Delta", "Omega"]

        if name_list_b is not None:
            self.name_list_b = name_list_b
        else:
            self.name_list_b = ["One", "Two", "Three", "Four", "Five"]

        self.name_list_type = name_list_type if name_list_type is not None else []

        # registry of child windows opened by the app (Add / Edit dialogs)
        self._child_windows = set()

        # edit/remove mode for main list
        self.edit_mode = False
        self.remove_mode_main = False

        # current filters (None means no filter)
        self.filter_a: Optional[str] = None
        self.filter_b: Optional[str] = None
        self.filter_type: Optional[str] = None

        # sort_state cycles: None -> "asc" -> "desc" -> None
        self.sort_state: Optional[str] = None

        self._low_power_var = tk.BooleanVar(value=False)
        self._dark_mode_var = tk.BooleanVar(value=False)
        self._update_batch_index = 0

        # drag state for main list
        self._drag_data_main: Optional[dict] = None  # {'index': int}

        self.main_frame = ttk.Frame(root, padding=8)
        self.main_frame.pack(fill="both", expand=True)

        self._create_filter_controls()

        # Keep the column labels in the scrollable timer list, immediately above its rows.
        self.scrollable = ScrollableFrame(self.main_frame)
        self.scrollable.pack(fill="both", expand=True)
        self.header = ttk.Frame(self.scrollable.inner)
        self.header.pack(fill="x", pady=(0, 6))
        self._header_handle_spacer = ttk.Label(self.header, text="", width=2, font=self.BUTTON_FONT)
        self._header_handle_spacer.pack(side="left", padx=(0, 4))
        self._header_label = ttk.Label(self.header, font=self.BUTTON_FONT)
        self._header_label.pack(side="left", anchor="w")
        self._displayed_name_width: Optional[int] = None
        self._update_header_label()

        # arrow indicators (hidden unless needed) - placed inside the canvas so they float above content
        self._top_arrow = tk.Label(self.scrollable.canvas, text="▲", bg="lightyellow", bd=1, relief="solid")
        self._bottom_arrow = tk.Label(self.scrollable.canvas, text="▼", bg="lightyellow", bd=1, relief="solid")

        # store row widgets as list of tuples (timer, frame, text_button)
        self._row_widgets: List[tuple] = []
        for idx, t in enumerate(self.timers):
            self._add_timer_row(idx, t)

        # single floating Edit button bottom-right (toggles edit mode)
        self.edit_btn = tk.Button(self.root, text="Edit", font=("Segoe UI", 12), width=6, height=1,
                                  command=self._toggle_edit_mode)
        # place it
        self._place_floating_buttons()
        apply_classic_widget_colors(self.root, False, self._timer_row_frames())

        # Refresh row formatting as the timer viewport changes during interactive resizing.
        self.scrollable.canvas.bind("<Configure>", self._on_timer_viewport_configure, add="+")
        self.root.bind("<Configure>", self._on_root_configure)

        # intercept main window close to save state and clean up children
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # attempt to size window so approximately `visible_rows` are visible without scrolling
        approx_row_height = 24  # px per row (approximate)
        header_height = 40
        window_height = header_height + (self.visible_rows * approx_row_height) + 40
        window_width = 720

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        self.x = (screen_w // 2) - (window_width // 2)
        self.y = (screen_h // 2) - (window_height // 2)

        self.root.geometry(f"{window_width}x{window_height}+{self.x}+{self.y}")

        # start update loop
        self._update_loop()

    def _create_filter_controls(self):
        self.filter_frame = ttk.Frame(self.main_frame)
        self.filter_frame.pack(fill="x", pady=(0, 4))

        self.header_controls = ttk.Frame(self.filter_frame)
        self.header_controls.pack(side="right")

        self._filter_a_var = tk.StringVar(value="(All)")
        self._filter_b_var = tk.StringVar(value="(All)")
        self._filter_type_var = tk.StringVar(value="(All)")
        self._filter_a_label = ttk.Label(self.filter_frame, text="Name:")
        self._filter_a_label.pack(side="left", padx=(0, 4))
        self._filter_a_cb = ttk.Combobox(
            self.filter_frame, state="readonly", width=10, textvariable=self._filter_a_var
        )
        self._filter_a_cb["values"] = ["(All)"] + list(self.name_list_a)
        self._filter_a_cb.pack(side="left", padx=(0, 8))
        self._filter_a_cb.bind("<<ComboboxSelected>>", lambda e: self._on_filter_changed(a_changed=True))

        self._filter_b_label = ttk.Label(self.filter_frame, text="Upgrade:")
        self._filter_b_label.pack(side="left", padx=(4, 4))
        self._filter_b_cb = ttk.Combobox(
            self.filter_frame, state="readonly", width=10, textvariable=self._filter_b_var
        )
        self._filter_b_cb["values"] = ["(All)"] + list(self.name_list_b)
        self._filter_b_cb.pack(side="left", padx=(0, 8))
        self._filter_b_cb.bind("<<ComboboxSelected>>", lambda e: self._on_filter_changed(b_changed=True))

        self._filter_type_label = ttk.Label(self.filter_frame, text="Type:")
        self._filter_type_label.pack(side="left", padx=(4, 4))
        self._filter_type_cb = ttk.Combobox(
            self.filter_frame, state="readonly", width=10, textvariable=self._filter_type_var
        )
        self._filter_type_cb["values"] = ["(All)"] + list(self.name_list_type)
        self._filter_type_cb.pack(side="left", padx=(0, 8))
        self._filter_type_cb.bind("<<ComboboxSelected>>", lambda e: self._on_filter_changed(type_changed=True))

        self.settings_frame = ttk.Frame(self.main_frame)
        self.settings_frame.pack(fill="x", pady=(0, 4))
        self._include_disabled_var = tk.BooleanVar(value=True)
        self._include_disabled_cb = ttk.Checkbutton(
            self.settings_frame,
            text="Include disabled",
            variable=self._include_disabled_var,
            command=self._on_disabled_filter_changed
        )
        self._include_disabled_cb.pack(side="left")
        self._dark_mode_cb = ttk.Checkbutton(
            self.settings_frame,
            text="Dark mode",
            variable=self._dark_mode_var,
            command=self._toggle_dark_mode
        )
        self._dark_mode_cb.pack(side="left", padx=(8, 0))
        self._low_power_cb = ttk.Checkbutton(
            self.settings_frame,
            text="Low-power Mode",
            variable=self._low_power_var
        )
        self._low_power_cb.pack(side="left", padx=(8, 0))

        self.filter_actions = ttk.Frame(self.settings_frame)
        self.filter_actions.pack(side="right")
        clear_btn = ttk.Button(self.filter_actions, text="Clear Filter", command=self._clear_filters)
        clear_btn.pack(side="right")
        refresh_btn = ttk.Button(self.filter_actions, text="Refresh", command=self._rebuild_rows)
        refresh_btn.pack(side="right", padx=(0, 8))
        self._sort_btn = ttk.Button(self.filter_actions, text="Sort", width=10, command=self._cycle_sort)
        self._sort_btn.pack(side="right", padx=(0, 8))
        self._update_responsive_controls()

    def _refresh_filter_options(self):
        # update combobox values from current name lists
        try:
            a_vals = ["(All)"] + list(self.name_list_a)
            b_vals = ["(All)"] + list(self.name_list_b)
            type_vals = ["(All)"] + list(self.name_list_type)
            self._filter_a_cb['values'] = a_vals
            self._filter_b_cb['values'] = b_vals
            self._filter_type_cb['values'] = type_vals
            # ensure currently selected values still valid, otherwise reset to (All)
            if self._filter_a_var.get() not in a_vals:
                self._filter_a_var.set("(All)")
                self.filter_a = None
            if self._filter_b_var.get() not in b_vals:
                self._filter_b_var.set("(All)")
                self.filter_b = None
            if self._filter_type_var.get() not in type_vals:
                self._filter_type_var.set("(All)")
                self.filter_type = None
        except Exception:
            pass

    def _on_filter_changed(self, a_changed: bool = False, b_changed: bool = False, type_changed: bool = False):
        # update filter state
        try:
            a_val = self._filter_a_var.get()
            b_val = self._filter_b_var.get()
            type_val = self._filter_type_var.get()
            self.filter_a = None if a_val == "(All)" else a_val
            self.filter_b = None if b_val == "(All)" else b_val
            self.filter_type = None if type_val == "(All)" else type_val
        except Exception:
            self.filter_a = None
            self.filter_b = None
            self.filter_type = None
        # rebuild visible rows under the new filter
        self._rebuild_rows()

    def _on_disabled_filter_changed(self):
        self._rebuild_rows()

    def _clear_filters(self):
        try:
            self._filter_a_var.set("(All)")
            self._filter_b_var.set("(All)")
            self._filter_type_var.set("(All)")
            self._include_disabled_var.set(True)
            self.filter_a = None
            self.filter_b = None
            self.filter_type = None
        except Exception:
            pass
        # also clear sorting state (return to default view)
        self.sort_state = None
        self._update_sort_button_labels()
        self._rebuild_rows()

    def _update_responsive_controls(self):
        if not hasattr(self, "filter_frame") or not hasattr(self, "settings_frame"):
            return

        main_width = self.main_frame.winfo_width()
        if main_width <= 1:
            main_width = 704

        label_width = sum(
            label.winfo_reqwidth() for label in (
                self._filter_a_label, self._filter_b_label, self._filter_type_label
            )
        )
        combo_overhead = 3 * 28
        combo_padding = 3 * 12
        edit_width = self.header_controls.winfo_reqwidth() if self.edit_mode else 0
        available_combo_width = max(
            4,
            int((main_width - label_width - combo_overhead - combo_padding - edit_width - 24) // 3
                / max(self._timer_text_font.measure("0"), 1))
        )
        combo_width = min(14, available_combo_width)
        for combo in (self._filter_a_cb, self._filter_b_cb, self._filter_type_cb):
            combo.configure(width=combo_width)

        self._include_disabled_cb.configure(text="Include disabled")
        self._dark_mode_cb.configure(text="Dark mode")
        self._low_power_cb.configure(text="Low-power Mode")
        full_checkbox_width = sum(
            checkbox.winfo_reqwidth() for checkbox in (
                self._include_disabled_cb, self._dark_mode_cb, self._low_power_cb
            )
        ) + 16
        available_settings_width = main_width - self.filter_actions.winfo_reqwidth() - 24
        if full_checkbox_width > available_settings_width:
            self._include_disabled_cb.configure(text="Disabled")
            self._dark_mode_cb.configure(text="Dark")
            self._low_power_cb.configure(text="Low")
        else:
            self._include_disabled_cb.configure(text="Include disabled")
            self._dark_mode_cb.configure(text="Dark mode")
            self._low_power_cb.configure(text="Low-power Mode")

    def _place_floating_buttons(self):
        # margin from edges
        margin_x = 16
        margin_y = 16
        # place edit button at bottom-right
        self.edit_btn.place(relx=1.0, rely=1.0, x=-margin_x, y=-margin_y, anchor="se")

    def _timer_row_frames(self):
        return [frame for _, frame, _ in self._row_widgets]

    def _toggle_dark_mode(self):
        self._dark_mode = self._dark_mode_var.get()
        self.root._dark_mode = self._dark_mode
        self.style.theme_use("clam" if self._dark_mode else self._light_theme)
        if self._dark_mode:
            self.root.configure(background="#333333")
            self.style.configure("TFrame", background="#333333")
            self.style.configure("TLabel", background="#333333", foreground="#f0f0f0")
            self.style.configure("TLabelframe", background="#333333", foreground="#f0f0f0")
            self.style.configure("TLabelframe.Label", background="#333333", foreground="#f0f0f0")
            self.style.configure("TButton", background="#444444", foreground="#f0f0f0")
            self.style.map("TButton", background=[("active", "#555555"), ("disabled", "#333333")],
                           foreground=[("disabled", "#888888")])
            self.style.configure("TCheckbutton", background="#333333", foreground="#f0f0f0")
            self.style.map("TCheckbutton", background=[("active", "#444444")],
                           foreground=[("disabled", "#888888")])
            self.style.configure("TEntry", fieldbackground="#222222", foreground="#f0f0f0")
            self.style.configure("TCombobox", fieldbackground="#222222", foreground="#f0f0f0",
                                 background="#444444", arrowcolor="#f0f0f0")
            self.style.map("TCombobox", fieldbackground=[("readonly", "#222222")],
                           foreground=[("readonly", "#f0f0f0")])
            self.style.configure("TScrollbar", background="#444444", troughcolor="#333333")
        if not self._dark_mode:
            self.root.configure(background=self._light_root_background)
        apply_classic_widget_colors(self.root, self._dark_mode, self._timer_row_frames())
        self._update_native_control_colors()
        self._refresh_timer_row_colors()

    def _update_native_control_colors(self):
        foreground = "#f0f0f0" if self._dark_mode else "black"
        default_background = "#444444" if self._dark_mode else "SystemButtonFace"
        edit_background = ("#52697d" if self._dark_mode else "lightblue") if self.edit_mode else default_background
        self.edit_btn.configure(background=edit_background, foreground=foreground)
        if hasattr(self, "trash_toggle_btn"):
            trash_background = "tomato" if self.remove_mode_main else default_background
            self.trash_toggle_btn.configure(background=trash_background, foreground=foreground)

    def _refresh_timer_row_colors(self):
        for timer, frame, button in self._row_widgets:
            background = self._timer_background_color(timer)
            frame.configure(background=background)
            frame.winfo_children()[0].configure(
                background=background,
                foreground="black" if self.edit_mode else background,
            )
            button.configure(background=background)

    def _toggle_edit_mode(self):
        self.edit_mode = not self.edit_mode
        if self.edit_mode:
            self.edit_btn.config(bg="lightblue", text="Done")
            for widget in self.header_controls.winfo_children():
                widget.destroy()
            add_btn = ttk.Button(self.header_controls, text="+ Add", width=8, command=self._on_add_button_pressed)
            add_btn.pack(side="left", padx=(4, 0))
            self.trash_toggle_btn = tk.Button(
                self.header_controls, text="Remove", width=8, command=self._toggle_remove_mode_main
            )
            self.trash_toggle_btn.pack(side="left", padx=(4, 0))
            self.header_controls.pack(side="right")
        else:
            self.edit_btn.config(bg="SystemButtonFace", text="Edit")
            # hide edit controls and ensure remove mode is cleared
            self.header_controls.pack_forget()
            self.remove_mode_main = False
            try:
                self.trash_toggle_btn.config(bg="SystemButtonFace")
            except Exception:
                pass
        self._update_responsive_controls()
        # rebuild rows so drag handles and per-item trash appear/disappear
        self._rebuild_rows()
        apply_classic_widget_colors(self.root, self._dark_mode, self._timer_row_frames())
        self._update_native_control_colors()

    def _toggle_remove_mode_main(self):
        self.remove_mode_main = not self.remove_mode_main
        # visual feedback on header trash toggle
        self._update_native_control_colors()
        # rebuild rows so per-item trash appears/disappears
        self._rebuild_rows()

    def _timer_name_width(self, canvas_width: Optional[int] = None) -> int:
        if canvas_width is None:
            canvas_width = self.scrollable.canvas.winfo_width()
        if canvas_width <= 1:
            canvas_width = max(self.root.winfo_width() - 24, 0)
        char_width = max(self._timer_text_font.measure("0"), 1)
        handle_width = self._timer_text_font.measure("  ") + 4
        row_right_padding = 4
        button_padding = 14
        following_columns = self._timer_text_font.measure(
            f" {'Remain':>8}   {'Ends At':<11} {'Resources':<10}"
        )
        available_pixels = canvas_width - handle_width - row_right_padding - button_padding
        available_chars = max(0, (available_pixels - following_columns) // char_width)
        return min(34, available_chars)

    def _update_header_label(self, canvas_width: Optional[int] = None):
        name_width = self._timer_name_width(canvas_width)
        self._header_label.config(
            text=f"{'Name':<{name_width}} {'Remain':>8}   {'Ends At':<11} {'Resources':<10}"
        )
        if name_width != self._displayed_name_width:
            self._displayed_name_width = name_width
            for timer, _, button in getattr(self, "_row_widgets", []):
                button.config(text=self._format_button_text(timer, name_width))

    def _on_timer_viewport_configure(self, event):
        if event.widget is self.scrollable.canvas:
            self._update_header_label(event.width)

    def _on_root_configure(self, event):
        if event.widget is self.root:
            self._place_floating_buttons()
            self._update_header_label()
            self._update_responsive_controls()

    def _format_button_text(self, timer: CountdownTimer, name_width: Optional[int] = None) -> str:
        if name_width is None:
            name_width = self._timer_name_width()
        name = timer.name[:name_width]
        remaining = timer.remaining_str()
        ends = unix_to_local_str(timer.end_ts)
        resource = RESOURCE_LABELS.get(timer.resource, RESOURCE_LABELS["Empty"])
        return f"{name:<{name_width}} {remaining:>8}   {ends:<11} {resource:<10}"

    def _timer_background_color(self, timer: CountdownTimer) -> str:
        if timer.disabled:
            return "#858585" if self._dark_mode else "grey"
        remaining = timer.remaining_seconds()
        if remaining == 0:
            return "#c46f73" if self._dark_mode else "red"
        if remaining < 300:
            return "#d88989" if self._dark_mode else "#ff9999"
        if remaining < 900:
            return "#d4aa70" if self._dark_mode else "#ffcc80"
        if remaining < 3600:
            return "#8fb7c4" if self._dark_mode else "lightblue"
        if remaining < 3600 * 6:
            return "#93bd8f" if self._dark_mode else "lightgreen"
        return "#b0b0b0" if self._dark_mode else "white"

    def _split_name_parts(self, name: str):
        return Save.split_timer_name(name, self.name_list_type)

    def _matches_filter(self, timer: CountdownTimer) -> bool:
        if timer.disabled and not self._include_disabled_var.get():
            return False
        if self.filter_a is None and self.filter_b is None and self.filter_type is None:
            return True
        name, upgrade, timer_type = self._split_name_parts(timer.name)
        if self.filter_a is not None and name != self.filter_a:
            return False
        if self.filter_b is not None and upgrade != self.filter_b:
            return False
        if self.filter_type is not None and timer_type != self.filter_type:
            return False
        return True

    def _sort_label_for_state(self) -> str:
        if self.sort_state == "asc":
            return "Sort ▲"
        if self.sort_state == "desc":
            return "Sort ▼"
        return "Sort"

    def _update_sort_button_labels(self):
        try:
            if hasattr(self, "_sort_btn") and self._sort_btn:
                self._sort_btn.config(text=self._sort_label_for_state())
        except Exception:
            pass

    def _cycle_sort(self):
        # cycle None -> asc -> desc -> None
        try:
            if self.sort_state is None:
                self.sort_state = "asc"
            elif self.sort_state == "asc":
                self.sort_state = "desc"
            else:
                self.sort_state = None
        except Exception:
            self.sort_state = None
        # update button label and rebuild rows to reflect the non-mutating visual sort
        self._update_sort_button_labels()
        self._rebuild_rows()

    def _get_sorted_timers(self) -> List[CountdownTimer]:
        # return the sequence of timers to present given current sort/filter state
        base = list(self.timers)
        if self.sort_state is None:
            return base
        # sort by remaining seconds (ascending or descending)
        try:
            rev = True if self.sort_state == "desc" else False
            return sorted(base, key=lambda t: t.remaining_seconds(), reverse=rev)
        except Exception:
            return base

    def _add_timer_row(self, idx: int, timer: CountdownTimer):
        """
        Create a row as a frame that contains:
         - drag handle (visible in edit mode)
         - the main button (click to edit)
         - optional trash button (visible when remove_mode_main is True)
        """
        # Only add row if it matches filter
        if not self._matches_filter(timer):
            return

        row_background = self._timer_background_color(timer)
        item_fr = tk.Frame(self.scrollable.inner, background=row_background)
        item_fr.pack(fill="x", pady=2, padx=(0, 4))

        # drag handle (always created, visible appearance controlled by edit_mode)
        handle = tk.Label(item_fr, text="≡", width=2, anchor="center", cursor="hand2",
                          font=self.BUTTON_FONT,
                          background=row_background,
                          foreground="black" if self.edit_mode else row_background)
        handle.pack(side="left", padx=(0,4))
        handle.bind("<ButtonPress-1>", lambda e, t=timer: self._start_drag_main(e, t))
        handle.bind("<ButtonRelease-1>", lambda e, t=timer: self._end_drag_main(e, t))
        handle.bind("<B1-Motion>", self._drag_motion_main)

        # main text button
        btn = tk.Button(
            item_fr,
            text=self._format_button_text(timer),
            font=self.BUTTON_FONT,
            anchor="w",
            justify="left",
            relief="raised",
            command=lambda t=timer, b=None: self._on_timer_clicked(t)
        )
        btn.pack(side="left", fill="x", expand=True)

        # per-item trash (only shown in remove mode)
        trash_btn = None
        if self.edit_mode and self.remove_mode_main:
            trash_btn = tk.Button(item_fr, text="🗑", width=3, background=row_background,
                                  foreground="black", command=lambda t=timer: self._confirm_remove_timer(t))
            trash_btn.pack(side="right", padx=(4,0))

        # store tuple; frame and main button needed for later updates or destruction
        self._row_widgets.append((timer, item_fr, btn))
        self.scrollable._bind_mousewheel_tree(item_fr)
        # ensure scrollregion updates
        self.scrollable._on_frame_configure()

        # Keep timer rows' background and text colors independent of the app theme.
        btn.config(bg=row_background, fg="black")

    def _rebuild_rows(self):
        # clear existing rows and rebuild in order from self.timers (sorted view if applicable)
        for _, frame, _ in list(self._row_widgets):
            try:
                frame.destroy()
            except Exception:
                pass
        self._row_widgets.clear()
        # ensure filter options reflect any external changes to name lists
        self._refresh_filter_options()
        # iterate over the sorted/presented sequence, do not mutate self.timers here
        present = self._get_sorted_timers()
        for idx, t in enumerate(present):
            self._add_timer_row(idx, t)

    def _confirm_remove_timer(self, timer: CountdownTimer):
        if messagebox.askyesno("Remove timer", f"Remove timer '{timer.name}'?"):
            try:
                self._remove_timer(timer)
            except Exception:
                pass

    def _remove_timer(self, timer: CountdownTimer):
        # remove from timers list and UI
        try:
            self.timers.remove(timer)
        except ValueError:
            pass
        for i, (t, fr, btn) in enumerate(list(self._row_widgets)):
            if t is timer:
                try:
                    fr.destroy()
                except Exception:
                    pass
                self._row_widgets.pop(i)
                break
        self.scrollable._on_frame_configure()
        # persist change
        try:
            Save.save_state(self.name_list_a, self.name_list_b, self.timers,
                            name_list_type=self.name_list_type)
        except Exception:
            pass

    def _on_timer_clicked(self, timer: CountdownTimer, btn: Optional[tk.Widget] = None):
        if self.edit_mode and self.remove_mode_main:
            # removal flow (header remove mode active) — confirm and remove
            if messagebox.askyesno("Remove timer", f"Remove timer '{timer.name}'?"):
                self._remove_timer(timer)
            return

        # not in removal mode: open edit dialog
        self._open_edit_dialog(timer)

    def _start_drag_main(self, event, timer: CountdownTimer):
        if (not self.edit_mode or self.remove_mode_main or self.sort_state is not None
                or self.filter_a is not None or self.filter_b is not None or self.filter_type is not None
                or not self._include_disabled_var.get()):
            return

        row = next((item for item in self._row_widgets if item[0] is timer), None)
        if row is None:
            return

        frame = row[1]
        frame.update_idletasks()
        width = max(frame.winfo_width(), 1)
        height = max(frame.winfo_height(), 1)

        ghost = tk.Toplevel(self.root)
        ghost.overrideredirect(True)
        ghost.attributes("-alpha", 0.5)
        ghost.attributes("-topmost", True)
        preview = tk.Label(
            ghost,
            text=self._format_button_text(timer),
            font=self.BUTTON_FONT,
            anchor="w",
            relief="raised",
            bd=1,
            background=self._timer_background_color(timer),
            foreground="black",
        )
        preview.pack(fill="both", expand=True)
        ghost.geometry(f"{width}x{height}+{event.x_root}+{event.y_root}")

        placeholder = tk.Frame(
            self.scrollable.inner,
            height=height,
            background="#d9eaf7",
            relief="solid",
            borderwidth=1,
        )
        placeholder.pack_propagate(False)
        self._drag_data_main = {
            "row": row,
            "placeholder": placeholder,
            "ghost": ghost,
            "handle": event.widget
        }
        event.widget.grab_set()
        event.widget.configure(cursor="fleur")
        self._repack_drag_rows()

    def _drag_motion_main(self, event):
        drag = self._drag_data_main
        if not drag:
            return

        ghost = drag["ghost"]
        ghost.geometry(f"+{event.x_root}+{event.y_root}")

        dragged_row = drag["row"]
        remaining_rows = [row for row in self._row_widgets if row is not dragged_row]
        target_index = len(remaining_rows)
        for index, row in enumerate(remaining_rows):
            frame = row[1]
            midpoint = frame.winfo_rooty() + frame.winfo_height() / 2
            if event.y_root < midpoint:
                target_index = index
                break

        new_order = remaining_rows[:target_index] + [dragged_row] + remaining_rows[target_index:]
        if new_order != self._row_widgets:
            self._row_widgets[:] = new_order
            self._repack_drag_rows()
            self.root.update_idletasks()

    def _repack_drag_rows(self):
        drag = self._drag_data_main
        if drag:
            drag["placeholder"].pack_forget()
        for _, frame, _ in self._row_widgets:
            frame.pack_forget()
        for row in self._row_widgets:
            widget = drag["placeholder"] if drag and row is drag["row"] else row[1]
            widget.pack(fill="x", pady=2, padx=(0, 4))
        self.scrollable._on_frame_configure()

    def _end_drag_main(self, event, timer: CountdownTimer):
        drag = self._drag_data_main
        if not drag or drag["row"][0] is not timer:
            return

        drag["handle"].grab_release()
        drag["placeholder"].destroy()
        drag["ghost"].destroy()
        drag["handle"].configure(cursor="hand2")
        self._drag_data_main = None
        self._repack_drag_rows()

        self.timers[:] = [row[0] for row in self._row_widgets]
        try:
            Save.save_state(self.name_list_a, self.name_list_b, self.timers,
                            name_list_type=self.name_list_type)
        except Exception:
            pass

    def _register_child(self, win: tk.Toplevel):
        # keep a reference so we can close and release grabs on shutdown
        self._child_windows.add(win)
        # remove from set when destroyed
        win.bind("<Destroy>", lambda e, w=win: self._child_windows.discard(w), add="+")
        apply_classic_widget_colors(self.root, self._dark_mode, self._timer_row_frames())
        # also ensure we remove if the dialog sets its own protocol
        try:
            orig = win.protocol("WM_DELETE_WINDOW")
        except Exception:
            pass

    def _open_edit_dialog(self, timer: CountdownTimer):
        # open the edit dialog, pass shared name lists and a callback to refresh UI immediately
        def refresh():
            self._refresh_filter_options()
            self._rebuild_rows()
            # update scroll region in case size changed
            self.scrollable._on_frame_configure()
            # persist changes after edits
            try:
                Save.save_state(self.name_list_a, self.name_list_b, self.timers,
                                name_list_type=self.name_list_type)
            except Exception:
                pass

        dlg = EditTimerDialog(
            self.root,
            timer,
            self.name_list_a,
            self.name_list_b,
            self.name_list_type,
            on_update=refresh,
        )
        self._register_child(dlg)

    def _update_loop(self):
        # In low-power mode, update one of ten rotating groups on each tick.
        batch_index = self._update_batch_index
        if self._low_power_var.get():
            self._update_batch_index = (batch_index + 1) % self.LOW_POWER_BATCH_COUNT

        # update texts and colors
        for row_index, (timer, fr, btn) in enumerate(self._row_widgets):
            if self._low_power_var.get() and row_index % self.LOW_POWER_BATCH_COUNT != batch_index:
                continue
            text = self._format_button_text(timer)
            try:
                background = self._timer_background_color(timer)
                fr.configure(background=background)
                fr.winfo_children()[0].configure(
                    background=background,
                    foreground="black" if self.edit_mode else background,
                )
                btn.config(text=text, bg=background, fg="black")
            except Exception:
                pass

        # update finished-timer arrows indicating finished items offscreen
        try:
            canvas = self.scrollable.canvas
            visible_top = canvas.canvasy(0)
            visible_bottom = visible_top + canvas.winfo_height()
            show_up = False
            show_down = False
            for timer, fr, _ in self._row_widgets:
                if not timer.is_finished():
                    continue
                fr_top = fr.winfo_y()
                fr_bottom = fr_top + (fr.winfo_height() or 1)
                if fr_bottom < visible_top:
                    show_up = True
                elif fr_top > visible_bottom:
                    show_down = True
                if show_up and show_down:
                    break

            if show_up:
                self._top_arrow.place(in_=self.scrollable.canvas, relx=0.98, rely=0.02, anchor="ne")
            else:
                self._top_arrow.place_forget()

            if show_down:
                self._bottom_arrow.place(in_=self.scrollable.canvas, relx=0.98, rely=0.98, anchor="se")
            else:
                self._bottom_arrow.place_forget()
        except Exception:
            pass

        self.root.after(self.UPDATE_INTERVAL_MS, self._update_loop)

    def _on_add_button_pressed(self):
        # open AddTimerDialog; provide callback to receive the new timer data
        dlg = AddTimerDialog(
            self.root, self._add_timer_from_dialog, self.name_list_a, self.name_list_b, self.name_list_type
        )
        self._register_child(dlg)
        # name lists may have changed in the dialog, refresh filter options when it closes
        self.root.wait_window(dlg)
        self._refresh_filter_options()

    def _add_timer_from_dialog(self, name: str, seconds: int, note: str):
        new_timer = CountdownTimer(name, seconds, note=note)
        self.timers.append(new_timer)
        # add to UI
        self._add_timer_row(len(self._row_widgets), new_timer)
        # persist new timer
        try:
            Save.save_state(self.name_list_a, self.name_list_b, self.timers,
                            name_list_type=self.name_list_type)
        except Exception:
            pass

    def _on_close(self):
        # Save state via Save.py
        try:
            Save.save_state(self.name_list_a, self.name_list_b, self.timers,
                            name_list_type=self.name_list_type)
        except Exception:
            pass

        # Close child dialogs cleanly (release grabs then destroy)
        for win in list(self._child_windows):
            try:
                try:
                    win.grab_release()
                except Exception:
                    pass
                if win.winfo_exists():
                    win.destroy()
            except Exception:
                pass
        self._child_windows.clear()

        # finally destroy main window
        try:
            self.root.destroy()
        except Exception:
            pass

def main():
    # Attempt to restore state from save file
    state = Save.load_state()
    sample_timers: List[CountdownTimer] = []

    if state and isinstance(state.get("timers"), list):
        now = int(time.time())
        for t in state.get("timers", []):
            name = t.get("name", "Timer")
            upgrade = t.get("upgrade")
            timer_type = t.get("type")
            if upgrade is not None:
                name_parts = [str(name), str(upgrade)]
                if timer_type is not None:
                    name_parts.append(str(timer_type))
                name = " - ".join(name_parts)
            end_ts = int(t.get("end_ts", now))
            remaining = max(0, end_ts - now)
            sample_timers.append(CountdownTimer(
                name,
                remaining,
                disabled=bool(t.get("disabled", False)),
                note=str(t.get("note", "")),
                resource=str(t.get("resource", "Empty"))
            ))
        name_list_a = state.get("name_list_a", None)
        name_list_b = state.get("name_list_b", None)
        name_list_type = state.get("name_list_type", [])
    else:
        # fallback example timers
        lengths = [10, 30, 60, 90, 150, 300, 600, 1200, 3600, 7200, 86400, 86500, 172800, 5, 45]
        for i, secs in enumerate(lengths, start=1):
            sample_timers.append(CountdownTimer(f"Timer {i}", secs))
        name_list_a = None
        name_list_b = None
        name_list_type = None

    root = tk.Tk()
    # visible_rows=10 will size the window so ~10 rows are visible before scrolling
    app = SimpleCountdownApp(root, sample_timers, visible_rows=10,
                             name_list_a=name_list_a, name_list_b=name_list_b,
                             name_list_type=name_list_type)
    root.mainloop()

if __name__ == "__main__":
    main()