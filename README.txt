Python Libraries Updater
========================

Created by Lewis Bennett, Berlin, 17.09.2024.

Overview
--------
The Python Libraries Updater is a utility application designed to automatically update Python and its installed libraries. It provides both a graphical user interface (GUI) for manual operation and a command-line interface for scheduled tasks.

Key Features
------------
1. Update Python: Checks for and notifies about new Python versions.
2. Update Libraries: Automatically updates all installed Python libraries.
3. View Installed Libraries: Displays a list of all installed libraries with versions.
4. Update Reports: Generates reports of update activities.
5. Scheduled Updates: Can be configured to run automatically at set intervals.

Installation
------------
1. Ensure Python 3.6 or higher is installed on your system.
2. Install required libraries:
   pip install PyQt6 requests packaging pip-review

3. Download the 'python_updater_gui.py' script to your preferred location.

Usage
-----
1. GUI Mode:
   - Run 'python python_updater_gui.py'
   - Use the interface to manually trigger updates or view installed libraries.

2. Command-Line Mode (for scheduled tasks):
   - Run 'python python_updater_gui.py --update'
   - This mode performs updates without launching the GUI.

Automated Setup
---------------
To run the updater automatically at set intervals:

Windows:
1. Open Task Scheduler
2. Create a new task
3. Set the trigger to your desired schedule (e.g., weekly)
4. Set the action to start a program
5. Program/script: python
6. Add arguments: path\to\python_updater_gui.py --update
7. Start in: path\to\script\directory

macOS/Linux:
1. Open terminal
2. Edit crontab: crontab -e
3. Add a line (for weekly updates):
   0 0 * * 0 /usr/bin/python3 /path/to/python_updater_gui.py --update
4. Save and exit

Note: Adjust the Python path and script path as necessary for your system.

Considerations
--------------
1. Permissions: Ensure the script has necessary permissions to update Python and libraries.
2. Virtual Environments: The updater affects the Python environment it runs in. For global updates, run outside of virtual environments.
3. System-wide vs. User Installs: Be aware of whether you're updating system-wide or user-specific installations.
4. Backup: Always maintain backups before running mass updates.
5. Testing: After updates, test critical applications to ensure compatibility.
6. Network: Stable internet connection required for updates.
7. Storage: Ensure sufficient disk space for new versions.

Troubleshooting
---------------
1. Update Failures: Check internet connection and permissions.
2. GUI Not Launching: Ensure PyQt6 is correctly installed.
3. Libraries Not Updating: Verify pip and pip-review are up-to-date.
4. Scheduled Task Not Running: Check system logs for any error messages.

Security Notes
--------------
1. The application requires internet access to check for and download updates.
2. It may require elevated permissions to update system-wide Python installations.
3. Always download the script from trusted sources.

Customization
-------------
- Modify update frequency in the scheduling setup.
- Edit the script to change GUI appearance or add new features.
- Adjust logging settings for more or less verbose output.

Feedback and Contributions
--------------------------
For issues, suggestions, or contributions, please contact Lewis Bennett or submit a pull request if the project is hosted on a public repository.

Disclaimer
----------
This tool automates the update process for Python and its libraries. While it aims to maintain system integrity, unforeseen compatibility issues may arise. Use at your own risk and always backup your system before major updates.

License
-------
Open source. The creator does not accept any liability for this software. Please consult the license file on the distro.

Version History
---------------
v1.0 - Initial release
