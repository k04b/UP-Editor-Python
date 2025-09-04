from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QFileDialog, QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt
import xml_handler
import sys

from PyQt5.QtWidgets import QSizePolicy  # ← Добавь в начало файла

# Матplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt


class PlotWidget(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
       self.fig = Figure(figsize=(width, height), dpi=dpi)
       self.ax = self.fig.add_subplot(111)
       self.ax.set_aspect('equal')
       super().__init__(self.fig)
       self.setParent(parent)

    # Правильно: используем QSizePolicy
       self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
       self.updateGeometry()

    def clear_plot(self):
        self.ax.clear()
        self.ax.set_aspect('equal')
        self.ax.grid(True, linestyle='--', alpha=0.5)

    def draw_panel(self, length, width):
        self.clear_plot()
        # Рисуем контур детали
        rectangle = plt.Rectangle((0, 0), length, width, linewidth=2, edgecolor='black', facecolor='lightblue', alpha=0.7)
        self.ax.add_patch(rectangle)
        self.ax.set_xlim(-10, length + 10)
        self.ax.set_ylim(-10, width + 10)
        self.ax.set_xlabel("X, мм")
        self.ax.set_ylabel("Y, мм")
        self.ax.set_title("Чертёж детали")
        self.ax.invert_yaxis()  # Y внизу — как на станке
        self.draw()

    def draw_operations(self, operations, panel_length, panel_width):
        self.clear_plot()
        self.draw_panel(panel_length, panel_width)

        for op in operations:
            try:
                x1_str = op.get("X1", "0")
                y1_str = op.get("Y1", "0")
                diameter = float(op.get("Diameter", op.get("Width", "0")) or 0)
                depth = float(op.get("Depth", "0") or 0)
                type_name = op["TypeName"]

                # Для Line
                if type_name == "Line":
                    coords_x = [float(x) for x in x1_str.split(";") if x.strip()]
                    coords_y = [float(y) for y in y1_str.split(";") if y.strip()]
                    if len(coords_x) == 2 and len(coords_y) == 2:
                        self.ax.plot(coords_x, coords_y, color='blue', linewidth=2, label="Фрезеровка" if "Фрезеровка" not in [l.get_text() for l in self.ax.get_legend_handles_labels()[1]] else "")
                else:
                    x_val = float(x1_str)
                    y_val = float(y1_str)
                    radius = diameter / 2
                    circle = plt.Circle((x_val, y_val), radius, color='red', fill=False, linewidth=1.5)
                    self.ax.add_patch(circle)
                    self.ax.plot(x_val, y_val, 'x', color='red', markersize=5)
            except:
                continue

        self.ax.legend()
        self.draw()


class EditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Редактор УП — MVP")
        self.setGeometry(100, 100, 1200, 600)

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

        # Чертёж
        self.plot = PlotWidget(self, width=6, height=5, dpi=100)

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

        # Разделитель: таблица слева, чертёж справа
        splitter = QSplitter(Qt.Horizontal)
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.addLayout(form_layout)
        left_layout.addWidget(self.table)
        left_layout.addLayout(button_layout)
        left_widget.setLayout(left_layout)

        splitter.addWidget(left_widget)
        splitter.addWidget(self.plot)
        splitter.setSizes([400, 600])

        layout.addWidget(splitter)
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
        self.refresh_plot()

        QMessageBox.information(self, "Готово", "Файл загружен и чертёж построен!")

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
        QMessageBox.information(self, "Сохранено", "Файл сохранён в формате станка!")

    def refresh_plot(self):
        try:
            length = float(self.length_input.text() or 0)
            width = float(self.width_input.text() or 0)
            if length > 0 and width > 0:
                self.plot.draw_operations(self.cad_operations, length, width)
            else:
                self.plot.draw_panel(1000, 500)  # заглушка
        except:
            self.plot.draw_panel(1000, 500)


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    win = EditorWindow()
    win.show()
    app.exec()