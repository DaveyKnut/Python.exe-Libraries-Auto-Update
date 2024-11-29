# Import required modules
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton, QTableView, QLineEdit,
    QComboBox, QLabel, QWidget, QFileDialog, QTextEdit, QMessageBox, QDateEdit
)
from PySide6.QtCore import Qt, QMimeData, QPoint
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
        
        # Connect signals for live query preview
        self.operator_combo.currentTextChanged.connect(self.parent().update_query_preview)
        if isinstance(self.value_widget, QLineEdit):
            self.value_widget.textChanged.connect(self.parent().update_query_preview)
        
        layout.addWidget(self.field_label)
        layout.addWidget(self.operator_combo)
        layout.addWidget(self.value_widget)
        
        remove_btn = QPushButton("×")
        remove_btn.clicked.connect(self.remove_condition)
        layout.addWidget(remove_btn)

    def remove_condition(self):
        self.deleteLater()
        self.parent().update_query_preview()

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
        query_layout = QVBoxLayout()
        self.query_field_selector = QComboBox()
        self.query_builder = QTextEdit()
        self.query_builder.setPlaceholderText("Build your query here...")
        run_query_button = QPushButton("Run Query")
        run_query_button.clicked.connect(self.run_query)
        query_layout.addWidget(QLabel("Field Selector:"))
        query_layout.addWidget(self.query_field_selector)
        query_layout.addWidget(self.query_builder)
        query_layout.addWidget(run_query_button)
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
                    self.dataset = pl.read_csv(file_path, separator='\x14', quote_char=None)  # ASCII 20 (CTRL+T)
                else:  # Default CSV handling
                    self.dataset = pl.read_csv(file_path)
                
                self.query_field_selector.clear()  # Clear existing items
                self.query_field_selector.addItems(self.dataset.columns)
                QMessageBox.information(self, "Success", "File loaded successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {e}")

    def run_query(self):
        query = self.query_builder.toPlainText()
        try:
            result_df = self.dataset.lazy().filter(eval(query)).collect()
            self.result_df = result_df
            QMessageBox.information(self, "Success", "Query executed successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to execute query: {e}")

    def show_statistics(self):
        if self.dataset is None:
            QMessageBox.warning(self, "Warning", "Load a dataset first!")
            return

        stats = self.dataset.describe()
        stats_str = stats.to_string()
        QMessageBox.information(self, "Statistics", stats_str)

    def save_query(self):
        """Enhanced save query with template support"""
        query_data = {
            'query': self.query_builder.toPlainText(),
            'conditions': self.get_query_conditions(),
            'timestamp': datetime.now().isoformat()
        }
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Query Template", "", "Query Templates (*.qry)")
        if file_path:
            with open(file_path, 'wb') as f:
                pickle.dump(query_data, f)
            self.add_to_recent_queries(query_data['query'])

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
        for i in range(self.query_conditions.count()):
            widget = self.query_conditions.itemAt(i).widget()
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


# Run the application
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PolarsQueryApp()
    window.show()
    sys.exit(app.exec())
