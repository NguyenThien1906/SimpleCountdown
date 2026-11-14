from __future__ import annotations

from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk
from typing import Any, List, Optional, Tuple

from app_behavior import TimerMouseControls, TimerUpdateController
from assets import Account, ClockTower, Helper, Timer
from data import load_accounts
from timer_behavior import BuilderBaseControl, HomeVillageControl


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

    def add_potion_row(
        self, parent_id: str, potion: Helper, potion_name: str
    ) -> str:
        item_id = self.tree.insert(
            parent_id,
            0,
            text=self.potion_label(potion, potion_name),
            values=self.assistant_values(potion),
            tags=("apprentice",),
        )
        return item_id

    def refresh_potion_row(self, potion: Helper, potion_name: str) -> None:
        item_id = self.app._potion_rows.get(id(potion))
        if item_id is not None:
            self.tree.item(
                item_id,
                text=self.potion_label(potion, potion_name),
                values=self.assistant_values(potion),
            )

    def remove_potion_row(self, potion: Helper) -> None:
        item_id = self.app._potion_rows.pop(id(potion), None)
        if item_id is not None:
            self.tree.delete(item_id)

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

    @staticmethod
    def potion_label(potion: Helper, potion_name: str) -> str:
        status = "Active" if potion.active else "Inactive"
        return f"{potion_name} ({status}, {potion.multiplier}x)"

    def assistant_values(self, assistant: Any) -> Tuple[str, str, str, str]:
        return (
            "",
            self.format_time(assistant.cooldown),
            "",
            "",
        )


class TimerApp(ttk.Frame):
    """App displays timers and stuff from each account."""

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
        self._lab_category_accounts: dict[str, Account] = {}
        self._pet_category_accounts: dict[str, Account] = {}
        self._potion_rows: dict[int, str] = {}
        self._updates = TimerUpdateController(self)
        self._mouse_controls = TimerMouseControls(self)

        # app configuration
        self.configure(style="App.TFrame", padding=(24, 20)) # overall frame design
        # allow contents of the frame (content table) to stretch
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1) # row 0 is the header, row 1 is the content table

        # content layout
        self.timer_view = TimerTreeView(self, self)
        self.timer_view.grid(row=0, column=0, sticky="nsew")
        self.tree = self.timer_view.tree

        footer = ttk.Frame(self, style="App.TFrame")
        footer.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        self._summary_label = ttk.Label(footer, style="Summary.TLabel")
        self._summary_label.pack(side="left")

        # content view
        self._populate()
        self.tree.bind("<<TreeviewOpen>>", self._updates.on_tree_toggle)
        self.tree.bind("<<TreeviewClose>>", self._updates.on_tree_toggle)
        self.tree.bind("<Button-3>", self._mouse_controls.show_context_menu) # right click
        self.tree.bind("<Button-1>", self._mouse_controls.on_left_click, add="+") # left click
        self._updates.update_summary()
        self.after(1000, self._updates.tick)

    def _populate(self) -> None:
        for account in self.accounts:
            for helper in (
                account.builder_apprentice,
                account.lab_assistant,
                account.clock_tower,
                account.builder_potion,
                account.lab_potion,
                account.pet_potion,
            ):
                self._updates.sync_helper_timers(account, helper)
            account_id = self.tree.insert(
                "", "end", text=account.name, open=True, tags=("account",)
            )
            self._summary_items.append((account_id, account.name, account.timers))
            HomeVillageControl().populate(self, account, account_id)
            BuilderBaseControl().populate(self, account, account_id)
            for (
                category_id,
                category_account,
            ) in self._building_category_accounts.items():
                if category_account is account and account.builder_potion.active:
                    self._mouse_controls.potions.show_potion_row(
                        account.builder_potion, category_id, "Builder Potion"
                    )
            for (
                category_id,
                category_account,
            ) in self._lab_category_accounts.items():
                if category_account is account and account.lab_potion.active:
                    self._mouse_controls.potions.show_potion_row(
                        account.lab_potion, category_id, "Lab Potion"
                    )
            for (
                category_id,
                category_account,
            ) in self._pet_category_accounts.items():
                if category_account is account and account.pet_potion.active:
                    self._mouse_controls.potions.show_potion_row(
                        account.pet_potion, category_id, "Pet Potion"
                    )
        self._updates.refresh_collapsed_summaries()

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