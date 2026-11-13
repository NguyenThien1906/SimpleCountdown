from __future__ import annotations

from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, List, Optional, Tuple

from assets import (
    Account,
    Assistant,
    BuilderPotion,
    ClockTower,
    Helper,
    LabAssistant,
    Timer,
)
from controls import BuilderBaseControl, HomeVillageControl
from data import load_accounts
from dialogs import AssignTimerDialog, EditAssistantDialog, TimerEditor


class TimerUpdateController:
    """Advance timer and helper state and keep overview rows synchronized."""

    def __init__(self, overview: TimerApp) -> None:
        self.overview = overview

    def tick(self) -> None:
        overview = self.overview
        for _timer_id, timer in overview._timer_items:
            timer.advance()
        for (
            item_id,
            assistant,
            account,
            assistant_name,
            _eligible,
        ) in overview._assistant_items:
            previous_state = (
                assistant.active,
                getattr(assistant, "assigned", False),
                getattr(assistant, "assigned_timer", None),
            )
            if (
                not isinstance(assistant, ClockTower)
                and assistant.assigned_timer is not None
                and assistant.assigned_timer.value == 0
            ):
                assistant.assigned = False
                assistant.assigned_timer = None
                if assistant.active:
                    assistant.active = False
                    assistant.cooldown = assistant.inactive_cooldown
                self.sync_helper_timers(account, assistant)
                overview.tree.item(
                    item_id,
                    text=overview.timer_view.assistant_label(
                        assistant_name, assistant
                    ),
                    values=overview.timer_view.assistant_values(assistant),
                )
                continue
            if assistant.cooldown > 0:
                assistant.cooldown -= 1
                if assistant.cooldown == 0 and (
                    isinstance(assistant, ClockTower) or assistant.assigned
                ):
                    assistant.active = not assistant.active
                    assistant.cooldown = (
                        assistant.active_cooldown
                        if assistant.active
                        else assistant.inactive_cooldown
                    )
            current_state = (
                assistant.active,
                getattr(assistant, "assigned", False),
                getattr(assistant, "assigned_timer", None),
            )
            if current_state != previous_state:
                self.sync_helper_timers(account, assistant)
            overview.tree.item(
                item_id,
                text=overview.timer_view.assistant_label(
                    assistant_name, assistant
                ),
                values=overview.timer_view.assistant_values(assistant),
            )
        for account in overview.accounts:
            potion = account.builder_potion
            if not potion.active:
                continue
            potion.cooldown = max(0, potion.cooldown - 1)
            if potion.cooldown == 0:
                potion.active = False
                self.sync_helper_timers(account, potion)
        self.refresh_timer_end_times()
        self.refresh_collapsed_summaries()
        self.update_summary()
        overview.after(1000, self.tick)

    def refresh_timer_end_times(self) -> None:
        overview = self.overview
        now = datetime.now()
        for timer_id, timer in overview._timer_items:
            seconds_until_done = timer.actual_time_left
            end_time = now + timedelta(seconds=seconds_until_done)
            overview._end_times[timer_id] = end_time
            overview.tree.item(
                timer_id,
                values=overview.timer_view.timer_values(
                    timer, end_time, seconds_until_done
                ),
            )

    def sync_helper_timers(
        self, account: Account, helper: Helper, recalculate: bool = False
    ) -> None:
        for timer in account.timers:
            is_ongoing = any(
                existing is helper for existing in timer.ongoing_helpers
            )
            if isinstance(helper, Assistant):
                assigned = helper.assigned and helper.assigned_timer is timer
                active = assigned and helper.active
                should_recalculate = recalculate and (
                    assigned
                    or timer.assigned_assistant is helper
                    or is_ongoing
                )
            else:
                assigned = False
                if isinstance(helper, BuilderPotion):
                    affects_timer = (
                        timer.village == "Home Village"
                        and timer.category == "Building"
                    )
                else:
                    affects_timer = timer.village == "Builder Base"
                active = affects_timer and helper.active
                should_recalculate = recalculate and (
                    affects_timer and (active or is_ongoing)
                )
            timer.sync_helper(
                helper,
                assigned=assigned,
                active=active,
                recalculate=should_recalculate,
            )

    def on_tree_toggle(self, _event: tk.Event) -> None:
        self.overview.after_idle(self.refresh_collapsed_summaries)

    def refresh_collapsed_summaries(self) -> None:
        overview = self.overview
        for item_id, label, timers in overview._summary_items:
            is_open = overview.tree.item(item_id, "open")
            overview.tree.item(item_id, text=label)
            if not is_open and timers:
                shortest = min(timers, key=lambda timer: timer.value)
                overview.tree.item(
                    item_id,
                    values=overview.timer_view.timer_values(shortest),
                )
            else:
                overview.tree.item(item_id, values=("", "", "", ""))

    def update_summary(self) -> None:
        overview = self.overview
        running = sum(timer.value > 0 for _, timer in overview._timer_items)
        completed = len(overview._timer_items) - running
        overview._summary_label.configure(
            text=f"{running} running  ·  {completed} completed"
        )


