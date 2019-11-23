"""
"Task" widgets used as tab pages in RKS Manager's main window, or as their own
windows. Most of these are for viewing a table of records, viewing the details
of a specific record, or editing a record. Smaller "control" widgets go in the
gui.widgets module.

"""
from decimal import Decimal
import functools
import sys
import datetime

from PySide2.QtWidgets import (QWidget, QFormLayout, QHBoxLayout, QPushButton,
                               QTableView, QVBoxLayout, QAbstractItemView)
from PySide2.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel

from .widgets import (Label, LineEdit, TextEdit, ListLabel, ListEdit,
                      PrimaryItemListLabel, PrimaryItemListEdit, ComboListEdit,
                      MappedDoubleListLabel)
from . import dialogboxes


class BasePage(QWidget):
    """
    Base class for all tab page widgets. Subclasses should set the tab_name_fmt
    attribute to an appropriate format string.

    If the tab_name_fmt attribute contains any string formatting replacement
    fields, they will be replaced by the corresponding data from the widget's
    data set. The resulting tab name string is accessible through the tab_name
    attribute.

        tab_name_fmt = "Person Details ({id:d}: {first_name_or_nickname})"

    Subclasses can define a load() method with no arguments, which will be
    called when the page is initialized and whenever the Gui.database_modified
    signal is emitted. Alternatively, the loader attribute can be set to the
    name of a Database method to use instead. If a data_id argument is passed
    to this on initialization, it will be passed to the Database method as the
    first argument.

    If the default_data attribute is set, it will be used as an initial data
    set for the page before the load() method is called.

    If the extra_loader attribute is set or the load_extra() method is defined,
    they will be treated similarly to the loader attribute and load() method
    for a supplemental data set. Supplemental data is currently not refreshed
    when the database changes.

    """
    def __init__(self, gui, data_id=None):
        super().__init__()
        self.gui = gui
        self.data_id = data_id

        # Python is picky about when we're allowed to set an attribute to a
        # class reference, so we may have to use class names instead. This loop
        # converts them back to references.
        for linked_class_attribute in ("details_class", "editor_class"):
            if hasattr(self, linked_class_attribute):
                linked_class = getattr(self, linked_class_attribute)
                if isinstance(linked_class, str):
                    this_module = sys.modules[__name__]
                    linked_class = getattr(this_module, linked_class)
                    setattr(self, linked_class_attribute, linked_class)

        if hasattr(self, "default_data"):
            self.data = self.default_data
        self.load()
        gui.database_modified.connect(self.load)
        self.load_extra()

    def load(self):
        """
        If the loader attribute is set, use the corresponding Database method
        to set this page's data.

        """
        if hasattr(self, "loader"):
            db_method = getattr(self.gui.db, self.loader)
            if self.data_id:
                db_method = functools.partial(db_method, self.data_id)
            self.data = db_method()

    def load_extra(self):
        """
        If the extra_loader attribute is set, use the corresponding Database
        method to set this page's supplemental data.

        """
        if hasattr(self, "extra_loader"):
            db_extra_method = getattr(self.gui.db, self.extra_loader)
            if self.data_id:
                self.extra_data = db_extra_method(self.data_id)
            else:
                self.extra_data = db_extra_method()

    @classmethod
    def create_or_focus(cls, gui, data_id=None, replace_tab=None):
        """
        Create a new tab page of this type with the given data ID, or focus it
        if it already exists.

        Args:
            gui: A reference to the main Gui object.
            data_id: Optional ID of the data set the page will be working with.
            replace_tab: Optional tab ID, page widget, or index of a tab to
                replace with this one.

        """
        tab_id = cls.get_tab_id(data_id)
        tab = gui.tab_holder.get_tab(tab_id)
        if not tab:
            tab = cls(gui, data_id)
            gui.tab_holder.addTab(tab, tab.tab_name, tab_id, replace_tab)
            if replace_tab:
                gui.tab_holder.close_tab(replace_tab)
        gui.tab_holder.setCurrentWidget(tab)
        return tab

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

    By default, "Cancel" and "Save" buttons will be created. Subclasses should
    either define a save() method which will be called when the save button is
    clicked, or override place_buttons() to create different buttons.

    """
    default_widget = LineEdit

    def __init__(self, *args, **kwargs):
        self._data = dict()
        self._data_widgets = dict()
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
        super().__init__(*args, **kwargs)
        self.setLayout(layout)
        self.place_buttons()

    def place_buttons(self):
        """
        Place the cancel and save buttons into the layout. Shouldn't be called
        by external code, but can be overridden by subclasses to change
        which buttons are used and how they are placed.

        """
        button_layout = QHBoxLayout()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.cancel)
        button_layout.addWidget(cancel_button)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save)
        button_layout.addWidget(save_button)
        self.layout().addRow(button_layout)

    def cancel(self):
        """Close the editor tab. Called when the cancel button is clicked."""
        self.gui.tab_holder.close_tab(self)

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

    By default, an "Edit" button will be created. Subclasses should either
    define an edit() method which will be called when the edit button is
    clicked, or override place_buttons() to create different buttons.
    Alternatively, if the editor_class attribute is set to a tab page widget
    class, that will be used to edit the data set.

    """
    default_widget = Label

    def place_buttons(self):
        edit_button = QPushButton("Edit")
        edit_button.clicked.connect(self.edit)
        self.layout().addRow(edit_button)

    def edit(self):
        """
        If the editor_class attribute is defined, replace this tab with an
        editor tab for the same data set. Called when the edit button is
        clicked.

        """
        self.editor_class.create_or_focus(self.gui, self.data_id,
                                          replace_tab=self)


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
            if isinstance(cell, datetime.time):
                return str(cell)
            else:
                return cell

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
                return self.headers[section]


