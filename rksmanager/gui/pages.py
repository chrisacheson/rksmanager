"""
"Task" widgets used as tab pages in RKS Manager's main window, or as their own
windows. Most of these are for viewing a table of records, viewing the details
of a specific record, or editing a record. Smaller "control" widgets go in the
gui.widgets module.

"""
from decimal import Decimal

from PySide2.QtWidgets import (QWidget, QFormLayout, QHBoxLayout, QPushButton,
                               QTableView, QVBoxLayout, QAbstractItemView)
from PySide2.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel

from .widgets import (Label, LineEdit, TextEdit, ListLabel, ListEdit,
                      PrimaryItemListLabel, PrimaryItemListEdit, ComboListEdit)


class RefreshMixin:
    """
    Adds a refresh() method to any widget inheriting this, which can be
    connected to the Gui.database_modified() signal. The widget's refresher
    attribute should be set to a function that takes no arguments and returns a
    fresh data set from the database.

    """
    def refresh(self):
        """Populate the widget with fresh data from the database."""
        self.data = self.refresher()


class BaseDetailsOrEditor(QWidget):
    """Parent class for BaseDetails and BaseEditor."""
    def __init__(self, data=None):
        """
        Args:
            data: Optional initial data set. Can be set later using the data
                attribute.

        """
        self._data = data or dict()
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
        self.values = self._data
        self.setLayout(layout)

    @property
    def data(self):
        """
        The page's current data set (a dictionary of field id and widget
        value pairs), without any modifications by the user.

        Setting this will replace the data set and update any widget values
        that haven't been changed by the user.

        """
        return self._data

    @data.setter
    def data(self, data):
        keys = self._data_widgets.keys() & data.keys()
        for key in keys:
            widget = self._data_widgets[key]
            if self._data.get(key, widget.empty_value) == widget.value:
                widget.value = data[key]
        self._data = data

    @property
    def values(self):
        """
        The current values of all of the page's data widgets as a dictionary of
        field id and widget value pairs.

        Setting this will update the values of all of the data widgets.

        """
        values = dict()
        for field_id, widget in self._data_widgets.items():
            values[field_id] = widget.value
        return values

    @values.setter
    def values(self, values):
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        button_layout.addWidget(self.cancel_button)
        self.save_button = QPushButton("Save")
        button_layout.addWidget(self.save_button)
        self.layout().addRow(button_layout)


class BaseListModel(QAbstractTableModel):
    """
    Generic Model object for holding data to be displayed by a QTableView
    widget. Subclasses should set the headers attribute to a tuple of column
    headers to be displayed by the QTableView. For example:

    headers = ("ID", "Name", "Email Address", "Pronouns", "Notes")

    """
    def __init__(self):
        self.dataset = []
        super().__init__()

    def populate(self, data):
        """
        Assign a new data set to this model.

        Args:
            data: The data set as a 2-dimensional list or similar.

        """
        self.dataset = data
        # For some reason this causes segmentation faults, so we'll just let
        # the list widget call the proxy model's invalidate() method instead
        # self.layoutChanged.emit()

    def rowCount(self, index):
        return len(self.dataset)

    def columnCount(self, index):
        return len(self.headers)

    def data(self, index, role):
        if role == Qt.DisplayRole:
            row = self.dataset[index.row()]
            cell = row[index.column()]
            if isinstance(cell, Decimal):
                # QTableView won't display Decimal objects, so return a float
                return float(cell)
            else:
                return cell

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

    @property
    def data(self):
        """The page's current data set (a 2-dimensional sequence)."""
        return self._model.dataset

    @data.setter
    def data(self, data):
        self._model.populate(data)
        self.proxy_model.invalidate()


class PersonDetails(BaseDetails):
    """Viewer widget for Create Person and Person Details tabs."""
    tab_id = "person_details_{:d}"
    tab_name = "Person Details ({id:d}: {first_name_or_nickname})"

    fields = (
        ("id", "Person ID"),
        ("first_name_or_nickname", "First name\nor nickname"),
        ("aliases", "Aliases", ListLabel),
        ("email_addresses", "Email Addresses", PrimaryItemListLabel),
        ("other_contact_info", "Other Contact Info", ListLabel),
        ("pronouns", "Pronouns"),
        ("notes", "Notes"),
    )


