"""
"Control" widgets that are generically useful. "Task" widgets specific to RKS
Manager go in the gui.pages module.

"""
import functools

from PySide2.QtWidgets import (QTabWidget, QWidget, QGridLayout, QLabel,
                               QLineEdit, QTextEdit, QPushButton, QComboBox)


class TabHolder(QTabWidget):
    """
    A QTabWidget with some extra methods. Used as the central widget of our
    main window.

    """
    def __init__(self):
        super().__init__()
        self.setMovable(True)
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.close_tab)
        self._tab_ids = {}
        self._tab_ids_inverse = {}

    # Establish a new tab ID
    #
    # Args:
    #   tab_id: The tab ID (usually a string) to create.
    #   widget: The page widget associated with the ID.
    def _new_tab_id(self, tab_id, widget):
        self._tab_ids[tab_id] = widget
        self._tab_ids_inverse[widget] = tab_id

    # Delete a tab ID
    #
    # Args:
    #   tab_id: The tab ID (usually a string) to delete.
    def _del_tab_id(self, tab_id):
        widget = self._tab_ids[tab_id]
        del self._tab_ids[tab_id]
        del self._tab_ids_inverse[widget]

    def addTab(self, widget, label, tab_id, before=None):
        """
        Create a new tab. Overrides QTabWidget's addTab() method.

        Args:
            widget: The widget to be displayed by the tab.
            label: The name to display on the tab.
            tab_id: Unique ID string used to refer to the tab later.
            before: Optional ID or page widget of the tab that the new tab will
                be inserted in front of. If unspecified, the new tab will be
                added to the end of the tab bar.

        """
        if before:
            if isinstance(before, QWidget):
                before_widget = before
            else:
                before_widget = self.get_tab(before)
            index = self.indexOf(before_widget)
            super().insertTab(index, widget, label)
        else:
            super().addTab(widget, label)
        self._new_tab_id(tab_id, widget)

    def get_tab(self, tab_id):
        """
        Retrieve the tab with the specified ID.

        Args:
            tab_id: The ID of the tab to get.

        Returns:
            The tab with the specified ID, or None if there is no such tab.

        """
        return self._tab_ids.get(tab_id)

    def close_tab(self, tab):
        """
        Close the specified tab and delete the widget. Called when the tab's
        close button is clicked.

        Args:
            tab: The index, tab ID, or page widget of the tab to close.

        """
        if isinstance(tab, int):
            index = tab
            widget = self.widget(index)
        elif isinstance(tab, QWidget):
            widget = tab
            index = self.indexOf(widget)
        else:
            widget = self.get_tab(tab)
            index = self.indexOf(widget)
        tab_id = self._tab_ids_inverse[widget]
        self._del_tab_id(tab_id)
        self.removeTab(index)
        widget.deleteLater()

    def close_all_tabs(self):
        """Close all tabs and delete all page widgets."""
        self.clear()
        for widget in self._tab_ids.values():
            widget.deleteLater()
        self._tab_ids = {}
        self._tab_ids_inverse = {}


class ValuePropertyMixin:
    """
    Add a value property to any widget inheriting this. Widgets that use
    methods other than text() and setText() to get and set their value should
    set the getter_method and setter_method attributes appropriately. Non-text
    widgets should also set their empty_value attribute to whatever value the
    widget has before its value is set.

    """
    getter_method = "text"
    setter_method = "setText"
    empty_value = None

    @property
    def value(self):
        """
        Get or set the widget's current value. A widget containing an empty
        string will return a value of None. Setting a widget's value to None
        will assign it an empty string.

        """
        getter = getattr(self, self.getter_method)
        v = getter()
        if v == "":
            return None
        else:
            return v

    @value.setter
    def value(self, value):
        setter = getattr(self, self.setter_method)
        if value is None:
            setter("")
        else:
            setter(str(value))


class Label(ValuePropertyMixin, QLabel):
    """A QLabel with a value property and word wrap enabled by default."""
    def __init__(self):
        super().__init__()
        self.setWordWrap(True)


class LineEdit(ValuePropertyMixin, QLineEdit):
    """A QLineEdit with a value property."""


