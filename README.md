# SimpleCountdown
A simple timer app for Clash of Clans or any base-building game.

## Summary
Clash of Clans is a well-known base-building game by Supercell Inc., primarily for mobile players. Released in 2012, this game is about attacking and building bases, where you upgrade your armies and defenses as you progress through the contents.\\

One main issue with those that have to juggle between multiple accounts in this game is the ability to manage upgrade timers between multiple accounts. The game does have its own notification system, though, not only does it work for one account per device, it is inconsistent and lacks additional features that would make management much easier and far less time-consuming than it should have been.

## Main features
The application would have these primary features:
- Timers (CRUD).
- Sorting and filtering timers by account, village and upgrade types.
- A global view of timers.
- Notifications.
- Additional in-game boosts.

Additional features are included, but not limited to:
- Ability to input using village data in the JSON format.
- Resources management.
- Upgrade plan.
- Star Bonus.
- An Android version to continue tracking on the phone.

## Programming
This application will be implemented as a Windows desktop application, using Visual Studios with Claude Code implemented. This would also be the first time I will be trying Claude Code in programming.

## Account timer overview
Run the Tkinter overview with `py -3 src/app.py`. The `src/data.json` file contains accounts, each with a `timers` list. Every timer has a `name` and a non-negative integer `value` measured in seconds. `src/data.py` loads and validates the data into the `Account` and `Timer` classes defined in `src/assets.py`.
