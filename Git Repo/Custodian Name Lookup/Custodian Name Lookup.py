import sys
import re
import traceback
import os
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTextEdit, QPushButton, QFileDialog, QLabel, QSlider, QCheckBox,
                             QMessageBox)
from PyQt6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor
from PyQt6.QtCore import Qt, QTimer
from fuzzywuzzy import fuzz
import pandas as pd

class HighlightedTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)

    def highlight_text(self, results):
        self.clear()
        cursor = QTextCursor(self.document())
        default_format = QTextCharFormat()
        
        for client_item, matches, similar_matches in results:
            cursor.insertText(f"Client Item: {client_item}\n", default_format)
            
            if not matches and not similar_matches:
                # No matches - highlight in red
                format = QTextCharFormat()
                format.setBackground(QColor(255, 200, 200))  # Light red
                cursor.insertText("No matches found.\n", format)
            elif matches:
                # Exact matches - highlight in green
                format = QTextCharFormat()
                format.setBackground(QColor(200, 255, 200))  # Light green
                cursor.insertText("Exact Matches:\n", default_format)
                for match in matches:
                    cursor.insertText("  - ", default_format)
                    cursor.insertText(f"{match}\n", format)
            elif similar_matches:
                # Similar matches - highlight in yellow
                format = QTextCharFormat()
                format.setBackground(QColor(255, 255, 200))  # Light yellow
                cursor.insertText("Similar Matches:\n", default_format)
                for match, ratio in similar_matches[:5]:
                    cursor.insertText("  - ", default_format)
                    cursor.insertText(f"{match}", format)
                    cursor.insertText(f" (Similarity: {ratio}%)\n", default_format)
            
            cursor.insertText("\n", default_format)