class TextEdit(ValuePropertyMixin, QTextEdit):
    """A QTextEdit with a value property."""
    getter_method = "toPlainText"
    setter_method = "setPlainText"


class ListLabel(QLabel):
    """A label that displays a list of strings."""
    empty_value = []

    def __init__(self):
        super().__init__()
        self._data = []

    def setText(self, items):
        """
        Overrides QLabel.setText(). Don't use this, set the value property
        instead.

        Args:
            items: List of strings to display.

        """
        super().setText("\n".join(items))

    @property
    def value(self):
        """The widget's current list of strings."""
        return self._data

    @value.setter
    def value(self, value):
        self._data = value
        self.setText(value)


class PrimaryItemListLabel(ListLabel):
    """
    A ListLabel that displays "(Primary)" next to the first item in the list.

    """
    def setText(self, items):
        """
        Overrides ListLabel.setText(). Don't use this, set the value property
        instead.

        Args:
            items: List of strings to display.

        """
        new_items = list(items)
        if new_items:
            new_items[0] += " (Primary)"
        super().setText(new_items)


class GridLayout(QGridLayout):
    """
    A QGridLayout with methods for inserting and removing rows of widgets.

    """
    def get_widget_coordinates(self, widget):
        """
        Get the grid coordinates of a single widget managed by this layout.

        Args:
            widget: Widget to get the coordinates of.

        Returns:
            A (row, column, rowspan, colspan) tuple.

        """
        layout_index = self.indexOf(widget)
        return self.getItemPosition(layout_index)

    def get_all_widget_coordinates(self):
        """
        Get the coordinates of all widgets managed by this layout.

        Returns:
            A list of (widget, row, column, rowspan, colspan) tuples.

        """
        coordinates = []
        for i in range(self.count()):
            widget = self.itemAt(i).widget()
            if not widget:
                # TODO: Handle child layouts too?
                continue
            row, column, rowspan, colspan = self.getItemPosition(i)
            coordinates.append((widget, row, column, rowspan, colspan))
        return coordinates

    def get_widget_coordinates_in_rect(self, row, column, height, width):
        """
        Get all of the widgets in the specified rectangular area.

        Args:
            row: The index of the first row of the rectangle.
            column: The index of the first column of the rectangle.
            height: The number of rows in the rectangle.
            width: The number of columns in the rectangle.

        Returns:
            A list of (widget, row, column, rowspan, colspan) tuples.

        """
        end_row = row + height - 1
        end_col = column + width - 1
        coordinates = []
        for coordinate in self.get_all_widget_coordinates():
            _, r, c, _, _ = coordinate
            if (row <= r <= end_row) and (column <= c <= end_col):
                coordinates.append(coordinate)
        return coordinates

    def remove_widgets_in_rect(self, row, column, height, width):
        """
        Remove all of the widgets in the specified rectangular area from the
        layout.

        Args:
            row: The index of the first row of the rectangle.
            column: The index of the first column of the rectangle.
            height: The number of rows in the rectangle.
            width: The number of columns in the rectangle.

        Returns:
            A list of removed widgets.

        """
        widgets = []
        for coordinate in self.get_widget_coordinates_in_rect(row, column,
                                                              height, width):
            widget, _, _, _, _ = coordinate
            self.removeWidget(widget)
            widgets.append(widget)
        return widgets

    def shift_widgets_in_rect(self, row, column, height, width,
                              row_shift, col_shift):
        """
        Shift all of the widgets in the specified rectangular area by the
        specified number of rows and columns.

        Args:
            row: The index of the first row of the rectangle.
            column: The index of the first column of the rectangle.
            height: The number of rows in the rectangle.
            width: The number of columns in the rectangle.
            row_shift: The number of rows to shift the widgets by. If positive,
                the widgets will be shifted downwards, otherwise they'll be
                shifted upwards.
            col_shift: The number of columns to shift the widgets by. If
                positive, the widgets will be shifted rightwards, otherwise
                they'll be shifted leftwards.

        """
        coordinates = self.get_widget_coordinates_in_rect(row, column,
                                                          height, width)
        for coordinate in coordinates:
            self.removeWidget(coordinate[0])
        for w, r, c, rspan, cspan in coordinates:
            self.addWidget(w, r + row_shift, c + col_shift, rspan, cspan)

    def insert_row(self, insert_index, new_row):
        """
        Insert a row of widgets into the layout at the specified row index. The
        widgets currently in or below that row will be shifted downwards.

        Args:
            insert_index: The row index at which to insert the new row.
            new_row: A sequence of (widget, column, colspan) tuples.

        """
        num_rows, num_columns = self.rowCount(), self.columnCount()
        rect_height = num_rows - insert_index
        self.shift_widgets_in_rect(insert_index, 0,
                                   rect_height, num_columns,
                                   1, 0)  # Down by 1
        for widget, column, colspan in new_row:
            self.addWidget(widget, insert_index, column, 1, colspan)

    def remove_row(self, index):
        """
        Remove a row of widgets from the layout. The widgets below that row
        will be shifted upwards.

        Args:
            index: The index of the row to remove.

        Returns:
            A list of removed widgets.

        """
        num_rows, num_columns = self.rowCount(), self.columnCount()
        removed_widgets = self.remove_widgets_in_rect(index, 0, 1, num_columns)

        row_below_removed = index + 1
        rect_height = num_rows - row_below_removed
        self.shift_widgets_in_rect(row_below_removed, 0,
                                   rect_height, num_columns,
                                   -1, 0)  # Up by 1
        return removed_widgets


