import traceback
import types
import sys

from PySide2.QtWidgets import (QApplication, QMainWindow, QAction, QWidget,
                               QGridLayout, QLabel, QPushButton, QTableView,
                               QVBoxLayout, QAbstractItemView)
from PySide2.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel

import rksmanager.database
from . import dialogboxes
from .widgets import (TabHolder, Label, LineEdit, TextEdit, ListLabel,
                      ListEdit, PrimaryItemListLabel, PrimaryItemListEdit)


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
        main_window.setGeometry(0, 0, 1000, 700)
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
        create_person_action.triggered.connect(self.edit_person)
        people_menu.addAction(create_person_action)

        view_people_action = QAction(text="View People", parent=window)
        view_people_action.triggered.connect(self.view_people)
        people_menu.addAction(view_people_action)

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

    def view_person_details(self, person_id, before=None):
        """
        Open or focus the Person Details tab for the specified person. Called
        after the user clicks save in the Create Person tab.

        Args:
            person_id: The ID of the person to show the details of.
            before: Optional ID or page widget of the tab to insert this tab in
                front of.

        """
        tab_id = "person_details_{:d}".format(person_id)
        tab = self._widgets.tab_holder.get_tab(tab_id)
        if not tab:
            person_data = self._db.get_person(person_id)
            tab = PersonDetails()
            tab.set_values(person_data)

            def edit():
                self.edit_person(person_id)
                self._widgets.tab_holder.close_tab(tab)
            tab.edit_button.clicked.connect(edit)

            title = "Person Details ({:d})".format(person_id)
            self._widgets.tab_holder.addTab(tab, title, tab_id, before)
        self._widgets.tab_holder.setCurrentWidget(tab)

    def edit_person(self, person_id=None, before=None):
        """
        Open or focus a PersonEditor tab for the specified person or for a new
        person. Called when the "Create new person record" menu item is
        selected, or when the Edit button is clicked on a Person Details tab.

        Args:
            person_id: Optional ID of the person to edit. If unspecified the
                editor will create a new person when the save button is
                clicked.
            before: Optional ID or page widget of the tab to insert this tab in
                front of.

        """
        if person_id:
            tab_id = "edit_person_{:d}".format(person_id)
            title = "Edit Person ({:d})".format(person_id)
            person_data = self._db.get_person(person_id)
        else:
            tab_id = "create_person"
            title = "Create Person"
            person_data = {"id": "Not assigned yet"}
        tab = self._widgets.tab_holder.get_tab(tab_id)
        if not tab:
            tab = PersonEditor()
            tab.set_values(person_data)

            def cancel():
                if person_id:
                    # Go "back" to the details of the person we're editing
                    self.view_person_details(person_id, tab)
                self._widgets.tab_holder.close_tab(tab)
            tab.cancel_button.clicked.connect(cancel)

            def save():
                self.save_person(tab, person_id)
            tab.save_button.clicked.connect(save)

            self._widgets.tab_holder.addTab(tab, title, tab_id, before)
        self._widgets.tab_holder.setCurrentWidget(tab)

    def save_person(self, editor, person_id=None):
        """
        Save the data in a PersonEditor to the database. Called when the tab's
        Save button is clicked. Closes the tab afterwards and opens a Person
        Details tab for the newly created/updated person.

        Args:
            editor: The PersonEditor widget containing the data.
            person_id: Optional ID of person to update. If unspecified, a new
                person will be created.

        """
        person_id = self._db.save_person(editor.get_values(), person_id)
        self.view_person_details(person_id, editor)
        self._widgets.tab_holder.close_tab(editor)

    def view_people(self):
        """
        Open or focus the People tab. Called when the "View People" menu item
        is selected.

        """
        tab_id = "view_people"
        tab = self._widgets.tab_holder.get_tab(tab_id)
        if not tab:
            tab = PersonList()

            def details(index):
                id_index = index.siblingAtColumn(0)
                person_id = tab.proxy_model.itemData(id_index)[0]
                self.view_person_details(person_id)
            tab.table_view.doubleClicked.connect(details)

            tab.model.populate(self._db.get_people())
            self._widgets.tab_holder.addTab(tab, "People", tab_id)
        self._widgets.tab_holder.setCurrentWidget(tab)

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


