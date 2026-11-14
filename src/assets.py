from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar, Optional

VILLAGES = ("Home Village", "Builder Base")
SUBCATEGORIES = {
    "Home Village": ("Building", "Lab", "Pet"),
    "Builder Base": ("Building", "Lab"),
}


@dataclass
class Timer:
    name: str
    value: int
    village: str
    category: str
    ongoing_helpers: list[Helper] = field(
        default_factory=list, init=False, repr=False, compare=False
    )
    assigned_assistant: Optional[Assistant] = field(
        default=None, init=False, repr=False, compare=False
    )
    actual_time_left: int = field(init=False, compare=False)

    def __post_init__(self) -> None:
        self.actual_time_left = self.value

    @property
    def rate(self) -> int:
        return sum(helper.multiplier for helper in self.ongoing_helpers) + 1

    def advance(self) -> None:
        if self.value > 0:
            self.value = max(0, self.value - self.rate)
            self.actual_time_left = max(0, self.actual_time_left - 1)

    def sync_helper(
        self,
        helper: Helper,
        assigned: bool = False,
        active: bool = False,
        recalculate: bool = False,
    ) -> None:
        if isinstance(helper, BuilderPotion):
            active = (
                active
                and self.village == "Home Village"
                and self.category == "Building"
            )
        elif isinstance(helper, BuilderBite):
            active = (
                active
                and self.village == "Home Village"
                and self.category == "Building"
            )
        elif isinstance(helper, LabPotion):
            active = (
                active
                and self.village == "Home Village"
                and self.category == "Lab"
            )
        elif isinstance(helper, StudySoup):
            active = (
                active
                and self.village == "Home Village"
                and self.category == "Lab"
            )
        elif isinstance(helper, PetPotion):
            active = (
                active
                and self.village == "Home Village"
                and self.category == "Pet"
            )
        elif isinstance(helper, ClockTower):
            active = active and self.village == "Builder Base"

        is_ongoing = any(existing is helper for existing in self.ongoing_helpers)
        assigned_assistant = (
            helper if isinstance(helper, Assistant) and assigned else None
        )
        if (
            is_ongoing == active
            and (
                not isinstance(helper, Assistant)
                or self.assigned_assistant is assigned_assistant
            )
            and not recalculate
        ):
            return

        if active and not is_ongoing:
            self.ongoing_helpers.append(helper)
        elif not active and is_ongoing:
            self.ongoing_helpers = [
                existing
                for existing in self.ongoing_helpers
                if existing is not helper
            ]
        if isinstance(helper, Assistant):
            if self.assigned_assistant is helper or assigned_assistant is not None:
                self.assigned_assistant = assigned_assistant
        self.recalculate_actual_time_left()

    def recalculate_actual_time_left(self) -> None:
        if self.value <= 0:
            self.actual_time_left = 0
            return

        assistant = self.assigned_assistant
        if assistant is not None:
            self.actual_time_left = self._seconds_with_assistant(assistant)
            return

        timed_boosts = [
            helper
            for helper in self.ongoing_helpers
            if isinstance(helper, TimedBoost) and helper.cooldown > 0
        ]
        if timed_boosts:
            self.actual_time_left = self._seconds_with_timed_boosts(timed_boosts)
            return

        self.actual_time_left = self.value

    def _seconds_with_timed_boosts(self, helpers: list[TimedBoost]) -> int:
        remaining = self.value
        elapsed = 0
        active_helpers = [(helper, helper.cooldown) for helper in helpers]
        while active_helpers and remaining > 0:
            rate = 1 + sum(helper.multiplier for helper, _ in active_helpers)
            seconds_to_expiry = min(cooldown for _, cooldown in active_helpers)
            ticks_to_finish = (remaining + rate - 1) // rate
            if ticks_to_finish <= seconds_to_expiry:
                return elapsed + ticks_to_finish

            remaining -= seconds_to_expiry * rate
            elapsed += seconds_to_expiry
            active_helpers = [
                (helper, cooldown - seconds_to_expiry)
                for helper, cooldown in active_helpers
                if cooldown > seconds_to_expiry
            ]
        return elapsed + remaining

    def _seconds_with_assistant(self, assistant: Assistant) -> int:
        active = assistant.active
        phase_seconds = assistant.cooldown
        remaining = self.value
        elapsed = 0
        active_rate = assistant.multiplier + 1
        active_seconds = assistant.active_cooldown
        inactive_seconds = assistant.inactive_cooldown
        cycle_seconds = active_seconds + inactive_seconds
        timed_boosts = [
            (helper, helper.cooldown)
            for helper in self.ongoing_helpers
            if isinstance(helper, TimedBoost) and helper.cooldown > 0
        ]

        while timed_boosts and remaining > 0:
            rate = (active_rate if active else 1) + sum(
                helper.multiplier for helper, _ in timed_boosts
            )
            boost_seconds = min(cooldown for _, cooldown in timed_boosts)
            seconds_to_phase_end = (
                phase_seconds if phase_seconds > 0 else boost_seconds
            )
            phase_length = min(boost_seconds, seconds_to_phase_end)
            ticks_to_finish = (remaining + rate - 1) // rate
            if ticks_to_finish <= phase_length:
                return elapsed + ticks_to_finish

            remaining -= phase_length * rate
            elapsed += phase_length
            timed_boosts = [
                (helper, cooldown - phase_length)
                for helper, cooldown in timed_boosts
                if cooldown > phase_length
            ]
            if phase_seconds > 0:
                phase_seconds -= phase_length
                if phase_seconds == 0:
                    active = not active
                    phase_seconds = (
                        active_seconds if active else inactive_seconds
                    )

        if phase_seconds <= 0:
            rate = active_rate if active else 1
            return elapsed + (remaining + rate - 1) // rate

        cycle_progress = active_seconds * active_rate + inactive_seconds

        while remaining > 0:
            rate = active_rate if active else 1
            ticks_to_finish = (remaining + rate - 1) // rate
            if ticks_to_finish <= phase_seconds:
                return elapsed + ticks_to_finish

            remaining -= phase_seconds * rate
            elapsed += phase_seconds
            active = not active
            phase_seconds = active_seconds if active else inactive_seconds

            full_cycles = (remaining - 1) // cycle_progress
            elapsed += full_cycles * cycle_seconds
            remaining -= full_cycles * cycle_progress

        return elapsed


