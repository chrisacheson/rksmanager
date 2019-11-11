import functools

from PySide2.QtWidgets import (QTabWidget, QWidget, QGridLayout, QLabel,
                               QLineEdit, QTextEdit, QPushButton)


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
    def _new_tab_id(self, tab_id, widget):
        self._tab_ids[tab_id] = widget
        self._tab_ids_inverse[widget] = tab_id

    # Delete a tab ID
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

    def close_tab(self, index_or_widget):
        """
        Close the tab at the specified index or with the specified page widget,
        and delete the widget. Called when the tab's close button is clicked.

        Args:
            index_or_widget: The index of the tab to close, or the page widget
                corresponding to the tab.

        """
        if isinstance(index_or_widget, int):
            index = index_or_widget
            widget = self.widget(index)
        else:
            widget = index_or_widget
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
    set the getter_method and setter_method attributes appropriately.

    """
    getter_method = "text"
    setter_method = "setText"

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
    def __init__(self):
        super().__init__()
        self.setWordWrap(True)


class LineEdit(ValuePropertyMixin, QLineEdit):
    pass


class TextEdit(ValuePropertyMixin, QTextEdit):
    getter_method = "toPlainText"
    setter_method = "setPlainText"


class ListLabel(QLabel):
    def __init__(self):
        super().__init__()
        self._data = []

    def setText(self, items):
        super().setText("\n".join(items))

    @property
    def value(self):
        return self._data

    @value.setter
    def value(self, value):
        self._data = value
        self.setText(value)


class PrimaryItemListLabel(ListLabel):
    def setText(self, items):
        new_items = list(items)
        if new_items:
            new_items[0] += " (Primary)"
        super().setText(new_items)


class GridLayout(QGridLayout):
    def get_all_widget_coordinates(self):
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
        end_row = row + height - 1
        end_col = column + width - 1
        coordinates = []
        for coordinate in self.get_all_widget_coordinates():
            _, r, c, _, _ = coordinate
            if (row <= r <= end_row) and (column <= c <= end_col):
                coordinates.append(coordinate)
        return coordinates

    def remove_widgets_in_rect(self, row, column, height, width):
        widgets = []
        for coordinate in self.get_widget_coordinates_in_rect(row, column,
                                                              height, width):
            widget, _, _, _, _ = coordinate
            self.removeWidget(widget)
            widgets.append(widget)
        return widgets

    def shift_widgets_in_rect(self, row, column, height, width,
                              row_shift, col_shift):
        coordinates = self.get_widget_coordinates_in_rect(row, column,
                                                          height, width)
        for coordinate in coordinates:
            self.removeWidget(coordinate[0])
        for w, r, c, rspan, cspan in coordinates:
            self.addWidget(w, r + row_shift, c + col_shift, rspan, cspan)

    def insert_row(self, insert_index, new_row):
        num_rows, num_columns = self.rowCount(), self.columnCount()
        rect_height = num_rows - insert_index
        self.shift_widgets_in_rect(insert_index, 0,
                                   rect_height, num_columns,
                                   1, 0)  # Down by 1
        for widget, column, colspan in new_row:
            self.addWidget(widget, insert_index, column, 1, colspan)

    def remove_row(self, index):
        num_rows, num_columns = self.rowCount(), self.columnCount()
        removed_widgets = self.remove_widgets_in_rect(index, 0, 1, num_columns)

        row_below_removed = index + 1
        rect_height = num_rows - row_below_removed
        self.shift_widgets_in_rect(row_below_removed, 0,
                                   rect_height, num_columns,
                                   -1, 0)  # Up by 1
        return removed_widgets


class ListEdit(QWidget):
    def __init__(self):
        super().__init__()
        # We have to track this ourselves, because QGridLayout.rowCount() never
        # shrinks
        self.num_items = 0
        self.before_append_callback = None
        self.layout = GridLayout()
        self._text_box = QLineEdit()

        def add():
            self.append(self._text_box.text())
            self._text_box.setText("")
        add_button = QPushButton("+")
        add_button.clicked.connect(add)

        self.build_text_box_row(self._text_box, add_button)
        self.setLayout(self.layout)

    def build_text_box_row(self, text_box, add_button):
        self.layout.insert_row(0, (
            (text_box, 0, 1),  # Column 0, span 1
            (add_button, 1, 1),  # Column 1, span 1
        ))

    def build_label_row(self, index, label, remove_button):
        self.layout.insert_row(index, (
            (label, 0, 1),  # Column 0, span 1
            (remove_button, 1, 1),  # Column 1, span 1
        ))

    def append(self, text):
        if (not text) or (text in self.value):
            return

        def remove(button):
            layout_index = self.layout.indexOf(button)
            row_index, _, _, _ = self.layout.getItemPosition(layout_index)
            self._text_box.setText(self.pop(row_index))
        remove_button = QPushButton("-")
        remove_button.clicked.connect(functools.partial(remove, remove_button))

        self.build_label_row(self.num_items, QLabel(text), remove_button)
        self.num_items += 1

    def get_item(self, index):
        return self.layout.itemAtPosition(index, 0).widget().text()

    def set_item(self, index, text):
        self.layout.itemAtPosition(index, 0).widget().setText(text)

    def pop(self, index):
        text = self.get_item(index)
        removed_widgets = self.layout.remove_row(index)
        for widget in removed_widgets:
            widget.deleteLater()
        self.num_items -= 1
        return text

    @property
    def value(self):
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
    def build_text_box_row(self, text_box, add_button):
        self.layout.insert_row(0, (
            (text_box, 0, 2),  # Column 0, span 2
            (add_button, 2, 1),  # Column 2, span 1
        ))

    def build_label_row(self, index, label, remove_button):
        if index == 0:
            primary_widget = QLabel("(Primary)")
        else:
            def make_primary(button):
                layout_index = self.layout.indexOf(button)
                row_index, _, _, _ = self.layout.getItemPosition(layout_index)
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
        text = super().pop(index)
        if index == 0 and self.num_items:
            # First row was removed and there are still items left, so swap new
            # first row's Make Primary button for a Primary label
            primary_button = self.layout.itemAtPosition(0, 1).widget()
            self.layout.removeWidget(primary_button)
            primary_button.deleteLater()
            self.layout.addWidget(QLabel("(Primary)"), 0, 1)
        return text
