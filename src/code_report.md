This report is intended to keep track of the codebase architecture, component responsibilities, and design patterns.



#### `app.py`: Main Architecture Base

**Design pattern: Chain of Responsibility**



The application starts from `app.py::`<span style="color: #0969DA;">TimerApp</span>, where it configures the application layout using a grid-based structure. The simple application design consists of the main content area and a footer.



The main content is responsible for retrieving synchronized data and updating the Treeview (`<span style="color: #0969DA;">TimerTreeView</span>`) every tick (second), with additional controls handled by `<span style="color: #0969DA;">TimerMouseControls</span>`.



Retrieving synchronized data in `\\\\\\\_populate()` connects to multiple types of content: `<span style="color: #0969DA;">HomeVillageControl</span>` and `<span style="color: #0969DA;">BuilderBaseControl</span>`. Meanwhile, `<span style="color: #0969DA;">TimerApp</span>` assigns input data from files to `<span style="color: #0969DA;">TimerUpdateController</span>`, which is responsible for handling update behavior on each tick.



#### `behaviors.py`: Timer Update Behaviors

**Design patterns: Strategy + Composite**



These are semi-data classes. The main management class is `<span style="color: #0969DA;">VillageControl</span>`, which assigns and wraps multiple `<span style="color: #0969DA;">TimerCategoryControl</span>` objects for both Treeview representation and timer updates.



`<span style="color: #0969DA;">TimerCategoryControl</span>` is a semi-data class that tracks active boosts. This allows it to calculate actual timer values and handle behavior changes more accurately when tracking multiple boosts simultaneously.



#### `assets.py`: Basic Data Classes



Contains basic data classes organized around an Abstract pattern, with some Builder pattern characteristics in the relationship between the Assistant and Helper classes.



#### `data.py`: Data Loading



Responsible for loading application data from JSON files.

