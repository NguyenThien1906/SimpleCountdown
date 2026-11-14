from __future__ import annotations

from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, List, Optional, Tuple

from app_behavior import TimerMouseControls, TimerUpdateController
from assets import Account, ClockTower, Helper, Timer
from data import load_accounts, load_accounts_from_records, save_accounts
from data_translation import extract_timers_from_json
from global_features import GlobalFeatures
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
        self.tree.tag_configure(
            "timer_under_24h", foreground="#881337", background="#fff1f2"
        )
        self.tree.tag_configure(
            "timer_under_6h", foreground="#881337", background="#ffe4e6"
        )
        self.tree.tag_configure(
            "timer_under_1h", foreground="#881337", background="#fecdd3"
        )
        self.tree.tag_configure(
            "timer_under_15m", foreground="#4c0519", background="#fda4af"
        )
        self.tree.tag_configure(
            "timer_under_5m", foreground="#4c0519", background="#fb7185"
        )
        self.tree.tag_configure(
            "timer_complete", foreground="#ffffff", background="#dc2626"
        )
        self.tree.tag_configure(
            "timer_complete_flash_on",
            foreground="#ffffff",
            background="#991b1b",
        )
        self.tree.tag_configure(
            "timer_complete_flash_off",
            foreground="#713f12",
            background="#fef08a",
        )
        self.tree.tag_configure(
            "timer_summary_under_24h",
            font=("Segoe UI", 9, "bold"),
            foreground="#111827",
            background="#fff1f2",
        )
        self.tree.tag_configure(
            "timer_summary_under_6h",
            font=("Segoe UI", 9, "bold"),
            foreground="#111827",
            background="#ffe4e6",
        )
        self.tree.tag_configure(
            "timer_summary_under_1h",
            font=("Segoe UI", 9, "bold"),
            foreground="#111827",
            background="#fecdd3",
        )
        self.tree.tag_configure(
            "timer_summary_under_15m",
            font=("Segoe UI", 9, "bold"),
            foreground="#111827",
            background="#fda4af",
        )
        self.tree.tag_configure(
            "timer_summary_under_5m",
            font=("Segoe UI", 9, "bold"),
            foreground="#111827",
            background="#fb7185",
        )
        self.tree.tag_configure(
            "timer_summary_complete",
            font=("Segoe UI", 9, "bold"),
            foreground="#ffffff",
            background="#b91c1c",
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
            tags=self.timer_tags(seconds_until_done),
        )
        app._timer_items.append((timer_id, timer))
        app._end_times[timer_id] = end_time

    @staticmethod
    def timer_tags(seconds_until_done: int) -> Tuple[str, ...]:
        if seconds_until_done <= 0:
            return ("timer_complete",)
        if seconds_until_done <= 5 * 60:
            return ("timer_under_5m",)
        if seconds_until_done <= 15 * 60:
            return ("timer_under_15m",)
        if seconds_until_done <= 60 * 60:
            return ("timer_under_1h",)
        if seconds_until_done <= 6 * 60 * 60:
            return ("timer_under_6h",)
        if seconds_until_done <= 24 * 60 * 60:
            return ("timer_under_24h",)
        return ()

    @staticmethod
    def timer_summary_tags(seconds_until_done: int) -> Tuple[str, ...]:
        timer_tag = TimerTreeView.timer_tags(seconds_until_done)
        if not timer_tag:
            return ()
        return (timer_tag[0].replace("timer_", "timer_summary_", 1),)

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
        self._save_error_shown = False
        self._save_after_id: Optional[str] = None
        self._account_rows: dict[int, str] = {}
        self._timer_items: List[Tuple[str, Timer]] = []
        self._summary_items: List[Tuple[str, str, List[Timer]]] = []
        self._end_times: dict[str, datetime] = {}
        self._assistant_items: List[Tuple[str, Any, Account, str, List[Timer]]] = []
        self._building_category_accounts: dict[str, Account] = {}
        self._lab_category_accounts: dict[str, Account] = {}
        self._pet_category_accounts: dict[str, Account] = {}
        self._timer_list_categories: dict[str, Tuple[Account, str, str]] = {}
        self._village_rows: dict[Tuple[int, str], str] = {}
        self._potion_rows: dict[int, str] = {}
        self._updates = TimerUpdateController(self)
        self._mouse_controls = TimerMouseControls(self)

        # app configuration
        self.configure(style="App.TFrame", padding=(24, 20)) # overall frame design
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # content layout
        self.global_features = GlobalFeatures(self, self)
        self.global_features.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.timer_view = TimerTreeView(self, self)
        self.timer_view.grid(row=1, column=0, sticky="nsew")
        self.tree = self.timer_view.tree

        footer = ttk.Frame(self, style="App.TFrame")
        footer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self._summary_label = ttk.Label(footer, style="Summary.TLabel")
        self._summary_label.pack(side="left")

        # content view
        self._populate()
        self.tree.bind("<<TreeviewOpen>>", self._updates.on_tree_toggle)
        self.tree.bind("<<TreeviewClose>>", self._updates.on_tree_toggle)
        self.tree.bind("<Button-3>", self._mouse_controls.show_context_menu) # right click
        self.tree.bind("<Button-1>", self._updates.on_tree_click, add="+")
        self.tree.bind("<Button-1>", self._mouse_controls.on_left_click, add="+") # left click
        self.bind_all("<Button-1>", self._on_application_click, add="+")
        self.winfo_toplevel().bind(
            "<FocusOut>", self._on_application_focus_out, add="+"
        )
        self._updates.update_summary()
        self.after(1000, self._updates.tick)
        self._schedule_periodic_save()

    def persist_accounts(self) -> None:
        try:
            save_accounts(self.accounts)
        except OSError as error:
            if not self._save_error_shown:
                messagebox.showerror(
                    "Unable to save timers",
                    f"The timer data could not be saved:\n{error}",
                    parent=self.winfo_toplevel(),
                )
                self._save_error_shown = True
        else:
            self._save_error_shown = False

    def _schedule_periodic_save(self) -> None:
        self._save_after_id = self.after(10_000, self._periodic_save)

    def _periodic_save(self) -> None:
        self._save_after_id = None
        self.persist_accounts()
        self._schedule_periodic_save()

    def close(self) -> None:
        if self._save_after_id is not None:
            self.after_cancel(self._save_after_id)
            self._save_after_id = None
        self.persist_accounts()
        self.winfo_toplevel().destroy()

    def _on_application_click(self, event: tk.Event) -> None:
        if event.widget is not self.tree:
            self._clear_tree_selection()

    def _on_application_focus_out(self, _event: tk.Event) -> None:
        self.after_idle(self._clear_selection_if_focus_left_application)

    def _clear_selection_if_focus_left_application(self) -> None:
        focused_widget = self.focus_get()
        if (
            focused_widget is None
            or focused_widget.winfo_toplevel() is not self.winfo_toplevel()
        ):
            self._clear_tree_selection()

    def _clear_tree_selection(self) -> None:
        selection = self.tree.selection()
        if selection:
            self.tree.selection_remove(*selection)

    def _populate(self) -> None:
        for account in self.accounts:
            self._populate_account(account)
        self._updates.refresh_collapsed_summaries()

    def _populate_account(self, account: Account) -> None:
        for helper in (
            account.builder_apprentice,
            account.lab_assistant,
            account.clock_tower,
            account.builder_potion,
            account.builder_bite,
            account.lab_potion,
            account.study_soup,
            account.pet_potion,
        ):
            self._updates.sync_helper_timers(account, helper)
        account_id = self.tree.insert(
            "", "end", text=account.name, open=True, tags=("account",)
        )
        self._account_rows[id(account)] = account_id
        self._summary_items.append((account_id, account.name, account.timers))
        home_village_id = HomeVillageControl().populate(self, account, account_id)
        self._village_rows[(id(account), "Home Village")] = home_village_id
        builder_base_id = BuilderBaseControl().populate(self, account, account_id)
        self._village_rows[(id(account), "Builder Base")] = builder_base_id
        for (
            category_id,
            category_account,
        ) in self._building_category_accounts.items():
            if category_account is account:
                for boost, boost_name in (
                    (account.builder_potion, "Builder Potion"),
                    (account.builder_bite, "Builder Bite"),
                ):
                    if boost.active:
                        self._mouse_controls.potions.show_potion_row(
                            boost, category_id, boost_name
                        )
        for (
            category_id,
            category_account,
        ) in self._lab_category_accounts.items():
            if category_account is account:
                for boost, boost_name in (
                    (account.lab_potion, "Lab Potion"),
                    (account.study_soup, "Study Soup"),
                ):
                    if boost.active:
                        self._mouse_controls.potions.show_potion_row(
                            boost, category_id, boost_name
                        )
        for (
            category_id,
            category_account,
        ) in self._pet_category_accounts.items():
            if category_account is account and account.pet_potion.active:
                self._mouse_controls.potions.show_potion_row(
                    account.pet_potion, category_id, "Pet Potion"
                )
        self.global_features.apply_village_filter()
        self._updates.refresh_collapsed_summaries()

    def add_account(self, name: str) -> Account:
        account = Account(name=name)
        self.accounts.append(account)
        self._populate_account(account)
        self._updates.update_summary()
        return account

    def import_account_json(self, account: Account, raw_text: str) -> None:
        record = extract_timers_from_json(raw_text)[0]
        record["name"] = account.name
        replacement = load_accounts_from_records([record])[0]

        account_index = self.accounts.index(account)
        updated_accounts = list(self.accounts)
        updated_accounts[account_index] = replacement
        save_accounts(updated_accounts)

        self.remove_account(account)
        self.accounts.insert(account_index, replacement)
        self._populate_account(replacement)
        self.tree.move(
            self._account_rows[id(replacement)], "", account_index
        )
        self._updates.update_summary()

    def move_account(self, account: Account, destination: int) -> None:
        current = self.accounts.index(account)
        if not 0 <= destination < len(self.accounts):
            raise IndexError("Account destination is outside the account list.")
        if current == destination:
            return
        self.accounts.pop(current)
        self.accounts.insert(destination, account)
        self.tree.move(self._account_rows[id(account)], "", destination)

    def remove_account(self, account: Account) -> None:
        account_id = self._account_rows.pop(id(account))
        account_timer_ids = {id(timer) for timer in account.timers}
        descendant_ids: set[str] = set()
        pending = list(self.tree.get_children(account_id))
        while pending:
            item_id = pending.pop()
            descendant_ids.add(item_id)
            pending.extend(self.tree.get_children(item_id))
        account_village_rows = [
            (village_name, village_id)
            for (account_id_key, village_name), village_id
            in self._village_rows.items()
            if account_id_key == id(account)
        ]
        for village_name, village_id in account_village_rows:
            if village_id not in self.tree.get_children(account_id):
                pending = [village_id]
                while pending:
                    item_id = pending.pop()
                    descendant_ids.add(item_id)
                    pending.extend(self.tree.get_children(item_id))
                self.tree.delete(village_id)
            self._village_rows.pop((id(account), village_name), None)
        descendant_ids.add(account_id)

        self.tree.delete(account_id)
        timer_ids = {
            item_id
            for item_id, timer in self._timer_items
            if id(timer) in account_timer_ids
        }
        self._timer_items = [
            (item_id, timer)
            for item_id, timer in self._timer_items
            if id(timer) not in account_timer_ids
        ]
        for timer_id in timer_ids:
            self._end_times.pop(timer_id, None)
        self._assistant_items = [
            item
            for item in self._assistant_items
            if item[2] is not account
        ]
        self._summary_items = [
            item for item in self._summary_items if item[0] not in descendant_ids
        ]
        for category_accounts in (
            self._building_category_accounts,
            self._lab_category_accounts,
            self._pet_category_accounts,
        ):
            for category_id, category_account in list(category_accounts.items()):
                if category_account is account:
                    del category_accounts[category_id]
        for category_id, category in list(self._timer_list_categories.items()):
            if category[0] is account:
                del self._timer_list_categories[category_id]
        for potion in (
            account.builder_potion,
            account.builder_bite,
            account.lab_potion,
            account.study_soup,
            account.pet_potion,
        ):
            self._potion_rows.pop(id(potion), None)
        self.accounts.remove(account)
        self._updates.refresh_collapsed_summaries()
        self._updates.update_summary()

def main() -> None:
    root = tk.Tk()
    root.title("Account Timers")
    root.geometry("1000x500")
    root.minsize(900, 360)
    root.configure(background="#f3f5f9")

    app = TimerApp(root)
    app.pack(fill="both", expand=True)

    root.protocol("WM_DELETE_WINDOW", app.close)

    root.mainloop()


if __name__ == "__main__":
    main()