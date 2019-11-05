import traceback
import types
import sys

from PySide2.QtWidgets import (QApplication, QMainWindow, QAction, QTabWidget,
                               QWidget, QGridLayout, QLabel, QLineEdit,
                               QTextEdit, QPushButton)

import rksmanager.database
from . import dialogboxes


class Gui:
    """Builds the GUI and handles all user interaction."""
    def __init__(self):
        self._db = None
        # For holding references to specific widgets that we need to access
        # later
        self._widgets = types.SimpleNamespace()

    def start(self):
        """Display the main window and pass control to the Gui object."""
        qt_app = QApplication()
        main_window = QMainWindow()
        self._widgets.main_window = main_window
        self._build_menu_bar(main_window)
        tab_holder = TabHolder()
        self._widgets.tab_holder = tab_holder
        main_window.setCentralWidget(tab_holder)
        main_window.show()
        if len(sys.argv) > 1:
            self.create_or_open_database(sys.argv[1])
        qt_app.exec_()

    # Build the menu bar and add it to the specified window
    def _build_menu_bar(self, window):
        menu_bar = window.menuBar()
        file_menu = menu_bar.addMenu("File")

        create_or_open_db_action = QAction(text="Create or Open Database...",
                                           parent=window)
        create_or_open_db_action.triggered.connect(
            lambda x: self.create_or_open_database()
        )
        file_menu.addAction(create_or_open_db_action)

        close_db_action = QAction(text="Close Database", parent=window)
        close_db_action.triggered.connect(self.close_database)
        close_db_action.setEnabled(False)
        self._widgets.close_db_action = close_db_action
        file_menu.addAction(close_db_action)

        file_menu.addSeparator()
        exit_action = QAction(text="Exit", parent=window)
        exit_action.triggered.connect(self._widgets.main_window.close)
        file_menu.addAction(exit_action)

        people_menu = menu_bar.addMenu("People")
        people_menu.setEnabled(False)
        # TODO: Disable the individual menu items too? Can they be triggered by
        # keyboard shortcuts when the menu is disabled?
        self._widgets.people_menu = people_menu

        create_person_action = QAction(text="Create new person record...",
                                       parent=window)
        create_person_action.triggered.connect(self.edit_new_person)
        people_menu.addAction(create_person_action)

    def create_or_open_database(self, filename=None):
        """
        Create or open a database. Called by the "Create or Open Database" menu
        item.

        Args:
            filename: Optional filename of the database to create/open. If
                unspecified, a file dialog will be opened so that the user can
                select a file or choose a filename.

        """
        window = self._widgets.main_window
        if not filename:
            filename = dialogboxes.create_or_open_database_dialog(window)
        if filename:
            self.close_database()
            self._db = rksmanager.database.Database(filename)
            self._database_is_open()
            version = self._db.get_sqlite_user_version()
            if version < self._db.expected_sqlite_user_version:
                if dialogboxes.convert_database_dialog(window):
                    success = False
                    try:
                        self._db.apply_migrations()
                        success = True
                    except Exception as e:
                        traceback.print_exception(
                            etype=type(e),
                            value=e,
                            tb=e.__traceback__,
                        )
                    if success:
                        dialogboxes.convert_database_success_dialog(window)
                    else:
                        self.close_database()
                        dialogboxes.convert_database_failure_dialog(window)
                else:
                    # User declined to convert database, so we can't work with
                    # it
                    self.close_database()
            elif version > self._db.expected_sqlite_user_version:
                self.close_database()
                dialogboxes.old_software_dialog(window)

    def close_database(self):
        """
        Close the database if we currently have one open. Called by the "Close
        Database" menu item.

        """
        if self._db:
            self._widgets.tab_holder.close_all_tabs()
            self._db.close()
            self._db = None
            self._database_is_closed()

    def edit_new_person(self):
        """
        Open or focus the Create Person tab. Called when the "Create new person
        record" menu item is selected.

        """
        tab_id = "create_person"
        create_person_tab = self._widgets.tab_holder.get_tab(tab_id)
        if create_person_tab:
            self._widgets.tab_holder.setCurrentWidget(create_person_tab)
        else:
            create_person_tab = PersonEditor()
            create_person_tab.set_values({"person_id": "Not assigned yet"})

            def save():
                self.save_new_person(create_person_tab)
            create_person_tab.save_button.clicked.connect(save)

            self._widgets.tab_holder.addTab(create_person_tab,
                                            "Create Person", tab_id)

    def save_new_person(self, editor):
        """
        Insert a new person record into the database from the data in the
        Create Person tab. Called when the tab's Save button is clicked. Closes
        the tab afterwards.

        Args:
            editor: The PersonEditor widget containing the data.

        """
        self._db.create_person(editor.get_values())
        # TODO: Open person details in place of editor
        self._widgets.tab_holder.close_tab(editor)

    # Change the state of various widgets in response to a database being
    # opened
    # TODO: Use signals and slots for this instead
    def _database_is_open(self):
        self._widgets.close_db_action.setEnabled(True)
        self._widgets.people_menu.setEnabled(True)

    # Change the state of various widgets in response to a database being
    # closed
    def _database_is_closed(self):
        self._widgets.close_db_action.setEnabled(False)
        self._widgets.people_menu.setEnabled(False)


