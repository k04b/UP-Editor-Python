from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt
import xml_handler


class EditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Редактор УП — MVP")
        self.setGeometry(100, 100, 900, 600)

        self.file_path = None
        self.panel_data = {}
        self.cad_operations = []

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        layout = QVBoxLayout()

        # Поля данных детали
        form_layout = QHBoxLayout()
        self.name_input = QLineEdit()
        self.length_input = QLineEdit()
        self.width_input = QLineEdit()
        self.thickness_input = QLineEdit()

        form_layout.addWidget(QLabel("Имя:"))
        form_layout.addWidget(self.name_input)
        form_layout.addWidget(QLabel("Длина:"))
        form_layout.addWidget(self.length_input)
        form_layout.addWidget(QLabel("Ширина:"))
        form_layout.addWidget(self.width_input)
        form_layout.addWidget(QLabel("Толщина:"))
        form_layout.addWidget(self.thickness_input)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Тип", "X", "Y", "Диаметр", "Глубина"])

        # Кнопки
        button_layout = QHBoxLayout()
        btn_open = QPushButton("Открыть XML")
        btn_save = QPushButton("Сохранить XML")
        btn_refresh = QPushButton("Обновить чертёж")

        btn_open.clicked.connect(self.open_xml)
        btn_save.clicked.connect(self.save_xml)
        btn_refresh.clicked.connect(self.refresh_plot)

        button_layout.addWidget(btn_open)
        button_layout.addWidget(btn_save)
        button_layout.addWidget(btn_refresh)

        layout.addLayout(form_layout)
        layout.addWidget(self.table)
        layout.addLayout(button_layout)
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def open_xml(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Открыть XML", "", "XML Files (*.xml)")
        if not file_path:
            return

        self.file_path = file_path
        self.panel_data, self.cad_operations = xml_handler.load_xml(file_path)

        self.name_input.setText(self.panel_data.get("PanelName", ""))
        self.length_input.setText(self.panel_data.get("PanelLength", ""))
        self.width_input.setText(self.panel_data.get("PanelWidth", ""))
        self.thickness_input.setText(self.panel_data.get("PanelThickness", ""))

        self.load_table()

        QMessageBox.information(self, "Готово", "Файл загружен!")

    def load_table(self):
        self.table.setRowCount(0)
        for op in self.cad_operations:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(op.get("TypeName", "")))
            if op["TypeName"] == "Line":
                x_val = f"{op.get('BeginX', '')};{op.get('EndX', '')}"
                y_val = f"{op.get('BeginY', '')};{op.get('EndY', '')}"
            else:
                x_val = op.get("X1", "")
                y_val = op.get("Y1", "")
            self.table.setItem(row, 1, QTableWidgetItem(x_val))
            self.table.setItem(row, 2, QTableWidgetItem(y_val))
            self.table.setItem(row, 3, QTableWidgetItem(op.get("Diameter", op.get("Width", ""))))
            self.table.setItem(row, 4, QTableWidgetItem(op.get("Depth", "")))

    def save_xml(self):
        if not self.file_path:
            return

        # Собираем данные из таблицы
        updated_cad = []
        for row in range(self.table.rowCount()):
            op = {
                "TypeName": self.table.item(row, 0).text() if self.table.item(row, 0) else "",
                "X1": self.table.item(row, 1).text() if self.table.item(row, 1) else "",
                "Y1": self.table.item(row, 2).text() if self.table.item(row, 2) else "",
                "Diameter": self.table.item(row, 3).text() if self.table.item(row, 3) else "",
                "Depth": self.table.item(row, 4).text() if self.table.item(row, 4) else ""
            }
            updated_cad.append(op)

        xml_handler.save_xml(self.file_path, self.panel_data, updated_cad)
        QMessageBox.information(self, "Сохранено", "Файл сохранён в том же формате, что и у станка!")

    def refresh_plot(self):
        # Пока заглушка
        QMessageBox.information(self, "Чертёж", "Чертёж будет добавлен в следующем обновлении!")


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication([])
    win = EditorWindow()
    win.show()
    app.exec()
