import sys, os, glob, json, importlib, fnmatch, datetime
try:
    import requests
except ImportError:
    requests = None  # для проверки обновлений понадобится requests

from PyQt5 import QtWidgets, QtCore, QtGui

CONFIG_FILE = "config.json"
GITHUB_REPO = "DenForCLM/XVI_logs"  # Замените на имя вашего репозитория GitHub
LOCAL_VERSION = "0.0.3"  # текущая версия программы

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle("Log Analyzer")
        self.resize(1000, 700)
        self.config = self.load_config()
        self.modules_info = []  # список информации о модулях

        self.setup_menu()  # добавляем меню настроек

        # Основной виджет и layout
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Левая панель: дерево модулей анализа
        left_panel = QtWidgets.QVBoxLayout()
        modules_label = QtWidgets.QLabel("Модули анализа")
        modules_label.setStyleSheet("font-size:16px; font-weight:bold;")
        left_panel.addWidget(modules_label)

        # Кнопки "Выделить всё" и "Снять выделение"
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_select_all = QtWidgets.QPushButton("Выделить всё")
        self.btn_deselect_all = QtWidgets.QPushButton("Снять выделение")
        self.btn_select_all.clicked.connect(self.select_all_modules)
        self.btn_deselect_all.clicked.connect(self.deselect_all_modules)
        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addWidget(self.btn_deselect_all)
        left_panel.addLayout(btn_layout)

        self.modules_tree = QtWidgets.QTreeWidget()
        self.modules_tree.setHeaderHidden(True)
        self.modules_tree.itemChanged.connect(self.update_file_list)
        left_panel.addWidget(self.modules_tree, 1)
        main_layout.addLayout(left_panel, 2)

        # Правая панель: выбор дат, список файлов и результаты анализа
        right_panel = QtWidgets.QVBoxLayout()

        # --- Изменённый блок для выбора дат ---
        date_group = QtWidgets.QGroupBox("Выбор дат")
        dates_hbox = QtWidgets.QHBoxLayout()  # общая горизонтальная компоновка

        # Колонка "Дата начала"
        start_vbox = QtWidgets.QVBoxLayout()
        start_label = QtWidgets.QLabel("Дата начала:")
        self.start_date = QtWidgets.QDateEdit(calendarPopup=True)
        self.start_date.setFixedWidth(100)
        start_vbox.addWidget(start_label)
        start_vbox.addWidget(self.start_date)

        # Колонка "Дата конца"
        end_vbox = QtWidgets.QVBoxLayout()
        end_label = QtWidgets.QLabel("Дата конца:")
        self.end_date = QtWidgets.QDateEdit(calendarPopup=True)
        self.end_date.setFixedWidth(100)
        end_vbox.addWidget(end_label)
        end_vbox.addWidget(self.end_date)

        # Добавляем колонки в общую горизонтальную компоновку
        dates_hbox.addLayout(start_vbox)
        dates_hbox.addLayout(end_vbox)
        date_group.setLayout(dates_hbox)

        today = QtCore.QDate.currentDate()
        self.start_date.setDate(today.addDays(-1))
        self.end_date.setDate(today)

        right_panel.addWidget(date_group)
        # --- Конец изменённого блока ---

        # Список файлов для анализа
        file_list_label = QtWidgets.QLabel("Файлы для анализа")
        file_list_label.setStyleSheet("font-size:14px;")
        right_panel.addWidget(file_list_label)
        self.file_list = QtWidgets.QListWidget()
        right_panel.addWidget(self.file_list, 1)

        # Кнопка запуска анализа
        self.analyze_button = QtWidgets.QPushButton("Запустить анализ")
        self.analyze_button.clicked.connect(self.run_analysis)
        right_panel.addWidget(self.analyze_button)

        # Поле вывода результатов
        result_label = QtWidgets.QLabel("Результаты")
        result_label.setStyleSheet("font-size:14px;")
        right_panel.addWidget(result_label)
        self.result_text = QtWidgets.QTextEdit()
        self.result_text.setReadOnly(True)
        right_panel.addWidget(self.result_text, 2)

        main_layout.addLayout(right_panel, 3)

        # Загружаем модули динамически и настраиваем дерево
        self.load_modules()
        self.populate_modules_tree()
        self.update_file_list()

    def setup_menu(self):
        """Настраивает строку меню с пунктами для выбора пути и проверки обновлений."""
        menubar = self.menuBar()
        settings_menu = menubar.addMenu("Настройки")

        action_set_log_path = QtWidgets.QAction("Выбрать папку с логами", self)
        action_set_log_path.triggered.connect(self.choose_log_directory)
        settings_menu.addAction(action_set_log_path)

        action_check_module_updates = QtWidgets.QAction("Проверить обновления модулей", self)
        action_check_module_updates.triggered.connect(self.check_module_updates)
        settings_menu.addAction(action_check_module_updates)

        action_check_program_updates = QtWidgets.QAction("Проверить обновления программы", self)
        action_check_program_updates.triggered.connect(self.check_program_updates)
        settings_menu.addAction(action_check_program_updates)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Ошибка загрузки конфигурации: {e}")
        return {}

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Ошибка сохранения конфигурации: {e}")

    def choose_log_directory(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Выберите папку с логами", self.config.get("log_directory", "logs"))
        if directory:
            self.config["log_directory"] = directory
            self.save_config()
            self.update_file_list()

    def load_modules(self):
        """Динамически загружает модули из папки modules и собирает информацию о них."""
        modules_dir = os.path.join(os.path.dirname(__file__), "modules")
        if not os.path.isdir(modules_dir):
            print("Папка modules не найдена!")
            return
        for file in os.listdir(modules_dir):
            if file.endswith(".py") and file != "__init__.py":
                module_name = file[:-3]
                try:
                    plugin = importlib.import_module(f"modules.{module_name}")
                    if hasattr(plugin, "MODULE_INFO"):
                        info = plugin.MODULE_INFO
                        info["module"] = plugin  # сохраняем ссылку на модуль
                        self.modules_info.append(info)
                except Exception as e:
                    print(f"Ошибка загрузки модуля {module_name}: {e}")

    def populate_modules_tree(self):
        """Заполняет дерево модулей на основе информации, полученной из модулей."""
        self.modules_tree.blockSignals(True)
        self.modules_tree.clear()
        groups = {}
        for info in self.modules_info:
            group = info.get("group", "Без группы")
            if group not in groups:
                group_item = QtWidgets.QTreeWidgetItem(self.modules_tree)
                group_item.setText(0, group)
                group_item.setFlags(group_item.flags() | QtCore.Qt.ItemIsTristate | QtCore.Qt.ItemIsUserCheckable)
                groups[group] = group_item
            mod_item = QtWidgets.QTreeWidgetItem(groups[group])
            mod_item.setText(0, info.get("name", "Неизвестный модуль"))
            mod_item.setFlags(mod_item.flags() | QtCore.Qt.ItemIsUserCheckable)
            mod_item.setCheckState(0, QtCore.Qt.Checked)
            # Устанавливаем иконку по умолчанию (пустой круг)
            mod_item.setIcon(0, self.get_default_icon())
            info["tree_item"] = mod_item  # сохраняем ссылку для обновления значка
            mod_item.setData(0, QtCore.Qt.UserRole, info)
        self.modules_tree.blockSignals(False)
        self.modules_tree.expandAll()

    def select_all_modules(self):
        root = self.modules_tree.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                child.setCheckState(0, QtCore.Qt.Checked)

    def deselect_all_modules(self):
        root = self.modules_tree.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                child.setCheckState(0, QtCore.Qt.Unchecked)

    def update_file_list(self):
        """Обновляет список лог-файлов на основе выбранных модулей и их шаблонов."""
        directory = self.config.get("log_directory", "logs")
        if not os.path.isdir(directory):
            self.file_list.clear()
            return

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
            self.file_list.clear()
            return

        all_files = glob.glob(os.path.join(directory, "*.log"))
        filtered_files = []
        for file in all_files:
            filename = os.path.basename(file)
            for pattern in selected_patterns:
                if fnmatch.fnmatch(filename, pattern):
                    filtered_files.append(file)
                    break

        filtered_files.sort(key=lambda x: os.path.getmtime(x))
        self.file_list.clear()
        for file in filtered_files:
            # Выводим только имя файла
            self.file_list.addItem(os.path.basename(file))

    def get_default_icon(self):
        """Возвращает иконку с пустым кружком (до запуска анализа)."""
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
        Возвращает иконку для заданного статуса:
          - Green: зелёный фон с галочкой (символ отрисовывается чёрным),
          - Red: красный фон с крестиком,
          - Yellow: жёлтый фон с восклицательным знаком.
        """
        pixmap = QtGui.QPixmap(16, 16)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Выбираем цвет фона в зависимости от статуса
        if status == "Green":
            bg_color = QtGui.QColor("green")
        elif status == "Red":
            bg_color = QtGui.QColor("red")
        elif status == "Yellow":
            bg_color = QtGui.QColor("yellow")
        else:
            bg_color = QtGui.QColor("white")

        # Рисуем заполненный кружок с чёрной обводкой
        painter.setBrush(QtGui.QBrush(bg_color))
        painter.setPen(QtGui.QPen(QtGui.QColor("black"), 2))
        painter.drawEllipse(1, 1, 14, 14)

        # Отрисовываем символ (чёрным цветом)
        painter.setPen(QtGui.QPen(QtGui.QColor("black"), 2))
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
        start = self.start_date.date().toPyDate()
        end = self.end_date.date().toPyDate()
        files = [self.file_list.item(i).text() for i in range(self.file_list.count())]

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
            QtWidgets.QMessageBox.warning(self, "Предупреждение", "Выберите хотя бы один модуль анализа.")
            return

        self.result_text.clear()

        for info in selected_modules:
            try:
                analysis_func = getattr(info["module"], "analyze", None)
                if analysis_func:
                    result, status = analysis_func(files, start, end)
                else:
                    result = "Функция analyze не определена."
                    status = "Red"
            except Exception as e:
                result = f"Ошибка: {e}"
                status = "Red"

            # Обновляем иконку в дереве модулей
            tree_item = info.get("tree_item")
            if tree_item:
                tree_item.setIcon(0, self.get_status_icon(status))

            # Подготовка HTML для вставки статусной иконки в результаты анализа
            icon = self.get_status_icon(status)
            pixmap = icon.pixmap(16, 16)
            buffer = QtCore.QByteArray()
            buffer_io = QtCore.QBuffer(buffer)
            buffer_io.open(QtCore.QIODevice.WriteOnly)
            pixmap.save(buffer_io, "PNG")
            img_base64 = bytes(buffer.toBase64()).decode("utf-8")
            img_html = f'<img src="data:image/png;base64,{img_base64}">'

            # Выводим название модуля, статусную иконку и результат (текст – чёрного цвета)
            self.result_text.append(
                f'{img_html} <span style="color:black;">{info.get("name", "Неизвестный модуль")}: {result}</span>'
            )

    def check_module_updates(self):
        """
        Пример логики проверки обновлений модулей:
        Отправляем запрос к GitHub API для получения информации о последнем коммите в папке modules.
        Если дата последнего коммита новее, чем сохранённая, предлагаем обновить модули.
        """
        if not requests:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Библиотека requests не установлена.")
            return

        url = f"https://api.github.com/repos/{GITHUB_REPO}/commits?path=modules"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                commits = response.json()
                if commits:
                    latest_commit_date = commits[0]["commit"]["committer"]["date"]
                    latest_dt = datetime.datetime.strptime(latest_commit_date, "%Y-%m-%dT%H:%M:%SZ")
                    msg = f"Последнее обновление модулей: {latest_dt.strftime('%d.%m.%Y %H:%M')}"
                    QtWidgets.QMessageBox.information(self, "Обновления модулей", msg)
                else:
                    QtWidgets.QMessageBox.information(self, "Обновления модулей", "Нет информации об обновлениях.")
            else:
                QtWidgets.QMessageBox.warning(self, "Ошибка", f"GitHub API вернул ошибку: {response.status_code}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Ошибка", f"Не удалось проверить обновления: {e}")

    def check_program_updates(self):
        """
        Пример логики проверки обновлений программы:
        Можно использовать GitHub Releases или API для получения информации о последнем коммите.
        Сравниваем LOCAL_VERSION с информацией из репозитория и предлагаем обновление.
        """
        if not requests:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Библиотека requests не установлена.")
            return

        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                release = response.json()
                latest_version = release.get("tag_name", "0.0.0")
                published_at = release.get("published_at", "")
                msg = f"Последняя версия: {latest_version}\nДата выпуска: {published_at}"
                if latest_version != LOCAL_VERSION:
                    msg += "\nДоступно обновление!"
                else:
                    msg += "\nВы используете актуальную версию."
                QtWidgets.QMessageBox.information(self, "Обновления программы", msg)
            else:
                QtWidgets.QMessageBox.warning(self, "Ошибка", f"GitHub API вернул ошибку: {response.status_code}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Ошибка", f"Не удалось проверить обновления: {e}")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet("""
        QMainWindow { background-color: #f2f2f2; }
        QPushButton {
            background-color: #0078d7;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 5px 10px;
        }
        QPushButton:hover { background-color: #005fa1; }
        QLabel { font-size: 14px; font-weight: bold; }
        QTreeWidget, QListWidget, QTextEdit {
            background-color: white;
            border: 1px solid #cccccc;
            font-size: 13px;
        }
        QDateEdit {
            background-color: white;
            border: 1px solid #cccccc;
            padding: 2px;
        }
        QGroupBox { font-size: 14px; font-weight: bold; }
    """)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