class TabHolder(QTabWidget):
    """
    A QTabWidget with some extra methods. Used as the central widget of our
    main window.

    """
    def __init__(self):
        super().__init__()
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.close_tab)
        self._tab_ids = {}
        self._tab_ids_inverse = {}

    def addTab(self, widget, label, tab_id):
        """
        Create a new tab. Overrides QTabWidget's addTab() method.

        Args:
            widget: The widget to be displayed by the tab.
            label: The name to display on the tab.
            tab_id: Unique ID string used to refer to the tab later.

        """
        self._tab_ids[tab_id] = widget
        self._tab_ids_inverse[widget] = tab_id
        super().addTab(widget, label)

    def get_tab(self, tab_id):
        """
        Retrieve the tab with the specified ID.

        Args:
            tab_id: The ID of the tab to get.

        Returns:
            The tab with the specified ID, or None if there is no such tab.

        """
        self._tab_ids.get(tab_id)

    def close_tab(self, index_or_widget):
        """
        Close the tab at the specified index or with the specified page widget,
        and delete the widget. Called when the tab's close button is clicked.

        Args:
            index_or_widget: The index of the tab to close, or the page widget
                corresponding to the tab.

        """
        if isinstance(index_or_widget, int):
            index = index_or_widget
            widget = self.widget(index)
        else:
            widget = index_or_widget
            index = self.indexOf(widget)
        tab_id = self._tab_ids_inverse[widget]
        del self._tab_ids[tab_id]
        del self._tab_ids_inverse[widget]
        self.removeTab(index)
        widget.deleteLater()

    def close_all_tabs(self):
        """Close all tabs and delete all page widgets."""
        self.clear()
        for widget in self._tab_ids.values():
            widget.deleteLater()
        self._tab_ids = {}
        self._tab_ids_inverse = {}


class ValuePropertyMixin:
    """
    Add a value property to any widget inheriting this. Widgets that use
    methods other than text() and setText() to get and set their value should
    set the getter_method and setter_method attributes appropriately.

    """
    getter_method = "text"
    setter_method = "setText"

    @property
    def value(self):
        """Get or set the widget's current value."""
        getter = getattr(self, self.getter_method)
        return getter()

    @value.setter
    def value(self, value):
        setter = getattr(self, self.setter_method)
        setter(value)


class Label(ValuePropertyMixin, QLabel):
    pass


class LineEdit(ValuePropertyMixin, QLineEdit):
    pass


class TextEdit(ValuePropertyMixin, QTextEdit):
    getter_method = "toPlainText"
    setter_method = "setPlainText"


class BaseEditor(QWidget):
    """
    Generic record editor widget. Subclasses should set the fields attribute to
    a sequence of 3-tuples, each containing a field ID, Label, and widget
    class. For example:

    fields = (
        ("person_id", "Person ID", Label),
        ("first_name_or_nickname", "First name or nickname", LineEdit),
        ("pronouns", "Pronouns", LineEdit),
        ("notes", "Notes", TextEdit),
    )

    """
    def __init__(self):
        self._data_widgets = {}
        super().__init__()
        layout = QGridLayout()
        for i, field in enumerate(self.fields):
            field_id, label, widget_type = field
            layout.addWidget(QLabel(label), i, 0)
            widget = widget_type()
            layout.addWidget(widget, i, 1)
            self._data_widgets[field_id] = widget
        self.save_button = QPushButton("Save")
        layout.addWidget(self.save_button, len(self.fields), 0, 1, -1)
        self.setLayout(layout)

    def get_values(self):
        """
        Get the current values of all of the editor's data widgets.

        Returns:
            A dictionary of field_id and widget value pairs, with any empty
            string values converted to None.

        """
        values = dict()
        for field_id, widget in self._data_widgets.items():
            value = widget.value
            if value == "":
                value = None
            values[field_id] = value
        return values

    def set_values(self, values):
        """
        Set the current values of all of the editor's data widgets.

        Args:
            values: A dictionary of field_id and widget value pairs.

        """
        keys = self._data_widgets.keys() & values.keys()
        for key in keys:
            self._data_widgets[key].value = values[key]


class PersonEditor(BaseEditor):
    fields = (
        ("person_id", "Person ID", Label),
        ("first_name_or_nickname", "First name or nickname", LineEdit),
        ("pronouns", "Pronouns", LineEdit),
        ("notes", "Notes", TextEdit),
    )
