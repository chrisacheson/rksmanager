import traceback
import types

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
        qt_app.exec_()

    # Build the menu bar and add it to the specified window
    def _build_menu_bar(self, window):
        # Callbacks
        def create_db_callback():
            filename = dialogboxes.create_database_dialog(window)
            if filename:
                self._close_database()
                self._db = rksmanager.database.Database(filename)
                self._database_is_open()
                self._db.apply_migrations()

        def open_db_callback():
            filename = dialogboxes.open_database_dialog(window)
            if filename:
                self._close_database()
                self._db = rksmanager.database.Database(filename)
                self._database_is_open()
                schema_version = self._db.get_schema_version()
                if schema_version < self._db.expected_schema_version:
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
                            self._close_database()
                            dialogboxes.convert_database_failure_dialog(window)
                    else:
                        # User declined to convert database, so we can't work
                        # with it
                        self._close_database()
                elif schema_version > self._db.expected_schema_version:
                    self._close_database()
                    dialogboxes.old_software_dialog(window)

        def close_db_callback():
            self._close_database()

        def create_person_callback():
            tab_id = "create_person"
            create_person_tab = self._widgets.tab_holder.get_tab(tab_id)
            if create_person_tab:
                self._widgets.tab_holder.setCurrentWidget(create_person_tab)
            else:
                create_person_tab = PersonEditor()
                create_person_tab.set_values({"person_id": "Not assigned yet"})
                self._widgets.tab_holder.addTab(create_person_tab,
                                                "Create Person", tab_id)

        menu_bar = window.menuBar()
        file_menu = menu_bar.addMenu("File")
        create_db_action = QAction(text="Create Database...", parent=window)
        create_db_action.triggered.connect(create_db_callback)
        file_menu.addAction(create_db_action)
        open_db_action = QAction(text="Open Database...", parent=window)
        open_db_action.triggered.connect(open_db_callback)
        file_menu.addAction(open_db_action)
        close_db_action = QAction(text="Close Database", parent=window)
        close_db_action.triggered.connect(close_db_callback)
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
        create_person_action.triggered.connect(create_person_callback)
        people_menu.addAction(create_person_action)

    # Close the database if we currently have one open
    def _close_database(self):
        if self._db:
            self._db.close()
            self._db = None
            self._database_is_closed()

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
    def __init__(self):
        super().__init__()
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.close_tab)
        self._tab_ids = dict()

    def addTab(self, widget, label, tab_id):
        self._tab_ids[tab_id] = widget
        super().addTab(widget, label)

    def get_tab(self, tab_id):
        self._tab_ids.get(tab_id)

    def close_tab(self, index):
        widget = self.widget(index)
        self.removeTab(index)
        widget.deleteLater()


class Label(QLabel):
    @property
    def value(self):
        return self.text()

    @value.setter
    def value(self, value):
        self.setText(value)


class LineEdit(QLineEdit):
    @property
    def value(self):
        return self.text()

    @value.setter
    def value(self, value):
        self.setText(value)


class TextEdit(QTextEdit):
    @property
    def value(self):
        return self.toPlainText()

    @value.setter
    def value(self, value):
        self.setPlainText(value)


class PersonEditor(QWidget):
    fields = (
        ("person_id", "Person ID", Label),
        ("first_name_or_nickname", "First name or nickname", LineEdit),
        ("pronouns", "Pronouns", LineEdit),
        ("notes", "Notes", TextEdit),
    )

    def __init__(self):
        self._data_widgets = dict()
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
        values = dict()
        for field_id, widget in self._data_widgets.items():
            values[field_id] = widget.value
        return values

    def set_values(self, values):
        keys = self._data_widgets.keys() & values.keys()
        for key in keys:
            self._data_widgets[key].value = values[key]
