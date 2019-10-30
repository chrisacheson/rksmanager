import tkinter as tk
import traceback
import types

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
        root = tk.Tk()
        self._build_menu_bar(root)
        root.mainloop()

    # Build the menu bar and add it to the specified window
    def _build_menu_bar(self, window):
        # Callbacks
        def create_database_callback():
            filename = dialogboxes.create_database_dialog()
            if filename:
                self._close_database()
                self._db = rksmanager.database.Database(filename)
                self._database_is_open()
                self._db.apply_migrations()

        def open_database_callback():
            filename = dialogboxes.open_database_dialog()
            if filename:
                self._close_database()
                self._db = rksmanager.database.Database(filename)
                self._database_is_open()
                schema_version = self._db.get_schema_version()
                if schema_version < self._db.expected_schema_version:
                    if dialogboxes.convert_database_dialog():
                        success = False
                        try:
                            self._db.apply_migrations()
                            success = True
                        except Exception as e:
                            print(traceback.format_exception(
                                etype=type(e),
                                value=e,
                                tb=e.__traceback__,
                            ))
                        if success:
                            dialogboxes.convert_database_success_dialog()
                        else:
                            self._close_database()
                            dialogboxes.convert_database_failure_dialog()
                    else:
                        # User declined to convert database, so we can't work
                        # with it
                        self._close_database()
                elif schema_version > self._db.expected_schema_version:
                    self._close_database()
                    dialogboxes.old_software_dialog()

        def close_database_callback():
            self._close_database()

        def create_person_callback():
            pass

        menu_bar = tk.Menu(window)
        self._widgets.menu_bar = menu_bar
        window.config(menu=menu_bar)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        self._widgets.file_menu = file_menu
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Create Database...",
                              command=create_database_callback)
        file_menu.add_command(label="Open Database...",
                              command=open_database_callback)
        file_menu.add_command(label="Close Database",
                              command=close_database_callback,
                              state=tk.DISABLED)
        file_menu.add_separator()
        file_menu.add_command(label="Exit",
                              command=window.quit)
        people_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="People", menu=people_menu,
                             state=tk.DISABLED)
        people_menu.add_command(label="Create new person record...",
                                command=create_person_callback)

    # Close the database if we currently have one open
    def _close_database(self):
        if self._db:
            self._db.close()
            self._db = None
            self._database_is_closed()

    # Change the state of various widgets in response to a database being
    # opened
    def _database_is_open(self):
        self._widgets.file_menu.entryconfig("Close Database",
                                            state=tk.NORMAL)
        self._widgets.menu_bar.entryconfig("People", state=tk.NORMAL)

    # Change the state of various widgets in response to a database being
    # closed
    def _database_is_closed(self):
        self._widgets.file_menu.entryconfig("Close Database",
                                            state=tk.DISABLED)
        self._widgets.menu_bar.entryconfig("People", state=tk.DISABLED)
