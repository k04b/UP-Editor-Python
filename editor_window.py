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
    if not isinstance(expr, str):
        return 0.0
    expr = expr.strip()
    if expr == "":
        return 0.0
    expr = expr.replace(',', '.')
    expr = re.sub(r"-\s*\(([\d.]+)\)", r"- \1", expr)
    expr = expr.replace("L", str(L_val)).replace("W", str(W_val))
    expr = re.sub(r"[^\d\.\+\-\*\/\(\) ]", "", expr)
    try:
        return float(eval(expr))
    except:
        return 0.0


# --- Отображаемые имена ---
def display_type(type_name):
    return {
        "Vertical Hole": "Верхняя плоскость",
        "Back Vertical Hole": "Нижняя плоскость",
        "Horizontal Hole": "Торцевое",
        "Line": "Линейная фрезеровка"
    }.get(type_name, type_name)


def internal_type(display_name):
    return {
        "Верхняя плоскость": "Vertical Hole",
        "Нижняя плоскость": "Back Vertical Hole",
        "Торцевое": "Horizontal Hole",
        "Линейная фрезеровка": "Line"
    }.get(display_name, display_name)
# ---------------------------


class PlotWidget(FigureCanvas):
    def __init__(self, main_window, width=6, height=4, dpi=100):
        self.main_window = main_window
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(main_window)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.updateGeometry()

        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_hover)

        self.operation_patches = []

    def clear_plot(self):
        self.ax.clear()
        self.operation_patches = []

    def clear_highlight(self):
        if hasattr(self, 'highlight_patch') and self.highlight_patch:
            self.highlight_patch.remove()
            self.highlight_patch = None
            self.draw()

    def highlight_element(self, idx):
        try:
            self.clear_highlight()
            for obj, i in self.operation_patches:
                if i == idx:
                    if isinstance(obj, plt.Circle):
                        center = obj.center
                        radius = obj.radius + 4
                        self.highlight_patch = plt.Circle(
                            center, radius,
                            color='red', fill=False, linewidth=4, zorder=30
                        )
                        self.ax.add_patch(self.highlight_patch)
                    elif isinstance(obj, plt.Rectangle):
                        xmin, ymin = obj.get_xy()
                        w, h = obj.get_width(), obj.get_height()
                        self.highlight_patch = plt.Rectangle(
                            (xmin - 2, ymin - 2), w + 4, h + 4,
                            edgecolor='red', facecolor='none', linewidth=4, zorder=30
                        )
                        self.ax.add_patch(self.highlight_patch)
                    elif hasattr(obj, 'get_xydata'):
                        xy = obj.get_xydata()
                        self.highlight_patch, = self.ax.plot(
                            xy[:, 0], xy[:, 1],
                            color='red', linewidth=5, zorder=30
                        )
                    break
            self.draw()
        except Exception as e:
            print(f"[ERROR] Ошибка в highlight_element: {e}")

    def parse_coord(self, value, L_val, W_val, is_y=False):
        if not isinstance(value, str):
            value = str(value)
        value = value.strip()
        if value == "":
            return 0.0
        if value.startswith('-') and value[1:].replace('.', '', 1).isdigit():
            try:
                num = float(value)
                if is_y:
                    return W_val + num
                else:
                    return L_val + num
            except:
                pass
        return evaluate_expression(value, L_val, W_val)

    def draw_operations(self, operations, panel_length, panel_width):
        self.clear_plot()
        margin = 50
        self.ax.set_xlim(panel_length + margin, -margin)
        self.ax.set_ylim(-margin, panel_width + margin)
        self.ax.set_aspect('equal', adjustable='box')
        self.ax.set_title("Чертёж детали")
        self.ax.axis('off')

        rectangle = plt.Rectangle(
            (0, 0), panel_length, panel_width,
            linewidth=2, edgecolor='black', facecolor='lightblue', alpha=0.5, zorder=1
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

                    if x_val < 10:
                        rect = plt.Rectangle((x_val, y_val - diameter_val / 2), depth_val, diameter_val,
                                           facecolor='blue', alpha=0.7, zorder=2)
                        self.ax.add_patch(rect)
                        self.operation_patches.append((rect, idx))
                        types_in_use.add(("Торцевое", 'blue'))
                    elif x_val > L_val - 10:
                        rect = plt.Rectangle((x_val - depth_val, y_val - diameter_val / 2), depth_val, diameter_val,
                                           facecolor='blue', alpha=0.7, zorder=2)
                        self.ax.add_patch(rect)
                        self.operation_patches.append((rect, idx))
                        types_in_use.add(("Торцевое", 'blue'))
                    elif y_val < 10:
                        rect = plt.Rectangle((x_val - diameter_val / 2, y_val), diameter_val, depth_val,
                                           facecolor='blue', alpha=0.7, zorder=2)
                        self.ax.add_patch(rect)
                        self.operation_patches.append((rect, idx))
                        types_in_use.add(("Торцевое", 'blue'))
                    elif y_val > W_val - 10:
                        rect = plt.Rectangle((x_val - diameter_val / 2, y_val - depth_val), diameter_val, depth_val,
                                           facecolor='blue', alpha=0.7, zorder=2)
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
                        color = 'magenta'
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
                    self.select_and_highlight_row(idx)
                    break
            elif isinstance(obj, plt.Rectangle):
                xmin, ymin = obj.get_xy()
                xmax = xmin + obj.get_width()
                ymax = ymin + obj.get_height()
                margin_x, margin_y = 10, 15
                if xmin - margin_x <= x_click <= xmax + margin_x and ymin - margin_y <= y_click <= ymax + margin_y:
                    self.select_and_highlight_row(idx)
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
                        self.select_and_highlight_row(idx)
                        break

    def select_and_highlight_row(self, idx):
        table = self.main_window.table
        table.selectRow(idx)
        self.highlight_element(idx)
        self.main_window.table.scrollTo(self.main_window.table.model().index(idx, 0))

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
                margin_x, margin_y = 10, 15
                if xmin - margin_x <= x <= xmax + margin_x and ymin - margin_y <= y <= ymax + margin_y:
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
        self.setGeometry(50, 50, 1300, 650)
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
        orm_layout = QHBoxLayout()

        self.name_input = QLineEdit()
        self.length_input = QLineEdit()
        self.width_input = QLineEdit()
        self.thickness_input = QLineEdit()

        orm_layout.addWidget(QLabel("    Имя"))
        orm_layout.addWidget(QLabel("    Длинна")) 
        orm_layout.addWidget(QLabel("    Ширина"))
        orm_layout.addWidget(QLabel("    Толщина"))      
        form_layout.addWidget(QLabel(""))
        form_layout.addWidget(self.name_input)
        form_layout.addWidget(QLabel(""))
        form_layout.addWidget(self.length_input)
        form_layout.addWidget(QLabel(""))
        form_layout.addWidget(self.width_input)
        form_layout.addWidget(QLabel(""))
        form_layout.addWidget(self.thickness_input)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Тип", "X1", "X2", "Y1", "Y2", "Диам.", "Глуб."])

        self.table.setColumnWidth(0, 90)  # Тип — шире
        self.table.setColumnWidth(1, 55)   # X1
        self.table.setColumnWidth(2, 55)   # X2
        self.table.setColumnWidth(3, 55)   # Y1
        self.table.setColumnWidth(4, 55)   # Y2
        self.table.setColumnWidth(5, 40)   # Диаметр
        self.table.setColumnWidth(6, 40)   # Глубина


        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        self.table.cellChanged.connect(self.on_table_edit)
        self.table.selectionModel().selectionChanged.connect(self.on_selection_changed)

        self.name_input.editingFinished.connect(self.update_panel_data)
        self.length_input.editingFinished.connect(self.update_panel_data)
        self.width_input.editingFinished.connect(self.update_panel_data)
        self.thickness_input.editingFinished.connect(self.update_panel_data)


        button_layout = QHBoxLayout()
        btn_open = QPushButton("Открыть XML")
        btn_save = QPushButton("Сохранить XML")
        btn_add_hole = QPushButton("Добавить отверстие")
        btn_delete = QPushButton("Удалить отверстие")

        btn_open.clicked.connect(self.open_xml)
        btn_save.clicked.connect(self.save_xml)
        btn_add_hole.clicked.connect(self.add_hole_dialog)
        btn_delete.clicked.connect(self.delete_selected_hole)
        

        button_layout.addWidget(btn_open)
        button_layout.addWidget(btn_save)
        button_layout.addWidget(btn_add_hole)  # вместо btn_refresh
        button_layout.addWidget(btn_delete)  # <-- Новая кнопка
        
        left_layout.addLayout(orm_layout)  
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

    def delete_selected_hole(self):
        """Удаляет выделенную операцию"""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Внимание", "Выберите отверстие для удаления")
            return

        # Подтверждение (опционально)
        reply = QMessageBox.question(
            self, "Удалить?", "Вы уверены, что хотите удалить выбранное отверстие?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        # Удаляем с конца, чтобы индексы не сбивались
        for row in sorted(selected_rows, key=lambda x: x.row(), reverse=True):
            self.table.removeRow(row.row())
            del self.cad_operations[row.row()]

        # Обновляем интерфейс
        self.refresh_plot()
        self.update_legend()
        QMessageBox.information(self, "Готово", "Отверстие удалено")


    def open_xml(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Открыть XML", "", "XML Files (*.xml)")
        if not file_path:
            return
        self.file_path = file_path

        self.table.blockSignals(True)
        self.plot.blockSignals(True)

        self.panel_data, self.cad_operations = xml_handler.load_xml(file_path)

        self.name_input.setText(self.panel_data.get("PanelName", ""))
        self.length_input.setText(str(self.panel_data.get("PanelLength", "")).replace('.', ','))
        self.width_input.setText(str(self.panel_data.get("PanelWidth", "")).replace('.', ','))
        self.thickness_input.setText(str(self.panel_data.get("PanelThickness", "")).replace('.', ','))

        self.load_table()
        self.refresh_plot()
        self.update_legend()

        self.table.blockSignals(False)
        self.plot.blockSignals(False)

        self.setWindowTitle(f"Редактор УП — {self.file_path}")
        QMessageBox.information(self, "Готово", "Файл загружен!")

    def load_table(self):
        self.table.blockSignals(True)  # 🔥 Отключаем сигналы
        self.table.setRowCount(0)
        for op in self.cad_operations:
            row = self.table.rowCount()
            self.table.insertRow(row)
            type_name = op.get("TypeName", "")
            display_name = display_type(type_name)
            self.table.setItem(row, 0, QTableWidgetItem(display_name))

            if type_name == "Line":
                x1 = op.get("BeginX", "0")
                x2 = op.get("EndX", "0")
                y1 = op.get("BeginY", "0")
                y2 = op.get("EndY", "0")
                self.table.setItem(row, 1, QTableWidgetItem(x1))
                self.table.setItem(row, 2, QTableWidgetItem(x2))
                self.table.setItem(row, 3, QTableWidgetItem(y1))
                self.table.setItem(row, 4, QTableWidgetItem(y2))
            else:
                x = op.get("X1", "0")
                y = op.get("Y1", "0")
                self.table.setItem(row, 1, QTableWidgetItem(x))
                self.table.setItem(row, 2, QTableWidgetItem(""))  # X2 пусто
                self.table.setItem(row, 3, QTableWidgetItem(y))
                self.table.setItem(row, 4, QTableWidgetItem(""))  # Y2 пусто

            self.table.setItem(row, 5, QTableWidgetItem(op.get("Diameter", op.get("Width", ""))))
            self.table.setItem(row, 6, QTableWidgetItem(op.get("Depth", "")))
        self.table.blockSignals(False)  # 🔥 Включаем обратно

    def on_table_edit(self, row, col):
        try:
            key = ["TypeName", "X1", "X2", "Y1", "Y2", "Diameter", "Depth"][col]
            item = self.table.item(row, col)
            if item is None:
                return
            value = item.text().strip()

            if key == "TypeName":
                internal_value = internal_type(value)
                self.cad_operations[row]["TypeName"] = internal_value
                # ❌ Убрали load_table()
                self.refresh_plot()
                return

            if key in ["X1", "X2", "Y1", "Y2", "Diameter", "Depth"]:
                try:
                    num = float(value.replace(',', '.'))
                    value = f"{num:.1f}"
                    item.setText(value)
                except:
                    value = "0.0"

            op = self.cad_operations[row]
            type_name = op["TypeName"]

            if type_name == "Line":
                if key == "X1": op["BeginX"] = value
                elif key == "X2": op["EndX"] = value
                elif key == "Y1": op["BeginY"] = value
                elif key == "Y2": op["EndY"] = value
                elif key == "Diameter": op["Width"] = value
                elif key == "Depth": op["Depth"] = value
            else:
                if key == "X1": op["X1"] = value
                elif key == "Y1": op["Y1"] = value
                elif key == "Diameter": op["Diameter"] = value
                elif key == "Depth": op["Depth"] = value

            self.refresh_plot()  # Перерисовываем чертёж

        except Exception as e:
            print(f"Ошибка при редактировании: {e}")

    def save_xml(self):
        self.save_xml_as()

    def save_xml_as(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить XML как...", "", "XML Files (*.xml)"
        )
        if not file_path:
            return

        if not file_path.lower().endswith('.xml'):
            file_path += '.xml'

        updated_cad = []
        for row in range(self.table.rowCount()):
            op = self.cad_operations[row].copy()  # Берём оригинальную операцию
            type_name = op.get("TypeName", "")

            if type_name == "Line":
                # Обновляем из таблицы
                begin_x_item = self.table.item(row, 1)
                begin_y_item = self.table.item(row, 3)
                end_x_item = self.table.item(row, 2)
                end_y_item = self.table.item(row, 4)
                width_item = self.table.item(row, 5)
                depth_item = self.table.item(row, 6)

                op["BeginX"] = begin_x_item.text().strip() if begin_x_item and begin_x_item.text().strip() else "0"
                op["BeginY"] = begin_y_item.text().strip() if begin_y_item and begin_y_item.text().strip() else "0"
                op["EndX"] = end_x_item.text().strip() if end_x_item and end_x_item.text().strip() else "0"
                op["EndY"] = end_y_item.text().strip() if end_y_item and end_y_item.text().strip() else "0"
                op["Width"] = width_item.text().strip() if width_item and width_item.text().strip() else "0"
                op["Depth"] = depth_item.text().strip() if depth_item and depth_item.text().strip() else "0"
            else:
                # Для отверстий
                x1_item = self.table.item(row, 1)
                y1_item = self.table.item(row, 3)
                diam_item = self.table.item(row, 5)
                depth_item = self.table.item(row, 6)

                op["X1"] = x1_item.text().strip() if x1_item and x1_item.text().strip() else "0"
                op["Y1"] = y1_item.text().strip() if y1_item and y1_item.text().strip() else "0"
                op["Diameter"] = diam_item.text().strip() if diam_item and diam_item.text().strip() else "0"
                op["Depth"] = depth_item.text().strip() if depth_item and depth_item.text().strip() else "0"

            updated_cad.append(op)

        try:
            xml_handler.save_xml(file_path, self.panel_data, updated_cad)
            self.file_path = file_path
            self.setWindowTitle(f"Редактор УП — {file_path}")
            QMessageBox.information(self, "Сохранено", "Файл успешно сохранён!")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл:\n{e}")

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

    def on_selection_changed(self, selected, deselected):
        indexes = self.table.selectionModel().selectedRows()
        if indexes:
            row = indexes[0].row()
            self.plot.highlight_element(row)

    def update_panel_data(self):
        """Обновляет panel_data при изменении полей ввода"""
        try:
            self.panel_data["PanelName"] = self.name_input.text().strip()

            length_text = self.length_input.text().strip().replace(',', '.')
            self.panel_data["PanelLength"] = float(length_text) if length_text else 0.0

            width_text = self.width_input.text().strip().replace(',', '.')
            self.panel_data["PanelWidth"] = float(width_text) if width_text else 0.0

            thickness_text = self.thickness_input.text().strip().replace(',', '.')
            self.panel_data["PanelThickness"] = float(thickness_text) if thickness_text else 0.0

            # Обновляем чертёж
            self.refresh_plot()

        except Exception as e:
            print(f"Ошибка обновления данных детали: {e}")

    def add_hole_dialog(self):
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QMessageBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Добавить отверстие")
        dialog.resize(300, 200)

        layout = QVBoxLayout()

        # Выбор типа
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Тип:"))
        type_combo = QComboBox()
        type_combo.addItems([
            "Верхняя плоскость",
            "Нижняя плоскость",
            "Торцевое",
            "Линейная фрезеровка"
        ])
        type_layout.addWidget(type_combo)
        layout.addLayout(type_layout)

        # Поля ввода
        x1_input = QLineEdit("0")
        x2_input = QLineEdit("0")
        y1_input = QLineEdit("0")
        y2_input = QLineEdit("0")
        diam_input = QLineEdit("5")
        depth_input = QLineEdit("16")

        layout.addWidget(QLabel("X1:"))
        layout.addWidget(x1_input)
        layout.addWidget(QLabel("X2 (для линии):"))
        layout.addWidget(x2_input)
        layout.addWidget(QLabel("Y1:"))
        layout.addWidget(y1_input)
        layout.addWidget(QLabel("Y2 (для линии):"))
        layout.addWidget(y2_input)
        layout.addWidget(QLabel("Диаметр / Ширина:"))
        layout.addWidget(diam_input)
        layout.addWidget(QLabel("Глубина:"))
        layout.addWidget(depth_input)

        # Кнопки
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Добавить")
        cancel_btn = QPushButton("Отмена")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        dialog.setLayout(layout)

        # Поведение X2/Y2
        def update_inputs():
            is_line = type_combo.currentText() == "Линейная фрезеровка"
            x2_input.setEnabled(is_line)
            y2_input.setEnabled(is_line)
            diam_input.setPlaceholderText("Ширина" if is_line else "Диаметр")

        type_combo.currentTextChanged.connect(update_inputs)
        update_inputs()

        # Обработка добавления
        def on_ok():
            try:
                type_display = type_combo.currentText()
                type_internal = internal_type(type_display)

                x1 = x1_input.text().strip()
                y1 = y1_input.text().strip()
                diam = diam_input.text().strip()
                depth = depth_input.text().strip()

                # Проверка чисел
                float(x1); float(y1); float(diam); float(depth)

                # Новая операция
                new_op = {
                    "TypeName": type_internal,
                    "X1": x1,
                    "Y1": y1,
                    "Diameter": diam,
                    "Depth": depth
                }

                if type_internal == "Line":
                    x2 = x2_input.text().strip()
                    y2 = y2_input.text().strip()
                    float(x2); float(y2)
                    new_op.update({
                        "BeginX": x1,
                        "BeginY": y1,
                        "EndX": x2,
                        "EndY": y2,
                        "Width": diam,
                        "Correction": "1",
                        "Direction": "6"
                    })

                self.cad_operations.append(new_op)
                self.load_table()
                self.refresh_plot()
                self.update_legend()  # ✅ Обновляем легенду
                dialog.accept()

            except ValueError:
                QMessageBox.critical(dialog, "Ошибка", "Введите корректные числовые значения!")
            except Exception as e:
                QMessageBox.critical(dialog, "Ошибка", f"Не удалось добавить отверстие: {e}")

        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(dialog.reject)

        dialog.exec_()            

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    win = EditorWindow()
    win.show()
    app.exec()