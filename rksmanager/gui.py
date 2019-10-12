import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox
import traceback

import rksmanager.database


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
        def create_database_dialog():
            filename = tkinter.filedialog.asksaveasfilename(
                defaultextension=".sqlite",
                filetypes=[("SQLite", "*.sqlite")],
                initialfile="rks_database",
                title="Create Database",
            )
            if filename:
                self._db = rksmanager.database.Database(filename)
                self._db.apply_migrations()

        def open_database_dialog():
            filename = tkinter.filedialog.askopenfilename(
                filetypes=[("SQLite", "*.sqlite")],
                title="Open Database",
            )
            if filename:
                self._db = rksmanager.database.Database(filename)
                schema_version = self._db.get_schema_version()
                if schema_version < self._db.expected_schema_version:
                    answer = tkinter.messagebox.askyesno(
                        title="Convert Database?",
                        message=("This database was created with an older"
                                 " version of RKS Manager. Do you want to"
                                 " convert it? It will become inaccessible to"
                                 " older versions of this software."),
                    )
                    if answer:
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
                            tkinter.messagebox.showinfo(
                                title="Database Converted",
                                message="Database successfully converted.",
                            )
                        else:
                            # TODO: Close database connection and file
                            tkinter.messagebox.showerror(
                                title="Conversion Failed",
                                message="Failed to convert database.",
                            )
                elif schema_version > self._db.expected_schema_version:
                    # TODO: Close database connection and file
                    tkinter.messagebox.showerror(
                        title="Software Out of Date",
                        message=("Database was created with a newer version of"
                                 " RKS Manager. You should upgrade to the"
                                 " latest version."),
                    )

        menu_bar = tk.Menu(window)
        window.config(menu=menu_bar)
        file_menu = tk.Menu(menu_bar)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Create Database...",
                              command=create_database_dialog)
        file_menu.add_command(label="Open Database...",
                              command=open_database_dialog)
