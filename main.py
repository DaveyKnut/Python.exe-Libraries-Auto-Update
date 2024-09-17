import sys
import subprocess
import requests
import re
from importlib.metadata import distributions
from packaging import version
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTextEdit, QPushButton, 
                             QVBoxLayout, QHBoxLayout, QWidget, QTableWidget, QTableWidgetItem,
                             QDialog, QFileDialog, QMessageBox, QLabel)
from PyQt6.QtCore import QThread, pyqtSignal, QUrl, Qt
from PyQt6.QtGui import QDesktopServices, QClipboard

class UpdateThread(QThread):
    update_signal = pyqtSignal(str)
    python_update_signal = pyqtSignal(str, str)
    update_complete_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.updated_libraries = []

    def run(self):
        self.check_python_version()
        self.update_libraries()

    def get_latest_python_version(self):
        try:
            response = requests.get("https://www.python.org/downloads/")
            version_pattern = r"Latest Python 3 Release - Python (3\.\d+\.\d+)"
            match = re.search(version_pattern, response.text)
            if match:
                return match.group(1)
        except Exception as e:
            self.update_signal.emit(f"Error checking latest Python version: {e}")
        return None

    def check_python_version(self):
        current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        latest_version = self.get_latest_python_version()
        
        if latest_version and version.parse(latest_version) > version.parse(current_version):
            self.update_signal.emit(f"A new version of Python is available. Current: {current_version}, Latest: {latest_version}")
            self.python_update_signal.emit(latest_version, f"https://www.python.org/downloads/release/python-{latest_version.replace('.', '')}/")
        else:
            self.update_signal.emit(f"Python is up to date (version {current_version}).")

    def update_libraries(self):
        self.update_signal.emit("Checking for library updates...")
        try:
            # Update pip itself
            process = subprocess.Popen([sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.update_signal.emit(output.strip())
                    if "Successfully installed pip" in output:
                        self.updated_libraries.append(("pip", output.split()[-1]))
            
            # Use pip-review to update all packages
            process = subprocess.Popen([sys.executable, "-m", "pip_review", "--auto"],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.update_signal.emit(output.strip())
                    if "Updated" in output:
                        package = output.split()[1]
                        version = output.split()[-1]
                        self.updated_libraries.append((package, version))
            
            self.update_signal.emit("All packages have been updated successfully.")
            self.update_complete_signal.emit(self.generate_report())
        except subprocess.CalledProcessError as e:
            self.update_signal.emit(f"An error occurred while updating: {e}")

    def generate_report(self):
        report = "Update Report:\n\n"
        if self.updated_libraries:
            for package, version in self.updated_libraries:
                report += f"{package} updated to version {version}\n"
        else:
            report += "No libraries were updated. All packages are up to date."
        return report

class ReportDialog(QDialog):
    def __init__(self, report):
        super().__init__()
        self.setWindowTitle("Update Report")
        self.setGeometry(200, 200, 400, 300)

        layout = QVBoxLayout()

        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setPlainText(report)
        layout.addWidget(self.report_text)

        button_layout = QHBoxLayout()

        save_button = QPushButton("Save as TXT")
        save_button.clicked.connect(self.save_report)
        button_layout.addWidget(save_button)

        copy_button = QPushButton("Copy to Clipboard")
        copy_button.clicked.connect(self.copy_to_clipboard)
        button_layout.addWidget(copy_button)

        okay_button = QPushButton("Okay")
        okay_button.clicked.connect(self.accept)
        button_layout.addWidget(okay_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def save_report(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Report", "", "Text Files (*.txt)")
        if file_name:
            with open(file_name, 'w') as file:
                file.write(self.report_text.toPlainText())
            QMessageBox.information(self, "Save Successful", "Report saved successfully.")

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.report_text.toPlainText())
        QMessageBox.information(self, "Copy Successful", "Report copied to clipboard.")

class LibrariesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Installed Libraries")
        self.setGeometry(150, 150, 600, 400)
        
        layout = QVBoxLayout()
        
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Library", "Version", "Description"])
        
        libraries = sorted([
            (dist.metadata['Name'], dist.version, dist.metadata.get('Summary', 'N/A'))
            for dist in distributions()
        ])
        table.setRowCount(len(libraries))
        
        for row, (name, version, summary) in enumerate(libraries):
            table.setItem(row, 0, QTableWidgetItem(name))
            table.setItem(row, 1, QTableWidgetItem(version))
            table.setItem(row, 2, QTableWidgetItem(summary))
        
        table.resizeColumnsToContents()
        layout.addWidget(table)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        
        self.setLayout(layout)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Python Libraries Updater")
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        main_layout.addWidget(self.text_edit)

        self.update_button = QPushButton("Manual Run")
        self.update_button.clicked.connect(self.start_update)
        main_layout.addWidget(self.update_button)

        self.python_update_button = QPushButton("Download Latest Python")
        self.python_update_button.clicked.connect(self.open_python_download)
        self.python_update_button.setVisible(False)
        main_layout.addWidget(self.python_update_button)

        self.view_libraries_button = QPushButton("View Installed Libraries")
        self.view_libraries_button.clicked.connect(self.view_installed_libraries)
        main_layout.addWidget(self.view_libraries_button)

        # Add "Created by" label
        created_by_label = QLabel("Created by: Lewis Bennett")
        created_by_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        main_layout.addWidget(created_by_label)

        self.update_thread = UpdateThread()
        self.update_thread.update_signal.connect(self.update_status)
        self.update_thread.python_update_signal.connect(self.show_python_update)
        self.update_thread.update_complete_signal.connect(self.show_report)

    def start_update(self):
        self.update_button.setEnabled(False)
        self.text_edit.clear()
        self.update_thread.start()

    def update_status(self, message):
        self.text_edit.append(message)

    def show_python_update(self, version, url):
        self.python_update_button.setText(f"Download Python {version}")
        self.python_update_button.setVisible(True)
        self.python_download_url = url

    def open_python_download(self):
        QDesktopServices.openUrl(QUrl(self.python_download_url))

    def view_installed_libraries(self):
        dialog = LibrariesDialog(self)
        dialog.exec()

    def show_report(self, report):
        self.update_button.setEnabled(True)
        dialog = ReportDialog(report)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.close()

def run_update():
    update_thread = UpdateThread()
    update_thread.run()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--update":
        run_update()
    else:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())