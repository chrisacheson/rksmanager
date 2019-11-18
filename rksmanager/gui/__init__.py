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
from .pages import (PersonList, PersonDetails, PersonEditor, PersonCreator,
                    ContactInfoTypeList, MembershipTypeList,
                    MembershipPricingOptionList, MembershipPricingOptionEditor,
                    MembershipPricingOptionCreator)


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

        # Convenience function for creating menu items.
        #
        # Args:
        #   text: The text shown on the menu item.
        #   menu: The menu to add the item to.
        #   triggered: Slot to connect the menu item's triggered signal to.
        #
        # Returns:
        #   The newly created QAction widget.
        def add_action(text, menu, triggered):
            action = QAction(text=text, parent=window)
            action.triggered.connect(triggered)
            menu.addAction(action)
            return action

        menu_bar = window.menuBar()
        file_menu = menu_bar.addMenu("File")

        add_action(text="Create or Open Database...",
                   menu=file_menu,
                   triggered=lambda x: self.create_or_open_database())
        close_db_action = add_action(text="Close Database",
                                     menu=file_menu,
                                     triggered=self.close_database)
        close_db_action.setEnabled(False)
        self.database_is_open.connect(close_db_action.setEnabled)

        file_menu.addSeparator()

        add_action(text="Exit",
                   menu=file_menu,
                   triggered=self._widgets.main_window.close)

        people_menu = menu_bar.addMenu("People")
        people_menu.setEnabled(False)
        self.database_is_open.connect(people_menu.setEnabled)
        # TODO: Disable the individual menu items too? Can they be triggered by
        # keyboard shortcuts when the menu is disabled?

        add_action(text="Create New Person Record...",
                   menu=people_menu,
                   triggered=self.edit_person)
        add_action(text="View People",
                   menu=people_menu,
                   triggered=self.view_people)

        people_menu.addSeparator()

        add_action(text="Manage Contact Info Types",
                   menu=people_menu,
                   triggered=self.manage_contact_info_types)
        add_action(text="Manage Membership Types",
                   menu=people_menu,
                   triggered=self.manage_membership_types)

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

    def create_or_focus_tab(self, page_type, loader, extra_loader=None,
                            button_callbacks=None, tab_id_arg=None,
                            replace_tab=None):
        tab_id = page_type.get_tab_id(tab_id_arg)
        tab = self._widgets.tab_holder.get_tab(tab_id)
        if not tab:
            if isinstance(loader, tuple):
                loader = functools.partial(*loader)
            tab = page_type(data=loader())
            tab.refresher = loader
            self.database_modified.connect(tab.refresh)
            if extra_loader:
                if isinstance(extra_loader, tuple):
                    extra_loader = functools.partial(*extra_loader)
                tab.extra_data = extra_loader()
                # TODO: Refresher for extra_data?
            for button_attr, callback in button_callbacks.items():
                if isinstance(callback, tuple):
                    callback = functools.partial(*callback)
                button = getattr(tab, button_attr)
                button.clicked.connect(callback)
            self._widgets.tab_holder.addTab(tab, tab.tab_name, tab_id,
                                            replace_tab)
            if replace_tab:
                self._widgets.tab_holder.close_tab(replace_tab)
        self._widgets.tab_holder.setCurrentWidget(tab)

    def view_person_details(self, person_id, replace_tab=None):
        """
        Open or focus the Person Details tab for the specified person. Called
        after the user clicks save in the Create Person tab or when they double
        click on a person in the View People tab.

        Args:
            person_id: The ID of the person to show the details of.
            replace_tab: Optional ID or page widget of a tab to replace with
                this tab.

        """
        def loader(person_id):
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

        self.create_or_focus_tab(
            page_type=PersonDetails,
            tab_id_arg=person_id,
            replace_tab=replace_tab,
            loader=(loader, person_id),
            button_callbacks={
                "edit_button": (self.edit_person, person_id,
                                PersonDetails.get_tab_id(person_id))
            },
        )

    def edit_person(self, person_id=None, replace_tab=None):
        """
        Open or focus a PersonEditor tab for the specified person or for a new
        person. Called when the "Create new person record" menu item is
        selected, or when the Edit button is clicked on a Person Details tab.

        Args:
            person_id: Optional ID of the person to edit. If unspecified the
                editor will create a new person when the save button is
                clicked.
            replace_tab: Optional ID or page widget of a tab to replace with
                this tab.

        """
        if person_id:
            tab_id = PersonEditor.get_tab_id(person_id)
        else:
            tab_id = PersonCreator.get_tab_id()
        tab = self._widgets.tab_holder.get_tab(tab_id)
        if not tab:
            if person_id:
                person_data = self._db.get_person(person_id)
                oci = person_data["other_contact_info"]
                page_type = PersonEditor
            else:
                person_data = {"id": "Not assigned yet"}
                oci = ()
                page_type = PersonCreator
            oci_types = self._db.get_other_contact_info_types()
            combo_items = [(cit["id"], cit["name"]) for cit in oci_types]
            person_data["other_contact_info"] = (oci, combo_items)
            tab = page_type(data=person_data)

            # Cancel button callback. Closes the tab. If we were editing an
            # existing person, open the person in a new Person Details tab.
            def cancel():
                if person_id:
                    # Go "back" to the details of the person we're editing
                    self.view_person_details(person_id, tab)
                else:
                    self._widgets.tab_holder.close_tab(tab)
            tab.cancel_button.clicked.connect(cancel)

            # Save button callback. Saves the person to the database, closes
            # the tab, and opens the person in a new Person Details tab.
            def save():
                self.save_person(tab, person_id)
            tab.save_button.clicked.connect(save)

            self._widgets.tab_holder.addTab(tab, tab.tab_name, tab_id,
                                            replace_tab)
            if replace_tab:
                self._widgets.tab_holder.close_tab(replace_tab)
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
        values = editor.values
        # ComboListEdit gives us a list of widget items and a list of combo box
        # items. We only want the former.
        values["other_contact_info"], _ = values["other_contact_info"]
        person_id = self._db.save_person(values, person_id)
        self.database_modified.emit()
        self.view_person_details(person_id, editor)

    def view_people(self):
        """
        Open or focus the People tab. Called when the "View People" menu item
        is selected.

        """
        tab_id = PersonList.get_tab_id()
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
            self._widgets.tab_holder.addTab(tab, tab.tab_name, tab_id)
        self._widgets.tab_holder.setCurrentWidget(tab)

    def manage_contact_info_types(self):
        """
        Open or focus the Manage Contact Info Types tab. Called when the
        "Manage Contact Info Types" menu item is selected.

        """
        tab_id = ContactInfoTypeList.get_tab_id()
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

            self._widgets.tab_holder.addTab(tab, tab.tab_name, tab_id)
        self._widgets.tab_holder.setCurrentWidget(tab)

    def manage_membership_types(self):
        """
        Open or focus the Manage Membership Types tab. Called when the "Manage
        Membership Types" menu item is selected.

        """
        tab_id = MembershipTypeList.get_tab_id()
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

            # Table double-click callback. Opens or focuses the Membership Type
            # Pricing Options tab for the membership type that was clicked on.
            #
            # Args:
            #   index: A QModelIndex representing the item that was clicked on.
            def pricing_options(index):
                id_index = index.siblingAtColumn(0)
                membership_type_id = tab.proxy_model.itemData(id_index)[0]
                self.membership_type_pricing_options(membership_type_id)
            tab.table_view.doubleClicked.connect(pricing_options)

            tab.refresher = self._db.get_membership_types
            tab.refresh()
            self.database_modified.connect(tab.refresh)

            self._widgets.tab_holder.addTab(tab, tab.tab_name, tab_id)
        self._widgets.tab_holder.setCurrentWidget(tab)

    def membership_type_pricing_options(self, membership_type_id):
        """
        Open or focus the Membership Type Pricing Options tab for the specified
        membership type. Called when a membership type in the "Manage
        Membership Types" tab is double clicked.

        """
        tab_id = MembershipPricingOptionList.get_tab_id(membership_type_id)
        tab = self._widgets.tab_holder.get_tab(tab_id)
        if not tab:
            mtype_data = self._db.get_membership_type(membership_type_id)
            tab = MembershipPricingOptionList(extra_data=mtype_data)

            # Add New Pricing Option button callback. Open or focus a Create
            # Pricing Option tab for this membership type.
            def add():
                self.edit_pricing_option(membership_type_id)
            tab.add_button.clicked.connect(add)

            # Table double-click callback. Opens or focuses the Edit Pricing
            # Option tab for the pricing option that was clicked on.
            #
            # Args:
            #   index: A QModelIndex representing the item that was clicked on.
            def edit(index):
                id_index = index.siblingAtColumn(0)
                pricing_option_id = tab.proxy_model.itemData(id_index)[0]
                self.edit_pricing_option(membership_type_id, pricing_option_id)
            tab.table_view.doubleClicked.connect(edit)

            tab.refresher = functools.partial(
                self._db.get_membership_type_pricing_options,
                membership_type_id,
            )
            tab.refresh()
            self.database_modified.connect(tab.refresh)

            self._widgets.tab_holder.addTab(tab, tab.tab_name, tab_id)
        self._widgets.tab_holder.setCurrentWidget(tab)

    def edit_pricing_option(self, membership_type_id, pricing_option_id=None):
        """
        Open or focus a MembershipPricingOptionEditor tab for the specified
        pricing option or for a new pricing option. Called when the "Add New
        Pricing Option" button is clicked, or when a pricing option is double
        clicked on a Membership Type Pricing Options tab.

        Args:
            membership_type_id: ID of the membership type that the pricing
                option belongs to.
            pricing_option_id: Optional ID of the pricing option to edit. If
                unspecified the editor will create a new pricing option when
                the save button is clicked.

        """
        if pricing_option_id:
            page_type = MembershipPricingOptionEditor
            tab_id = page_type.get_tab_id(pricing_option_id)
        else:
            page_type = MembershipPricingOptionCreator
            tab_id = page_type.get_tab_id(membership_type_id)
        tab = self._widgets.tab_holder.get_tab(tab_id)
        if not tab:
            if pricing_option_id:
                po_data = self._db.get_membership_type_pricing_option(
                    pricing_option_id
                )
            else:
                mtype_data = self._db.get_membership_type(membership_type_id)
                po_data = {"id": "Not assigned yet",
                           "membership_type_id": membership_type_id,
                           "membership_type_name": mtype_data["name"]}
            tab = page_type(po_data)

            # Cancel button callback. Closes the tab.
            def cancel():
                self._widgets.tab_holder.close_tab(tab)
            tab.cancel_button.clicked.connect(cancel)

            # Save button callback. Saves the pricing option to the database
            # and closes the tab.
            def save():
                self._db.save_membership_type_pricing_option(tab.values,
                                                             pricing_option_id)
                self.database_modified.emit()
                self._widgets.tab_holder.close_tab(tab)
            tab.save_button.clicked.connect(save)

            self._widgets.tab_holder.addTab(tab, tab.tab_name, tab_id)
        self._widgets.tab_holder.setCurrentWidget(tab)
