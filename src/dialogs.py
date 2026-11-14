import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any, Callable, List, Optional, Tuple

from assets import Account, ClockTower, Timer


class TimeEditingBehavior:
    """Shared D/H/M/S input behavior for dialogs that edit a duration."""

    def _init_time_editing(
        self, parent: ttk.Frame, seconds: int, pady: Tuple[int, int]
    ) -> None:
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.time_vars = [
            tk.StringVar(value=str(value))
            for value in (days, hours, minutes, seconds)
        ]
        self.time_entries: List[ttk.Entry] = []

        for column, (unit, field_var) in enumerate(
            zip(("D", "H", "M", "S"), self.time_vars)
        ):
            unit_frame = ttk.Frame(parent)
            unit_frame.grid(row=0, column=column, padx=(0 if column == 0 else 8, 0))
            ttk.Label(unit_frame, text=unit).pack(anchor="w")
            entry = ttk.Entry(unit_frame, textvariable=field_var, width=6)
            entry.pack()
            entry.bind("<Button-1>", self._select_time_field)
            self.time_entries.append(entry)

        for index, entry in enumerate(self.time_entries):
            entry.bind(
                "<Left>",
                lambda event, field_index=index: self._move_time_field(
                    event, field_index, -1
                ),
            )
            entry.bind(
                "<Right>",
                lambda event, field_index=index: self._move_time_field(
                    event, field_index, 1
                ),
            )
        parent.grid_configure(pady=pady)

    @staticmethod
    def _duration_from_fields(fields: Tuple[str, str, str, str]) -> int:
        labels = ("days", "hours", "minutes", "seconds")
        values = []
        for label, field in zip(labels, fields):
            if not field:
                values.append(0)
            elif field.isdecimal():
                values.append(int(field))
            else:
                raise ValueError(f"{label.capitalize()} must be a non-negative integer.")

        days, hours, minutes, seconds = values
        return days * 86400 + hours * 3600 + minutes * 60 + seconds

    def _select_time_field(self, event: tk.Event) -> None:
        entry = event.widget
        self.after_idle(lambda: entry.selection_range(0, tk.END))

    def _move_time_field(
        self, event: tk.Event, field_index: int, direction: int
    ) -> Optional[str]:
        entry = self.time_entries[field_index]
        if direction < 0:
            at_boundary = entry.index(tk.INSERT) == 0
        else:
            at_boundary = entry.index(tk.INSERT) == len(entry.get())
        next_index = field_index + direction
        if at_boundary and 0 <= next_index < len(self.time_entries):
            next_entry = self.time_entries[next_index]
            next_entry.focus_set()
            next_entry.icursor(tk.END if direction < 0 else 0)
            next_entry.selection_range(0, tk.END)
            return "break"
        return None