class CustodianMatcher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('eDiscovery Custodian Matcher')
        self.setGeometry(100, 100, 1000, 600)

        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # Top section with two text areas
        top_layout = QHBoxLayout()

        # Left text area (Relativity custodians)
        left_layout = QVBoxLayout()
        left_label = QLabel("Relativity Custodians:")
        self.left_text = QTextEdit()
        self.left_text.textChanged.connect(self.schedule_search)
        left_button = QPushButton("Load from file")
        left_button.clicked.connect(lambda: self.load_file(self.left_text))
        left_layout.addWidget(left_label)
        left_layout.addWidget(self.left_text)
        left_layout.addWidget(left_button)

        # Right text area (Client search list)
        right_layout = QVBoxLayout()
        right_label = QLabel("Client Search List:")
        self.right_text = QTextEdit()
        self.right_text.textChanged.connect(self.schedule_search)
        right_button = QPushButton("Load from file")
        right_button.clicked.connect(lambda: self.load_file(self.right_text))
        right_layout.addWidget(right_label)
        right_layout.addWidget(self.right_text)
        right_layout.addWidget(right_button)

        top_layout.addLayout(left_layout)
        top_layout.addLayout(right_layout)

        # Fuzzy search options
        fuzzy_layout = QHBoxLayout()
        self.fuzzy_checkbox = QCheckBox("Enable Fuzzy Search")
        self.fuzzy_checkbox.setChecked(False)
        self.fuzzy_checkbox.stateChanged.connect(self.toggle_fuzzy_search)
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(50, 100)
        self.threshold_slider.setValue(80)
        self.threshold_slider.setEnabled(False)
        self.threshold_slider.valueChanged.connect(self.update_threshold_label)
        self.threshold_slider.setInvertedAppearance(True)  # Invert the slider
        self.threshold_label = QLabel("Fuzziness: 20% (80% similarity required)")
        fuzzy_layout.addWidget(self.fuzzy_checkbox)
        fuzzy_layout.addWidget(self.threshold_slider)
        fuzzy_layout.addWidget(self.threshold_label)

        # Bottom section (Results)
        bottom_layout = QVBoxLayout()
        bottom_label = QLabel("Results:")
        self.bottom_text = HighlightedTextEdit()
        self.bottom_text.setReadOnly(True)
        bottom_layout.addWidget(bottom_label)
        bottom_layout.addWidget(self.bottom_text)

        # Buttons
        button_layout = QHBoxLayout()
        export_button = QPushButton("Export to Excel")
        export_button.clicked.connect(self.export_to_excel)
        button_layout.addWidget(export_button)

        main_layout.addLayout(top_layout)
        main_layout.addLayout(fuzzy_layout)
        main_layout.addLayout(bottom_layout)
        main_layout.addLayout(button_layout)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # Timer for delayed search
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)

    def load_file(self, text_edit):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Text File", "", "Text Files (*.txt)")
        if file_name:
            with open(file_name, 'r') as file:
                text_edit.setPlainText(file.read())

    def toggle_fuzzy_search(self, state):
        self.threshold_slider.setEnabled(state == Qt.CheckState.Checked.value)
        self.schedule_search()

    def update_threshold_label(self, value):
        fuzziness = 100 - value
        self.threshold_label.setText(f"Fuzziness: {fuzziness}% ({value}% similarity required)")
        self.schedule_search()

    def schedule_search(self):
        self.search_timer.start(300)  # 300 ms delay

    def preprocess_text(self, text):
        return re.sub(r'[^\w\s]', '', text.lower()).strip()

    def perform_search(self):
        try:
            relativity_custodians = [c.strip() for c in self.left_text.toPlainText().split('\n') if c.strip()]
            client_search_list = [c.strip() for c in self.right_text.toPlainText().split('\n') if c.strip()]
            use_fuzzy = self.fuzzy_checkbox.isChecked()
            similarity_threshold = self.threshold_slider.value()

            results = []
            for client_item in client_search_list:
                preprocessed_client_item = self.preprocess_text(client_item)
                matches = []
                similar_matches = []

                for custodian in relativity_custodians:
                    preprocessed_custodian = self.preprocess_text(custodian)
                    
                    if preprocessed_client_item in preprocessed_custodian or preprocessed_custodian in preprocessed_client_item:
                        matches.append(custodian)
                    elif use_fuzzy:
                        similarity_ratio = fuzz.ratio(preprocessed_client_item, preprocessed_custodian)
                        if similarity_ratio >= similarity_threshold:
                            similar_matches.append((custodian, similarity_ratio))

                similar_matches.sort(key=lambda x: x[1], reverse=True)
                results.append((client_item, matches, similar_matches))

            self.display_results(results)
        except Exception as e:
            error_msg = f"An error occurred during the search:\n\n{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            QMessageBox.critical(self, "Error", error_msg)
            print(error_msg)  # This will print the error to the console

    def display_results(self, results):
        try:
            self.bottom_text.highlight_text(results)
        except Exception as e:
            error_msg = f"An error occurred while displaying results:\n\n{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            QMessageBox.critical(self, "Error", error_msg)
            print(error_msg)  # This will print the error to the console

    def export_to_excel(self):
        try:
            if not self.bottom_text.toPlainText():
                return

            file_name, _ = QFileDialog.getSaveFileName(self, "Save Excel File", "", "Excel Files (*.xlsx)")
            if not file_name:
                return

            results = self.parse_results()
            df = pd.DataFrame(results, columns=['Client Item', 'Exact Matches', 'Similar Matches'])
            df.to_excel(file_name, index=False)
            
            # Automatically open the Excel file
            self.open_file(file_name)
        except Exception as e:
            error_msg = f"An error occurred during Excel export:\n\n{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            QMessageBox.critical(self, "Error", error_msg)
            print(error_msg)  # This will print the error to the console

    def parse_results(self):
        text = self.bottom_text.toPlainText()
        results = []
        current_item = None
        exact_matches = []
        similar_matches = []

        for line in text.split('\n'):
            if line.startswith("Client Item:"):
                if current_item:
                    results.append((current_item, ', '.join(exact_matches), ', '.join(similar_matches)))
                current_item = line.split(": ", 1)[1]
                exact_matches = []
                similar_matches = []
            elif line.strip().startswith("- "):
                if "Similarity:" in line:
                    similar_matches.append(line.strip()[2:].split(" (Similarity:")[0])
                else:
                    exact_matches.append(line.strip()[2:])

        if current_item:
            results.append((current_item, ', '.join(exact_matches), ', '.join(similar_matches)))

        return results

    def open_file(self, filename):
        if sys.platform == "win32":
            os.startfile(filename)
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.call([opener, filename])

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = CustodianMatcher()
    ex.show()
    sys.exit(app.exec())