import tkinter.filedialog
import tkinter.messagebox


def create_database_dialog():
    """
    "Create Database" file dialog.

    Returns:
        The file path chosen by the user as a string, or None if the user
        cancelled.

    """
    return tkinter.filedialog.asksaveasfilename(
        defaultextension=".sqlite",
        filetypes=[("SQLite", "*.sqlite")],
        initialfile="rks_database",
        title="Create Database",
    )


def open_database_dialog():
    """
    "Open Database" file dialog.

    Returns:
        The file path chosen by the user as a string, or None if the user
        cancelled.

    """
    return tkinter.filedialog.askopenfilename(
        filetypes=[("SQLite", "*.sqlite")],
        title="Open Database",
    )


def convert_database_dialog():
    """
    Ask the user whether to update an old database to the current schema
    version.

    Returns:
        True if the user answered yes, False if no.

    """
    return tkinter.messagebox.askyesno(
        title="Convert Database?",
        message=("This database was created with an older version of RKS"
                 " Manager. Do you want to convert it? It will become"
                 " inaccessible to older versions of this software."),
    )


def convert_database_success_dialog():
    """
    Tell the user that the database was successfully updated to the current
    schema version.

    """
    tkinter.messagebox.showinfo(
        title="Database Converted",
        message="Database successfully converted.",
    )


def convert_database_failure_dialog():
    """
    Tell the user that we failed to update the database to the current schema
    version.

    """
    tkinter.messagebox.showerror(
        title="Conversion Failed",
        message="Failed to convert database.",
    )


def old_software_dialog():
    """
    Tell the user that this version of RKS Manager is too old to access their
    database.

    """
    tkinter.messagebox.showerror(
        title="Software Out of Date",
        message=("Database was created with a newer version of"
                 " RKS Manager. You should upgrade to the"
                 " latest version."),
    )