class ListEdit(QWidget):
    """
    A widget for editing a list of string values. Each displayed string has a
    remove button next to it. At the bottom there's a text box and add button
    for adding new strings. Removing a string will place it in the text box to
    be edited and re-added if desired.

    """
    # TODO: Focus the text box and highlight the text whenever it's populated
    # with a removed string?
    # TODO: Change the color of the text in the text box to light grey when the
    # text box doesn't have focus. Indicates to the user that the text won't be
    # saved unless they actually add it to the list.
    empty_value = []

    def __init__(self):
        super().__init__()
        # We have to track this ourselves, because QGridLayout.rowCount() never
        # shrinks
        self.num_items = 0
        self.before_append_callback = None
        self.layout = GridLayout()
        self._text_box = QLineEdit()

        # Add button callback. Appends the text in the text box to the list and
        # clears the text box.
        def add():
            self.append(self._text_box.text())
            self._text_box.setText("")
        add_button = QPushButton("+")
        add_button.clicked.connect(add)

        self.build_text_box_row(self._text_box, add_button)
        self.setLayout(self.layout)

    def build_text_box_row(self, text_box, add_button):
        """
        Place the text box and add button into the layout. Shouldn't be called
        by external code, but can be overridden by subclasses to change
        placement behavior.

        Args:
            text_box: The text box widget.
            add_button: The add button widget.

        """
        self.layout.insert_row(0, (
            (text_box, 0, 1),  # Column 0, span 1
            (add_button, 1, 1),  # Column 1, span 1
        ))

    def build_label_row(self, index, label, remove_button):
        """
        Insert a new label and remove button into the layout at the specified
        row index. Shouldn't be called by external code, but can be overridden
        by subclasses to change placement behavior.

        Args:
            index: The index of the row to insert the widgets at.
            label: The label widget.
            remove_button: The remove button widget.

        """
        self.layout.insert_row(index, (
            (label, 0, 1),  # Column 0, span 1
            (remove_button, 1, 1),  # Column 1, span 1
        ))

    def append(self, text):
        """
        Add a new string to the end of the list.

        Args:
            text: The string to add.

        """
        if (not text) or (text in self.value):
            return

        # Remove button callback. Removes the corresponding string from the
        # list and puts it in the text box.
        #
        # Args:
        #   button: The remove button widget that was clicked. Used to find out
        #       which row to remove.
        def remove(button):
            row_index, _, _, _ = self.layout.get_widget_coordinates(button)
            self._text_box.setText(self.pop(row_index))
        remove_button = QPushButton("-")
        remove_button.clicked.connect(functools.partial(remove, remove_button))

        self.build_label_row(self.num_items, QLabel(text), remove_button)
        self.num_items += 1

    def get_item(self, index):
        """
        Get the string at the specified index.

        Args:
            index: The index of the string to get.

        Returns:
            The string.

        """
        return self.layout.itemAtPosition(index, 0).widget().text()

    def set_item(self, index, text):
        """
        Set the string at the specified index.

        Args:
            index: The index of the string to replace.
            text: The new string.

        """
        self.layout.itemAtPosition(index, 0).widget().setText(text)

    def pop(self, index):
        """
        Remove and return the string at the specified index.

        Args:
            index: The index of the string to remove.

        Returns:
            The string.

        """
        text = self.get_item(index)
        removed_widgets = self.layout.remove_row(index)
        for widget in removed_widgets:
            widget.deleteLater()
        self.num_items -= 1
        return text

    @property
    def value(self):
        """The widget's current list of strings."""
        data = []
        for i in range(self.num_items):
            data.append(self.get_item(i))
        return data

    @value.setter
    def value(self, value):
        while self.num_items:
            self.pop(0)
        for text in value:
            self.append(text)