class BaseList(BasePage):
    """
    Generic table viewer widget. Subclasses should set the model_class
    attribute to a subclass of BaseListModel.

    If a subclass defines an open_item method that accepts one argument, when
    an item in the table is clicked on, that method will be called with the ID
    of the clicked item. Alternatively, if the details_class attribute is set
    to a tab page widget class, that will be used to open the item.

    """
    def __init__(self, *args, **kwargs):
        self._model = self.model_class()
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self._model)
        layout = QVBoxLayout()
        self.table_view = QTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSortingEnabled(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.doubleClicked.connect(self.table_double_clicked)
        layout.addWidget(self.table_view)
        self.extra_data = dict()
        super().__init__(*args, **kwargs)
        self.setLayout(layout)

    def table_double_clicked(self, index):
        """
        Called when the QTableView is double clicked. If the open_item() method
        is defined, call it and pass the ID of the item that was clicked on.

        Args:
            The QModelIndex passed by the table_view.doubleClicked signal.

        """
        if hasattr(self, "open_item"):
            # TODO: Figure out a better way to get the ID besides assuming that
            # it's in the first (or any) column
            id_index = index.siblingAtColumn(0)
            try:
                data_id = int(index.model().itemData(id_index)[0])
                self.open_item(data_id)
            except ValueError:
                pass

    def open_item(self, data_id):
        """
        If the details_class attribute is defined, use it to open a Details tab
        for the specified item.

        """
        if hasattr(self, "details_class"):
            self.details_class.create_or_focus(self.gui, data_id)

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
    """Viewer widget for Person Details tab."""
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
    loader = "get_person"
    editor_class = "PersonEditor"

    def load_extra(self):
        """Fetch "other" contact info types from the database."""
        self.extra_data = {
            "other_contact_info": self.gui.db.get_other_contact_info_types()
        }


class BasePersonEditor(BaseEditor):
    """Common editor widget for the Create Person and Edit Person tabs."""
    fields = (
        ("id", "Person ID", Label),
        ("first_name_or_nickname", "First name\nor nickname", LineEdit),
        ("aliases", "Aliases", ListEdit),
        ("email_addresses", "Email Addresses", PrimaryItemListEdit),
        ("other_contact_info", "Other Contact Info", ComboListEdit),
        ("pronouns", "Pronouns", LineEdit),
        ("notes", "Notes", TextEdit),
    )

    def load_extra(self):
        """Fetch "other" contact info types from the database."""
        self.extra_data = {
            "other_contact_info": self.gui.db.get_other_contact_info_types()
        }

    def save(self):
        """
        Save the editor's current values to the database and replace this tab
        with a details tab for the same person. Called when the save button
        is clicked.

        """
        person_id = self.gui.db.save_person(self.values, self.data_id)
        self.gui.database_modified.emit()
        PersonDetails.create_or_focus(self.gui, person_id, replace_tab=self)


class PersonEditor(BasePersonEditor):
    """Editor widget for the Person Details tab."""
    tab_name_fmt = "Edit Person ({id:d}: {first_name_or_nickname})"
    loader = "get_person"

    def cancel(self):
        """
        Replace the editor tab with a details tab for the same person. Called
        when the cancel button is clicked.

        """
        PersonDetails.create_or_focus(self.gui, self.data_id, replace_tab=self)


class PersonCreator(BasePersonEditor):
    """Editor widget for the Create Person tab."""
    tab_name_fmt = "Create Person"
    default_data = {"id": "Not assigned yet"}


class PersonListModel(BaseListModel):
    """Model for holding person data to be displayed by a QTableView."""
    headers = ("ID", "Name", "Email Address", "Pronouns", "Notes")


class PersonList(BaseList):
    """Table viewer widget for the People tab."""
    tab_name_fmt = "People"

    model_class = PersonListModel
    loader = "get_people"
    details_class = PersonDetails


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
        add_button = QPushButton("Add New Contact Info Type")
        add_button.clicked.connect(self.add)
        self.layout().insertWidget(0, add_button)

    def add(self):
        """
        Prompt the user for a name, then create a new contact info type with
        that name.

        """
        # TODO: Prevent the user from adding "Email" or "Phone" once we get
        # around to doing validators
        window = self.gui.main_window
        name = dialogboxes.add_new_contact_info_type_dialog(window)
        if name is not None:
            self.gui.db.create_other_contact_info_type(name)
            self.gui.database_modified.emit()

    def load(self):
        """
        Fetch contact info type data from the database, and tack on rows for
        email and phone so that we have all contact info types covered.

        """
        ci_types = self.gui.db.get_other_contact_info_types_usage()
        email_address_count = self.gui.db.count_email_addresses()
        phone_number_count = self.gui.db.count_phone_numbers()
        ci_types.insert(0, ("", "Email", email_address_count))
        ci_types.insert(1, ("", "Phone", phone_number_count))
        self.data = ci_types


class MembershipTypeListModel(BaseListModel):
    """
    Model for holding membership type data to be displayed by a QTableView.

    """
    headers = ("ID", "Name", "Active Count")


class MembershipTypeList(BaseList):
    """Table viewer widget for the Manage Membership Types tab."""
    tab_name_fmt = "Manage Membership Types"

    model_class = MembershipTypeListModel
    loader = "get_membership_types"
    details_class = "MembershipPricingOptionList"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_button = QPushButton("Add New Membership Type")
        add_button.clicked.connect(self.add)
        self.layout().insertWidget(0, add_button)

    def add(self):
        """
        Prompt the user for a name, then create a new membership type with that
        name.

        """
        window = self.gui.main_window
        name = dialogboxes.add_new_membership_type_dialog(window)
        if name is not None:
            self.gui.db.create_membership_type(name)
            self.gui.database_modified.emit()


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
    loader = "get_membership_type_pricing_options"
    extra_loader = "get_membership_type"
    details_class = "MembershipPricingOptionEditor"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_button = QPushButton("Add New Pricing Option")
        add_button.clicked.connect(self.add)
        self.layout().insertWidget(0, add_button)

    def add(self):
        """Open a Create Pricing Option tab for the current membership type."""
        MembershipPricingOptionCreator.create_or_focus(self.gui, self.data_id)


class BaseMembershipPricingOptionEditor(BaseEditor):
    """
    Common editor widget for the Create Pricing Option and Edit Pricing Option
    tabs.

    """
    fields = (
        ("id", "Pricing Option ID", Label),
        ("membership_type_id", "Membership Type ID", Label),
        ("membership_type_name", "Membership Type Name", Label),
        ("length_months", "Length (Months)", LineEdit),
        ("price", "Price", LineEdit),
    )


class MembershipPricingOptionEditor(BaseMembershipPricingOptionEditor):
    """Editor widget for the Edit Pricing Option tab."""
    tab_name_fmt = "Edit {membership_type_name} Membership Pricing Option"

    loader = "get_membership_type_pricing_option"

    def save(self):
        """
        Save the editor's current values to the database and close this tab.
        Called when the save button is clicked.

        """
        self.gui.db.save_membership_type_pricing_option(self.values,
                                                        self.data_id)
        self.gui.database_modified.emit()
        self.cancel()


class MembershipPricingOptionCreator(BaseMembershipPricingOptionEditor):
    """Editor widget for the Create Pricing Option tab."""
    tab_name_fmt = "Create {membership_type_name} Membership Pricing Option"

    def load(self):
        """
        Load the membership type's data from the database and use it for the
        initial data set.

        """
        mtype_data = self.gui.db.get_membership_type(self.data_id)
        self.data = {"id": "Not assigned yet",
                     "membership_type_id": self.data_id,
                     "membership_type_name": mtype_data["name"]}

    def save(self):
        """
        Save the editor's current values to the database and close this tab.
        Called when the save button is clicked.

        """
        self.gui.db.save_membership_type_pricing_option(self.values)
        self.gui.database_modified.emit()
        self.cancel()


class EventTypeDetails(BaseDetails):
    """Viewer widget for the Event Type Details tab."""
    tab_name_fmt = "Event Type Details ({id:d}: {name})"
    fields = (
        ("id", "Event Type ID"),
        ("name", "Event Type Name"),
        ("default_start_time", "Default Start Time"),
        ("default_duration_minutes", "Default Duration (Minutes)"),
    )
    loader = "get_event_type"
    editor_class = "EventTypeEditor"


class BaseEventTypeEditor(BaseEditor):
    """
    Common editor widget for the Create Event Type and Edit Event Type tabs.

    """
    fields = (
        ("id", "Event Type ID", Label),
        ("name", "Event Type Name"),
        ("default_start_time", "Default Start Time"),
        ("default_duration_minutes", "Default Duration (Minutes)"),
    )

    def save(self):
        """
        Save the editor's current values to the database and close this tab.
        Called when the save button is clicked.

        """
        event_type_id = self.gui.db.save_event_type(self.values, self.data_id)
        self.gui.database_modified.emit()
        EventTypeDetails.create_or_focus(self.gui, event_type_id,
                                         replace_tab=self)


class EventTypeEditor(BaseEventTypeEditor):
    """Editor widget for the Edit Event Type tab."""
    tab_name_fmt = "Edit Event Type ({id:d}: {name})"
    loader = "get_event_type"

    def cancel(self):
        """
        Replace the editor tab with a details tab for the same event type.
        Called when the cancel button is clicked.

        """
        EventTypeDetails.create_or_focus(self.gui, self.data_id,
                                         replace_tab=self)


class EventTypeCreator(BaseEventTypeEditor):
    """Editor widget for the Create Event Type tab."""
    tab_name_fmt = "Create Event Type"
    default_data = {"id": "Not assigned yet"}


class EventTypeListModel(BaseListModel):
    """
    Model for holding event type data to be displayed by a QTableView.

    """
    headers = ("ID", "Event Type", "Default Start Time",
               "Default Duration (Minutes)")


class EventTypeList(BaseList):
    """Table viewer widget for the Manage Event Types tab."""
    tab_name_fmt = "Manage Event Types"
    model_class = EventTypeListModel
    loader = "get_event_types"
    details_class = EventTypeDetails

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_button = QPushButton("Add New Event Type")
        add_button.clicked.connect(self.add)
        self.layout().insertWidget(0, add_button)

    def add(self):
        """Open a Create Event Type tab."""
        EventTypeCreator.create_or_focus(self.gui)