class BaseDetailsOrEditor(QWidget):
    """Parent class for BaseDetails and BaseEditor."""
    def __init__(self):
        self._data_widgets = {}
        super().__init__()
        layout = QGridLayout()
        layout.setColumnStretch(1, 1)
        for i, field in enumerate(self.fields):
            if len(field) > 2:
                field_id, label, widget_type = field
            else:
                field_id, label = field
                widget_type = Label
            label_widget = QLabel(label)
            font = label_widget.font()
            font.setBold(True)
            label_widget.setFont(font)
            layout.addWidget(label_widget, i, 0)
            widget = widget_type()
            layout.addWidget(widget, i, 1)
            self._data_widgets[field_id] = widget
        self.setLayout(layout)

    def set_values(self, values):
        """
        Set the current values of all of the viewer/editor's data widgets.

        Args:
            values: A dictionary of field_id and widget value pairs.

        """
        keys = self._data_widgets.keys() & values.keys()
        for key in keys:
            self._data_widgets[key].value = values[key]


class BaseDetails(BaseDetailsOrEditor):
    """
    Generic record viewer widget. Subclasses should set the fields attribute to
    a sequence of 2-tuples or 3-tuples, each containing a field ID and label,
    and optionally a widget class (defaults to Label). For example:

    fields = (
        ("id", "Person ID"),
        ("first_name_or_nickname", "First name\nor nickname"),
        ("aliases", "Aliases", ListLabel),
        ("pronouns", "Pronouns"),
        ("notes", "Notes"),
    )

    """
    def __init__(self):
        super().__init__()
        self.edit_button = QPushButton("Edit")
        self.layout().addWidget(self.edit_button, len(self.fields), 0, 1, -1)


class BaseEditor(BaseDetailsOrEditor):
    """
    Generic record editor widget. Subclasses should set the fields attribute to
    a sequence of 3-tuples, each containing a field ID, label, and widget
    class. For example:

    fields = (
        ("id", "Person ID", Label),
        ("first_name_or_nickname", "First name or nickname", LineEdit),
        ("pronouns", "Pronouns", LineEdit),
        ("notes", "Notes", TextEdit),
    )

    """
    def __init__(self):
        super().__init__()
        self.cancel_button = QPushButton("Cancel")
        self.layout().addWidget(self.cancel_button, len(self.fields), 0)
        self.save_button = QPushButton("Save")
        self.layout().addWidget(self.save_button, len(self.fields), 1)

    def get_values(self):
        """
        Get the current values of all of the editor's data widgets.

        Returns:
            A dictionary of field_id and widget value pairs.

        """
        values = {}
        for field_id, widget in self._data_widgets.items():
            values[field_id] = widget.value
        return values


class BaseListModel(QAbstractTableModel):
    """
    Generic Model object for holding data to be displayed by a QTableView
    widget. Subclasses should set the headers attribute to a tuple of column
    headers to be displayed by the QTableView. For example:

    headers = ("ID", "Name", "Email Address", "Pronouns", "Notes")

    """
    def __init__(self):
        self._data = []
        super().__init__()

    def populate(self, data):
        """
        Assign a new data set to this model.

        Args:
            data: The data set as a 2-dimensional list or similar.

        """
        self._data = data
        self.layoutChanged.emit()

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        return len(self.headers)

    def data(self, index, role):
        if role == Qt.DisplayRole:
            row = self._data[index.row()]
            return row[index.column()]

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
                return self.headers[section]


class BaseList(QWidget):
    """
    Generic table viewer widget. Subclasses should set the model_class
    attribute to a subclass of BaseListModel.

    """
    def __init__(self):
        super().__init__()
        self.model = self.model_class()
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        layout = QVBoxLayout()
        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table_view)
        self.setLayout(layout)


class PersonDetails(BaseDetails):
    """Viewer widget for Create Person and Person Details tabs."""
    fields = (
        ("id", "Person ID"),
        ("first_name_or_nickname", "First name\nor nickname"),
        ("aliases", "Aliases", ListLabel),
        ("email_addresses", "Email Addresses", PrimaryItemListLabel),
        ("pronouns", "Pronouns"),
        ("notes", "Notes"),
    )


class PersonEditor(BaseEditor):
    """Editor widget for Create Person and Person Details tabs."""
    fields = (
        ("id", "Person ID", Label),
        ("first_name_or_nickname", "First name\nor nickname", LineEdit),
        ("aliases", "Aliases", ListEdit),
        ("email_addresses", "Email Addresses", PrimaryItemListEdit),
        ("pronouns", "Pronouns", LineEdit),
        ("notes", "Notes", TextEdit),
    )


class PersonListModel(BaseListModel):
    """Model for holding person data to be displayed by a QTableView."""
    headers = ("ID", "Name", "Email Address", "Pronouns", "Notes")


class PersonList(BaseList):
    """Table viewer widget for the People tab."""
    model_class = PersonListModel
