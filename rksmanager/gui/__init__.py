"""
Main GUI module. Contains the top-level Gui class which sets up the interface
and controls access to the database handler object.

"""
import traceback
import sys

from PySide2.QtWidgets import QApplication, QMainWindow, QAction
from PySide2.QtCore import Signal

import rksmanager.database
from . import dialogboxes
from .widgets import TabHolder
from .pages import (PersonList, PersonCreator, ContactInfoTypeList,
                    MembershipTypeList, EventTypeList, EventCreator, EventList)


class Gui(QApplication):
    """Builds the GUI and handles all user interaction."""

    # Argument will be True if the database is now open, or False if it is now
    # closed.
    database_is_open = Signal(bool)
    # TODO: Make this more granular if performance becomes an issue
    database_modified = Signal()

    def __init__(self):
        self.db = None
        super().__init__()

    def start(self):
        """Display the main window and pass control to the Gui object."""
        main_window = QMainWindow()
        self.main_window = main_window
        self._build_menu_bar(main_window)
        tab_holder = TabHolder()
        self.tab_holder = tab_holder
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
                   triggered=lambda: self.create_or_open_database())
        close_db_action = add_action(text="Close Database",
                                     menu=file_menu,
                                     triggered=self.close_database)
        close_db_action.setEnabled(False)
        self.database_is_open.connect(close_db_action.setEnabled)

        file_menu.addSeparator()

        add_action(text="Exit",
                   menu=file_menu,
                   triggered=self.main_window.close)

        people_menu = menu_bar.addMenu("People")
        people_menu.setEnabled(False)
        self.database_is_open.connect(people_menu.setEnabled)
        # TODO: Disable the individual menu items too? Can they be triggered by
        # keyboard shortcuts when the menu is disabled?

        add_action(text="Create New Person Record...",
                   menu=people_menu,
                   triggered=lambda: PersonCreator.create_or_focus(gui=self))
        add_action(text="View People",
                   menu=people_menu,
                   triggered=lambda: PersonList.create_or_focus(gui=self))

        people_menu.addSeparator()

        add_action(
            text="Manage Contact Info Types",
            menu=people_menu,
            triggered=lambda: ContactInfoTypeList.create_or_focus(gui=self),
        )
        add_action(
            text="Manage Membership Types",
            menu=people_menu,
            triggered=lambda: MembershipTypeList.create_or_focus(gui=self),
        )

        events_menu = menu_bar.addMenu("Events")
        events_menu.setEnabled(False)
        self.database_is_open.connect(events_menu.setEnabled)

        add_action(text="Create Event...",
                   menu=events_menu,
                   triggered=lambda: EventCreator.create_or_focus(gui=self))
        add_action(text="View Events",
                   menu=events_menu,
                   triggered=lambda: EventList.create_or_focus(gui=self))

        events_menu.addSeparator()

        add_action(text="Manage Event Types",
                   menu=events_menu,
                   triggered=lambda: EventTypeList.create_or_focus(gui=self))

    def create_or_open_database(self, filename=None):
        """
        Create or open a database. Called by the "Create or Open Database" menu
        item.

        Args:
            filename: Optional filename of the database to create/open. If
                unspecified, a file dialog will be opened so that the user can
                select a file or choose a filename.

        """
        window = self.main_window
        if not filename:
            filename = dialogboxes.create_or_open_database_dialog(window)
        if filename:
            self.close_database()
            self.db = rksmanager.database.Database(filename)
            self.database_is_open.emit(True)
            version = self.db.get_sqlite_user_version()
            if version < self.db.expected_sqlite_user_version:
                if dialogboxes.convert_database_dialog(window):
                    success = False
                    try:
                        self.db.apply_migrations()
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
            elif version > self.db.expected_sqlite_user_version:
                self.close_database()
                dialogboxes.old_software_dialog(window)

    def close_database(self):
        """
        Close the database if we currently have one open. Called by the "Close
        Database" menu item.

        """
        if self.db:
            self.tab_holder.close_all_tabs()
            self.db.close()
            self.db = None
            self.database_is_open.emit(False)
