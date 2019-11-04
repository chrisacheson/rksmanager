from PySide2.QtWidgets import QFileDialog, QMessageBox


def create_or_open_database_dialog(parent):
    """
    "Create or Open Database" file dialog.

    Args:
        parent: The parent widget to display the dialog over.

    Returns:
        The file path chosen by the user as a string, or an empty string if the
        user cancelled.

    """
    path, _ = QFileDialog.getSaveFileName(
        parent=parent,
        caption="Create or Open Database",
        dir="rks_database.rksm",
        filter="RKS Manager Databases (*.rksm)",
        options=QFileDialog.DontConfirmOverwrite,
    )
    return path


def convert_database_dialog(parent):
    """
    Ask the user whether to update an old database to the current version.

    Args:
        parent: The parent widget to display the dialog over.


    Returns:
        True if the user answered yes, False if no.

    """
    response = QMessageBox.question(
        parent,
        "Convert Database?",
        ("This database was created with an older version of RKS Manager. Do"
         " you want to convert it? It will become inaccessible to older"
         " versions of this software."),
    )
    return response == QMessageBox.Yes


def convert_database_success_dialog(parent):
    """
    Tell the user that the database was successfully updated to the current
    version.

    Args:
        parent: The parent widget to display the dialog over.

    """
    QMessageBox.information(parent, "Database Converted",
                            "Database successfully converted.")


def convert_database_failure_dialog(parent):
    """
    Tell the user that we failed to update the database to the current version.

    Args:
        parent: The parent widget to display the dialog over.

    """
    QMessageBox.critical(parent, "Conversion Failed",
                         "Failed to convert database.")


def old_software_dialog(parent):
    """
    Tell the user that this version of RKS Manager is too old to access their
    database.

    Args:
        parent: The parent widget to display the dialog over.

    """
    QMessageBox.critical(
        parent,
        "Software Out of Date",
        ("Database was created with a newer version of RKS Manager. You should"
         " upgrade to the latest version."),
    )
