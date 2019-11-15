"""
Main GUI module. Contains the top-level Gui class which sets up the interface
and controls access to the database handler object.

"""
import traceback
import types
import sys
import functools

from PySide2.QtWidgets import QApplication, QMainWindow, QAction
from PySide2.QtCore import Signal

import rksmanager.database
from . import dialogboxes
from .widgets import TabHolder
from .pages import (PersonList, PersonDetails, PersonEditor,
                    ContactInfoTypeList, MembershipTypeList)


class Gui(QApplication):
    """Builds the GUI and handles all user interaction."""

    # Argument will be True if the database is now open, or False if it is now
    # closed.
    database_is_open = Signal(bool)
    # TODO: Make this more granular if performance becomes an issue
    database_modified = Signal()

    def __init__(self):
        self._db = None
        # For holding references to specific widgets that we need to access
        # later
        self._widgets = types.SimpleNamespace()
        super().__init__()

    def start(self):
        """Display the main window and pass control to the Gui object."""
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
        self.exec_()

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
        self.database_is_open.connect(close_db_action.setEnabled)
        file_menu.addAction(close_db_action)

        file_menu.addSeparator()
        exit_action = QAction(text="Exit", parent=window)
        exit_action.triggered.connect(self._widgets.main_window.close)
        file_menu.addAction(exit_action)

        people_menu = menu_bar.addMenu("People")
        people_menu.setEnabled(False)
        self.database_is_open.connect(people_menu.setEnabled)
        # TODO: Disable the individual menu items too? Can they be triggered by
        # keyboard shortcuts when the menu is disabled?

        create_person_action = QAction(text="Create New Person Record...",
                                       parent=window)
        create_person_action.triggered.connect(self.edit_person)
        people_menu.addAction(create_person_action)

        view_people_action = QAction(text="View People", parent=window)
        view_people_action.triggered.connect(self.view_people)
        people_menu.addAction(view_people_action)

        people_menu.addSeparator()
        manage_contact_info_types_action = QAction(
            text="Manage Contact Info Types",
            parent=window,
        )
        manage_contact_info_types_action.triggered.connect(
            self.manage_contact_info_types
        )
        people_menu.addAction(manage_contact_info_types_action)

        manage_membership_types_action = QAction(
            text="Manage Membership Types",
            parent=window,
        )
        manage_membership_types_action.triggered.connect(
            self.manage_membership_types
        )
        people_menu.addAction(manage_membership_types_action)

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
            self.database_is_open.emit(True)
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
            self.database_is_open.emit(False)

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
            tab = PersonDetails()

            def refresher(person_id):
                # TODO: Refactor this
                person_data = self._db.get_person(person_id)
                contact_info_types = {}
                for cit in self._db.get_other_contact_info_types():
                    contact_info_types[cit["id"]] = cit["name"]
                other_contact_info = []
                for type_id, contact_info in person_data["other_contact_info"]:
                    type_name = contact_info_types[type_id]
                    other_contact_info.append("{}: {}".format(type_name,
                                                              contact_info))
                person_data["other_contact_info"] = other_contact_info
                return person_data
            tab.refresher = functools.partial(refresher, person_id)
            tab.refresh()
            self.database_modified.connect(tab.refresh)

            # Edit button callback. Opens the person in a new Edit Person tab
            # and closes the Person Details tab.
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
        else:
            tab_id = "create_person"
        tab = self._widgets.tab_holder.get_tab(tab_id)
        if not tab:
            if person_id:
                title = "Edit Person ({:d})".format(person_id)
                person_data = self._db.get_person(person_id)
            else:
                title = "Create Person"
                person_data = {"id": "Not assigned yet"}
            oci_types = self._db.get_other_contact_info_types()
            combo_items = [(cit["id"], cit["name"]) for cit in oci_types]
            oci = person_data["other_contact_info"]
            person_data["other_contact_info"] = (oci, combo_items)
            tab = PersonEditor()
            tab.set_values(person_data)

            # Cancel button callback. Closes the tab. If we were editing an
            # existing person, open the person in a new Person Details tab.
            def cancel():
                if person_id:
                    # Go "back" to the details of the person we're editing
                    self.view_person_details(person_id, tab)
                self._widgets.tab_holder.close_tab(tab)
            tab.cancel_button.clicked.connect(cancel)

            # Save button callback. Saves the person to the database, closes
            # the tab, and opens the person in a new Person Details tab.
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
        values = editor.get_values()
        # ComboListEdit gives us a list of widget items and a list of combo box
        # items. We only want the former.
        values["other_contact_info"], _ = values["other_contact_info"]
        person_id = self._db.save_person(values, person_id)
        self.database_modified.emit()
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

            # Table double-click callback. Opens the person that was clicked on
            # in a new Person Details tab.
            #
            # Args:
            #   index: A QModelIndex representing the item that was clicked on.
            def details(index):
                id_index = index.siblingAtColumn(0)
                person_id = tab.proxy_model.itemData(id_index)[0]
                self.view_person_details(person_id)
            tab.table_view.doubleClicked.connect(details)

            tab.refresher = self._db.get_people
            tab.refresh()
            self.database_modified.connect(tab.refresh)
            self._widgets.tab_holder.addTab(tab, "People", tab_id)
        self._widgets.tab_holder.setCurrentWidget(tab)

    def manage_contact_info_types(self):
        """
        Open or focus the Manage Contact Info Types tab. Called when the
        "Manage Contact Info Types" menu item is selected.

        """
        tab_id = "manage_contact_info_types"
        tab = self._widgets.tab_holder.get_tab(tab_id)
        if not tab:
            tab = ContactInfoTypeList()

            # Add New Contact Info Type button callback. Prompts the user for a
            # name, then creates a new contact info type with that name.
            # TODO: Prevent the user from adding "Email" or "Phone" once we get
            # around to doing validators
            def add():
                window = self._widgets.main_window
                name = dialogboxes.add_new_contact_info_type_dialog(window)
                if name is not None:
                    self._db.create_other_contact_info_type(name)
                    self.database_modified.emit()
            tab.add_button.clicked.connect(add)

            def refresher():
                contact_info_types = self._db.get_other_contact_info_types()
                email_address_count = self._db.count_email_addresses()
                phone_number_count = self._db.count_phone_numbers()
                contact_info_types.insert(0, ("", "Email",
                                              email_address_count))
                contact_info_types.insert(1, ("", "Phone",
                                              phone_number_count))
                return contact_info_types
            tab.refresher = refresher
            tab.refresh()
            self.database_modified.connect(tab.refresh)

            self._widgets.tab_holder.addTab(tab, "Manage Contact Info Types",
                                            tab_id)
        self._widgets.tab_holder.setCurrentWidget(tab)

    def manage_membership_types(self):
        """
        Open or focus the Manage Membership Types tab. Called when the "Manage
        Membership Types" menu item is selected.

        """
        tab_id = "manage_membership_types"
        tab = self._widgets.tab_holder.get_tab(tab_id)
        if not tab:
            tab = MembershipTypeList()

            # Add New Membership Type button callback. Prompts the user for a
            # name, then creates a new membership type with that name.
            def add():
                window = self._widgets.main_window
                name = dialogboxes.add_new_membership_type_dialog(window)
                if name is not None:
                    self._db.create_membership_type(name)
                    self.database_modified.emit()
            tab.add_button.clicked.connect(add)

            tab.refresher = self._db.get_membership_types
            tab.refresh()
            self.database_modified.connect(tab.refresh)

            self._widgets.tab_holder.addTab(tab, "Manage Membership Types",
                                            tab_id)
        self._widgets.tab_holder.setCurrentWidget(tab)