class TimerMouseControls:
    """Handle tree mouse actions, context menus, and edit workflows."""

    def __init__(self, overview: TimerApp) -> None:
        self.overview = overview
        self._context_menu = tk.Menu(overview, tearoff=False)
        self._context_menu.add_command(label="Edit", command=self.edit_selected_timer)
        self._category_context_menu = tk.Menu(overview, tearoff=False)
        self._category_context_menu.add_command(
            label="Builder Potion", command=self.activate_builder_potion
        )

    def show_context_menu(self, event: tk.Event) -> None:
        overview = self.overview
        item_id = overview.tree.identify_row(event.y)
        if item_id in overview._building_category_accounts:
            account = overview._building_category_accounts[item_id]
            state = "disabled" if account.builder_potion.active else "normal"
            self._category_context_menu.entryconfigure(0, state=state)
            overview.tree.selection_set(item_id)
            self._category_context_menu.tk_popup(event.x_root, event.y_root)
            return
        if any(
            row_id == item_id
            for row_id, _assistant, _account, _name, _eligible
            in overview._assistant_items
        ):
            overview.tree.selection_set(item_id)
            self._context_menu.entryconfigure(
                0, label="Edit", command=self.edit_selected_assistant
            )
        elif any(
            timer_id == item_id for timer_id, _ in overview._timer_items
        ):
            overview.tree.selection_set(item_id)
            self._context_menu.entryconfigure(
                0, label="Edit", command=self.edit_selected_timer
            )
        else:
            return
        self._context_menu.tk_popup(event.x_root, event.y_root)

    def on_left_click(self, event: tk.Event) -> None:
        overview = self.overview
        item_id = overview.tree.identify_row(event.y)
        assistant_row = next(
            (
                (assistant, account, assistant_name, eligible)
                for row_id, assistant, account, assistant_name, eligible
                in overview._assistant_items
                if row_id == item_id
            ),
            None,
        )
        if assistant_row is None:
            return

        assistant, account, _assistant_name, eligible = assistant_row
        if isinstance(assistant, ClockTower):
            if assistant.active or assistant.cooldown != 0:
                return
            confirmed = messagebox.askyesno(
                "Activate Clock Tower",
                f"Activate Clock Tower for {account.name}?\n"
                f"It will boost all Builder Base timers for "
                f"{assistant.active_cooldown_minutes} minutes.",
                parent=overview.winfo_toplevel(),
            )
            if not confirmed:
                return
            assistant.active = True
            assistant.cooldown = assistant.active_cooldown
            overview._updates.sync_helper_timers(account, assistant)
            overview.timer_view.refresh_assistant_row(assistant)
            overview._updates.refresh_timer_end_times()
            overview._updates.refresh_collapsed_summaries()
            return

        if assistant.active or assistant.cooldown != 0 or assistant.assigned:
            return
        AssignTimerDialog(
            overview,
            eligible,
            lambda timer: self.assign_assistant(assistant, timer),
            assignment_scope=self._assignment_scope(assistant),
        )

    @staticmethod
    def _assignment_scope(assistant: Helper) -> str:
        if isinstance(assistant, ClockTower):
            return "Builder Base / Building or Lab"
        if isinstance(assistant, LabAssistant):
            return "Home Village / Lab"
        return "Home Village / Building"

    def assign_assistant(self, assistant: Helper, timer: Timer) -> None:
        overview = self.overview
        if assistant.active or assistant.cooldown != 0 or assistant.assigned:
            return
        assistant.assigned_timer = timer
        assistant.assigned = True
        assistant.active = True
        assistant.cooldown = assistant.active_cooldown
        assistant_row = next(
            (
                (account, helper)
                for _item_id, helper, account, _name, _eligible
                in overview._assistant_items
                if helper is assistant
            ),
            None,
        )
        if assistant_row is not None:
            overview._updates.sync_helper_timers(*assistant_row)
        overview.timer_view.refresh_assistant_row(assistant)
        overview._updates.refresh_timer_end_times()
        overview._updates.refresh_collapsed_summaries()

    def activate_builder_potion(self) -> None:
        overview = self.overview
        selection = overview.tree.selection()
        if not selection:
            return
        account = overview._building_category_accounts.get(selection[0])
        if account is None or account.builder_potion.active:
            return

        potion = account.builder_potion
        potion.active = True
        potion.cooldown = potion.active_cooldown
        overview._updates.sync_helper_timers(
            account, potion, recalculate=True
        )
        overview._updates.refresh_timer_end_times()
        overview._updates.refresh_collapsed_summaries()

    def edit_selected_assistant(self) -> None:
        overview = self.overview
        selection = overview.tree.selection()
        if not selection:
            return
        selected_id = selection[0]
        assistant_row = next(
            (
                (assistant, account, name, eligible)
                for item_id, assistant, account, name, eligible
                in overview._assistant_items
                if item_id == selected_id
            ),
            None,
        )
        if assistant_row is None:
            return

        assistant, account, assistant_name, eligible = assistant_row
        EditAssistantDialog(
            overview,
            account,
            assistant,
            assistant_name,
            eligible,
            lambda cooldown, active, multiplier, assigned, timer, active_minutes: (
                self.apply_assistant_edit(
                    selected_id,
                    assistant,
                    assistant_name,
                    cooldown,
                    active,
                    multiplier,
                    assigned,
                    timer,
                    active_minutes,
                )
            ),
        )

    def apply_assistant_edit(
        self,
        item_id: str,
        assistant: Any,
        assistant_name: str,
        cooldown: int,
        active: bool,
        multiplier: int,
        assigned: bool,
        timer: Optional[Timer],
        active_cooldown_minutes: Optional[int],
    ) -> None:
        overview = self.overview
        assistant.cooldown = cooldown
        assistant.active = active
        if isinstance(assistant, ClockTower):
            if active_cooldown_minutes is not None:
                assistant.active_cooldown_minutes = active_cooldown_minutes
            if assistant.active and active_cooldown_minutes is not None:
                assistant.cooldown = assistant.active_cooldown
        else:
            assistant.multiplier = multiplier
            assistant.assigned = assigned
            assistant.assigned_timer = timer if assigned else None
        assistant_row = next(
            (
                (account, row_assistant)
                for _row_id, row_assistant, account, _name, _eligible
                in overview._assistant_items
                if row_assistant is assistant
            ),
            None,
        )
        if assistant_row is not None:
            overview._updates.sync_helper_timers(
                *assistant_row, recalculate=True
            )
        overview.tree.item(
            item_id,
            text=overview.timer_view.assistant_label(
                assistant_name, assistant
            ),
            values=overview.timer_view.assistant_values(assistant),
        )
        overview._updates.refresh_timer_end_times()
        overview._updates.refresh_collapsed_summaries()

    def edit_selected_timer(self) -> None:
        overview = self.overview
        selection = overview.tree.selection()
        if not selection:
            return
        timer_id = selection[0]
        timer = next(
            (timer for item_id, timer in overview._timer_items if item_id == timer_id),
            None,
        )
        if timer is None:
            return
        TimerEditor(
            overview,
            timer,
            lambda name, remaining: self.apply_timer_edit(
                timer_id, timer, name, remaining
            ),
        )

    def apply_timer_edit(
        self, timer_id: str, timer: Timer, name: str, remaining: int
    ) -> None:
        overview = self.overview
        timer.name = name
        timer.value = remaining
        timer.recalculate_actual_time_left()
        overview._end_times[timer_id] = datetime.now() + timedelta(
            seconds=timer.actual_time_left
        )
        overview.tree.item(
            timer_id,
            text=timer.name,
            values=overview.timer_view.timer_values(
                timer, overview._end_times[timer_id]
            ),
        )
        overview._updates.refresh_timer_end_times()
        overview._updates.refresh_collapsed_summaries()
        overview._updates.update_summary()