class PrimaryItemListEdit(ListEdit):
    """
    A ListEdit with an extra column, containg either a "(Primary)" label or a
    "Make Primary" button for each string in the list. Clicking on a make
    primary button will swap the corresponding string with the current primary
    string.

    """
    def build_text_box_row(self, text_box, add_button):
        """
        Place the text box and add button into the layout, giving the text box
        a colspan of 2. Overrides ListEdit.build_text_box_row(). Shouldn't be
        called by external code.

        Args:
            text_box: The text box widget.
            add_button: The add button widget.

        """
        self.layout.insert_row(0, (
            (text_box, 0, 2),  # Column 0, span 2
            (add_button, 2, 1),  # Column 2, span 1
        ))

    def build_label_row(self, index, label, remove_button):
        """
        Insert a new label, make primary button (or primary label), and remove
        button into the layout at the specified row index. Overrides
        ListEdit.build_label_row(). Shouldn't be called by external code.

        Args:
            index: The index of the row to insert the widgets at.
            label: The label widget.
            remove_button: The remove button widget.

        """
        if index == 0:
            primary_widget = QLabel("(Primary)")
        else:
            # Make primary button callback. Swaps the corresponding string with
            # the current primary string.
            #
            # Args:
            #   button: The make primary button widget that was clicked. Used
            #       to find out which string to swap.
            def make_primary(button):
                row_index, _, _, _ = self.layout.get_widget_coordinates(button)
                new_primary = self.get_item(row_index)
                old_primary = self.get_item(0)
                self.set_item(0, new_primary)
                self.set_item(row_index, old_primary)
            primary_widget = QPushButton("Make Primary")
            primary_widget.clicked.connect(functools.partial(make_primary,
                                                             primary_widget))
        self.layout.insert_row(index, (
            (label, 0, 1),  # Column 0, span 1
            (primary_widget, 1, 1),  # Column 1, span 1
            (remove_button, 2, 1),  # Column 2, span 1
        ))

    def pop(self, index):
        """
        Remove and return the string at the specified index. If this removes
        the primary string, mark the next string (if any) as primary. Overrides
        ListEdit.pop().

        Args:
            index: The index of the string to remove.

        """
        text = super().pop(index)
        if index == 0 and self.num_items:
            # First row was removed and there are still items left, so swap new
            # first row's Make Primary button for a Primary label
            primary_button = self.layout.itemAtPosition(0, 1).widget()
            self.layout.removeWidget(primary_button)
            primary_button.deleteLater()
            self.layout.addWidget(QLabel("(Primary)"), 0, 1)
        return text


