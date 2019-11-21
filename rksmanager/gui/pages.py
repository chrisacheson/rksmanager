"""
"Task" widgets used as tab pages in RKS Manager's main window, or as their own
windows. Most of these are for viewing a table of records, viewing the details
of a specific record, or editing a record. Smaller "control" widgets go in the
gui.widgets module.

"""
from decimal import Decimal

from PySide2.QtWidgets import (QWidget, QFormLayout, QHBoxLayout, QPushButton,
                               QTableView, QVBoxLayout, QAbstractItemView)
from PySide2.QtCore import (Qt, QAbstractTableModel, QSortFilterProxyModel,
                            Signal)

from .widgets import (Label, LineEdit, TextEdit, ListLabel, ListEdit,
                      PrimaryItemListLabel, PrimaryItemListEdit, ComboListEdit,
                      MappedDoubleListLabel)


class BasePage(QWidget):
    """
    Base class for all tab page widgets. Subclasses should set the tab_name_fmt
    attribute to an appropriate format string.

    If the tab_name_fmt attribute contains any string formatting replacement
    fields, they will be replaced by the corresponding data from the widget's
    data set. The resulting tab name string is accessible through the tab_name
    attribute.

        tab_name_fmt = "Person Details ({id:d}: {first_name_or_nickname})"

    """
    @classmethod
    def get_tab_id(cls, data_id=None):
        """
        Get the tab id that an instance of this class would use.

        Args:
            data_id: The id of the data set that the tab page will be working
                with. Subclasses will either require this to be specified or
                will ignore it.

        Returns:
            The tab id as a string.

        """
        return "{class_name}({data_id})".format(class_name=cls.__name__,
                                                data_id=data_id or "")

    @property
    def tab_name(self):
        """
        The name of the tab page. Determined by the tab_name_fmt attribute and
        the widget's current data set.

        """
        return self.tab_name_fmt.format(**self.data)

    def refresh(self):
        """
        Populate the widget with fresh data from the database. This can be
        connected to the Gui.database_modified() signal in order to
        auto-refresh the widget's data whenever a change is made to the
        database. The widget's refresher attribute should also be set to a
        function that takes no arguments and returns an appropriate data set
        from the database.

        """
        self.data = self.refresher()


class BaseEditor(BasePage):
    """
    Generic record editor widget. Subclasses should set the fields attribute to
    a sequence of 2-tuples or 3-tuples, each containing a field ID and label,
    and optionally a widget class. If unspecified, the widget class defaults to
    LineEdit. The default can be changed with the default_widget attribute. For
    example:

        default_widget = MySpecialCustomInputWidget
        fields = (
            ("id", "Person ID", Label),
            ("first_name_or_nickname", "First name or nickname"),
            ("pronouns", "Pronouns"),
            ("notes", "Notes", TextEdit),
        )

    Args:
        data: Optional initial data set as a dictionary of field id and widget
            value pairs. Can be set later using the data attribute.
        extra_data: Optional supplemental data set, as a dictionary of field id
            and extra value pairs. Can be set later using the extra_data
            attribute.

    """
    default_widget = LineEdit

    def __init__(self, data=None, extra_data=None):
        self._data = data or dict()
        self._data_widgets = {}
        super().__init__()
        layout = QFormLayout()
        for i, field in enumerate(self.fields):
            if len(field) > 2:
                field_id, label, widget_type = field
            else:
                field_id, label = field
                widget_type = self.default_widget
            widget = widget_type()
            layout.addRow(label, widget)
            self._data_widgets[field_id] = widget
        self.setLayout(layout)
        self.place_buttons()
        self.values = self._data
        self.extra_data = extra_data or dict()

    def place_buttons(self):
        """
        Place the cancel and save buttons into the layout. Shouldn't be called
        by external code, but can be overridden by subclasses to change
        which buttons are used and how they are placed.

        """
        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        button_layout.addWidget(self.cancel_button)
        self.save_button = QPushButton("Save")
        button_layout.addWidget(self.save_button)
        self.layout().addRow(button_layout)

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

        Setting this will update the values of all of the data widgets
        specified in the dictionary.

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

    @property
    def extra_data(self):
        """
        The current supplemental data of all of the page's data widgets as a
        dictionary of field id and widget extra value pairs.

        Setting this will update the extra_data attributes of all of the data
        widgets specified in the dictionary.

        """
        extra_data = dict()
        for field_id, widget in self._data_widgets.items():
            extra_data[field_id] = getattr(widget, "extra_data", None)
        return extra_data

    @extra_data.setter
    def extra_data(self, extra_data):
        keys = self._data_widgets.keys() & extra_data.keys()
        for key in keys:
            self._data_widgets[key].extra_data = extra_data[key]


class BaseDetails(BaseEditor):
    """
    Generic record viewer widget. Subclasses should set the fields attribute to
    a sequence of 2-tuples or 3-tuples, each containing a field ID and label,
    and optionally a widget class. If unspecified, the widget class defaults to
    Label. The default can be changed with the default_widget attribute. For
    example:

        default_widget = MySpecialCustomLabelWidget
        fields = (
            ("id", "Person ID"),
            ("first_name_or_nickname", "First name or nickname"),
            ("aliases", "Aliases", ListLabel),
            ("pronouns", "Pronouns"),
            ("notes", "Notes"),
        )

    Args:
        data: Optional initial data set. Can be set later using the data
            attribute.

    """
    default_widget = Label

    def place_buttons(self):
        self.edit_button = QPushButton("Edit")
        self.layout().addRow(self.edit_button)


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


