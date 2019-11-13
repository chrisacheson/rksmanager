"""
"Task" widgets used as tab pages in RKS Manager's main window, or as their own
windows. Most of these are for viewing a table of records, viewing the details
of a specific record, or editing a record. Smaller "control" widgets go in the
gui.widgets module.

"""
from PySide2.QtWidgets import (QWidget, QFormLayout, QHBoxLayout, QPushButton,
                               QTableView, QVBoxLayout, QAbstractItemView)
from PySide2.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel

from .widgets import (Label, LineEdit, TextEdit, ListLabel, ListEdit,
                      PrimaryItemListLabel, PrimaryItemListEdit)


class RefreshMixin:
    """
    Adds a refresh() method to any widget inheriting this, which can be
    connected to the Gui.database_modified() signal. The widget's refresher
    attribute should be set to a function that takes no arguments and returns a
    fresh data set from the database.

    """
    def refresh(self):
        """Populate the widget with fresh data from the database."""
        self.set_values(self.refresher())


class BaseDetailsOrEditor(QWidget):
    """Parent class for BaseDetails and BaseEditor."""
    def __init__(self):
        self._data_widgets = {}
        super().__init__()
        layout = QFormLayout()
        for i, field in enumerate(self.fields):
            if len(field) > 2:
                field_id, label, widget_type = field
            else:
                field_id, label = field
                widget_type = Label
            widget = widget_type()
            layout.addRow(label, widget)
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


class BaseDetails(RefreshMixin, BaseDetailsOrEditor):
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
        self.layout().addRow(self.edit_button)


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
        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        button_layout.addWidget(self.cancel_button)
        self.save_button = QPushButton("Save")
        button_layout.addWidget(self.save_button)
        self.layout().addRow(button_layout)

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
        # For some reason this causes segmentation faults, so we'll just let
        # the list widget call the proxy model's invalidate() method instead
        # self.layoutChanged.emit()

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


class BaseList(RefreshMixin, QWidget):
    """
    Generic table viewer widget. Subclasses should set the model_class
    attribute to a subclass of BaseListModel.

    """
    def __init__(self):
        super().__init__()
        self._model = self.model_class()
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self._model)
        layout = QVBoxLayout()
        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table_view)
        self.setLayout(layout)

    def set_values(self, values):
        """
        Set the current values to be displayed by the widget.

        Args:
            values: The data set as a 2-dimensional list or similar.

        """
        self._model.populate(values)
        self.proxy_model.invalidate()


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


class ContactInfoTypeListModel(BaseListModel):
    """
    Model for holding contact info type data to be displayed by a QTableView.

    """
    headers = ("ID", "Name", "Usage Count")


class ContactInfoTypeList(BaseList):
    """Table viewer widget for the Manage Contact Info Types tab."""
    model_class = ContactInfoTypeListModel

    def __init__(self):
        super().__init__()
        self.add_button = QPushButton("Add New Contact Info Type")
        self.layout().insertWidget(0, self.add_button)
