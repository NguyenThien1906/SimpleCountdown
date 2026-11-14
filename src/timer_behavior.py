from typing import Any

from assets import Account, Timer


class TimerCategoryControl:
    village = ""
    category = ""

    def populate(
        self, overview: Any, account: Account, village_id: str
    ) -> str:
        category_id = overview.tree.insert(
            village_id,
            "end",
            text=self.category,
            open=True,
            tags=("category",),
        )
        timers = [
            timer
            for timer in account.timers
            if timer.village == self.village and timer.category == self.category
        ]
        overview._timer_list_categories[category_id] = (
            account,
            self.village,
            self.category,
        )
        overview._summary_items.append((category_id, self.category, timers))
        self._add_helper(overview, account, category_id, timers)
        for timer in timers:
            overview.timer_view.add_timer_row(category_id, timer)
        return category_id

    def _add_helper(
        self,
        overview: Any,
        account: Account,
        category_id: str,
        timers: list[Timer],
    ) -> None:
        return


class HomeVillageBuilding(TimerCategoryControl):
    village = "Home Village"
    category = "Building"

    def _add_helper(
        self,
        overview: Any,
        account: Account,
        category_id: str,
        timers: list[Timer],
    ) -> None:
        overview._building_category_accounts[category_id] = account
        overview.timer_view.add_assistant_row(
            category_id,
            account,
            account.builder_apprentice,
            "Builder Apprentice",
            timers,
        )


class HomeVillageLab(TimerCategoryControl):
    village = "Home Village"
    category = "Lab"

    def _add_helper(
        self,
        overview: Any,
        account: Account,
        category_id: str,
        timers: list[Timer],
    ) -> None:
        overview._lab_category_accounts[category_id] = account
        overview.timer_view.add_assistant_row(
            category_id,
            account,
            account.lab_assistant,
            "Lab Assistant",
            timers,
        )


class HomeVillagePet(TimerCategoryControl):
    village = "Home Village"
    category = "Pet"

    def _add_helper(
        self,
        overview: Any,
        account: Account,
        category_id: str,
        timers: list[Timer],
    ) -> None:
        overview._pet_category_accounts[category_id] = account


class BuilderBaseBuilding(TimerCategoryControl):
    village = "Builder Base"
    category = "Building"


class BuilderBaseLab(TimerCategoryControl):
    village = "Builder Base"
    category = "Lab"


class VillageControl:
    name = ""
    categories: tuple[TimerCategoryControl, ...] = ()

    def populate(self, overview: Any, account: Account, account_id: str) -> str:
        village_id = overview.tree.insert(
            account_id,
            "end",
            text=self.name,
            open=True,
            tags=("category",),
        )
        timers = [
            timer for timer in account.timers if timer.village == self.name
        ]
        overview._summary_items.append((village_id, self.name, timers))
        self._add_helper(overview, account, village_id)
        for category in self.categories:
            category.populate(overview, account, village_id)
        return village_id

    def _add_helper(
        self, overview: Any, account: Account, village_id: str
    ) -> None:
        return


class HomeVillageControl(VillageControl):
    name = "Home Village"
    categories = (
        HomeVillageBuilding(),
        HomeVillageLab(),
        HomeVillagePet(),
    )


class BuilderBaseControl(VillageControl):
    name = "Builder Base"
    categories = (BuilderBaseBuilding(), BuilderBaseLab())

    def _add_helper(
        self, overview: Any, account: Account, village_id: str
    ) -> None:
        eligible = [
            timer
            for timer in account.timers
            if timer.village == self.name and timer.category in ("Building", "Lab")
        ]
        overview.timer_view.add_assistant_row(
            village_id,
            account,
            account.clock_tower,
            "Clock Tower",
            eligible,
        )
