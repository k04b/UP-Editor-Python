from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QLineEdit,
    QFileDialog, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt
import xml_handler
import sys

# Матplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import re


def evaluate_expression(expr, L_val, W_val):
    """
    Вычисляет выражение: L, W, формулы, запятые, отрицания.
    """
    if not isinstance(expr, str):
        return 0.0
    expr = expr.strip()
    if expr == "":
        return 0.0

    expr = expr.replace(',', '.')
    try:
        num = float(expr)
        return num
    except:
        pass

    expr = expr.replace("L", str(L_val)).replace("W", str(W_val))

    def replace_neg(match):
        return " - " + match.group(1)

    expr = re.sub(r"-\((\d+\.?\d*)\)", replace_neg, expr)
    expr = re.sub(r"[^\d\.\+\-\*\/\(\) ]", "", expr)

    try:
        return float(eval(expr))
    except:
        return 0.0


class PlotWidget(FigureCanvas):
    def __init__(self, main_window, width=6, height=4, dpi=100):
        self.main_window = main_window
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(main_window)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.updateGeometry()

        # Подключаем события
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_hover)

        self.operation_patches = []

    def clear_plot(self):
        self.ax.clear()
        self.operation_patches = []

    def parse_coord(self, value, L_val, W_val, is_y=False):
        if not isinstance(value, str):
            value = str(value)
        value = value.replace(',', '.').strip()
        if value == "":
            return 0.0

        try:
            num = float(value)
            if num < 0:
                return L_val + num if not is_y else W_val + num
            return num
        except:
            pass

        expr = value.replace("L", str(L_val)).replace("W", str(W_val))
        expr = re.sub(r"-\((\d+\.?\d*)\)", r" - \1", expr)
        expr = re.sub(r"[^\d\.\+\-\*\/\(\) ]", "", expr)
        try:
            return float(eval(expr))
        except:
            return 0.0

    def draw_operations(self, operations, panel_length, panel_width):
        self.clear_plot()

        margin = 50
        self.ax.set_xlim(panel_length + margin, -margin)
        self.ax.set_ylim(-margin, panel_width + margin)

        self.ax.set_aspect('equal', adjustable='box')
        self.ax.set_title("Чертёж детали")
        self.ax.axis('off')

        rectangle = plt.Rectangle(
            (0, 0),
            panel_length,
            panel_width,
            linewidth=2,
            edgecolor='black',
            facecolor='lightblue',
            alpha=0.5,
            zorder=1
        )
        self.ax.add_patch(rectangle)

        types_in_use = set()

        for idx, op in enumerate(operations):
            try:
                type_name = op["TypeName"]
                L_val = float(panel_length)
                W_val = float(panel_width)

                if type_name == "Line":
                    begin_x = self.parse_coord(op.get("BeginX", "0"), L_val, W_val)
                    begin_y = self.parse_coord(op.get("BeginY", "0"), L_val, W_val, is_y=True)
                    end_x = self.parse_coord(op.get("EndX", "0"), L_val, W_val)
                    end_y = self.parse_coord(op.get("EndY", "0"), L_val, W_val, is_y=True)
                    line, = self.ax.plot([begin_x, end_x], [begin_y, end_y], color='brown', linewidth=2, zorder=2)
                    self.operation_patches.append((line, idx))
                    types_in_use.add(("Фрезеровка", 'brown'))

                elif type_name == "Horizontal Hole":
                    x_val = self.parse_coord(op.get("X1", "0"), L_val, W_val)
                    y_val = self.parse_coord(op.get("Y1", "0"), L_val, W_val, is_y=True)
                    try:
                        depth_val = float(str(op.get("Depth", "0")).replace(',', '.'))
                    except:
                        depth_val = 0.0
                    try:
                        diameter_val = float(str(op.get("Diameter", "5")).replace(',', '.'))
                    except:
                        diameter_val = 5.0

                    if x_val < 10:  # Правый торец → влево (внутрь)
                        rect = plt.Rectangle(
                            (x_val, y_val - diameter_val / 2),
                            depth_val,
                            diameter_val,
                            linewidth=0,
                            edgecolor='none',
                            facecolor='blue',
                            alpha=0.7,
                            zorder=2
                        )
                        self.ax.add_patch(rect)
                        self.operation_patches.append((rect, idx))
                        types_in_use.add(("Торцевое", 'blue'))
                    elif x_val > L_val - 10:  # Левый торец → влево (внутрь)
                        rect = plt.Rectangle(
                            (x_val - depth_val, y_val - diameter_val / 2),
                            depth_val,
                            diameter_val,
                            linewidth=0,
                            edgecolor='none',
                            facecolor='blue',
                            alpha=0.7,
                            zorder=2
                        )
                        self.ax.add_patch(rect)
                        self.operation_patches.append((rect, idx))
                        types_in_use.add(("Торцевое", 'blue'))
                    elif y_val < 10:  # Верхний торец → вниз (внутрь)
                        rect = plt.Rectangle(
                            (x_val - diameter_val / 2, y_val),
                            diameter_val,
                            depth_val,
                            linewidth=0,
                            edgecolor='none',
                            facecolor='blue',
                            alpha=0.7,
                            zorder=2
                        )
                        self.ax.add_patch(rect)
                        self.operation_patches.append((rect, idx))
                        types_in_use.add(("Торцевое", 'blue'))
                    elif y_val > W_val - 10:  # Нижний торец → вверх (внутрь)
                        rect = plt.Rectangle(
                            (x_val - diameter_val / 2, y_val - depth_val),
                            diameter_val,
                            depth_val,
                            linewidth=0,
                            edgecolor='none',
                            facecolor='blue',
                            alpha=0.7,
                            zorder=2
                        )
                        self.ax.add_patch(rect)
                        self.operation_patches.append((rect, idx))
                        types_in_use.add(("Торцевое", 'blue'))
                    else:
                        point, = self.ax.plot(x_val, y_val, 'o', color='blue', markersize=4)
                        self.operation_patches.append((point, idx))
                        types_in_use.add(("Торцевое", 'blue'))

                else:
                    x_val = self.parse_coord(op.get("X1", "0"), L_val, W_val)
                    y_val = self.parse_coord(op.get("Y1", "0"), L_val, W_val, is_y=True)
                    diameter = float(op.get("Diameter", "0") or 0)

                    try:
                        depth_val = float(str(op.get("Depth", "0")).replace(',', '.'))
                    except:
                        depth_val = 0.0

                    if depth_val >= 16.0:
                        color = 'yellow'
                        label = "Сквозное"
                    elif type_name == "Vertical Hole":
                        color = 'green'
                        label = "Верхняя плоскость"
                    elif type_name == "Back Vertical Hole":
                        color = 'red'
                        label = "Нижняя плоскость"
                    else:
                        color = 'red'
                        label = "Отверстие"

                    radius = diameter / 2
                    circle = plt.Circle((x_val, y_val), radius, color=color, fill=False, linewidth=1.5, zorder=2)
                    self.ax.add_patch(circle)
                    cross, = self.ax.plot(x_val, y_val, 'x', color=color, markersize=5, zorder=2)
                    self.operation_patches.append((circle, idx))
                    self.operation_patches.append((cross, idx))
                    types_in_use.add((label, color))

            except Exception as e:
                print(f"Ошибка при отрисовке: {e}")
                continue

        self.types_in_use = sorted(types_in_use, key=lambda x: x[0])
        self.draw()

    def on_click(self, event):
        if event.inaxes != self.ax:
            return
        x_click, y_click = event.xdata, event.ydata
        for obj, idx in reversed(self.operation_patches):
            if isinstance(obj, plt.Circle):
                dx = x_click - obj.center[0]
                dy = y_click - obj.center[1]
                if dx*dx + dy*dy <= (obj.radius + 10)**2:
                    self.main_window.table.selectRow(idx)
                    self.main_window.table.scrollTo(self.main_window.table.model().index(idx, 0))
                    break
            elif isinstance(obj, plt.Rectangle):
                xmin, ymin = obj.get_xy()
                xmax = xmin + obj.get_width()
                ymax = ymin + obj.get_height()

                # Увеличиваем зону клика
                margin_x = 10
                margin_y = 15
                click_xmin = xmin - margin_x
                click_xmax = xmax + margin_x
                click_ymin = ymin - margin_y
                click_ymax = ymax + margin_y

                if click_xmin <= x_click <= click_xmax and click_ymin <= y_click <= click_ymax:
                    self.main_window.table.selectRow(idx)
                    self.main_window.table.scrollTo(self.main_window.table.model().index(idx, 0))
                    break
            elif hasattr(obj, 'get_xydata'):
                xy = obj.get_xydata()
                if len(xy) >= 2:
                    x1, y1 = xy[0]
                    x2, y2 = xy[1]
                    A = x_click - x1
                    B = y_click - y1
                    C = x2 - x1
                    D = y2 - y1
                    dot = A * C + B * D
                    len_sq = C * C + D * D
                    param = -1 if len_sq == 0 else dot / len_sq
                    if param < 0:
                        xx, yy = x1, y1
                    elif param > 1:
                        xx, yy = x2, y2
                    else:
                        xx = x1 + param * C
                        yy = y1 + param * D
                    dist = ((x_click - xx)**2 + (y_click - yy)**2)**0.5
                    if dist < 10:
                        self.main_window.table.selectRow(idx)
                        self.main_window.table.scrollTo(self.main_window.table.model().index(idx, 0))
                        break

    def on_hover(self, event):
        if event.inaxes != self.ax:
            return

        x, y = event.xdata, event.ydata
        found = False

        for obj, idx in reversed(self.operation_patches):
            contains = False
            if isinstance(obj, plt.Circle):
                dx = x - obj.center[0]
                dy = y - obj.center[1]
                dist = (dx*dx + dy*dy)**0.5
                if dist <= obj.radius + 10:
                    contains = True
            elif isinstance(obj, plt.Rectangle):
                xmin, ymin = obj.get_xy()
                xmax = xmin + obj.get_width()
                ymax = ymin + obj.get_height()

                # Увеличиваем зону срабатывания
                margin_x = 10
                margin_y = 15
                hover_xmin = xmin - margin_x
                hover_xmax = xmax + margin_x
                hover_ymin = ymin - margin_y
                hover_ymax = ymax + margin_y

                if hover_xmin <= x <= hover_xmax and hover_ymin <= y <= hover_ymax:
                    contains = True
            elif hasattr(obj, 'get_xydata'):
                xy = obj.get_xydata()
                if len(xy) >= 2:
                    x1, y1 = xy[0]
                    x2, y2 = xy[1]
                    A = x - x1
                    B = y - y1
                    C = x2 - x1
                    D = y2 - y1
                    dot = A * C + B * D
                    len_sq = C * C + D * D
                    param = -1 if len_sq == 0 else dot / len_sq
                    if param < 0:
                        xx, yy = x1, y1
                    elif param > 1:
                        xx, yy = x2, y2
                    else:
                        xx = x1 + param * C
                        yy = y1 + param * D
                    dist = ((x - xx)**2 + (y - yy)**2)**0.5
                    if dist < 10:
                        contains = True

            if contains:
                self.fig.canvas.setCursor(Qt.PointingHandCursor)
                found = True
                break

        if not found:
            self.fig.canvas.setCursor(Qt.ArrowCursor)


class EditorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Редактор УП — MVP")
        self.setGeometry(100, 100, 1300, 650)
        self.file_path = None
        self.panel_data = {}
        self.cad_operations = []
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        main_layout = QHBoxLayout()

        left_widget = QWidget()
        left_layout = QVBoxLayout()
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

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Тип", "X", "Y", "Диаметр", "Глубина"])

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

        left_layout.addLayout(form_layout)
        left_layout.addWidget(self.table)
        left_layout.addLayout(button_layout)
        left_widget.setLayout(left_layout)

        right_widget = QWidget()
        right_layout = QVBoxLayout()

        self.plot = PlotWidget(self, width=6, height=4, dpi=100)
        right_layout.addWidget(self.plot)

        self.legend_widget = QWidget()
        self.legend_layout = QVBoxLayout()
        self.legend_widget.setLayout(self.legend_layout)
        self.legend_widget.setMaximumHeight(150)
        right_layout.addWidget(self.legend_widget)

        right_widget.setLayout(right_layout)

        main_layout.addWidget(left_widget, stretch=1)
        main_layout.addWidget(right_widget, stretch=2)

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def open_xml(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Открыть XML", "", "XML Files (*.xml)")
        if not file_path:
            return
        self.file_path = file_path
        self.panel_data, self.cad_operations = xml_handler.load_xml(file_path)
        self.name_input.setText(self.panel_data.get("PanelName", ""))
        self.length_input.setText(str(self.panel_data.get("PanelLength", "")).replace('.', ','))
        self.width_input.setText(str(self.panel_data.get("PanelWidth", "")).replace('.', ','))
        self.thickness_input.setText(str(self.panel_data.get("PanelThickness", "")).replace('.', ','))
        self.load_table()
        self.refresh_plot()
        self.update_legend()
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
            length_text = self.length_input.text().strip().replace(',', '.')
            width_text = self.width_input.text().strip().replace(',', '.')
            length = float(length_text) if length_text else 0.0
            width = float(width_text) if width_text else 0.0
            if length > 0 and width > 0:
                self.plot.draw_operations(self.cad_operations, length, width)
            else:
                self.plot.clear_plot()
                self.plot.ax.text(0.5, 0.5, 'Укажите размеры детали', transform=self.plot.ax.transAxes, ha='center')
                self.plot.draw()
        except Exception as e:
            print(f"Ошибка: {e}")
            self.plot.clear_plot()
            self.plot.ax.text(0.5, 0.5, 'Ошибка построения', transform=self.plot.ax.transAxes, ha='center', color='red')
            self.plot.draw()

    def update_legend(self):
        for i in reversed(range(self.legend_layout.count())):
            self.legend_layout.itemAt(i).widget().setParent(None)
        if hasattr(self.plot, 'types_in_use'):
            for label, color in self.plot.types_in_use:
                label_widget = QLabel(f" ■ {label}")
                label_widget.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 10pt;")
                self.legend_layout.addWidget(label_widget)


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    win = EditorWindow()
    win.show()
    app.exec()