class BaseList(BasePage):
    """
    Generic table viewer widget. Subclasses should set the model_class
    attribute to a subclass of BaseListModel.

    Args:
        data: Optional initial data set, as a 2-dimensional list or similar.
            Can be set later using the data attribute.
        extra_data: Optional supplemental data set, as a dictionary. This data
            won't be displayed in the QTableView, but can be used for other
            purposes such as setting the tab name. Can be set later using the
            extra_data attribute.

    """
    table_double_clicked = Signal(int)

    def __init__(self, data=None, extra_data=None):
        super().__init__()
        self._model = self.model_class()
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self._model)
        layout = QVBoxLayout()
        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.doubleClicked.connect(
            self.emit_table_double_click_with_data_id
        )
        layout.addWidget(self.table_view)
        self.setLayout(layout)
        self.data = data or list()
        self.extra_data = extra_data or dict()

    def emit_table_double_click_with_data_id(self, index):
        """
        Emit the table_double_clicked signal with the data ID of the row that
        was clicked on. Called when the user double clicks on a row in our
        QTableView.

        Args:
            The QModelIndex passed by the table_view.doubleClicked signal.

        """
        # TODO: Figure out a better way to get the ID besides assuming that
        # it's in the first (or any) column
        id_index = index.siblingAtColumn(0)
        try:
            data_id = int(index.model().itemData(id_index)[0])
            self.table_double_clicked.emit(data_id)
        except ValueError:
            pass

    @property
    def data(self):
        """The page's current data set (a 2-dimensional sequence)."""
        return self._model.dataset

    @data.setter
    def data(self, data):
        self._model.populate(data)
        self.proxy_model.invalidate()

    @property
    def tab_name(self):
        """
        The name of the tab page. Determined by the tab_name_fmt attribute and
        the widget's current supplemental data set.

        """
        return self.tab_name_fmt.format(**self.extra_data)


class PersonDetails(BaseDetails):
    """Viewer widget for Create Person and Person Details tabs."""
    tab_name_fmt = "Person Details ({id:d}: {first_name_or_nickname})"

    fields = (
        ("id", "Person ID"),
        ("first_name_or_nickname", "First name\nor nickname"),
        ("aliases", "Aliases", ListLabel),
        ("email_addresses", "Email Addresses", PrimaryItemListLabel),
        ("other_contact_info", "Other Contact Info", MappedDoubleListLabel),
        ("pronouns", "Pronouns"),
        ("notes", "Notes"),
    )


class PersonEditor(BaseEditor):
    """Editor widget for the Person Details tab."""
    tab_name_fmt = "Edit Person ({id:d}: {first_name_or_nickname})"

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
    tab_name_fmt = "Create Person"


class PersonListModel(BaseListModel):
    """Model for holding person data to be displayed by a QTableView."""
    headers = ("ID", "Name", "Email Address", "Pronouns", "Notes")


class PersonList(BaseList):
    """Table viewer widget for the People tab."""
    tab_name_fmt = "People"

    model_class = PersonListModel


class ContactInfoTypeListModel(BaseListModel):
    """
    Model for holding contact info type data to be displayed by a QTableView.

    """
    headers = ("ID", "Name", "Usage Count")


class ContactInfoTypeList(BaseList):
    """Table viewer widget for the Manage Contact Info Types tab."""
    tab_name_fmt = "Manage Contact Info Types"

    model_class = ContactInfoTypeListModel

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_button = QPushButton("Add New Contact Info Type")
        self.layout().insertWidget(0, self.add_button)


class MembershipTypeListModel(BaseListModel):
    """
    Model for holding membership type data to be displayed by a QTableView.

    """
    headers = ("ID", "Name", "Active Count")


class MembershipTypeList(BaseList):
    """Table viewer widget for the Manage Membership Types tab."""
    tab_name_fmt = "Manage Membership Types"

    model_class = MembershipTypeListModel

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
    tab_name_fmt = "{name} Membership Pricing Options"

    model_class = MembershipPricingOptionListModel

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_button = QPushButton("Add New Pricing Option")
        self.layout().insertWidget(0, self.add_button)


class MembershipPricingOptionEditor(BaseEditor):
    """Editor widget for the Edit Pricing Option tab."""
    tab_name_fmt = "Edit {membership_type_name} Membership Pricing Option"

    fields = (
        ("id", "Pricing Option ID", Label),
        ("membership_type_id", "Membership Type ID", Label),
        ("membership_type_name", "Membership Type Name", Label),
        ("length_months", "Length (Months)", LineEdit),
        ("price", "Price", LineEdit),
    )


class MembershipPricingOptionCreator(MembershipPricingOptionEditor):
    """Editor widget for the Create Pricing Option tab."""
    tab_name_fmt = "Create {membership_type_name} Membership Pricing Option"