class PersonEditor(BaseEditor):
    """Editor widget for the Person Details tab."""
    tab_id = "edit_person_{:d}"
    tab_name = "Edit Person ({id:d}: {first_name_or_nickname})"

    fields = (
        ("id", "Person ID", Label),
        ("first_name_or_nickname", "First name\nor nickname", LineEdit),
        ("aliases", "Aliases", ListEdit),
        ("email_addresses", "Email Addresses", PrimaryItemListEdit),
        ("other_contact_info", "Other Contact Info", ComboListEdit),
        ("pronouns", "Pronouns", LineEdit),
        ("notes", "Notes", TextEdit),
    )


class PersonCreator(PersonEditor):
    """Editor widget for the Create Person tab."""
    tab_id = "create_person"
    tab_name = "Create Person"


class PersonListModel(BaseListModel):
    """Model for holding person data to be displayed by a QTableView."""
    headers = ("ID", "Name", "Email Address", "Pronouns", "Notes")


class PersonList(BaseList):
    """Table viewer widget for the People tab."""
    tab_id = "view_people"
    tab_name = "People"

    model_class = PersonListModel


class ContactInfoTypeListModel(BaseListModel):
    """
    Model for holding contact info type data to be displayed by a QTableView.

    """
    headers = ("ID", "Name", "Usage Count")


class ContactInfoTypeList(BaseList):
    """Table viewer widget for the Manage Contact Info Types tab."""
    tab_id = "manage_contact_info_types"
    tab_name = "Manage Contact Info Types"

    model_class = ContactInfoTypeListModel

    def __init__(self):
        super().__init__()
        self.add_button = QPushButton("Add New Contact Info Type")
        self.layout().insertWidget(0, self.add_button)


class MembershipTypeListModel(BaseListModel):
    """
    Model for holding membership type data to be displayed by a QTableView.

    """
    headers = ("ID", "Name", "Active Count")


class MembershipTypeList(BaseList):
    """Table viewer widget for the Manage Membership Types tab."""
    tab_id = "manage_membership_types"
    tab_name = "Manage Membership Types"

    model_class = MembershipTypeListModel

    def __init__(self):
        super().__init__()
        self.add_button = QPushButton("Add New Membership Type")
        self.layout().insertWidget(0, self.add_button)


class MembershipPricingOptionListModel(BaseListModel):
    """
    Model for holding membership pricing option data to be displayed by a
    QTableView.

    """
    headers = ("ID", "Length (Months)", "Price")


class MembershipPricingOptionList(BaseList):
    """Table viewer widget for the Membership Type Pricing Options tab."""
    tab_id = "membership_type_pricing_options_{:d}"
    tab_name = "{membership_type_name} Membership Pricing Options"

    model_class = MembershipPricingOptionListModel

    def __init__(self):
        super().__init__()
        self.add_button = QPushButton("Add New Pricing Option")
        self.layout().insertWidget(0, self.add_button)


class MembershipPricingOptionEditor(BaseEditor):
    """Editor widget for the Edit Pricing Option tab."""
    tab_id = "edit_pricing_option_{:d}"
    tab_name = "Edit {membership_type_name} Membership Pricing Option"

    fields = (
        ("id", "Pricing Option ID", Label),
        ("membership_type_id", "Membership Type ID", Label),
        ("membership_type_name", "Membership Type Name", Label),
        ("length_months", "Length (Months)", LineEdit),
        ("price", "Price", LineEdit),
    )


class MembershipPricingOptionCreator(MembershipPricingOptionEditor):
    """Editor widget for the Create Pricing Option tab."""
    tab_id = "create_pricing_option_{:d}"
    tab_name = "Create {membership_type_name} Membership Pricing Option"
