from __future__ import annotations

from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox
from typing import Any, List, Optional, Tuple

from assets import (
    Account,
    Assistant,
    BuilderPotion,
    ClockTower,
    Helper,
    LabPotion,
    LabAssistant,
    PetPotion,
    Timer,
)
from dialogs import AssignTimerDialog, EditAssistantDialog, TimerEditor


class TimerUpdateController:
    """Advance timer and helper state and keep overview rows synchronized."""

    def __init__(self, overview) -> None:
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
            for potion, potion_name in (
                (account.builder_potion, "Builder Potion"),
                (account.lab_potion, "Lab Potion"),
                (account.pet_potion, "Pet Potion"),
            ):
                was_active = potion.active
                if was_active:
                    potion.cooldown = max(0, potion.cooldown - 1)
                    if potion.cooldown == 0:
                        potion.active = False

                if potion.cooldown == 0 or not potion.active:
                    has_ongoing_effect = any(
                        any(helper is potion for helper in timer.ongoing_helpers)
                        for timer in account.timers
                    )
                    if was_active or has_ongoing_effect:
                        self.sync_helper_timers(account, potion)
                    overview.timer_view.remove_potion_row(potion)
                else:
                    overview.timer_view.refresh_potion_row(potion, potion_name)
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
                elif isinstance(helper, LabPotion):
                    affects_timer = (
                        timer.village == "Home Village"
                        and timer.category == "Lab"
                    )
                elif isinstance(helper, PetPotion):
                    affects_timer = (
                        timer.village == "Home Village"
                        and timer.category == "Pet"
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
    """Route tree mouse actions to focused behavior controllers."""

    def __init__(self, overview) -> None:
        self.overview = overview
        self.assistants = AssistantControls(overview)
        self.potions = PotionControls(overview)
        self._context_menu = tk.Menu(overview, tearoff=False)
        self._context_menu.add_command(label="Edit", command=self.edit_selected_timer)
        self._category_context_menu = tk.Menu(overview, tearoff=False)
        self._category_context_menu.add_command(
            label="Builder Potion", command=self.potions.activate_builder_potion
        )
        self._lab_context_menu = tk.Menu(overview, tearoff=False)
        self._lab_context_menu.add_command(
            label="Lab Potion", command=self.potions.activate_lab_potion
        )
        self._pet_context_menu = tk.Menu(overview, tearoff=False)
        self._pet_context_menu.add_command(
            label="Pet Potion", command=self.potions.activate_pet_potion
        )

    def show_context_menu(self, event: tk.Event) -> None:
        overview = self.overview
        item_id = overview.tree.identify_row(event.y)
        if item_id in overview._building_category_accounts:
            overview.tree.selection_set(item_id)
            self._category_context_menu.tk_popup(event.x_root, event.y_root)
            return
        if item_id in overview._lab_category_accounts:
            overview.tree.selection_set(item_id)
            self._lab_context_menu.tk_popup(event.x_root, event.y_root)
            return
        if item_id in overview._pet_category_accounts:
            overview.tree.selection_set(item_id)
            self._pet_context_menu.tk_popup(event.x_root, event.y_root)
            return
        if any(
            row_id == item_id
            for row_id, _assistant, _account, _name, _eligible
            in overview._assistant_items
        ):
            overview.tree.selection_set(item_id)
            self._context_menu.entryconfigure(
                0, label="Edit", command=self.assistants.edit_selected_assistant
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
        self.assistants.on_left_click(event)

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


class AssistantControls:
    """Handle assistant activation, assignment, and editing."""

    def __init__(self, overview) -> None:
        self.overview = overview

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


class PotionControls:
    """Handle Builder Potion and Lab Potion activation and rows."""

    def __init__(self, overview) -> None:
        self.overview = overview

    def activate_builder_potion(self) -> None:
        overview = self.overview
        selection = overview.tree.selection()
        if not selection:
            return
        account = overview._building_category_accounts.get(selection[0])
        if account is None:
            return

        potion = account.builder_potion
        potion.active = True
        potion.cooldown += potion.active_cooldown
        self.show_potion_row(potion, selection[0], "Builder Potion")
        overview._updates.sync_helper_timers(
            account, potion, recalculate=True
        )
        overview._updates.refresh_timer_end_times()
        overview._updates.refresh_collapsed_summaries()

    def activate_lab_potion(self) -> None:
        overview = self.overview
        selection = overview.tree.selection()
        if not selection:
            return
        account = overview._lab_category_accounts.get(selection[0])
        if account is None:
            return

        potion = account.lab_potion
        potion.active = True
        potion.cooldown += potion.active_cooldown
        self.show_potion_row(potion, selection[0], "Lab Potion")
        overview._updates.sync_helper_timers(account, potion, recalculate=True)
        overview._updates.refresh_timer_end_times()
        overview._updates.refresh_collapsed_summaries()

    def activate_pet_potion(self) -> None:
        overview = self.overview
        selection = overview.tree.selection()
        if not selection:
            return
        account = overview._pet_category_accounts.get(selection[0])
        if account is None:
            return

        potion = account.pet_potion
        potion.active = True
        potion.cooldown += potion.active_cooldown
        self.show_potion_row(potion, selection[0], "Pet Potion")
        overview._updates.sync_helper_timers(account, potion, recalculate=True)
        overview._updates.refresh_timer_end_times()
        overview._updates.refresh_collapsed_summaries()

    def show_potion_row(
        self, potion: Helper, category_id: str, potion_name: str
    ) -> None:
        overview = self.overview
        potion_key = id(potion)
        potion_row = overview._potion_rows.get(potion_key)
        if potion_row is None:
            potion_row = overview.timer_view.add_potion_row(
                category_id, potion, potion_name
            )
            overview._potion_rows[potion_key] = potion_row
        else:
            overview.tree.move(potion_row, category_id, 0)
            overview.timer_view.refresh_potion_row(potion, potion_name)