class ComboListEdit(QWidget):
    """
    A ListEdit for pairs of values. When inputting a new pair, the first value
    is chosen from a combo box, and the second is entered into the usual text
    box.

    """
    empty_value = ([], [])

    def __init__(self):
        super().__init__()
        # We have to track this ourselves, because QGridLayout.rowCount() never
        # shrinks
        self.num_items = 0
        self.layout = GridLayout()
        self._combo_box = QComboBox()
        self._text_box = QLineEdit()

        # Add button callback. Appends the selected data in the combo box and
        # the text in the text box to the list and resets both.
        def add():
            text = self._text_box.text()
            if self._combo_box.currentIndex() == 0 or text == "":
                return
            self.append((self._combo_box.currentData(), text))
            self._combo_box.setCurrentIndex(0)
            self._text_box.setText("")
        add_button = QPushButton("+")
        add_button.clicked.connect(add)

        self.layout.insert_row(0, (
            (self._combo_box, 0, 1),  # Column 0, span 1
            (self._text_box, 1, 1),  # Column 1, span 1
            (add_button, 2, 1),  # Column 2, span 1
        ))
        self.setLayout(self.layout)

    def append(self, item):
        """
        Add a new item to the end of the list.

        Args:
            item: An (integer, string) tuple to add.

        """
        combo_data, text = item
        if (not combo_data) or (not text) or (item in self.value):
            return

        # Remove button callback. Removes the corresponding item from the list
        # and puts it in the combo box and text box.
        #
        # Args:
        #   button: The remove button widget that was clicked. Used to find out
        #       which row to remove.
        def remove(button):
            row_index, _, _, _ = self.layout.get_widget_coordinates(button)
            combo_data, text = self.pop(row_index)
            combo_index = self._combo_box.findData(combo_data)
            self._combo_box.setCurrentIndex(combo_index)
            self._text_box.setText(text)
        remove_button = QPushButton("-")
        remove_button.clicked.connect(functools.partial(remove, remove_button))

        combo_index = self._combo_box.findData(combo_data)
        combo_text = self._combo_box.itemText(combo_index)
        self.layout.insert_row(self.num_items, (
            (QLabel(combo_text), 0, 1),  # Column 0, span 1
            (QLabel(text), 1, 1),  # Column 1, span 1
            (remove_button, 2, 1),  # Column 2, span 1
        ))
        self.num_items += 1

    def get_item(self, index):
        """
        Get the item at the specified index.

        Args:
            index: The index of the item to get.

        Returns:
            The item at the specified index as an (integer, string) tuple.

        """
        combo_text = self.layout.itemAtPosition(index, 0).widget().text()
        combo_index = self._combo_box.findText(combo_text)
        combo_data = self._combo_box.itemData(combo_index)
        text = self.layout.itemAtPosition(index, 1).widget().text()
        return (combo_data, text)

    def pop(self, index):
        """
        Remove and return the item at the specified index.

        Args:
            index: The index of the item to remove.

        Returns:
            The item as an (integer, string) tuple.

        """
        item = self.get_item(index)
        removed_widgets = self.layout.remove_row(index)
        for widget in removed_widgets:
            widget.deleteLater()
        self.num_items -= 1
        return item

    @property
    def value(self):
        """
        A 2-tuple containing a list of the widget's items, and a list of the
        combo box's items. For example:

        (
            [
                # Widget items. The integers represent which combo box item the
                # user selected.
                (2, "Text entered by the user"),
                (1, "More text entered by the user"),
                (3, "Even more text entered by the user"),
            ],
            [
                # Combo box items. The integers are item IDs, while the strings
                # are the text actually shown to the user in the combo box.
                (1, "Combo box option A"),
                (2, "Combo box option B"),
                (3, "Combo box option C"),
            ],
        )

        """
        items = []
        for i in range(self.num_items):
            items.append(self.get_item(i))
        combo_items = []
        # Skip blank first item
        for i in range(1, self._combo_box.count()):
            combo_data = self._combo_box.itemData(i)
            combo_text = self._combo_box.itemText(i)
            combo_items.append((combo_data, combo_text))
        return (items, combo_items)

    @value.setter
    def value(self, value):
        while self.num_items:
            self.pop(0)
        self._combo_box.clear()
        items, combo_items = value
        self._combo_box.addItem("")
        for combo_item in combo_items:
            combo_data, combo_text = combo_item
            self._combo_box.addItem(combo_text, combo_data)
        for item in items:
            self.append(item)
