from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, List, Optional

from assets import Account


class GlobalFeatures(ttk.Frame):
    """Provide account sorting and tree collapse controls."""

    def __init__(
        self,
        master: tk.Misc,
        app: Any,
        collapse_level: str = "None",
        village_filter: str = "Both",
    ) -> None:
        super().__init__(master, style="App.TFrame")
        self.app = app
        if collapse_level not in TreeCollapseControl.LEVELS:
            raise ValueError(f"Unknown collapse level: {collapse_level!r}")
        if village_filter not in VillageFilterControl.FILTERS:
            raise ValueError(f"Unknown village filter: {village_filter!r}")
        self.collapse_level = tk.StringVar(self, value=collapse_level)
        self.village_filter = tk.StringVar(self, value=village_filter)

        ttk.Label(self, text="Collapse:", style="Summary.TLabel").pack(
            side="left", padx=(0, 8)
        )
        collapse_menu = ttk.Menubutton(
            self,
            textvariable=self.collapse_level,
            width=15,
        )
        collapse_options = tk.Menu(collapse_menu, tearoff=False)
        collapse_options.add_command(
            label="None",
            command=lambda: self._select_collapse_level("None"),
        )
        collapse_options.add_separator()
        for level in ("Account", "Village", "Upgrade Type"):
            collapse_options.add_command(
                label=level,
                command=lambda selected=level: self._select_collapse_level(
                    selected
                ),
            )
        collapse_menu.configure(menu=collapse_options)
        collapse_menu.pack(side="left")

        self._sort_button = ttk.Button(
            self,
            text="Sort",
        )
        self._sort_control = AccountSortControl(app, self._sort_button)
        self._collapse_control = TreeCollapseControl(app)
        self._sort_button.configure(command=self._sort_control.sort_accounts)
        ttk.Label(self, text="Village:", style="Summary.TLabel").pack(
            side="left", padx=(16, 8)
        )
        village_menu = ttk.Menubutton(
            self,
            textvariable=self.village_filter,
            width=15,
        )
        village_options = tk.Menu(village_menu, tearoff=False)
        village_options.add_command(
            label="Both",
            command=lambda: self._select_village("Both"),
        )
        village_options.add_separator()
        for village in ("Home Village", "Builder Base"):
            village_options.add_command(
                label=village,
                command=lambda selected=village: self._select_village(selected),
            )
        village_menu.configure(menu=village_options)
        village_menu.pack(side="left")
        self._village_filter_control = VillageFilterControl(app)
        self._sort_button.pack(side="left", padx=(16, 8))
        ttk.Button(
            self,
            text="Reset Filters",
            command=self.reset_filters,
        ).pack(side="left")

    def reset_filters(self) -> None:
        self.collapse_level.set("None")
        self.village_filter.set("Both")
        self._village_filter_control.show_village(self.village_filter.get())
        self._collapse_control.collapse_to_level(self.collapse_level.get())
        self._sort_control.reset_order()
        self.app._updates.refresh_display()

    def _select_collapse_level(self, level: str) -> None:
        self.collapse_level.set(level)
        self._collapse_control.collapse_to_level(self.collapse_level.get())
        self.app._updates.refresh_display()

    def _select_village(self, village: str) -> None:
        self.village_filter.set(village)
        self._village_filter_control.show_village(self.village_filter.get())
        self._sort_control.resort_if_active()
        self.app._updates.refresh_display()

    def apply_village_filter(self) -> None:
        self._village_filter_control.show_village(self.village_filter.get())
        self._collapse_control.collapse_to_level(self.collapse_level.get())
        self._sort_control.resort_if_active()
        self.app._updates.refresh_display()

    def visible_timers(self, timers: List[Any]) -> List[Any]:
        return self._village_filter_control.visible_timers(
            timers, self.village_filter.get()
        )


class AccountSortControl:
    """Sort accounts by their shortest timer and restore their prior order."""

    def __init__(self, app: Any, button: ttk.Button) -> None:
        self.app = app
        self.button = button
        self._original_account_order: Optional[List[Account]] = None

    def sort_accounts(self) -> None:
        if self._original_account_order is None:
            self.ensure_sorted()
            return

        self.reset_order()

    def reset_order(self) -> None:
        if self._original_account_order is None:
            self.button.configure(text="Sort")
            return

        current_account_ids = {id(account) for account in self.app.accounts}
        ordered_accounts = [
            account
            for account in self._original_account_order
            if id(account) in current_account_ids
        ]
        original_account_ids = {
            id(account) for account in self._original_account_order
        }
        ordered_accounts.extend(
            account
            for account in self.app.accounts
            if id(account) not in original_account_ids
        )
        self._original_account_order = None
        self.button.configure(text="Sort")
        self._move_accounts(ordered_accounts)

    def ensure_sorted(self) -> None:
        if self._original_account_order is None:
            self._original_account_order = self.app.accounts.copy()
        ordered_accounts = sorted(
            self.app.accounts,
            key=lambda account: min(
                (
                    timer.actual_time_left
                    for timer in self.app.global_features.visible_timers(
                        account.timers
                    )
                ),
                default=float("inf"),
            ),
        )
        self.button.configure(text="Restore")
        self._move_accounts(ordered_accounts)

    def resort_if_active(self) -> None:
        if self._original_account_order is not None:
            self.ensure_sorted()

    def _move_accounts(self, accounts: List[Account]) -> None:
        for destination, account in enumerate(accounts):
            self.app.move_account(account, destination)


class TreeCollapseControl:
    """Collapse account-tree rows to a selected hierarchy level."""

    LEVELS = ("None", "Account", "Village", "Upgrade Type")

    def __init__(self, app: Any) -> None:
        self.app = app

    def collapse_to_level(self, level: str) -> None:
        if level not in self.LEVELS:
            raise ValueError(f"Unknown collapse level: {level!r}")

        for account in self.app.accounts:
            account_id = self.app._account_rows.get(id(account))
            if account_id is None:
                continue
            self.app.tree.item(account_id, open=level != "Account")
            for village_id in self.app.tree.get_children(account_id):
                self.app.tree.item(
                    village_id, open=level in ("None", "Upgrade Type")
                )
                if level in ("None", "Upgrade Type"):
                    for category_id in self.app.tree.get_children(village_id):
                        if category_id in self.app._timer_list_categories:
                            self.app.tree.item(category_id, open=level == "None")


class VillageFilterControl:
    """Show one village's tree rows or both villages."""

    VILLAGES = ("Home Village", "Builder Base")
    FILTERS = (*VILLAGES, "Both")

    def __init__(self, app: Any) -> None:
        self.app = app

    def show_village(self, village: str) -> None:
        if village not in self.FILTERS:
            raise ValueError(f"Unknown village filter: {village!r}")

        for account in self.app.accounts:
            account_key = id(account)
            account_id = self.app._account_rows.get(account_key)
            if account_id is None:
                continue
            for index, village_name in enumerate(self.VILLAGES):
                village_id = self.app._village_rows.get(
                    (account_key, village_name)
                )
                if village_id is None:
                    continue
                should_show = village == "Both" or village == village_name
                is_attached = village_id in self.app.tree.get_children(account_id)
                if should_show:
                    self.app.tree.move(village_id, account_id, index)
                elif is_attached:
                    self.app.tree.detach(village_id)

    def visible_timers(self, timers: List[Any], village: str) -> List[Any]:
        if village not in self.FILTERS:
            raise ValueError(f"Unknown village filter: {village!r}")
        if village == "Both":
            return list(timers)
        return [timer for timer in timers if timer.village == village]