@dataclass
class Helper(ABC):
    active: bool = False
    cooldown: int = 0
    multiplier: int = 1

    ACTIVE_COOLDOWN_SECONDS: ClassVar[int] = 60 * 60
    INACTIVE_COOLDOWN_SECONDS: ClassVar[int] = 23 * 60 * 60

    @property
    def active_cooldown(self) -> int:
        return self.ACTIVE_COOLDOWN_SECONDS

    @property
    def inactive_cooldown(self) -> int:
        return self.INACTIVE_COOLDOWN_SECONDS

    @property
    @abstractmethod
    def supports_multiple_timers(self) -> bool:
        """Whether the helper boosts its whole eligible timer group."""


@dataclass
class TimedBoost(Helper):
    """A temporary helper that boosts its eligible timer group."""


@dataclass
class Assistant(Helper):
    assigned: bool = False
    assigned_timer: Optional[Timer] = None


@dataclass
class BuilderApprentice(Assistant):
    @property
    def supports_multiple_timers(self) -> bool:
        return False


@dataclass
class LabAssistant(Assistant):
    @property
    def supports_multiple_timers(self) -> bool:
        return False


@dataclass
class ClockTower(TimedBoost):
    active_cooldown_minutes: int = 30

    multiplier: int = field(default=9, init=False)

    @property
    def active_cooldown(self) -> int:
        return self.active_cooldown_minutes * 60

    @property
    def inactive_cooldown(self) -> int:
        return 22 * 60 * 60

    @property
    def supports_multiple_timers(self) -> bool:
        return True


@dataclass
class BuilderPotion(TimedBoost):
    multiplier: int = field(default=9, init=False)

    @property
    def supports_multiple_timers(self) -> bool:
        return True


@dataclass
class LabPotion(TimedBoost):
    multiplier: int = field(default=23, init=False)

    @property
    def supports_multiple_timers(self) -> bool:
        return True


@dataclass
class PetPotion(TimedBoost):
    multiplier: int = field(default=23, init=False)

    @property
    def supports_multiple_timers(self) -> bool:
        return True


@dataclass
class BuilderBite(TimedBoost):
    multiplier: int = field(default=1, init=False)

    @property
    def supports_multiple_timers(self) -> bool:
        return True


@dataclass
class StudySoup(TimedBoost):
    multiplier: int = field(default=3, init=False)

    @property
    def supports_multiple_timers(self) -> bool:
        return True


@dataclass
class Account:
    name: str
    timers: list[Timer] = field(default_factory=list)
    builder_apprentice: BuilderApprentice = field(default_factory=BuilderApprentice)
    lab_assistant: LabAssistant = field(default_factory=LabAssistant)
    clock_tower: ClockTower = field(default_factory=ClockTower)
    builder_potion: BuilderPotion = field(default_factory=BuilderPotion)
    builder_bite: BuilderBite = field(default_factory=BuilderBite)
    lab_potion: LabPotion = field(default_factory=LabPotion)
    study_soup: StudySoup = field(default_factory=StudySoup)
    pet_potion: PetPotion = field(default_factory=PetPotion)
    tag: Optional[str] = None
