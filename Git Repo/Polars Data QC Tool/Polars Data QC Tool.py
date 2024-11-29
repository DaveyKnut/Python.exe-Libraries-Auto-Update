# Import required modules
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton, QTableView, QLineEdit,
    QComboBox, QLabel, QWidget, QFileDialog, QTextEdit, QMessageBox, QDateEdit, QListWidget
)
from PySide6.QtCore import Qt, QMimeData, QPoint, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QKeySequence, QShortcut, QDrag
import pyperclip
import polars as pl
import sys
import os
import json
from datetime import datetime
import pickle


class QueryConditionWidget(QWidget):
    def __init__(self, field_name, field_type, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        layout = QHBoxLayout(self)
        
        # Add grip handle for drag and drop
        grip = QLabel("::")
        grip.setStyleSheet("background-color: #e0e0e0; padding: 2px;")
        grip.setCursor(Qt.OpenHandCursor)
        layout.addWidget(grip)
        
        self.field_label = QLabel(field_name)
        self.operator_combo = QComboBox()
        self.value_widget = None
        
        if field_type == 'date':
            self.operator_combo.addItems(['is before', 'is after', 'is between', 'is on', 'is not set'])
            self.value_widget = QDateEdit()
        else:
            self.operator_combo.addItems(['is set', 'is not set', 'equals', 'does not equal', 'contains'])
            self.value_widget = QLineEdit()
        
        # Connect signals to the QueryBuilderWidget's update method
        self.operator_combo.currentTextChanged.connect(self.value_changed)
        if isinstance(self.value_widget, QLineEdit):
            self.value_widget.textChanged.connect(self.value_changed)
        elif isinstance(self.value_widget, QDateEdit):
            self.value_widget.dateChanged.connect(self.value_changed)
        
        layout.addWidget(self.field_label)
        layout.addWidget(self.operator_combo)
        layout.addWidget(self.value_widget)
        
        remove_btn = QPushButton("×")
        remove_btn.clicked.connect(self.remove_condition)
        layout.addWidget(remove_btn)

    def value_changed(self):
        # Find the QueryBuilderWidget parent and call its update method
        parent = self.parent()
        while parent and not isinstance(parent, QueryBuilderWidget):
            parent = parent.parent()
        if parent:
            parent.update_query_preview()

    def remove_condition(self):
        self.deleteLater()
        # Update query preview after removal
        parent = self.parent()
        while parent and not isinstance(parent, QueryBuilderWidget):
            parent = parent.parent()
        if parent:
            parent.update_query_preview()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText("condition")
            drag.setMimeData(mime_data)
            drag.exec_(Qt.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        pos = event.pos()
        widget = self.parent().childAt(pos)
        if widget:
            current_idx = self.parent().layout().indexOf(self)
            target_idx = self.parent().layout().indexOf(widget.parent())
            if current_idx != target_idx:
                self.parent().move_condition(current_idx, target_idx)


class FieldListWidget(QWidget):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.layout = QVBoxLayout(self)
        self.field_list = QListWidget()
        self.field_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.field_list.itemDoubleClicked.connect(self.add_field_to_query)
        self.layout.addWidget(self.field_list)
        
    def add_field_to_query(self, item):
        selected_items = self.field_list.selectedItems()
        for item in selected_items:
            field_name = item.text()
            field_type = 'date' if 'date' in field_name.lower() else 'text'
            self.main_app.add_query_condition(field_name, field_type)


class QueryBuilderWidget(QWidget):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.layout = QVBoxLayout(self)
        
        # Operator buttons
        self.operator_layout = QHBoxLayout()
        self.and_btn = QPushButton("AND")
        self.or_btn = QPushButton("OR")
        self.bracket_left_btn = QPushButton("(")
        self.bracket_right_btn = QPushButton(")")
        
        self.operator_layout.addWidget(self.and_btn)
        self.operator_layout.addWidget(self.or_btn)
        self.operator_layout.addWidget(self.bracket_left_btn)
        self.operator_layout.addWidget(self.bracket_right_btn)
        
        self.layout.addLayout(self.operator_layout)
        
        # Conditions container
        self.conditions_widget = QWidget()
        self.conditions_layout = QVBoxLayout(self.conditions_widget)
        self.layout.addWidget(self.conditions_widget)
        
        # Add Run Query button
        self.run_query_btn = QPushButton("Run Query")
        self.run_query_btn.clicked.connect(self.main_app.run_query)
        self.run_query_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.layout.addWidget(self.run_query_btn)

    def update_query_preview(self):
        """Update the SQL-like query preview based on current conditions"""
        query_parts = []
        for i in range(self.conditions_layout.count()):
            widget = self.conditions_layout.itemAt(i).widget()
            if isinstance(widget, QueryConditionWidget):
                field = widget.field_label.text()
                operator = widget.operator_combo.currentText()
                if isinstance(widget.value_widget, QDateEdit):
                    value = widget.value_widget.date().toString("yyyy-MM-dd")
                else:
                    value = widget.value_widget.text()
                query_parts.append(f"{field} {operator} '{value}'")
        
        query = " AND ".join(query_parts)
        self.main_app.query_preview.setText(query)


class PolarsTableModel(QAbstractTableModel):
    def __init__(self, data=None):
        super().__init__()
        self._data = data

    def rowCount(self, index):
        if self._data is None:
            return 0
        return len(self._data)

    def columnCount(self, index):
        if self._data is None:
            return 0
        return len(self._data.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or self._data is None:
            return None

        if role == Qt.DisplayRole:
            value = self._data.row(index.row())[index.column()]
            # Handle the þþ delimiter case
            if value == 'þþ' or value == '\x14\x14':
                return ''
            # Remove þ characters if they're at start/end of value
            if isinstance(value, str):
                value = value.strip('þ')
            # Format dates nicely
            if isinstance(value, datetime):
                return value.strftime('%Y-%m-%d %H:%M:%S')
            # Handle None/null values
            if value is None:
                return ''
            return str(value)

        elif role == Qt.TextAlignmentRole:
            value = self._data.row(index.row())[index.column()]
            if isinstance(value, (int, float)):
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        return None

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal and self._data is not None:
                # Get column name and remove any þ characters
                header = str(self._data.columns[section])
                header = header.strip('þ')
                return header
            if orientation == Qt.Vertical:
                return str(section + 1)
        return None


class PolarsQueryApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Polars Query Tool")
        self.setGeometry(100, 100, 1200, 800)
        
        # Variables for app state
        self.dataset = None
        self.file_path = None
        self.query_history = []
        self.result_df = None

        # Main UI layout
        layout = QVBoxLayout()

        # File Load Section
        file_load_layout = QHBoxLayout()
        self.file_path_input = QLineEdit()
        self.file_path_input.setPlaceholderText("Select a CSV/DAT file...")
        file_load_button = QPushButton("Load File")
        file_load_button.clicked.connect(self.load_file)
        file_load_layout.addWidget(self.file_path_input)
        file_load_layout.addWidget(file_load_button)
        layout.addLayout(file_load_layout)

        # Query Builder Section
        query_layout = QHBoxLayout()
        
        # Field list on the left
        field_list_container = QWidget()
        field_list_layout = QVBoxLayout(field_list_container)
        field_list_layout.addWidget(QLabel("Available Fields:"))
        self.field_list = FieldListWidget(self, field_list_container)
        field_list_layout.addWidget(self.field_list)
        
        # Query builder on the right
        query_builder_container = QWidget()
        query_builder_layout = QVBoxLayout(query_builder_container)
        query_builder_layout.addWidget(QLabel("Query Builder:"))
        self.query_builder = QueryBuilderWidget(self, query_builder_container)
        query_builder_layout.addWidget(self.query_builder)
        
        # Add both widgets to the query layout
        query_layout.addWidget(field_list_container, 1)
        query_layout.addWidget(query_builder_container, 2)
        
        layout.addLayout(query_layout)

        # Results Viewer Section
        self.results_view = QTableView()
        layout.addWidget(QLabel("Results:"))
        layout.addWidget(self.results_view)

        # Statistics Viewer Section
        stats_button = QPushButton("View Statistics")
        stats_button.clicked.connect(self.show_statistics)
        layout.addWidget(stats_button)

        # Save Query and History Section
        history_layout = QHBoxLayout()
        save_query_button = QPushButton("Save Query")
        save_query_button.clicked.connect(self.save_query)
        load_query_button = QPushButton("Load Query")
        load_query_button.clicked.connect(self.load_query)
        history_layout.addWidget(save_query_button)
        history_layout.addWidget(load_query_button)
        layout.addLayout(history_layout)

        # Export and Clipboard Section
        export_layout = QHBoxLayout()
        export_button = QPushButton("Export Results")
        export_button.clicked.connect(self.export_results)
        clipboard_button = QPushButton("Copy Document IDs to Clipboard")
        clipboard_button.clicked.connect(self.copy_to_clipboard)
        export_layout.addWidget(export_button)
        export_layout.addWidget(clipboard_button)
        layout.addLayout(export_layout)

        # Add query preview section
        self.query_preview = QTextEdit()
        self.query_preview.setReadOnly(True)
        self.query_preview.setMaximumHeight(100)
        self.query_preview.setPlaceholderText("Query preview will appear here...")
        layout.addWidget(QLabel("Query Preview:"))
        layout.addWidget(self.query_preview)

        # Recent queries list
        self.recent_queries = []
        self.recent_queries_combo = QComboBox()
        self.recent_queries_combo.currentIndexChanged.connect(self.load_recent_query)
        layout.addWidget(QLabel("Recent Queries:"))
        layout.addWidget(self.recent_queries_combo)

        # Add keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_query)
        QShortcut(QKeySequence("Ctrl+O"), self, self.load_query)
        QShortcut(QKeySequence("Ctrl+R"), self, self.run_query)
        QShortcut(QKeySequence("Ctrl+P"), self, self.toggle_preview)

        # Preview mode toggle
        self.preview_mode = False
        self.preview_toggle = QPushButton("Toggle Preview Mode")
        self.preview_toggle.setCheckable(True)
        self.preview_toggle.clicked.connect(self.toggle_preview)
        layout.addWidget(self.preview_toggle)

        # Initialize the table model
        self.table_model = PolarsTableModel()
        self.results_view.setModel(self.table_model)

        # Set central widget
        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def load_file(self):
        file_dialog = QFileDialog(self)
        file_path, _ = file_dialog.getOpenFileName(self, "Open File", "", "CSV or DAT files (*.csv *.dat)")
        if file_path:
            self.file_path = file_path
            self.file_path_input.setText(file_path)
            try:
                # Determine file type and use appropriate loading parameters
                file_extension = os.path.splitext(file_path)[1].lower()
                if file_extension == '.dat':
                    # Load the DAT file and clean the data
                    self.dataset = pl.read_csv(file_path, separator='\x14', quote_char=None)
                    
                    # Clean the column names
                    self.dataset.columns = [col.strip('þ') for col in self.dataset.columns]
                    
                    # Clean the data - replace 'þþ' with None
                    for col in self.dataset.columns:
                        self.dataset = self.dataset.with_columns(
                            pl.col(col).map_elements(
                                lambda x: None if x in ['þþ', '\x14\x14'] else x.strip('þ') if isinstance(x, str) else x,
                                return_dtype=pl.Utf8  # Specify return type as string
                            ).alias(col)
                        )
                else:  # Default CSV handling
                    self.dataset = pl.read_csv(file_path)
                
                # Update field list
                self.field_list.field_list.clear()
                for column in self.dataset.columns:
                    self.field_list.field_list.addItem(column)
                
                QMessageBox.information(self, "Success", "File loaded successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")
                print(f"Detailed error: {e}")  # For debugging

    def run_query(self):
        if self.dataset is None:
            QMessageBox.warning(self, "Warning", "Please load a dataset first!")
            return

        try:
            # Build the query expression from conditions
            query_conditions = []
            for i in range(self.query_builder.conditions_layout.count()):
                widget = self.query_builder.conditions_layout.itemAt(i).widget()
                if isinstance(widget, QueryConditionWidget):
                    field = widget.field_label.text()
                    operator = widget.operator_combo.currentText()
                    
                    if isinstance(widget.value_widget, QDateEdit):
                        value = widget.value_widget.date().toString("yyyy-MM-dd")
                    else:
                        value = widget.value_widget.text()

                    # Convert the UI-friendly operators to Polars expressions
                    if operator == "is set":
                        condition = f"pl.col('{field}').is_not_null()"
                    elif operator == "is not set":
                        condition = f"pl.col('{field}').is_null()"
                    elif operator == "equals":
                        condition = f"pl.col('{field}') == '{value}'"
                    elif operator == "does not equal":
                        condition = f"pl.col('{field}') != '{value}'"
                    elif operator == "contains":
                        condition = f"pl.col('{field}').str.contains('{value}')"
                    elif operator == "is before":
                        condition = f"pl.col('{field}') < '{value}'"
                    elif operator == "is after":
                        condition = f"pl.col('{field}') > '{value}'"
                    elif operator == "is on":
                        condition = f"pl.col('{field}') == '{value}'"
                    else:
                        continue

                    query_conditions.append(condition)

            if not query_conditions:
                QMessageBox.warning(self, "Warning", "Please add some query conditions first!")
                return

            # Combine conditions with AND
            query_expr = " & ".join(query_conditions)
            
            # Execute the query
            self.result_df = self.dataset.filter(eval(query_expr))
            
            # Update the table model with new results
            self.table_model = PolarsTableModel(self.result_df)
            self.results_view.setModel(self.table_model)
            
            # Resize columns to content
            self.results_view.resizeColumnsToContents()
            
            # Show success message
            QMessageBox.information(self, "Success", f"Query executed successfully! Found {len(self.result_df)} rows.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to execute query: {str(e)}")

    def show_statistics(self):
        if self.dataset is None:
            QMessageBox.warning(self, "Warning", "Load a dataset first!")
            return

        stats = self.dataset.describe()
        stats_str = stats.to_string()
        QMessageBox.information(self, "Statistics", stats_str)

    def save_query(self):
        query_data = {
            'conditions': self.get_query_conditions(),
            'timestamp': datetime.now().isoformat()
        }
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Query", "", "JSON files (*.json)")
        if file_path:
            with open(file_path, 'w') as f:
                json.dump(query_data, f)

    def load_query(self):
        file_dialog = QFileDialog(self)
        file_path, _ = file_dialog.getOpenFileName(self, "Load Query", "", "JSON files (*.json)")
        if file_path:
            with open(file_path, "r") as f:
                data = json.load(f)
            self.query_builder.setPlainText(data.get("query", ""))
            QMessageBox.information(self, "Success", "Query loaded successfully!")

    def copy_to_clipboard(self):
        if self.result_df is None:
            QMessageBox.warning(self, "Warning", "No results to copy!")
            return

        try:
            doc_ids = self.result_df.select("Document ID").to_pandas()
            pyperclip.copy("\n".join(map(str, doc_ids["Document ID"])))
            QMessageBox.information(self, "Success", "Document IDs copied to clipboard!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to copy to clipboard: {e}")

    def export_results(self):
        if self.result_df is None:
            QMessageBox.warning(self, "Warning", "No results to export!")
            return

        file_dialog = QFileDialog(self)
        file_path, _ = file_dialog.getSaveFileName(self, "Export Results", "", "CSV files (*.csv)")
        if file_path:
            try:
                self.result_df.write_csv(file_path)
                QMessageBox.information(self, "Success", "Results exported successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export results: {e}")

    def update_query_preview(self):
        """Update the SQL-like query preview based on current conditions"""
        query_parts = []
        for i in range(self.query_builder.conditions_layout.count()):
            widget = self.query_builder.conditions_layout.itemAt(i).widget()
            if isinstance(widget, QueryConditionWidget):
                field = widget.field_label.text()
                operator = widget.operator_combo.currentText()
                value = widget.value_widget.text()
                query_parts.append(f"{field} {operator} '{value}'")
        
        query = " AND ".join(query_parts)
        self.query_preview.setText(query)

    def add_to_recent_queries(self, query):
        """Add query to recent queries list"""
        if query not in self.recent_queries:
            self.recent_queries.insert(0, query)
            if len(self.recent_queries) > 10:  # Keep only last 10 queries
                self.recent_queries.pop()
            self.update_recent_queries_combo()

    def update_recent_queries_combo(self):
        """Update the recent queries dropdown"""
        self.recent_queries_combo.clear()
        for query in self.recent_queries:
            self.recent_queries_combo.addItem(query[:50] + "..." if len(query) > 50 else query)

    def load_recent_query(self, index):
        """Load a query from the recent queries list"""
        if index >= 0 and index < len(self.recent_queries):
            self.query_builder.setPlainText(self.recent_queries[index])

    def toggle_preview(self):
        """Toggle between query preview and query builder"""
        self.preview_mode = not self.preview_mode
        self.preview_toggle.setChecked(self.preview_mode)
        if self.preview_mode:
            self.query_preview.setVisible(True)
            self.query_builder.setVisible(False)
        else:
            self.query_preview.setVisible(False)
            self.query_builder.setVisible(True)

    def add_query_condition(self, field_name, field_type):
        condition = QueryConditionWidget(field_name, field_type, self.query_builder)
        self.query_builder.conditions_layout.addWidget(condition)

    def get_query_conditions(self):
        conditions = []
        for i in range(self.query_builder.conditions_layout.count()):
            widget = self.query_builder.conditions_layout.itemAt(i).widget()
            if isinstance(widget, QueryConditionWidget):
                condition = {
                    'field': widget.field_label.text(),
                    'operator': widget.operator_combo.currentText(),
                    'value': widget.value_widget.text()
                }
                conditions.append(condition)
        return conditions


# Run the application
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PolarsQueryApp()
    window.show()
    sys.exit(app.exec())