class TimerTreeView(ttk.Frame):
    """Render timer, helper, and summary rows in the account tree."""

    def __init__(self, master: tk.Misc, app: TimerApp) -> None:
        super().__init__(master, style="Surface.TFrame", padding=1)
        self.app = app
        self._configure_styles()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            self,
            columns=("actual_time_left", "remaining", "ends_at", "resources"),
            show="tree headings",
            style="Timers.Treeview",
        )
        self.tree.heading("#0", text="ACCOUNT / TIMER", anchor="w")
        self.tree.heading("actual_time_left", text="ACTUAL TIME LEFT", anchor="e")
        self.tree.heading("remaining", text="TIME LEFT / COOLDOWN", anchor="e")
        self.tree.heading("ends_at", text="ENDS AT", anchor="w")
        self.tree.heading("resources", text="RESOURCES", anchor="w")
        self.tree.column("#0", anchor="w", stretch=True, minwidth=200)
        self.tree.column("actual_time_left", anchor="e", width=145, stretch=False)
        self.tree.column("remaining", anchor="e", width=150, stretch=False)
        self.tree.column("ends_at", anchor="w", width=125, stretch=False)
        self.tree.column("resources", anchor="w", width=110, stretch=False)
        self.tree.tag_configure(
            "account", font=("Segoe UI", 10, "bold"), foreground="#34405c"
        )
        self.tree.tag_configure(
            "category", font=("Segoe UI", 9, "bold"), foreground="#69758a"
        )
        self.tree.tag_configure(
            "apprentice", font=("Segoe UI", 9, "bold"), foreground="#4d5b78"
        )
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure("App.TFrame", background="#f3f5f9")
        style.configure("Surface.TFrame", background="#ffffff")
        style.configure(
            "Title.TLabel",
            background="#f3f5f9",
            foreground="#1c2538",
            font=("Segoe UI", 20, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background="#f3f5f9",
            foreground="#69758a",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Summary.TLabel",
            background="#f3f5f9",
            foreground="#69758a",
            font=("Segoe UI", 9),
        )
        style.configure(
            "Timers.Treeview",
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#364158",
            font=("Segoe UI", 10),
            rowheight=34,
            borderwidth=0,
        )
        style.configure(
            "Timers.Treeview.Heading",
            background="#f7f8fb",
            foreground="#7a8497",
            font=("Segoe UI", 8, "bold"),
            padding=(12, 10),
            relief="flat",
        )
        style.map(
            "Timers.Treeview",
            background=[("selected", "#e7ebfa")],
            foreground=[("selected", "#26365f")],
        )
        style.map(
            "Timers.Treeview.Heading",
            background=[("active", "#f0f2f7")],
        )

    def add_timer_row(self, parent_id: str, timer: Timer) -> None:
        app = self.app
        seconds_until_done = timer.actual_time_left
        end_time = datetime.now() + timedelta(seconds=seconds_until_done)
        timer_id = self.tree.insert(
            parent_id,
            "end",
            text=timer.name,
            values=self.timer_values(timer, end_time, seconds_until_done),
        )
        app._timer_items.append((timer_id, timer))
        app._end_times[timer_id] = end_time

    def add_assistant_row(
        self,
        parent_id: str,
        account: Account,
        assistant: Any,
        assistant_name: str,
        assignable_timers: List[Timer],
    ) -> None:
        item_id = self.tree.insert(
            parent_id,
            "end",
            text=self.assistant_label(assistant_name, assistant),
            values=self.assistant_values(assistant),
            tags=("apprentice",),
        )
        self.app._assistant_items.append(
            (item_id, assistant, account, assistant_name, assignable_timers)
        )

    def refresh_assistant_row(self, assistant: Any) -> None:
        for (
            item_id,
            row_assistant,
            _account,
            assistant_name,
            _eligible,
        ) in self.app._assistant_items:
            if row_assistant is assistant:
                self.tree.item(
                    item_id,
                    text=self.assistant_label(assistant_name, assistant),
                    values=self.assistant_values(assistant),
                )
                break

    @staticmethod
    def format_time(seconds: int) -> str:
        days, remainder = divmod(seconds, 24 * 60 * 60)
        hours, remainder = divmod(remainder, 60 * 60)
        minutes, seconds = divmod(remainder, 60)
        time = f"{hours:02}:{minutes:02}:{seconds:02}"
        return f"{days}d {time}" if days else time

    @staticmethod
    def format_end_at(end_time: datetime) -> str:
        return end_time.strftime("%d/%m %H:%M")

    def timer_values(
        self,
        timer: Timer,
        end_time: Optional[datetime] = None,
        actual_time_left: Optional[int] = None,
    ) -> Tuple[str, str, str, str]:
        if actual_time_left is None:
            actual_time_left = timer.actual_time_left
        if end_time is None:
            end_time = datetime.now() + timedelta(seconds=actual_time_left)
        return (
            self.format_time(actual_time_left),
            self.format_time(timer.value),
            self.format_end_at(end_time),
            "",
        )

    @staticmethod
    def assistant_label(assistant_name: str, assistant: Any) -> str:
        status = "Active" if assistant.active else "Inactive"
        multiplier = (
            str(int(assistant.multiplier))
            if assistant.multiplier == int(assistant.multiplier)
            else str(assistant.multiplier)
        )
        if isinstance(assistant, ClockTower):
            return f"{assistant_name} ({status}, {multiplier}x)"
        assignment = "Assigned" if assistant.assigned else "Unassigned"
        return f"{assistant_name} ({status}, {assignment}, {multiplier}x)"

    def assistant_values(self, assistant: Any) -> Tuple[str, str, str, str]:
        return (
            "",
            self.format_time(assistant.cooldown),
            "",
            "",
        )


class TimerApp(ttk.Frame):
    """Display every timer grouped under its account."""

    def __init__(
        self,
        master: tk.Misc,
        accounts: Optional[List[Account]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        self.accounts = load_accounts() if accounts is None else accounts
        self._timer_items: List[Tuple[str, Timer]] = []
        self._summary_items: List[Tuple[str, str, List[Timer]]] = []
        self._end_times: dict[str, datetime] = {}
        self._assistant_items: List[Tuple[str, Any, Account, str, List[Timer]]] = []
        self._building_category_accounts: dict[str, Account] = {}
        self._updates = TimerUpdateController(self)
        self._mouse_controls = TimerMouseControls(self)

        self.configure(style="App.TFrame", padding=(24, 20))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Account timers", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="A live overview of every upgrade.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.timer_view = TimerTreeView(self, self)
        self.timer_view.grid(row=1, column=0, sticky="nsew")
        self.tree = self.timer_view.tree

        footer = ttk.Frame(self, style="App.TFrame")
        footer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self._summary_label = ttk.Label(footer, style="Summary.TLabel")
        self._summary_label.pack(side="left")

        self._populate()
        self.tree.bind("<<TreeviewOpen>>", self._updates.on_tree_toggle)
        self.tree.bind("<<TreeviewClose>>", self._updates.on_tree_toggle)
        self.tree.bind("<Button-3>", self._mouse_controls.show_context_menu)
        self.tree.bind("<Button-1>", self._mouse_controls.on_left_click, add="+")
        self._updates.update_summary()
        self.after(1000, self._updates.tick)

    def _populate(self) -> None:
        for account in self.accounts:
            for helper in (
                account.builder_apprentice,
                account.lab_assistant,
                account.clock_tower,
                account.builder_potion,
            ):
                self._updates.sync_helper_timers(account, helper)
            account_id = self.tree.insert(
                "", "end", text=account.name, open=True, tags=("account",)
            )
            self._summary_items.append((account_id, account.name, account.timers))
            HomeVillageControl().populate(self, account, account_id)
            BuilderBaseControl().populate(self, account, account_id)
        self._updates.refresh_collapsed_summaries()


TimerOverview = TimerApp


def main() -> None:
    root = tk.Tk()
    root.title("Account Timers")
    root.geometry("1000x500")
    root.minsize(900, 360)
    root.configure(background="#f3f5f9")

    app = TimerApp(root)
    app.pack(fill="both", expand=True)

    root.mainloop()


if __name__ == "__main__":
    main()