class TimerEditor(TimeEditingBehavior, tk.Toplevel):
    """Dialog for editing a timer's name and remaining duration."""

    def __init__(
        self,
        master: tk.Misc,
        timer: Timer,
        on_save: Callable[[str, int], None],
        title: str = "Edit timer",
    ) -> None:
        super().__init__(master)
        self.timer = timer
        self.on_save = on_save
        self.title(title)
        self.transient(master.winfo_toplevel())
        self.resizable(False, False)
        self.grab_set()

        content = ttk.Frame(self, padding=18)
        content.grid(row=0, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)

        ttk.Label(content, text="Timer name").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar(value=timer.name)
        name_entry = ttk.Entry(content, textvariable=self.name_var, width=34)
        name_entry.grid(row=1, column=0, sticky="ew", pady=(4, 14))

        ttk.Label(content, text="Remaining time").grid(row=2, column=0, sticky="w")
        time_fields = ttk.Frame(content)
        time_fields.grid(row=3, column=0, sticky="w")
        self._init_time_editing(time_fields, timer.value, (6, 12))

        self.error_label = ttk.Label(content, foreground="#b42318")
        self.error_label.grid(row=4, column=0, sticky="w")
        buttons = ttk.Frame(content)
        buttons.grid(row=5, column=0, sticky="e", pady=(12, 0))

        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(buttons, text="Save", command=self._save).pack(side="right")
        self.bind("<Return>", lambda _event: self._save())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        self.grab_set()
        name_entry.focus_set()

    def _save(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            self.error_label.configure(text="Enter a timer name.")
            return
        try:
            remaining = self._duration_from_fields(
                tuple(field_var.get().strip() for field_var in self.time_vars)
            )
        except ValueError as error:
            self.error_label.configure(text=str(error))
            return

        self.on_save(name, remaining)
        self.destroy()


class TimerListDialog(tk.Toplevel):
    """View and edit timers belonging to one village category."""

    def __init__(
        self,
        master: tk.Misc,
        timers: List[Timer],
        village: str,
        category: str,
        on_add: Callable[[Timer], None],
        on_edit: Callable[[Timer, str, int], None],
        on_delete: Callable[[Timer], None],
    ) -> None:
        super().__init__(master)
        self.timers = list(timers)
        self.village = village
        self.category = category
        self.on_add = on_add
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.title("Edit Timer List")
        self.transient(master.winfo_toplevel())
        self.resizable(False, False)
        self.grab_set()

        content = ttk.Frame(self, padding=18)
        content.grid(row=0, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        ttk.Label(content, text=f"{village} / {category} timers").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )

        self.timer_list = tk.Listbox(
            content, height=min(max(len(self.timers), 3), 10), width=42,
            exportselection=False,
        )
        self.timer_list.grid(row=1, column=0, sticky="nsew")
        content.rowconfigure(1, weight=1)

        buttons = ttk.Frame(content)
        buttons.grid(row=1, column=1, sticky="ns", padx=(12, 0))
        ttk.Button(buttons, text="Add", command=self._add).pack(
            fill="x", pady=(0, 8)
        )
        self.edit_button = ttk.Button(
            buttons, text="Edit", command=self._edit, state="disabled"
        )
        self.edit_button.pack(fill="x", pady=(0, 8))
        self.delete_button = ttk.Button(
            buttons, text="Delete", command=self._delete, state="disabled"
        )
        self.delete_button.pack(fill="x", pady=(0, 8))
        ttk.Button(buttons, text="Close", command=self.destroy).pack(
            fill="x", side="bottom"
        )
        self._refresh_timers()
        self.timer_list.bind("<<ListboxSelect>>", self._on_selection)
        self.timer_list.bind("<Double-Button-1>", lambda _event: self._edit())
        self.bind("<Escape>", lambda _event: self.destroy())

        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _refresh_timers(self) -> None:
        self.timer_list.delete(0, tk.END)
        for timer in self.timers:
            self.timer_list.insert(
                tk.END, f"{timer.name} - {self._format_time(timer.value)}"
            )
        self.edit_button.configure(state="disabled")

    @staticmethod
    def _format_time(seconds: int) -> str:
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        time = f"{hours:02}:{minutes:02}:{seconds:02}"
        return f"{days}d {time}" if days else time

    def _on_selection(self, _event: tk.Event) -> None:
        state = "normal" if self.timer_list.curselection() else "disabled"
        self.edit_button.configure(state=state)
        self.delete_button.configure(state=state)

    def _add(self) -> None:
        draft = Timer("", 0, self.village, self.category)
        TimerEditor(
            self,
            draft,
            lambda name, remaining: self._save_new_timer(
                draft, name, remaining
            ),
            title="Add Timer",
        )

    def _save_new_timer(self, draft: Timer, name: str, remaining: int) -> None:
        timer = Timer(name, remaining, draft.village, draft.category)
        self.on_add(timer)
        self.timers.append(timer)
        self._refresh_timers()

    def _edit(self) -> None:
        selection = self.timer_list.curselection()
        if not selection:
            return
        timer = self.timers[selection[0]]
        TimerEditor(
            self,
            timer,
            lambda name, remaining: self._save_edited_timer(
                timer, name, remaining
            ),
        )

    def _save_edited_timer(
        self, timer: Timer, name: str, remaining: int
    ) -> None:
        self.on_edit(timer, name, remaining)
        self._refresh_timers()

    def _delete(self) -> None:
        selection = self.timer_list.curselection()
        if not selection:
            return
        index = selection[0]
        timer = self.timers[index]
        if not messagebox.askyesno(
            "Delete Timer",
            f"Delete {timer.name!r}?",
            parent=self,
        ):
            return
        self.on_delete(timer)
        self.timers.pop(index)
        self._refresh_timers()


class AccountListDialog(tk.Toplevel):
    """Add and remove accounts from the timer overview."""

    def __init__(
        self,
        master: tk.Misc,
        accounts: List[Account],
        on_add: Callable[[str], Account],
        on_delete: Callable[[Account], None],
        on_move: Callable[[Account, int], None],
    ) -> None:
        super().__init__(master)
        self.accounts = list(accounts)
        self.on_add = on_add
        self.on_delete = on_delete
        self.on_move = on_move
        self.title("Edit Account List")
        self.transient(master.winfo_toplevel())
        self.resizable(False, False)
        self.grab_set()

        content = ttk.Frame(self, padding=18)
        content.grid(row=0, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        ttk.Label(content, text="Accounts").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )

        self.account_list = tk.Listbox(
            content,
            height=min(max(len(self.accounts), 3), 10),
            width=42,
            exportselection=False,
        )
        self.account_list.grid(row=1, column=0, sticky="nsew")
        content.rowconfigure(1, weight=1)

        buttons = ttk.Frame(content)
        buttons.grid(row=1, column=1, sticky="ns", padx=(12, 0))
        ttk.Button(buttons, text="Add", command=self._add).pack(
            fill="x", pady=(0, 8)
        )
        self.delete_button = ttk.Button(
            buttons, text="Delete", command=self._delete, state="disabled"
        )
        self.delete_button.pack(fill="x", pady=(0, 8))
        self.move_up_button = ttk.Button(
            buttons, text="Move Up", command=self._move_up, state="disabled"
        )
        self.move_up_button.pack(fill="x", pady=(0, 8))
        self.move_down_button = ttk.Button(
            buttons, text="Move Down", command=self._move_down, state="disabled"
        )
        self.move_down_button.pack(fill="x", pady=(0, 8))
        ttk.Button(buttons, text="Close", command=self.destroy).pack(
            fill="x", side="bottom"
        )
        self._refresh_accounts()
        self.account_list.bind("<<ListboxSelect>>", self._on_selection)
        self.bind("<Escape>", lambda _event: self.destroy())

        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _refresh_accounts(self) -> None:
        self.account_list.delete(0, tk.END)
        for account in self.accounts:
            self.account_list.insert(tk.END, account.name)
        self.delete_button.configure(state="disabled")
        self.move_up_button.configure(state="disabled")
        self.move_down_button.configure(state="disabled")

    def _on_selection(self, _event: tk.Event) -> None:
        selection = self.account_list.curselection()
        self.delete_button.configure(
            state="normal" if selection else "disabled"
        )
        index = selection[0] if selection else -1
        self.move_up_button.configure(
            state="normal" if index > 0 else "disabled"
        )
        self.move_down_button.configure(
            state="normal"
            if 0 <= index < len(self.accounts) - 1
            else "disabled"
        )

    def _add(self) -> None:
        name = simpledialog.askstring(
            "Add Account", "Account name:", parent=self
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            messagebox.showerror(
                "Add Account", "Enter an account name.", parent=self
            )
            return
        if any(account.name.casefold() == name.casefold() for account in self.accounts):
            messagebox.showerror(
                "Add Account",
                "An account with that name already exists.",
                parent=self,
            )
            return
        account = self.on_add(name)
        self.accounts.append(account)
        self._refresh_accounts()

    def _move_up(self) -> None:
        self._move_selected(-1)

    def _move_down(self) -> None:
        self._move_selected(1)

    def _move_selected(self, direction: int) -> None:
        selection = self.account_list.curselection()
        if not selection:
            return
        index = selection[0]
        destination = index + direction
        if not 0 <= destination < len(self.accounts):
            return
        account = self.accounts[index]
        self.on_move(account, destination)
        self.accounts.pop(index)
        self.accounts.insert(destination, account)
        self._refresh_accounts()
        self.account_list.selection_set(destination)
        self.account_list.activate(destination)
        self._on_selection(None)

    def _delete(self) -> None:
        selection = self.account_list.curselection()
        if not selection:
            return
        index = selection[0]
        account = self.accounts[index]
        if not messagebox.askyesno(
            "Delete Account",
            f"Delete account {account.name!r} and its timers?",
            parent=self,
        ):
            return
        self.on_delete(account)
        self.accounts.pop(index)
        self._refresh_accounts()


class AssignTimerDialog(tk.Toplevel):
    """Choose a timer for an account upgrade assistant."""

    def __init__(
        self,
        master: tk.Misc,
        timers: List[Timer],
        on_assign: Callable[[Timer], None],
        on_cancel: Optional[Callable[[], None]] = None,
        assignment_scope: str = "Home Village / Building",
    ) -> None:
        super().__init__(master)
        self.timers = timers
        self.on_assign = on_assign
        self.on_cancel = on_cancel
        self.title("Assign Timer")
        self.transient(master.winfo_toplevel())
        self.resizable(False, False)
        self.grab_set()

        content = ttk.Frame(self, padding=18)
        content.grid(row=0, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)

        ttk.Label(content, text=f"Select a {assignment_scope} timer:").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        self.timer_list = tk.Listbox(content, height=min(max(len(timers), 3), 10), width=36)
        self.timer_list.grid(row=1, column=0, sticky="ew")
        for timer in timers:
            self.timer_list.insert(tk.END, timer.name)
        self.timer_list.bind("<<ListboxSelect>>", self._on_selection)
        self.timer_list.bind("<Double-Button-1>", lambda _event: self._assign())

        buttons = ttk.Frame(content)
        buttons.grid(row=2, column=0, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=self._cancel).pack(
            side="right", padx=(8, 0)
        )
        self.assign_button = ttk.Button(
            buttons, text="Assign", command=self._assign, state="disabled"
        )
        self.assign_button.pack(side="right")
        self.bind("<Return>", lambda _event: self._assign())
        self.bind("<Escape>", lambda _event: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        if timers:
            self.timer_list.focus_set()

    def _on_selection(self, _event: tk.Event) -> None:
        state = "normal" if self.timer_list.curselection() else "disabled"
        self.assign_button.configure(state=state)

    def _assign(self) -> None:
        selection = self.timer_list.curselection()
        if not selection:
            return
        self.on_assign(self.timers[selection[0]])
        self.destroy()

    def _cancel(self) -> None:
        if self.on_cancel is not None:
            self.on_cancel()
        self.destroy()


class EditAssistantDialog(TimeEditingBehavior, tk.Toplevel):
    """Edit an upgrade assistant's state, cooldown, and timer assignment."""

    def __init__(
        self,
        master: tk.Misc,
        account: Account,
        assistant: Any,
        assistant_name: str,
        assignable_timers: List[Timer],
        on_save: Callable[
            [int, bool, int, bool, Optional[Timer], Optional[int]], None
        ],
    ) -> None:
        super().__init__(master)
        self.account = account
        self.assistant = assistant
        self.assistant_name = assistant_name
        self.assignable_timers = assignable_timers
        self.on_save = on_save
        self.pending_timer = (
            None if isinstance(assistant, ClockTower) else assistant.assigned_timer
        )
        self.title(f"Edit {assistant_name}")
        self.transient(master.winfo_toplevel())
        self.resizable(False, False)
        self.grab_set()

        content = ttk.Frame(self, padding=18)
        content.grid(row=0, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)

        self.is_clock_tower = isinstance(assistant, ClockTower)
        row = 0
        if not self.is_clock_tower:
            ttk.Label(content, text="Cooldown").grid(
                row=row, column=0, sticky="w"
            )
            time_fields = ttk.Frame(content)
            time_fields.grid(row=row + 1, column=0, sticky="w")
            self._init_time_editing(time_fields, assistant.cooldown, (6, 14))
            row += 2

        ttk.Label(content, text="Status").grid(row=row, column=0, sticky="w")
        self.active_var = tk.StringVar(
            value="Active" if assistant.active else "Inactive"
        )
        ttk.Combobox(
            content,
            textvariable=self.active_var,
            values=("Active", "Inactive"),
            state="readonly",
            width=18,
        ).grid(row=row + 1, column=0, sticky="w", pady=(4, 12))
        row += 2

        ttk.Label(content, text="Multiplier").grid(row=row, column=0, sticky="w")
        if self.is_clock_tower:
            ttk.Label(content, text="9 (fixed)").grid(
                row=row + 1, column=0, sticky="w", pady=(4, 12)
            )
            row += 2
            ttk.Label(content, text="Active duration (minutes)").grid(
                row=row, column=0, sticky="w"
            )
            self.active_duration_var = tk.StringVar(
                value=str(assistant.active_cooldown_minutes)
            )
            ttk.Entry(content, textvariable=self.active_duration_var, width=20).grid(
                row=row + 1, column=0, sticky="w", pady=(4, 12)
            )
            row += 2
        else:
            self.multiplier_var = tk.StringVar(value=str(assistant.multiplier))
            ttk.Entry(content, textvariable=self.multiplier_var, width=20).grid(
                row=row + 1, column=0, sticky="w", pady=(4, 12)
            )
            row += 2

        self.has_assignment = not isinstance(assistant, ClockTower)
        if self.has_assignment:
            ttk.Label(content, text="Assignment").grid(
                row=row, column=0, sticky="w"
            )
            self.assignment_var = tk.StringVar(
                value="Assigned" if assistant.assigned else "Unassigned"
            )
            self.assignment_combo = ttk.Combobox(
                content,
                textvariable=self.assignment_var,
                values=("Assigned", "Unassigned"),
                state="readonly",
                width=18,
            )
            self.assignment_combo.grid(
                row=row + 1, column=0, sticky="w", pady=(4, 0)
            )
            self.assignment_combo.bind(
                "<<ComboboxSelected>>", self._on_assignment_changed
            )
            row += 2

        self.error_label = ttk.Label(content, foreground="#b42318")
        self.error_label.grid(row=row, column=0, sticky="w", pady=(8, 0))
        buttons = ttk.Frame(content)
        buttons.grid(row=row + 1, column=0, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(buttons, text="Save", command=self._save).pack(side="right")
        self.bind("<Return>", lambda _event: self._save())
        self.bind("<Escape>", lambda _event: self.destroy())

        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _on_assignment_changed(self, _event: tk.Event) -> None:
        if not self.has_assignment:
            return
        if self.assignment_var.get() == "Unassigned":
            self.pending_timer = None
            self.error_label.configure(text="")
            return

        if not self.assignable_timers:
            self.assignment_var.set("Unassigned")
            self.pending_timer = None
            self.error_label.configure(text="No eligible timers are available.")
            return

        def assigned(timer: Timer) -> None:
            self.pending_timer = timer
            self.error_label.configure(text="")

        def cancelled() -> None:
            if self.pending_timer is None:
                self.assignment_var.set("Unassigned")

        AssignTimerDialog(
            self,
            self.assignable_timers,
            assigned,
            cancelled,
            self.assistant_name,
        )

    def _save(self) -> None:
        cooldown = self.assistant.cooldown
        if not self.is_clock_tower:
            try:
                cooldown = self._duration_from_fields(
                    tuple(variable.get().strip() for variable in self.time_vars)
                )
            except ValueError as error:
                self.error_label.configure(text=str(error))
                return

        active_duration_minutes: Optional[int] = None
        if self.is_clock_tower:
            duration_text = self.active_duration_var.get().strip()
            if not duration_text.isdecimal():
                self.error_label.configure(
                    text="Active duration must be a non-negative whole number of minutes."
                )
                return
            active_duration_minutes = int(duration_text)
            multiplier = 9
        else:
            multiplier_text = self.multiplier_var.get().strip()
            if not multiplier_text.isdecimal():
                self.error_label.configure(
                    text="Multiplier must be a non-negative integer."
                )
                return
            multiplier = int(multiplier_text)
        assigned = self.has_assignment and self.assignment_var.get() == "Assigned"
        if assigned and self.pending_timer is None:
            self.error_label.configure(text="Select a timer to assign.")
            return

        self.on_save(
            cooldown,
            self.active_var.get() == "Active",
            multiplier,
            assigned,
            self.pending_timer if assigned else None,
            active_duration_minutes,
        )
        self.destroy()
