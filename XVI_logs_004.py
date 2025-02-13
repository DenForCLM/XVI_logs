import sys, os, glob, json, importlib, fnmatch, datetime, shutil, re, tarfile, tempfile 
try:
    import requests
except ImportError:
    requests = None  # requests library is needed for update checking

from PyQt5 import QtWidgets, QtCore, QtGui

CONFIG_FILE = "config.json"
GITHUB_REPO = "DenForCLM/XVI_logs"
LOCAL_VERSION = "0.4"  # current program version (only major.minor)

def compare_versions(v1, v2):
    """
    Compares two versions by the first two components (major.minor).
    Returns:
       -1 if v1 < v2,
        0 if v1 == v2,
        1 if v1 > v2.
    """
    def normalize(v):
        # Take only the first two components
        return [int(x) for x in v.lstrip("v").split(".")[:2]]
    n1 = normalize(v1)
    n2 = normalize(v2)
    for a, b in zip(n1, n2):
        if a < b:
            return -1
        elif a > b:
            return 1
    if len(n1) < len(n2):
        return -1
    elif len(n1) > len(n2):
        return 1
    return 0

def get_module_version_from_content(content):
    """
    Searches for 'version' in MODULE_INFO within the module content.
    Returns that version or '0.0' if not found.
    """
    pattern = r'["\']version["\']\s*:\s*["\']\s*([\d\.]+)\s*["\']'
    match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
    if match:
        return match.group(1)
    else:
        print("Debug: Version not found in file content.")
    return "0.0"

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        # Set the window title (with version)
        self.setWindowTitle("Log Analyzer v." + LOCAL_VERSION)
        self.resize(1000, 700)

        # Load configuration
        self.config = self.load_config()

        # Will store info about analysis modules
        self.modules_info = []

        # Create the main menu
        self.setup_menu()

        # Create central widget and main layout
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_vlayout = QtWidgets.QVBoxLayout(central_widget)
        main_vlayout.setContentsMargins(5, 5, 5, 5)
        main_vlayout.setSpacing(5)

        # Top-level horizontal layout (left panel + right panel)
        main_hlayout = QtWidgets.QHBoxLayout()
        main_hlayout.setSpacing(10)
        main_vlayout.addLayout(main_hlayout, 1)

        # --- Left Panel: Module tree and buttons ---
        left_container = QtWidgets.QWidget()
        left_container.setFixedWidth(300)  # fixed width for modules panel
        left_layout = QtWidgets.QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)

        # Label for modules
        modules_label = QtWidgets.QLabel("Analysis Modules")
        modules_label.setStyleSheet("font-size:16px; font-weight:bold;")
        left_layout.addWidget(modules_label)

        # "Select All" / "Deselect All" buttons
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_select_all = QtWidgets.QPushButton("Select All")
        self.btn_deselect_all = QtWidgets.QPushButton("Deselect All")
        # Simple style for these buttons
        button_style = """
            QPushButton {
                background-color: #dddddd;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #cccccc;
            }
        """
        self.btn_select_all.setStyleSheet(button_style)
        self.btn_deselect_all.setStyleSheet(button_style)
        # Avoid expanding buttons
        self.btn_select_all.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.btn_deselect_all.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.btn_select_all.clicked.connect(self.select_all_modules)
        self.btn_deselect_all.clicked.connect(self.deselect_all_modules)
        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addWidget(self.btn_deselect_all)
        left_layout.addLayout(btn_layout)

        # Tree widget for modules
        self.modules_tree = QtWidgets.QTreeWidget()
        self.modules_tree.setHeaderHidden(True)
        self.modules_tree.itemChanged.connect(self.update_file_list)
        left_layout.addWidget(self.modules_tree, 1)

        main_hlayout.addWidget(left_container, 0)

        # --- Right Panel: Date selection, file list, analysis results ---
        right_container = QtWidgets.QWidget()
        right_container.setMinimumWidth(600)  # right panel minimum width of 600
        right_panel = QtWidgets.QVBoxLayout(right_container)
        right_panel.setContentsMargins(0, 0, 0, 0)
        right_panel.setSpacing(5)

        # Horizontal layout: left for date selection and right for file list
        middle_hlayout = QtWidgets.QHBoxLayout()
        middle_hlayout.setSpacing(10)

        # Group box for date selection (vertical layout: Start Date above End Date)
        date_group = QtWidgets.QGroupBox("Select Dates")
        #date_group.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; }")
        date_vbox = QtWidgets.QVBoxLayout()
        date_vbox.setContentsMargins(2, 2, 2, 2)
        date_vbox.setSpacing(2)
        #Add a stretch so that the date widgets are pushed to the bottom 
        date_vbox.addStretch(1)

        # Start Date block
        start_label = QtWidgets.QLabel("Start Date:")
        self.start_date = QtWidgets.QDateEdit(calendarPopup=True)
        self.start_date.setFixedWidth(90)
        self.start_date.dateChanged.connect(self.update_file_list)
        date_vbox.addWidget(start_label)
        date_vbox.addWidget(self.start_date)

        # End Date block (placed below Start Date)
        end_label = QtWidgets.QLabel("End Date:")
        self.end_date = QtWidgets.QDateEdit(calendarPopup=True)
        self.end_date.setFixedWidth(90)
        self.end_date.dateChanged.connect(self.update_file_list)
        date_vbox.addWidget(end_label)
        date_vbox.addWidget(self.end_date)

        date_group.setLayout(date_vbox)
        date_group.setFixedWidth(180)
        middle_hlayout.addWidget(date_group)

        # Table widget for files (File Name, Date Modified)
        self.file_list = QtWidgets.QTableWidget()
        self.file_list.setColumnCount(2)
        self.file_list.setHorizontalHeaderLabels(["File Name", "Date Modified"])
        # Set the header section style so that text is left aligned
        # and add extra right padding to position the sort indicator at the right.
        #self.file_list.horizontalHeaderItem(0).setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        #self.file_list.horizontalHeaderItem(1).setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.file_list.horizontalHeader().setStyleSheet("""
            QHeaderView::section {
                background-color: #f0f0f0;
                color: #333333;
                font-size: 14px;
                padding-right: 10px;
                qproperty-alignment: 'AlignVCenter|AlignLeft';
            }
            QHeaderView::up-arrow, QHeaderView::down-arrow {
                subcontrol-position: right center;
            }

        """)
            
            #QHeaderView::section {
            #    qproperty-alignment: 'AlignVCenter|AlignLeft';
            #}
            #QHeaderView::up-arrow, QHeaderView::down-arrow {
            #    subcontrol-position: right center;
            #}
            #QHeaderView::section {
            #    background-color: #f0f0f0;
            #    color: #333333;
            #    padding: 1px;
            #    margin: 1px;
            #    font-size: 14px;
            #    text-align: left;
            #    padding-right: 20px;
            

        # Set the default alignment for header text
        self.file_list.horizontalHeader().setDefaultAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.file_list.verticalHeader().setVisible(False)
        self.file_list.setShowGrid(False)
        self.file_list.setFrameShape(QtWidgets.QFrame.Box)
        self.file_list.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.file_list.setColumnWidth(0, 200)
        self.file_list.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.file_list.setSortingEnabled(True)
        self.file_list.verticalHeader().setMinimumSectionSize(14)
        # Disable stretch on the last section to remove extra space
        self.file_list.horizontalHeader().setStretchLastSection(False)

        middle_hlayout.addWidget(self.file_list, 1)

        right_panel.addLayout(middle_hlayout)

        # "Files for analysis" label placed below the horizontal layout and above Run Analysis
        self.file_list_label = QtWidgets.QLabel("<b>Files for analysis:</b> " + self.config.get("log_directory", ""))
        self.file_list_label.setStyleSheet("font-size:14px;")
        right_panel.addWidget(self.file_list_label)
        
        # "Run Analysis" button
        self.analyze_button = QtWidgets.QPushButton("Run Analysis")
        self.analyze_button.setFixedHeight(28)
        self.analyze_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d7;
                color: #ffffff;
                border: 1px solid #005fa1;
                border-radius: 4px;
                font-size: 16px;
                font-weight:bold;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #005fa1;
            }
        """)
        self.analyze_button.clicked.connect(self.run_analysis)
        right_panel.addWidget(self.analyze_button)

        # Results label
        result_label = QtWidgets.QLabel("Results")
        result_label.setStyleSheet("font-size:16px; font-weight:bold;")
        right_panel.addWidget(result_label)

        # TextEdit for analysis output
        self.result_text = QtWidgets.QTextEdit()
        self.result_text.setReadOnly(True)
        right_panel.addWidget(self.result_text, 2)

        main_hlayout.addWidget(right_container, 3)

        # Set default dates
        today = QtCore.QDate.currentDate()
        #self.start_date.setDate(today.addDays(-1))
        self.start_date.setDate(QtCore.QDate(2022, 10, 27))
        self.end_date.setDate(today)

        # Load modules and populate tree
        self.load_modules()
        self.populate_modules_tree()
        self.update_file_list()

    def setup_menu(self):
        """Creates a menu bar with settings."""
        menubar = self.menuBar()
        settings_menu = menubar.addMenu("Settings")

        # Action: select log folder
        action_set_log_path = QtWidgets.QAction("Select Log Folder", self)
        action_set_log_path.triggered.connect(self.choose_log_directory)
        settings_menu.addAction(action_set_log_path)

        # Action: check module updates
        action_check_module_updates = QtWidgets.QAction("Check Module Updates", self)
        action_check_module_updates.triggered.connect(self.check_module_updates)
        settings_menu.addAction(action_check_module_updates)

        # Action: update modules
        action_update_modules = QtWidgets.QAction("Update Modules", self)
        action_update_modules.triggered.connect(self.update_modules)
        settings_menu.addAction(action_update_modules)

        # Action: update program
        action_update_program = QtWidgets.QAction("Update Program", self)
        action_update_program.triggered.connect(self.update_program)
        settings_menu.addAction(action_update_program)

    def load_config(self):
        """Loads configuration from config.json if exists."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading config: {e}")
        return {}

    def save_config(self):
        """Saves current configuration to config.json."""
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving configuration: {e}")

    def choose_log_directory(self):
        """Lets the user choose a folder for log files."""
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Log Folder", self.config.get("log_directory", "logs"))
        if directory:
            self.config["log_directory"] = directory
            self.save_config()
            self.update_file_list()

    def load_modules(self):
        """Dynamically loads analysis modules from the 'modules' folder."""
        modules_dir = os.path.join(os.path.dirname(__file__), "modules")
        if not os.path.isdir(modules_dir):
            print("Modules folder not found!")
            return

        for file in os.listdir(modules_dir):
            if file.endswith(".py") and file != "__init__.py":
                module_name = file[:-3]
                try:
                    plugin = importlib.import_module(f"modules.{module_name}")
                    if hasattr(plugin, "MODULE_INFO"):
                        info = plugin.MODULE_INFO
                        info["module"] = plugin
                        self.modules_info.append(info)
                except Exception as e:
                    print(f"Error loading module {module_name}: {e}")

    def populate_modules_tree(self):
        """Creates a tree structure for modules, grouped if necessary."""
        self.modules_tree.blockSignals(True)
        self.modules_tree.clear()

        # Each group will have a top-level item
        groups = {}
        for info in self.modules_info:
            group_name = info.get("group", "Ungrouped")
            if group_name not in groups:
                group_item = QtWidgets.QTreeWidgetItem(self.modules_tree)
                group_item.setText(0, group_name)
                # Enable tristate so that checking/unchecking group affects children
                group_item.setFlags(group_item.flags() | QtCore.Qt.ItemIsTristate | QtCore.Qt.ItemIsUserCheckable)
                groups[group_name] = group_item

            mod_item = QtWidgets.QTreeWidgetItem(groups[group_name])
            mod_item.setText(0, info.get("name", "Unknown Module"))
            mod_item.setFlags(mod_item.flags() | QtCore.Qt.ItemIsUserCheckable)
            mod_item.setCheckState(0, QtCore.Qt.Checked)
            # Set default icon (empty circle before analysis)
            mod_item.setIcon(0, self.get_default_icon())
            info["tree_item"] = mod_item
            mod_item.setData(0, QtCore.Qt.UserRole, info)

        self.modules_tree.blockSignals(False)
        self.modules_tree.expandAll()

    def select_all_modules(self):
        """Checks all modules in the tree."""
        root = self.modules_tree.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                child.setCheckState(0, QtCore.Qt.Checked)

    def deselect_all_modules(self):
        """Unchecks all modules in the tree."""
        root = self.modules_tree.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                child.setCheckState(0, QtCore.Qt.Unchecked)

    def update_file_list(self):
        """Updates the file list based on selected modules and log directory."""
        directory = self.config.get("log_directory", "logs")
        if not os.path.isdir(directory):
            self.file_list.setRowCount(0)
            return

        # Update the "Files for analysis" label with the current log directory
        if hasattr(self, "file_list_label"):
            self.file_list_label.setText("<b>Files for analysis:</b> " + directory)

        # Get selected date range
        start_date = self.start_date.date().toPyDate()
        end_date = self.end_date.date().toPyDate()

        # Collect file name patterns from checked modules
        selected_patterns = []
        root = self.modules_tree.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            for j in range(group_item.childCount()):
                mod_item = group_item.child(j)
                if mod_item.checkState(0) == QtCore.Qt.Checked:
                    info = mod_item.data(0, QtCore.Qt.UserRole)
                    if info and "pattern" in info:
                        selected_patterns.append(info["pattern"])

        if not selected_patterns:
            self.file_list.setRowCount(0)

        # Find matching files and filter by date range
        all_files = glob.glob(os.path.join(directory, "*.*"))
        filtered_files = []
        for path in all_files:
            filename = os.path.basename(path)
            # Check file's modification date against selected range
            mod_date = datetime.datetime.fromtimestamp(os.path.getmtime(path)).date()
            if mod_date < start_date or mod_date > end_date:
                continue
            for pattern in selected_patterns:
                if fnmatch.fnmatch(filename, pattern):
                    filtered_files.append(path)
                    break

        # Sort by modification time
        filtered_files.sort(key=lambda x: os.path.getmtime(x))
        
        # Fill table
        self.file_list.setRowCount(len(filtered_files))
        for row, filepath in enumerate(filtered_files):
            file_name_item = QtWidgets.QTableWidgetItem(os.path.basename(filepath))
            mod_time = os.path.getmtime(filepath)
            date_item = QtWidgets.QTableWidgetItem(datetime.datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M:%S"))
            # Store actual timestamp for better sorting
            date_item.setData(QtCore.Qt.UserRole, mod_time)

            self.file_list.setItem(row, 0, file_name_item)
            self.file_list.setItem(row, 1, date_item)
            self.file_list.setRowHeight(row, 18)    # row height ###

    def get_default_icon(self):
        """Returns an icon with an empty circle (before analysis)."""
        pixmap = QtGui.QPixmap(16, 16)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen(QtGui.QColor("black"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawEllipse(1, 1, 14, 14)
        painter.end()
        return QtGui.QIcon(pixmap)

    def get_status_icon(self, status):
        """
        Returns an icon for the given status:
          - "Green" -> green circle with check
          - "Red" -> red circle with cross
          - "Yellow" -> yellow circle with exclamation
        """
        pixmap = QtGui.QPixmap(16, 16)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        if status == "Green":
            bg_color = QtGui.QColor("green")
        elif status == "Red":
            bg_color = QtGui.QColor("red")
        elif status == "Yellow":
            bg_color = QtGui.QColor("yellow")
        else:
            bg_color = QtGui.QColor("white")

        painter.setBrush(QtGui.QBrush(bg_color))
        painter.setPen(QtGui.QPen(QtGui.QColor("black"), 2))
        painter.drawEllipse(1, 1, 14, 14)

        # Draw symbol inside
        if status == "Green":
            painter.setPen(QtGui.QPen(QtGui.QColor("white"), 2))
            painter.drawLine(4, 9, 7, 12)
            painter.drawLine(7, 12, 12, 5)
        elif status == "Red":
            painter.drawLine(4, 4, 12, 12)
            painter.drawLine(12, 4, 4, 12)
        elif status == "Yellow":
            painter.drawLine(8, 4, 8, 10)
            painter.drawPoint(8, 12)

        painter.end()
        return QtGui.QIcon(pixmap)

    def run_analysis(self):
        """Runs the analysis using selected modules and displays results."""
        # Get date range
        start_date = self.start_date.date().toPyDate()
        end_date = self.end_date.date().toPyDate()

        # Collect file names from table
        files = []
        for row in range(self.file_list.rowCount()):
            item = self.file_list.item(row, 0)
            if item:
                files.append(item.text())
        
        # Clear previous results
        self.result_text.clear()
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        header = f"=== Analysis started at: {now_str} ==="
        self.result_text.append(header)
        
        # Which modules are checked?
        selected_modules = []
        root = self.modules_tree.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            for j in range(group_item.childCount()):
                mod_item = group_item.child(j)
                if mod_item.checkState(0) == QtCore.Qt.Checked:
                    info = mod_item.data(0, QtCore.Qt.UserRole)
                    if info:
                        selected_modules.append(info)
        
        if not selected_modules:
            QtWidgets.QMessageBox.warning(self, "Warning", "Select at least one analysis module.")
            return

        # Reload each selected module to ensure latest code changes
        for info in selected_modules:
            try:
                info["module"] = importlib.reload(info["module"])
            except Exception as e:
                print(f"Error reloading module {info.get('name', 'Unknown')}:", e)

        # Run analyze function for each selected module
        for info in selected_modules:
            try:
                analysis_func = getattr(info["module"], "analyze", None)
                if analysis_func:
                    pattern = info.get("pattern")
                    module_files = [f for f in files if fnmatch.fnmatch(f, pattern)] if pattern else files
                    result, status = analysis_func(module_files, start_date, end_date)
                else:
                    result = "analyze function not defined."
                    status = "Red"
            except Exception as e:
                result = f"Error: {e}"
                status = "Red"

            # Update icon in the tree
            tree_item = info.get("tree_item")
            if tree_item:
                tree_item.setIcon(0, self.get_status_icon(status))

            # Display in the results text
            icon = self.get_status_icon(status)
            pixmap = icon.pixmap(16, 16)
            buffer = QtCore.QByteArray()
            buffer_io = QtCore.QBuffer(buffer)
            buffer_io.open(QtCore.QIODevice.WriteOnly)
            pixmap.save(buffer_io, "PNG")
            img_base64 = bytes(buffer.toBase64()).decode("utf-8")
            img_html = f'<img src="data:image/png;base64,{img_base64}">'
            module_name = info.get("name", "Unknown Module")
            self.result_text.append(f'{img_html} <span style="color:#333333;">{module_name}: {result}</span>')

    def check_module_updates(self):
        """
        Checks for module updates.
        Instead of simply showing the last commit date, this function:
          - Converts the commit time from UTC to local time.
          - Determines the last modification time of local module files.
          - Displays comparative information to show how up-to-date the local modules are relative to GitHub updates.
        """
        if not requests:
            QtWidgets.QMessageBox.warning(self, "Error", "The requests library is not installed.")
            return

        url = f"https://api.github.com/repos/{GITHUB_REPO}/commits?path=modules"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                commits = response.json()
                if commits:
                    latest_commit_date = commits[0]["commit"]["committer"]["date"]
                    remote_dt = datetime.datetime.strptime(latest_commit_date, "%Y-%m-%dT%H:%M:%SZ")
                    remote_dt = remote_dt.replace(tzinfo=datetime.timezone.utc).astimezone(tz=None)
                    remote_str = remote_dt.strftime('%Y-%m-%d %H:%M')
                else:
                    remote_str = "No commit data found."
            else:
                QtWidgets.QMessageBox.warning(self, "Error", f"GitHub API error: {response.status_code}")
                return
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to check updates: {e}")
            return

        # Compare to local modules' modification time
        local_modules_dir = os.path.join(os.getcwd(), "modules")
        if os.path.isdir(local_modules_dir):
            local_mtimes = []
            for root_dir, dirs, files in os.walk(local_modules_dir):
                for file in files:
                    if file.endswith(".py"):
                        full_path = os.path.join(root_dir, file)
                        local_mtimes.append(os.path.getmtime(full_path))
            if local_mtimes:
                latest_local_mtime = max(local_mtimes)
                local_dt = datetime.datetime.fromtimestamp(latest_local_mtime)
                local_str = local_dt.strftime('%Y-%m-%d %H:%M')
            else:
                local_str = "No modification info"
        else:
            local_str = "Modules folder not found"

        msg = (
            f"GitHub modules update: {remote_str}\n"
            f"Your local modules version: {local_str}\n\n"
        )
        try:
            if local_str not in ["No modification info", "Modules folder not found"]:
                local_dt = datetime.datetime.strptime(local_str, '%Y-%m-%d %H:%M')
                if remote_dt > local_dt:
                    msg += "Module updates are available!"
                else:
                    msg += "Your modules are up-to-date."
        except Exception:
            pass

        QtWidgets.QMessageBox.information(self, "Module Updates", msg)

    def update_modules(self):
        """
        Updates modules by downloading them directly from the GitHub repository using the API /contents.
        For each file in the modules folder (excluding __init__.py):
          - The file content is requested (download_url).
          - The version is extracted from the content (using get_module_version_from_content).
          - If the local file exists, its version is compared to the remote version:
                - If the remote version is newer, the file is replaced.
                - If the versions match, the module is considered up-to-date.
                - If the local version is newer (development version), no update is performed.
          - If the file does not exist, it is created.
        The final result is organized into sections and written to a log.
        """
        if not requests:
            QtWidgets.QMessageBox.warning(self, "Error", "The requests library is not installed.")
            return

        print("=== Starting module update via API /contents ===")
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/modules"
        response = requests.get(url)
        if response.status_code != 200:
            QtWidgets.QMessageBox.warning(self, "Error", f"GitHub API returned error: {response.status_code}")
            return

        modules_list = response.json()
        local_modules_dir = os.path.join(os.getcwd(), "modules")
        if not os.path.exists(local_modules_dir):
            os.makedirs(local_modules_dir)
            print("Local modules folder created:", local_modules_dir)

        updated = []       # list of tuples (name, version) for updated or created modules
        up_to_date = []    # list of tuples (name, version) for modules already up-to-date
        development = []   # list of tuples (name, version) for local development versions

        for file_obj in modules_list:
            file_name = file_obj.get("name")
            if not file_name.endswith(".py") or file_name == "__init__.py":
                continue

            remote_url = file_obj.get("download_url")
            print(f"Processing module: {file_name} (URL: {remote_url})")
            remote_resp = requests.get(remote_url)
            if remote_resp.status_code != 200:
                print(f"Error loading {file_name}: HTTP {remote_resp.status_code}")
                continue
            remote_content = remote_resp.text
            remote_version = get_module_version_from_content(remote_content)
            local_file_path = os.path.join(local_modules_dir, file_name)
            if os.path.exists(local_file_path):
                with open(local_file_path, "r", encoding="utf-8") as f:
                    local_content = f.read()
                local_version = get_module_version_from_content(local_content)
                print(f"  Local version: {local_version}")
                print(f"  Remote version: {remote_version}")
                cmp_result = compare_versions(local_version, remote_version)
                if cmp_result < 0:
                    with open(local_file_path, "w", encoding="utf-8", newline="") as f:
                        f.write(remote_content)
                    updated.append((file_name, remote_version))
                    print("  -> File updated (remote version is newer).")
                elif cmp_result == 0:
                    up_to_date.append((file_name, local_version))
                    print("  -> File is up-to-date (versions match).")
                else:
                    development.append((file_name, local_version))
                    print("  -> Local version is higher, development version (no update required).")
            else:
                with open(local_file_path, "w", encoding="utf-8", newline="") as f:
                    f.write(remote_content)
                updated.append((file_name, remote_version))
                print(f"New module: {file_name}")
                print(f"  Remote version set: {remote_version}")

        summary_lines = []
        summary_lines.append("Updated:")
        if updated:
            for name, ver in updated:
                summary_lines.append(f"  {name} ({ver})")
        else:
            summary_lines.append("  No updates.")
        summary_lines.append("\nUp-to-date:")
        if up_to_date:
            for name, ver in up_to_date:
                summary_lines.append(f"  {name} ({ver})")
        else:
            summary_lines.append("  No up-to-date modules.")
        if development:
            summary_lines.append("\nLocal development versions (no update required):")
            for name, ver in development:
                summary_lines.append(f"  {name} ({ver})")
        summary = "\n".join(summary_lines)
        print("=== Module update summary ===")
        print(summary)

        log_filename = "update_modules.log"
        try:
            with open(log_filename, "a", encoding="utf-8") as log_file:
                log_file.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_file.write(summary + "\n")
                log_file.write("=" * 40 + "\n")
            print(f"Update result saved in {log_filename}")
        except Exception as e:
            print(f"Error saving log: {e}")

        QtWidgets.QMessageBox.information(self, "Module Updates", summary)
        self.modules_info = []   # reset modules list
        self.load_modules()
        self.populate_modules_tree()
        self.update_file_list()

    def update_program(self):
        """
        Updates the program.
        Checks for a new version by comparing LOCAL_VERSION with the release version from GitHub.
        If the local version is newer, it indicates a development version.
        If the GitHub version is newer, it offers to update.
        """
        if not requests:
            QtWidgets.QMessageBox.warning(self, "Error", "The requests library is not installed.")
            return

        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                release = response.json()
                latest_version = release.get("tag_name", "0.0")
                cmp_result = compare_versions(LOCAL_VERSION, latest_version)
                if cmp_result == 0:
                    QtWidgets.QMessageBox.information(self, "Program Update", "You are using the latest version.")
                    return
                elif cmp_result > 0:
                    QtWidgets.QMessageBox.information(self, "Program Update", "You are using a development version. No update required.")
                    return
                else:
                    reply = QtWidgets.QMessageBox.question(
                        self,
                        "Program Update",
                        f"A new version is available: {latest_version}. Update program?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                    )
                    if reply == QtWidgets.QMessageBox.Yes:
                        self.perform_update(release)
            else:
                QtWidgets.QMessageBox.warning(self, "Error", f"GitHub API returned error: {response.status_code}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to check updates: {e}")

    def perform_update(self, release):
        """
        Updates the program:
          - Downloads the update tarball.
          - Extracts it to a temporary folder.
          - Copies files (preserving config.json).
        """
        tarball_url = release.get("tarball_url")
        if not tarball_url:
            QtWidgets.QMessageBox.warning(self, "Error", "Failed to get update URL.")
            return
        try:
            response = requests.get(tarball_url, stream=True)
            if response.status_code != 200:
                QtWidgets.QMessageBox.warning(self, "Error", f"Error downloading update: {response.status_code}")
                return

            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz")
            with open(tmp_file.name, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)

            tmp_dir = tempfile.mkdtemp()
            with tarfile.open(tmp_file.name, "r:gz") as tar:
                tar.extractall(path=tmp_dir)

            extracted_contents = os.listdir(tmp_dir)
            if not extracted_contents:
                QtWidgets.QMessageBox.warning(self, "Error", "Update does not contain files.")
                return
            extracted_dir = os.path.join(tmp_dir, extracted_contents[0])

            # Backup config.json
            if os.path.exists(CONFIG_FILE):
                shutil.copy2(CONFIG_FILE, CONFIG_FILE + ".backup")

            # Copy files from the updated version (excluding config.json)
            for root_dir, dirs, files in os.walk(extracted_dir):
                rel_path = os.path.relpath(root_dir, extracted_dir)
                dest_dir = os.path.join(os.getcwd(), rel_path)
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir)
                for file in files:
                    src_file = os.path.join(root_dir, file)
                    dest_file = os.path.join(dest_dir, file)
                    if os.path.basename(dest_file) == CONFIG_FILE:
                        continue
                    shutil.copy2(src_file, dest_file)

            # Restore config.json from backup
            if os.path.exists(CONFIG_FILE + ".backup"):
                shutil.copy2(CONFIG_FILE + ".backup", CONFIG_FILE)
                os.remove(CONFIG_FILE + ".backup")

            QtWidgets.QMessageBox.information(self, "Program Update", "Program successfully updated. Please restart the application.")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to perform update: {e}")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    # Minimal stylesheet for a cleaner look
    app.setStyleSheet("""
        QMainWindow { background-color: #f7f7f7; }
        QPushButton {
            font-family: 'Segoe UI', sans-serif;
        }
        QLabel { font-family: 'Segoe UI', sans-serif; color: #333333; }
        QTreeWidget, QTableWidget, QTextEdit {
            background-color: white;
            border: 1px solid #e0e0e0;
            font-family: 'Segoe UI', sans-serif;
            font-size: 13px;
        }
        QDateEdit {
            background-color: white;
            border: 1px solid #e0e0e0;
            font-family: 'Segoe UI', sans-serif;
            font-size: 13px;
        }
    """)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())