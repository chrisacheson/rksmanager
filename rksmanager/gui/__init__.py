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

    def create_or_focus_tab(self, page_type, loader=None, data=None,
                            extra_loader=None, extra_data=None,
                            signal_connections=None, tab_id_arg=None,
                            replace_tab=None):
        """
        Create a new "task" tab, or focus it if it already exists.

        Args:
            page_type: The page widget class to use for the new tab.
            loader: Optional function that will load the appropriate data set
                from the database for the tab to use. This argument will also
                accept a tuple consisting of a function followed by the
                positional arguments to pass to that function.
            data: Optional data set to populate the page widget with. Ignored
                if the loader argument is specified.
            extra_loader: Optional loader for a supplemental data set,
                specified in the same way as the loader argument.
            extra_data: Optional supplemental data set. Ignored if the
                extra_loader argument is specified.
            signal_connections: Optional dictionary of signal names and
                functions (or Callback objects containing functions) to be
                called when the corresponding signal is emitted. Signals are
                specified as "object.signal", where object is an attribute of
                the page widget, such as a button. If "self" is specified for
                the object, the page widget itself will be used. If the signal
                name is omitted, it will default to "clicked". If a Callback's
                self_ref_kw attribute is set, the function will be passed a
                reference to the page widget via the specified keyword
                argument.
            tab_id_arg: Argument to pass to page_type.get_tab_id()
                when generating the tab's ID string. Depending on the page
                type, this will be either required or ignored.
            replace_tab: Optional tab ID, page widget, or index of a tab to
                replace with this one.

        """
        tab_id = page_type.get_tab_id(tab_id_arg)
        tab = self._widgets.tab_holder.get_tab(tab_id)
        if not tab:
            if loader:
                if isinstance(loader, tuple):
                    loader = functools.partial(*loader)
                data = loader()
            if extra_loader:
                if isinstance(extra_loader, tuple):
                    extra_loader = functools.partial(*extra_loader)
                extra_data = extra_loader()
            tab = page_type(data=data, extra_data=extra_data)
            if loader:
                tab.refresher = loader
                self.database_modified.connect(tab.refresh)
                # TODO: Refresher for extra_data?
            for signal_string, callback in signal_connections.items():
                if isinstance(callback, Callback):
                    callback = callback.bind(self_ref=tab)
                if "." in signal_string:
                    emitter_name, signal_name = signal_string.split(".")
                else:
                    emitter_name, signal_name = signal_string, "clicked"
                if emitter_name == "self":
                    emitter = tab
                else:
                    emitter = getattr(tab, emitter_name)
                signal = getattr(emitter, signal_name)
                signal.connect(callback)
            self._widgets.tab_holder.addTab(tab, tab.tab_name, tab_id,
                                            replace_tab)
            if replace_tab:
                self._widgets.tab_holder.close_tab(replace_tab)
        self._widgets.tab_holder.setCurrentWidget(tab)

    def view_person_details(self, person_id, replace_tab=None):
        """
        Open or focus the Person Details tab for the specified person. Called
        after the user clicks save in the Create Person or Edit Person tabs or
        when they double click on a person in the View People tab.

        Args:
            person_id: The ID of the person to show the details of.
            replace_tab: Optional ID or page widget of a tab to replace with
                this tab.

        """
        self.create_or_focus_tab(
            page_type=PersonDetails,
            tab_id_arg=person_id,
            replace_tab=replace_tab,
            loader=(self._db.get_person, person_id),
            extra_data={
                "other_contact_info": self._db.get_other_contact_info_types()
            },
            signal_connections={
                "edit_button": Callback(self.edit_person, (person_id,),
                                        self_ref_kw="replace_tab")
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
            page_type = PersonEditor
            loader = (self._db.get_person, person_id)
            data = None
            cancel = Callback(self.view_person_details, (person_id,),
                              self_ref_kw="replace_tab")
        else:
            page_type = PersonCreator
            loader = None
            data = {"id": "Not assigned yet"}
            cancel = Callback(self._widgets.tab_holder.close_tab,
                              self_ref_kw="tab")
        self.create_or_focus_tab(
            page_type=page_type,
            tab_id_arg=person_id,
            replace_tab=replace_tab,
            loader=loader,
            data=data,
            extra_data={
                "other_contact_info": self._db.get_other_contact_info_types()
            },
            signal_connections={
                "cancel_button": cancel,
                "save_button": Callback(self.save_person,
                                        kwargs={"person_id": person_id},
                                        self_ref_kw="editor"),
            },
        )

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
        person_id = self._db.save_person(editor.values, person_id)
        self.database_modified.emit()
        self.view_person_details(person_id, editor)

    def view_people(self):
        """
        Open or focus the People tab. Called when the "View People" menu item
        is selected.

        """
        self.create_or_focus_tab(
            page_type=PersonList,
            loader=self._db.get_people,
            signal_connections={
                "self.table_double_clicked": self.view_person_details
            },
        )

    def manage_contact_info_types(self):
        """
        Open or focus the Manage Contact Info Types tab. Called when the
        "Manage Contact Info Types" menu item is selected.

        """
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

        # Fetch contact info type data from the database, and tack on rows for
        # email and phone so that we have all contact info types covered.
        def loader():
            ci_types = self._db.get_other_contact_info_types_usage()
            email_address_count = self._db.count_email_addresses()
            phone_number_count = self._db.count_phone_numbers()
            ci_types.insert(0, ("", "Email", email_address_count))
            ci_types.insert(1, ("", "Phone", phone_number_count))
            return ci_types

        self.create_or_focus_tab(
            page_type=ContactInfoTypeList,
            loader=loader,
            signal_connections={"add_button": add},
        )

    def manage_membership_types(self):
        """
        Open or focus the Manage Membership Types tab. Called when the "Manage
        Membership Types" menu item is selected.

        """
        # Add New Membership Type button callback. Prompts the user for a
        # name, then creates a new membership type with that name.
        def add():
            window = self._widgets.main_window
            name = dialogboxes.add_new_membership_type_dialog(window)
            if name is not None:
                self._db.create_membership_type(name)
                self.database_modified.emit()

        self.create_or_focus_tab(
            page_type=MembershipTypeList,
            loader=self._db.get_membership_types,
            signal_connections={
                "add_button": add,
                "self.table_double_clicked": (
                    self.membership_type_pricing_options
                ),
            },
        )

    def membership_type_pricing_options(self, membership_type_id):
        """
        Open or focus the Membership Type Pricing Options tab for the specified
        membership type. Called when a membership type in the "Manage
        Membership Types" tab is double clicked.

        """
        self.create_or_focus_tab(
            page_type=MembershipPricingOptionList,
            tab_id_arg=membership_type_id,
            loader=(self._db.get_membership_type_pricing_options,
                    membership_type_id),
            extra_data=self._db.get_membership_type(membership_type_id),
            signal_connections={
                "add_button": Callback(self.edit_pricing_option,
                                       (membership_type_id,)),
                "self.table_double_clicked": (
                    Callback(self.edit_pricing_option, (membership_type_id,))
                ),
            },
        )

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
        # Save button callback. Saves the pricing option to the database
        # and closes the tab.
        #
        # Args:
        #   tab: This page widget.
        def save(tab):
            self._db.save_membership_type_pricing_option(tab.values,
                                                         pricing_option_id)
            self.database_modified.emit()
            self._widgets.tab_holder.close_tab(tab)

        if pricing_option_id:
            page_type = MembershipPricingOptionEditor
            loader = (self._db.get_membership_type_pricing_option,
                      pricing_option_id)
            data = None
        else:
            page_type = MembershipPricingOptionCreator
            loader = None
            mtype_data = self._db.get_membership_type(membership_type_id)
            data = {"id": "Not assigned yet",
                    "membership_type_id": membership_type_id,
                    "membership_type_name": mtype_data["name"]}
        self.create_or_focus_tab(
            page_type=page_type,
            tab_id_arg=pricing_option_id or membership_type_id,
            loader=loader,
            data=data,
            signal_connections={
                "cancel_button": Callback(self._widgets.tab_holder.close_tab,
                                          self_ref_kw="tab"),
                "save_button": Callback(save, self_ref_kw="tab"),
            },
        )


class Callback:
    """
    Class for handling callback functions and their arguments.

    Args:
        function: The function to be called.
        args: An optional sequence of positional arguments to pass to the
            function.
        kwargs: An optional dictionary of keyword arguments to pass to the
            function.
        self_ref_kw: Optional keyword of a self reference that will be passed
            to the function.

    """
    def __init__(self, function, args=None, kwargs=None, self_ref_kw=None):
        self.function = function
        self.args = args or tuple()
        self.kwargs = kwargs or dict()
        self.self_ref_kw = self_ref_kw

    def bind(self, self_ref=None):
        """
        Create a copy of the function with the arguments bound to it.

        Args:
            self_ref: A reference to the object that will be calling the
                function. Ignored if the self_ref_kw attribute is not set.

        Returns:
            The bound function.

        """
        if self.self_ref_kw and self_ref:
            self.kwargs[self.self_ref_kw] = self_ref
        return functools.partial(self.function, *self.args, **self.kwargs)
