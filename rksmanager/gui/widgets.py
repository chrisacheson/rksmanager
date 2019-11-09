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

    @property
    def value(self):
        return self._data

    @value.setter
    def value(self, value):
        self._data = value
        self.setText("\n".join(value))


class GridLayout(QGridLayout):
    def append_row(self, new_row):
        self.insert_row(self.rowCount(), new_row)

    def insert_row(self, insert_index, new_row):
        num_rows = self.rowCount()
        if insert_index < num_rows:
            num_columns = self.columnCount()
            # Shift the insert_index row and all rows below it downward,
            # starting with the lowest row
            for i in reversed(range(insert_index, num_rows)):
                for j in range(num_columns):
                    layout_item = self.itemAtPosition(i, j)
                    if not layout_item:
                        continue
                    widget = layout_item.widget()
                    self.removeWidget(widget)
                    self.addWidget(widget, i + 1, j)
        # Add the new row
        for j, widget in enumerate(new_row):
            self.addWidget(widget, insert_index, j)

    def pop_row(self, index=None):
        num_rows = self.rowCount()
        if index is None:
            index = num_rows - 1
        num_columns = self.columnCount()
        popped_row = []
        # Remove the index row
        for j in range(num_columns):
            layout_item = self.itemAtPosition(index, j)
            if not layout_item:
                popped_row.append(None)
                continue
            widget = layout_item.widget()
            popped_row.append(widget)
            self.removeWidget(widget)
        # Shift everything below the index row up
        for i in range(index + 1, num_rows):
            for j in range(num_columns):
                layout_item = self.itemAtPosition(i, j)
                if not layout_item:
                    continue
                widget = layout_item.widget()
                self.removeWidget(widget)
                self.addWidget(widget, i - 1, j)
        return popped_row


class ListEdit(QWidget):
    def __init__(self):
        super().__init__()
        # We have to track this ourselves, because QGridLayout.rowCount() never
        # shrinks
        self._num_items = 0
        self._layout = GridLayout()
        self._text_box = QLineEdit()

        def add():
            self.append(self._text_box.text())
            self._text_box.setText("")
        add_button = QPushButton("+")
        add_button.clicked.connect(add)

        self._layout.append_row((self._text_box, add_button))
        self.setLayout(self._layout)

    def append(self, text):
        if (not text) or (text in self.value):
            return

        def remove(button):
            layout_index = self._layout.indexOf(button)
            row_index, _, _, _ = self._layout.getItemPosition(layout_index)
            self._text_box.setText(self.pop(row_index))
        remove_button = QPushButton("-")
        remove_button.clicked.connect(functools.partial(remove, remove_button))

        self._layout.insert_row(self._num_items, (QLabel(text), remove_button))
        self._num_items += 1

    def pop(self, index=None):
        label, remove_button = self._layout.pop_row(index)
        text = label.text()
        label.deleteLater()
        remove_button.deleteLater()
        self._num_items -= 1
        return text

    @property
    def value(self):
        data = []
        for i in range(self._num_items):
            data.append(self._layout.itemAtPosition(i, 0).widget().text())
        return data

    @value.setter
    def value(self, value):
        while self._num_items:
            self.pop()
        for text in value:
            self.append(text)
