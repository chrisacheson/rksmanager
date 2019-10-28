import tkinter as tk
import traceback

import rksmanager.database

from . import dialogboxes


class Gui:
    """Builds the GUI and handles all user interaction."""
    def __init__(self):
        self._db = None

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
                # TODO: Enable "Close Database" menu command
                self._db.apply_migrations()

        def open_database_callback():
            filename = dialogboxes.open_database_dialog()
            if filename:
                self._close_database()
                self._db = rksmanager.database.Database(filename)
                # TODO: Enable "Close Database" menu command
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

        menu_bar = tk.Menu(window)
        window.config(menu=menu_bar)
        file_menu = tk.Menu(menu_bar)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Create Database...",
                              command=create_database_callback)
        file_menu.add_command(label="Open Database...",
                              command=open_database_callback)

    # If open, call the close() method on our Database object, and set our
    # reference to it back to None
    # TODO: Grey out the "Close Database" menu command
    def _close_database(self):
        if self._db:
            self._db.close()
            self._db = None
