from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta
import sys
import tkinter as tk
from tkinter import messagebox
from typing import Any, List, Optional, Tuple

from assets import (
    Account,
    Assistant,
    BuilderBite,
    BuilderPotion,
    ClockTower,
    Helper,
    LabPotion,
    LabAssistant,
    PetPotion,
    StudySoup,
    Timer,
)
from dialogs import (
    AssignTimerDialog,
    AccountListDialog,
    EditAssistantDialog,
    TimerEditor,
    TimerListDialog,
)


class TimerUpdateController:
    """Advance timer and helper state and keep overview rows synchronized."""

    def __init__(self, overview) -> None:
        self.overview = overview
        self._summary_base_tags: dict[str, Tuple[str, ...]] = {}
        self._unnoticed_timer_ids: set[str] = set()
        self._completion_flash_phase = False

    def tick(self) -> None:
        overview = self.overview
        timer_completed = False
        for timer_id, timer in overview._timer_items:
            previous_time_left = timer.actual_time_left
            timer.advance()
            if previous_time_left > 0 and timer.actual_time_left == 0:
                timer_completed = True
                self._unnoticed_timer_ids.add(timer_id)
                overview.global_features.notify_timer_completed(timer)
        if timer_completed:
            self._completion_flash_phase = True
            self._flash_taskbar_until_foreground()
        elif self._unnoticed_timer_ids:
            self._completion_flash_phase = not self._completion_flash_phase
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
                (account.builder_bite, "Builder Bite"),
                (account.lab_potion, "Lab Potion"),
                (account.study_soup, "Study Soup"),
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
        self.refresh_display()
        overview.after(1000, self.tick)

    def _flash_taskbar_until_foreground(self) -> None:
        if sys.platform != "win32":
            return

        class FlashWindowInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.UINT),
                ("hwnd", wintypes.HWND),
                ("dwFlags", wintypes.DWORD),
                ("uCount", wintypes.UINT),
                ("dwTimeout", wintypes.DWORD),
            ]

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_ancestor = user32.GetAncestor
        get_ancestor.argtypes = [wintypes.HWND, wintypes.UINT]
        get_ancestor.restype = wintypes.HWND
        flash_window = user32.FlashWindowEx
        flash_window.argtypes = [ctypes.POINTER(FlashWindowInfo)]
        flash_window.restype = wintypes.BOOL
        window_handle = self.overview.winfo_toplevel().winfo_id()
        top_level_handle = get_ancestor(window_handle, 2)
        info = FlashWindowInfo(
            ctypes.sizeof(FlashWindowInfo),
            top_level_handle or window_handle,
            0x00000002 | 0x0000000C,
            0,
            0,
        )
        flash_window(ctypes.byref(info))

    def _stop_taskbar_flash(self) -> None:
        if sys.platform != "win32":
            return

        class FlashWindowInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.UINT),
                ("hwnd", wintypes.HWND),
                ("dwFlags", wintypes.DWORD),
                ("uCount", wintypes.UINT),
                ("dwTimeout", wintypes.DWORD),
            ]

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_ancestor = user32.GetAncestor
        get_ancestor.argtypes = [wintypes.HWND, wintypes.UINT]
        get_ancestor.restype = wintypes.HWND
        flash_window = user32.FlashWindowEx
        flash_window.argtypes = [ctypes.POINTER(FlashWindowInfo)]
        flash_window.restype = wintypes.BOOL
        window_handle = self.overview.winfo_toplevel().winfo_id()
        top_level_handle = get_ancestor(window_handle, 2)
        info = FlashWindowInfo(
            ctypes.sizeof(FlashWindowInfo),
            top_level_handle or window_handle,
            0,
            0,
            0,
        )
        flash_window(ctypes.byref(info))

    def refresh_display(self) -> None:
        self.refresh_timer_end_times()
        self.refresh_collapsed_summaries()
        self.update_summary()

    def refresh_timer_end_times(self) -> None:
        overview = self.overview
        timer_ids = {timer_item[0] for timer_item in overview._timer_items}
        ended_ids = {
            timer_id
            for timer_id, timer in overview._timer_items
            if timer.actual_time_left == 0
        }
        had_unnoticed_timers = bool(self._unnoticed_timer_ids)
        self._unnoticed_timer_ids.intersection_update(timer_ids & ended_ids)
        if had_unnoticed_timers and not self._unnoticed_timer_ids:
            self._stop_taskbar_flash()
        summary_ids = {summary_item[0] for summary_item in overview._summary_items}
        self._summary_base_tags = {
            item_id: tags
            for item_id, tags in self._summary_base_tags.items()
            if item_id in summary_ids
        }
        now = datetime.now()
        for timer_id, timer in overview._timer_items:
            seconds_until_done = timer.actual_time_left
            end_time = now + timedelta(seconds=seconds_until_done)
            overview._end_times[timer_id] = end_time
            tags = overview.timer_view.timer_tags(seconds_until_done)
            if timer_id in self._unnoticed_timer_ids:
                phase = "on" if self._completion_flash_phase else "off"
                tags = (f"timer_complete_flash_{phase}",)
            overview.tree.item(
                timer_id,
                values=overview.timer_view.timer_values(
                    timer, end_time, seconds_until_done
                ),
                tags=tags,
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
                elif isinstance(helper, BuilderBite):
                    affects_timer = (
                        timer.village == "Home Village"
                        and timer.category == "Building"
                    )
                elif isinstance(helper, LabPotion):
                    affects_timer = (
                        timer.village == "Home Village"
                        and timer.category == "Lab"
                    )
                elif isinstance(helper, StudySoup):
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

    def on_tree_click(self, event: tk.Event) -> None:
        item_id = self.overview.tree.identify_row(event.y)
        if item_id in self._unnoticed_timer_ids:
            self._notice_completed_row(item_id)

    def _notice_completed_row(self, item_id: str) -> None:
        if item_id not in self._unnoticed_timer_ids:
            return

        self._unnoticed_timer_ids.remove(item_id)
        if not self._unnoticed_timer_ids:
            self._stop_taskbar_flash()
        self.refresh_display()

    def refresh_collapsed_summaries(self) -> None:
        overview = self.overview
        for item_id, label, timers in overview._summary_items:
            is_open = overview.tree.item(item_id, "open")
            visible_timers = overview.global_features.visible_timers(timers)
            if not is_open and visible_timers:
                shortest = min(
                    visible_timers, key=lambda timer: timer.actual_time_left
                )
                visible_timer_ids = {id(timer) for timer in visible_timers}
                unnoticed_ids = {
                    timer_id
                    for timer_id, timer in overview._timer_items
                    if timer_id in self._unnoticed_timer_ids
                    and id(timer) in visible_timer_ids
                }
                summary_label = (
                    f"{label} ({len(unnoticed_ids)})" if unnoticed_ids else label
                )
                if item_id not in self._summary_base_tags:
                    self._summary_base_tags[item_id] = overview.tree.item(
                        item_id, "tags"
                    )
                summary_tags = overview.timer_view.timer_summary_tags(
                    shortest.actual_time_left
                )
                overview.tree.item(
                    item_id,
                    text=summary_label,
                    values=overview.timer_view.timer_values(shortest),
                    tags=summary_tags,
                )
            else:
                base_tags = self._summary_base_tags.pop(
                    item_id, overview.tree.item(item_id, "tags")
                )
                overview.tree.item(
                    item_id,
                    text=label,
                    values=("", "", "", ""),
                    tags=base_tags,
                )

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
        self._context_menu.add_command(
            label="Remove", command=self.remove_selected_timer
        )
        self._blank_context_menu = tk.Menu(overview, tearoff=False)
        self._blank_context_menu.add_command(
            label="Edit Account List", command=self.edit_account_list
        )
        self._category_context_menu = tk.Menu(overview, tearoff=False)
        self._category_context_menu.add_command(
            label="Builder Potion", command=self.potions.activate_builder_potion
        )
        self._category_context_menu.add_command(
            label="Builder Bite", command=self.potions.activate_builder_bite
        )
        self._category_context_menu.add_separator()
        self._category_context_menu.add_command(
            label="Edit Timer List", command=self.edit_selected_timer_list
        )
        self._lab_context_menu = tk.Menu(overview, tearoff=False)
        self._lab_context_menu.add_command(
            label="Lab Potion", command=self.potions.activate_lab_potion
        )
        self._lab_context_menu.add_command(
            label="Study Soup", command=self.potions.activate_study_soup
        )
        self._lab_context_menu.add_separator()
        self._lab_context_menu.add_command(
            label="Edit Timer List", command=self.edit_selected_timer_list
        )
        self._pet_context_menu = tk.Menu(overview, tearoff=False)
        self._pet_context_menu.add_command(
            label="Pet Potion", command=self.potions.activate_pet_potion
        )
        self._pet_context_menu.add_separator()
        self._pet_context_menu.add_command(
            label="Edit Timer List", command=self.edit_selected_timer_list
        )
        self._builder_base_context_menu = tk.Menu(overview, tearoff=False)
        self._builder_base_context_menu.add_command(
            label="Edit Timer List", command=self.edit_selected_timer_list
        )

    def show_context_menu(self, event: tk.Event) -> None:
        overview = self.overview
        item_id = overview.tree.identify_row(event.y)
        if not item_id:
            self._blank_context_menu.tk_popup(event.x_root, event.y_root)
            return
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
        category = overview._timer_list_categories.get(item_id)
        if category is not None and category[1] == "Builder Base":
            overview.tree.selection_set(item_id)
            self._builder_base_context_menu.tk_popup(
                event.x_root, event.y_root
            )
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
            self._context_menu.entryconfigure(1, state="disabled")
        elif any(
            timer_id == item_id for timer_id, _ in overview._timer_items
        ):
            overview.tree.selection_set(item_id)
            self._context_menu.entryconfigure(
                0, label="Edit", command=self.edit_selected_timer
            )
            self._context_menu.entryconfigure(1, state="normal")
        else:
            return
        self._context_menu.tk_popup(event.x_root, event.y_root)

    def edit_account_list(self) -> None:
        overview = self.overview
        AccountListDialog(
            overview,
            overview.accounts,
            overview.add_account,
            overview.remove_account,
            overview.move_account,
        )

    def on_left_click(self, event: tk.Event) -> None:
        if not self.overview.tree.identify_row(event.y):
            selection = self.overview.tree.selection()
            if selection:
                self.overview.tree.selection_remove(*selection)
            return
        self.assistants.on_left_click(event)

    def edit_selected_timer_list(self) -> None:
        overview = self.overview
        selection = overview.tree.selection()
        if not selection:
            return
        category_id = selection[0]
        category = overview._timer_list_categories.get(category_id)
        if category is None:
            return
        account, village, category_name = category
        timers = [
            timer
            for timer in account.timers
            if timer.village == village and timer.category == category_name
        ]

        def add_timer(timer: Timer) -> None:
            account.timers.append(timer)
            if village == "Home Village":
                helpers = {
                    "Building": (account.builder_potion, account.builder_bite),
                    "Lab": (account.lab_potion, account.study_soup),
                    "Pet": (account.pet_potion,),
                }[category_name]
            else:
                helpers = (account.clock_tower,)
            for helper in helpers:
                if helper.active:
                    overview._updates.sync_helper_timers(
                        account, helper, recalculate=True
                    )
            overview.timer_view.add_timer_row(category_id, timer)
            parent_id = overview.tree.parent(category_id)
            for item_id, _label, summary_timers in overview._summary_items:
                if item_id in (category_id, parent_id):
                    summary_timers.append(timer)
            overview._updates.refresh_timer_end_times()
            overview._updates.refresh_collapsed_summaries()
            overview._updates.update_summary()

        def edit_timer(timer: Timer, name: str, remaining: int) -> None:
            timer_id = next(
                item_id
                for item_id, row_timer in overview._timer_items
                if row_timer is timer
            )
            self.apply_timer_edit(timer_id, timer, name, remaining)

        def delete_timer(timer: Timer) -> None:
            self.remove_timer(timer)

        TimerListDialog(
            overview,
            timers,
            village,
            category_name,
            add_timer,
            edit_timer,
            delete_timer,
        )

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

    def remove_selected_timer(self) -> None:
        selection = self.overview.tree.selection()
        if not selection:
            return
        timer = next(
            (
                timer
                for item_id, timer in self.overview._timer_items
                if item_id == selection[0]
            ),
            None,
        )
        if timer is not None:
            self.remove_timer(timer)

    def remove_timer(self, timer: Timer) -> None:
        overview = self.overview
        timer_row = next(
            (
                item_id
                for item_id, row_timer in overview._timer_items
                if row_timer is timer
            ),
            None,
        )
        account = next(
            (account for account in overview.accounts if timer in account.timers),
            None,
        )
        if timer_row is None or account is None:
            return

        assigned_helper = next(
            (
                helper
                for helper in (account.builder_apprentice, account.lab_assistant)
                if helper.assigned_timer is timer
            ),
            None,
        )
        if assigned_helper is not None:
            assigned_helper.assigned = False
            assigned_helper.assigned_timer = None
            if assigned_helper.active:
                assigned_helper.active = False
                assigned_helper.cooldown = assigned_helper.inactive_cooldown
            timer.sync_helper(
                assigned_helper,
                assigned=False,
                active=False,
                recalculate=True,
            )
            overview._updates.sync_helper_timers(
                account, assigned_helper, recalculate=True
            )
            overview.timer_view.refresh_assistant_row(assigned_helper)

        account.timers.remove(timer)
        overview.tree.delete(timer_row)
        overview._timer_items = [
            (item_id, row_timer)
            for item_id, row_timer in overview._timer_items
            if row_timer is not timer
        ]
        overview._updates._unnoticed_timer_ids.discard(timer_row)
        overview._end_times.pop(timer_row, None)
        for _item_id, _label, summary_timers in overview._summary_items:
            summary_timers[:] = [
                summary_timer
                for summary_timer in summary_timers
                if summary_timer is not timer
            ]
        overview._updates.refresh_timer_end_times()
        overview._updates.refresh_collapsed_summaries()
        overview._updates.update_summary()

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
    """Handle temporary category boosts and their tree rows."""

    def __init__(self, overview) -> None:
        self.overview = overview

    def activate_builder_potion(self) -> None:
        self._activate_boost(
            "_building_category_accounts", "builder_potion", "Builder Potion"
        )

    def activate_builder_bite(self) -> None:
        self._activate_boost(
            "_building_category_accounts", "builder_bite", "Builder Bite"
        )

    def activate_lab_potion(self) -> None:
        self._activate_boost("_lab_category_accounts", "lab_potion", "Lab Potion")

    def activate_study_soup(self) -> None:
        self._activate_boost("_lab_category_accounts", "study_soup", "Study Soup")

    def _activate_boost(
        self, category_map_name: str, helper_attribute: str, helper_name: str
    ) -> None:
        overview = self.overview
        selection = overview.tree.selection()
        if not selection:
            return
        category_accounts = getattr(overview, category_map_name)
        account = category_accounts.get(selection[0])
        if account is None:
            return

        boost = getattr(account, helper_attribute)
        boost.active = True
        boost.cooldown += boost.active_cooldown
        self.show_potion_row(boost, selection[0], helper_name)
        overview._updates.sync_helper_timers(account, boost, recalculate=True)
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
