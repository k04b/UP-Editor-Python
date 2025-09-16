# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QFileDialog, QMessageBox, QDialog, QFormLayout, QTableWidget, QTableWidgetItem
)
from PyQt5.QtCore import Qt
import xml_handler
import sys

# Матplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.patches import Arc  # ← Обязательно добавь это!
#import matplotlib
import re
from math import atan2, degrees
import math

def calculate_arc_center(A, B, radius, direction):
    """
    Вычисляет центр дуги, соединяющей A и B с заданным радиусом и направлением.
    
    :param A: (x1, y1) — начальная точка
    :param B: (x2, y2) — конечная точка
    :param radius: радиус дуги
    :param direction: 1 = по часовой, 0 = против часовой
    :return: (cx, cy) — координаты центра дуги
    """
    x1, y1 = A
    x2, y2 = B

    # Вектор от A к B
    dx = x2 - x1
    dy = y2 - y1
    chord_length = math.hypot(dx, dy)

    # Проверка: радиус должен быть >= половине хорды
    half_chord = chord_length / 2
    if radius < half_chord:
        raise ValueError(f"Радиус {radius} слишком мал для соединения точек на расстоянии {chord_length}")

    # Середина хорды AB
    mx = (x1 + x2) / 2
    my = (y1 + y2) / 2

    # Единичный вектор вдоль хорды
    ux = dx / chord_length
    uy = dy / chord_length

    # Единичный перпендикуляр (вращение на 90°)
    nx = -uy  # нормаль
    ny = ux

    # Расстояние от середины хорды до центра дуги
    dist_to_center = math.sqrt(radius**2 - half_chord**2)

    # Выбор стороны: direction определяет, в какую сторону отклониться
    # В системе координат с Y вниз (как у станка) — может быть наоборот
    sign = 1 if direction == 1 else -1

    center_x = mx + sign * dist_to_center * nx
    center_y = my + sign * dist_to_center * ny

    return (center_x, center_y)


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
        "Line": "Линейная фрезеровка",
        "Path": "Путь фрезеровки"
    }.get(type_name, type_name)


def internal_type(display_name):
    return {
        "Верхняя плоскость": "Vertical Hole",
        "Нижняя плоскость": "Back Vertical Hole",
        "Торцевое": "Horizontal Hole",
        "Линейная фрезеровка": "Line",
        "Путь фрезеровки": "Path"
    }.get(display_name, display_name)
# ---------------------------


class PlotWidget(FigureCanvas):
    def __init__(self, main_window, width=10, height=6, dpi=100):
        self.main_window = main_window
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(main_window)
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

    def parse_coord(self, value, L_val, W_val, is_y=False, is_path=False):
        """
        Парсит координату.
        :param is_path: если True — отключаем обработку `-1` как `L-1`, т.к. это Path
        """
        if not isinstance(value, str):
            value = str(value)
        value = value.strip()
        if value == "":
            return 0.0

        # Для Path: отрицательные числа — абсолютные координаты
        if is_path:
            try:
                if value.startswith('-') and value[1:].replace('.', '', 1).isdigit():
                    return float(value)
                elif value.replace('.', '', 1).isdigit():
                    return float(value)
            except:
                pass
            return evaluate_expression(value, L_val, W_val)

        # Для остальных: -1 → L - 1 (если is_y=False) или W - 1 (если is_y=True)
        if value.startswith('-') and value[1:].replace('.', '', 1).isdigit():
            try:
                num = float(value)
                if is_y:
                    return W_val + num  # W - 10 → W + (-10)
                else:
                    return L_val + num  # L - 10 → L + (-10)
            except:
                pass

        return evaluate_expression(value, L_val, W_val)

    def draw_operations(self, operations, panel_length, panel_width):
        self.clear_plot()
        margin = 50
        # Устанавливаем пределы осей
        self.ax.set_xlim(panel_length + margin, -margin)  # X: справа (0) → слева (L)
        self.ax.set_ylim(panel_width + margin, -margin)   # Y: сверху (0) → снизу (W)

        # Инвертируем оси, чтобы рост координат шёл влево и вниз
        self.ax.invert_xaxis()  # X увеличивается влево
        self.ax.invert_yaxis()  # Y увеличивается вниз

        # Начало координат — правый верхний угол
        self.ax.set_xlim(panel_length + margin, -margin)
        self.ax.set_ylim(panel_width + margin, -margin)
        self.ax.set_aspect('equal', adjustable='box')
                # Получаем параметры
        try:
            L_val = float(panel_length)
        except:
            L_val = 0.0
        try:
            W_val = float(panel_width)
        except:
            W_val = 0.0
        thickness = self.main_window.panel_data.get("PanelThickness", "0")
        name = self.main_window.panel_data.get("PanelName", "Без имени")

        try:
            T_val = float(str(thickness).replace(',', '.'))
        except:
            T_val = 0.0

        title = f"Чертёж детали: {name}"
        subtitle = f"Размеры: {L_val:.1f} × {W_val:.1f} × {T_val:.1f} мм"
        self.ax.set_title(f"{title}\n{subtitle}", fontsize=12, loc='left')
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

                elif type_name == "Path":
                    vertexes = op.get("Vertexes", [])
                    if len(vertexes) < 2:
                        continue
                    points = []
                    for v in vertexes:
                        try:
                            x = self.parse_coord(v.get("X1", "0"), L_val, W_val, is_path=True)
                            y = self.parse_coord(v.get("Y1", "0"), L_val, W_val, is_y=True, is_path=True)
                            points.append((x, y))
                        except:
                            continue

                    for i in range(1, len(points)):
                        prev = points[i-1]
                        curr = points[i]
                        v = vertexes[i]  # <-- vertexes[i], т.к. vertexes[0] = Point

                        if v["type"] == "Line":
                            line, = self.ax.plot([prev[0], curr[0]], [prev[1], curr[1]], color='purple', linewidth=2, zorder=2)
                            self.operation_patches.append((line, idx))
                        elif v["type"] == "Arc":
                            try:
                                radius = float(v.get("Radius", 10))
                                direction = int(v.get("Direction", 1))
                                A = prev  # начальная точка
                                B = curr  # конечная точка

                                # Определяем порядок точек для расчёта угла
                                if direction == 0:
                                    # Для Direction = 0: рисуем от B к A (обратно)
                                    start_point = B
                                    end_point = A
                                else:
                                    # Для Direction = 1: от A к B
                                    start_point = A
                                    end_point = B

                                # Вычисляем центр дуги как середину перпендикуляра
                                center_x, center_y = calculate_arc_center(A, B, radius, direction)

                                # Углы от центра к точкам
                                start_angle = math.degrees(math.atan2(start_point[1] - center_y, start_point[0] - center_x))
                                end_angle = math.degrees(math.atan2(end_point[1] - center_y, end_point[0] - center_x))

                                # Нормализуем углы
                                start_angle = start_angle % 360
                                end_angle = end_angle % 360

                                # Корректируем конечный угол, чтобы дуга шла в нужную сторону
                                if end_angle >= start_angle + 180:
                                    end_angle -= 360
                                elif end_angle <= start_angle - 180:
                                    end_angle += 360

                                # matplotlib всегда рисует против часовой, поэтому:
                                # Чтобы дуга была "по часовой", нужно start_angle > end_angle
                                # Это уже обеспечивается коррекцией выше

                                arc_patch = Arc(
                                    (center_x, center_y),
                                    2 * radius, 2 * radius,
                                    theta1=start_angle,
                                    theta2=end_angle,
                                    color='purple',
                                    linewidth=2,
                                    zorder=2
                                )
                                self.ax.add_patch(arc_patch)
                                self.operation_patches.append((arc_patch, idx))

                            except Exception as e:
                                print(f"Arc error: {e}")
                                # Резерв: рисуем линию
                                line, = self.ax.plot([A[0], B[0]], [A[1], B[1]], color='purple', linewidth=2)
                                self.operation_patches.append((line, idx))

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
        if event.inaxes != self.ax or not event.xdata or not event.ydata:
            return

        x_click, y_click = event.xdata, event.ydata
        clicked_idx = None
        for obj, idx in reversed(self.operation_patches):
            try:
                if isinstance(obj, plt.Circle):
                    dx = x_click - obj.center[0]
                    dy = y_click - obj.center[1]
                    if dx*dx + dy*dy <= (obj.radius + 10)**2:
                        clicked_idx = idx
                        break
                elif isinstance(obj, plt.Rectangle):
                    xmin, ymin = obj.get_xy()
                    xmax = xmin + obj.get_width()
                    ymax = ymin + obj.get_height()
                    margin_x, margin_y = 10, 15
                    if xmin - margin_x <= x_click <= xmax + margin_x and ymin - margin_y <= y_click <= ymax + margin_y:
                        clicked_idx = idx
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
                            clicked_idx = idx
                            break
                elif isinstance(obj, Arc):
                    center = obj.center
                    radius = obj.width / 2
                    import numpy as np
                    angles = np.linspace(np.radians(obj.theta1), np.radians(obj.theta2), 100)
                    x_arc = center[0] + radius * np.cos(angles)
                    y_arc = center[1] + radius * np.sin(angles)
                    dist = np.min((x_arc - x_click)**2 + (y_arc - y_click)**2)**0.5
                    if dist < 10:
                        clicked_idx = idx
                        break
            except:
                continue

        if clicked_idx is not None:
            op = self.main_window.cad_operations[clicked_idx]
            type_name = op["TypeName"]

            if event.button == 1:  # Левый клик
                self.main_window.edit_operation(clicked_idx)
            elif event.button == 3:  # Правый клик
                if type_name in ["Vertical Hole", "Back Vertical Hole", "Horizontal Hole"]:
                    self.show_context_menu(event, clicked_idx)

    def show_context_menu(self, event, idx):
        from PyQt5.QtWidgets import QMenu
        from PyQt5.QtCore import QPoint

        menu = QMenu(self.main_window)
        action_mirror_x = menu.addAction("Отразить/скопировать по X")
        action_mirror_y = menu.addAction("Отразить/скопировать по Y")

        # 🔥 Правильное преобразование координат
        pos = QPoint(int(event.x), self.height() - int(event.y))
        global_pos = self.mapToGlobal(pos)

        action = menu.exec_(global_pos)
        if action == action_mirror_x:
            self.mirror_operation(idx, axis='x')
        elif action == action_mirror_y:
            self.mirror_operation(idx, axis='y')

    def mirror_operation(self, idx, axis):
        op = self.main_window.cad_operations[idx]
        try:
            L_val = float(evaluate_expression(str(self.main_window.panel_data.get("PanelLength", 0)), 0, 0))
        except:
            L_val = 0.0
        try:
            W_val = float(evaluate_expression(str(self.main_window.panel_data.get("PanelWidth", 0)), 0, 0))
        except:
            W_val = 0.0

        dialog = QDialog(self.main_window)
        dialog.setWindowTitle("Отразить с копированием?")
        dialog.resize(300, 150)
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"Отразить по {axis.upper()} с копированием?"))
        btn_layout = QHBoxLayout()
        yes_btn = QPushButton("Да")
        no_btn = QPushButton("Нет")
        btn_layout.addWidget(yes_btn)
        btn_layout.addWidget(no_btn)
        layout.addLayout(btn_layout)
        dialog.setLayout(layout)

        result = [None]

        def on_yes():
            result[0] = 'copy'
            dialog.accept()

        def on_no():
            result[0] = 'move'
            dialog.accept()

        yes_btn.clicked.connect(on_yes)
        no_btn.clicked.connect(on_no)

        if dialog.exec_() == QDialog.Rejected:
            return

        mode = result[0]
        x_str = op.get("X1", "0").strip()
        y_str = op.get("Y1", "0").strip()

        # --- Обработка X ---
        try:
            x_val = evaluate_expression(x_str, L_val, W_val)
        except:
            x_val = 0.0

        # Определяем, является ли X отрицательным (L - ...)
        is_x_negative = False
        try:
            if isinstance(x_str, str) and x_str.startswith('-') and x_str[1:].replace('.', '', 1).isdigit():
                offset = float(x_str[1:])
                original_offset = offset
                new_x_val = offset  # Расстояние от левого края
                is_x_negative = True
            else:
                # Положительное или формула: определяем расстояние до ближайшего края
                dist_to_left = abs(x_val - L_val)
                dist_to_right = abs(x_val)
                tolerance = 1.0
                if dist_to_left < tolerance:
                    original_offset = L_val - x_val
                    new_x_val = original_offset
                    is_x_negative = True
                elif dist_to_right < tolerance:
                    original_offset = x_val
                    new_x_val = original_offset
                    is_x_negative = False
                else:
                    original_offset = 0.0
                    new_x_val = x_val
        except:
            original_offset = 0.0
            new_x_val = x_val

        # --- Обработка Y ---
        try:
            y_val = evaluate_expression(y_str, L_val, W_val)
        except:
            y_val = 0.0

        is_y_negative = False
        try:
            if isinstance(y_str, str) and y_str.startswith('-') and y_str[1:].replace('.', '', 1).isdigit():
                offset = float(y_str[1:])
                original_offset_y = offset
                new_y_val = offset
                is_y_negative = True
            else:
                dist_to_top = abs(y_val)
                dist_to_bottom = abs(y_val - W_val)
                tolerance = 1.0
                if dist_to_bottom < tolerance:
                    original_offset_y = W_val - y_val
                    new_y_val = original_offset_y
                    is_y_negative = True
                elif dist_to_top < tolerance:
                    original_offset_y = y_val
                    new_y_val = original_offset_y
                    is_y_negative = False
                else:
                    original_offset_y = 0.0
                    new_y_val = y_val
        except:
            original_offset_y = 0.0
            new_y_val = y_val

        # --- Вычисляем новые координаты ---
        if axis == 'x':
            if is_x_negative:
                new_x = str(round(new_x_val, 1))  # Было L - 100 → станет 100
            else:
                new_x = f"-{round(new_x_val, 1)}"  # Было 100 → станет -100
            new_y = y_str
        else:  # axis == 'y'
            if is_y_negative:
                new_y = str(round(new_y_val, 1))  # Было -78 → станет 78
            else:
                new_y = f"-{round(new_y_val, 1)}"  # Было 78 → станет -78
            new_x = x_str

        # 🔥 Сохраняем состояние перед изменением
        self.main_window.save_state("Отражение отверстия")

        # --- Применяем изменение ---
        if mode == 'copy':
            new_op = {
                "TypeName": op["TypeName"],
                "X1": new_x,
                "Y1": new_y,
                "Diameter": op.get("Diameter", "5"),
                "Depth": op.get("Depth", "16")
            }
            self.main_window.cad_operations.append(new_op)
        else:  # move
            op["X1"] = new_x
            op["Y1"] = new_y

        #self.main_window.refresh_plot()



        self.main_window.refresh_plot()

class EditorWindow(QMainWindow):


    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Редактор УП — Минимализм")
        self.setGeometry(50, 30, 1300, 600)
        self.file_path = None
        self.panel_data = {}
        self.cad_operations = []
        self.undo_stack = []  # ← Стек для отмены
        self.max_undo_steps = 50  # Максимум шагов
        self.init_ui()
        self.update_window_title()

    def edit_line_dialog(self, idx=-1):
        """
        Диалог для добавления/редактирования линии (Line)
        idx = -1 → добавление, иначе редактирование
        """
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Редактирование линии" if idx >= 0 else "Добавить линию")
        dialog.resize(400, 300)

        layout = QVBoxLayout()

        # Поля ввода
        x1_input = QLineEdit("0")
        y1_input = QLineEdit("0")
        x2_input = QLineEdit("100")
        y2_input = QLineEdit("100")
        width_input = QLineEdit("8")
        depth_input = QLineEdit("17")

        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("Начало (X1, Y1):"))
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("X1:"))
        row1.addWidget(x1_input)
        row1.addWidget(QLabel("Y1:"))
        row1.addWidget(y1_input)
        form_layout.addLayout(row1)

        form_layout.addWidget(QLabel("Конец (X2, Y2):"))
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("X2:"))
        row2.addWidget(x2_input)
        row2.addWidget(QLabel("Y2:"))
        row2.addWidget(y2_input)
        form_layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Ширина:"))
        row3.addWidget(width_input)
        row3.addWidget(QLabel("Глубина:"))
        row3.addWidget(depth_input)
        form_layout.addLayout(row3)

        layout.addLayout(form_layout)

        # Кнопки
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        delete_btn = QPushButton("Удалить")
        cancel_btn = QPushButton("Отмена")
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        dialog.setLayout(layout)

        # Заполнение при редактировании
        if idx >= 0:
            op = self.cad_operations[idx]
            x1_input.setText(op.get("BeginX", "0"))
            y1_input.setText(op.get("BeginY", "0"))
            x2_input.setText(op.get("EndX", "100"))
            y2_input.setText(op.get("EndY", "100"))
            width_input.setText(op.get("Width", "8"))
            depth_input.setText(op.get("Depth", "17"))
            delete_btn.setVisible(True)
        else:
            delete_btn.setVisible(False)

        def save():
            try:
                self.save_state("Редактирование линии")  # ←
                x1 = x1_input.text().strip()
                y1 = y1_input.text().strip()
                x2 = x2_input.text().strip()
                y2 = y2_input.text().strip()
                width = width_input.text().strip()
                depth = depth_input.text().strip()

                # Валидация
                float(x1); float(y1); float(x2); float(y2); float(width); float(depth)

                new_op = {
                    "TypeName": "Line",
                    "BeginX": x1, "BeginY": y1,
                    "EndX": x2, "EndY": y2,
                    "Width": width,
                    "Depth": depth,
                    "Correction": "1",
                    "Direction": "6"
                }

                if idx == -1:
                    self.cad_operations.append(new_op)
                else:
                    self.cad_operations[idx] = new_op

                self.refresh_plot()
                dialog.accept()

            except ValueError:
                QMessageBox.critical(dialog, "Ошибка", "Введите корректные числовые значения!")
            except Exception as e:
                QMessageBox.critical(dialog, "Ошибка", f"Не удалось сохранить: {e}")

        def delete():
            if idx >= 0:
                reply = QMessageBox.question(dialog, "Удалить?", "Удалить эту линию?",
                                            QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.save_state("Удаление линии")  # ← Добавлено
                    del self.cad_operations[idx]
                    self.refresh_plot()
                    dialog.accept()

        save_btn.clicked.connect(save)
        delete_btn.clicked.connect(delete)
        cancel_btn.clicked.connect(dialog.reject)

        dialog.exec_()

    def init_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout()

        # === Создаём меню ===
        menu_bar = self.menuBar()

        # Меню "Файл"
        file_menu = menu_bar.addMenu("Файл")
        action_open = file_menu.addAction("Открыть XML")
        action_save = file_menu.addAction("Сохранить XML")

        # Меню "Добавить отверстие"
        add_hole_menu = menu_bar.addMenu("Добавить отверстие")
        action_top = add_hole_menu.addAction("Верхняя плоскость")
        action_back = add_hole_menu.addAction("Нижняя плоскость")
        action_horizontal = add_hole_menu.addAction("Торцевое")

        # Меню "Добавить фрезеровку"
        add_mill_menu = menu_bar.addMenu("Добавить фрезеровку")
        action_path = add_mill_menu.addAction("Путь фрезеровки")
        action_line = add_mill_menu.addAction("Линейная фрезеровка")

        # Меню "Параметры детали"
        panel_menu = menu_bar.addMenu("Параметры детали")
        action_edit_panel = panel_menu.addAction("Изменить параметры детали")

        # === Привязка действий ===
        action_open.triggered.connect(self.open_xml)
        action_save.triggered.connect(self.save_xml)

        action_top.triggered.connect(lambda: self.add_hole("Vertical Hole"))
        action_back.triggered.connect(lambda: self.add_hole("Back Vertical Hole"))
        action_horizontal.triggered.connect(lambda: self.add_hole("Horizontal Hole"))

        action_path.triggered.connect(lambda: self.edit_path_dialog(-1))
        action_line.triggered.connect(lambda: self.edit_line_dialog(-1))

        action_edit_panel.triggered.connect(self.edit_panel_properties)

        # === Поля параметров детали (опционально, можно оставить) ===
        params_layout = QHBoxLayout()
        self.name_input = QLineEdit()
        self.length_input = QLineEdit()
        self.width_input = QLineEdit()
        self.thickness_input = QLineEdit()

       # params_layout.addWidget(QLabel("Имя:"))
       # params_layout.addWidget(self.name_input)
       # params_layout.addWidget(QLabel("Длина:"))
        #params_layout.addWidget(self.length_input)
        #params_layout.addWidget(QLabel("Ширина:"))
        #params_layout.addWidget(self.width_input)
       # params_layout.addWidget(QLabel("Толщина:"))
        #params_layout.addWidget(self.thickness_input)

        # === Чертёж ===
        self.plot = PlotWidget(self)
        self.plot.fig.canvas.mpl_connect('button_press_event', self.plot.on_click)

        # === Добавляем всё в layout ===
        main_layout.addLayout(params_layout)  # Можно убрать, если хочешь только меню
        main_layout.addWidget(self.plot)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # === Привязка обновления данных ===
        self.name_input.editingFinished.connect(self.update_panel_data)
        self.length_input.editingFinished.connect(self.update_panel_data)
        self.width_input.editingFinished.connect(self.update_panel_data)
        self.thickness_input.editingFinished.connect(self.update_panel_data)

        # Горячая клавиша Ctrl+Z
        from PyQt5.QtGui import QKeySequence
        from PyQt5.QtWidgets import QShortcut
        undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        undo_shortcut.activated.connect(self.undo_action)

    def undo_action(self):
        """
        Отменяет последнее действие.
        """
        if not self.undo_stack:
            QMessageBox.information(self, "Отмена", "Нет действий для отмены.")
            return

        # Восстанавливаем предыдущее состояние
        state = self.undo_stack.pop()
        self.panel_data = state["panel_data"]
        self.cad_operations = state["cad_operations"]

        # Обновляем интерфейс
        if hasattr(self, 'name_input'):
            self.name_input.setText(self.panel_data.get("PanelName", ""))
            self.length_input.setText(str(self.panel_data.get("PanelLength", "")).replace('.', ','))
            self.width_input.setText(str(self.panel_data.get("PanelWidth", "")).replace('.', ','))
            self.thickness_input.setText(str(self.panel_data.get("PanelThickness", "")).replace('.', ','))

        self.refresh_plot()
        QMessageBox.information(self, "Отменено", f"Действие '{state['action']}' отменено.")        


    def add_hole(self, hole_type):
        """
        Унифицированное добавление отверстия по типу.
        Поддерживает формулы: L-100, W/2 и т.д.
        Для "Торцевое" — проверяет, что на торце.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Добавить отверстие")
        dialog.resize(300, 250)
        layout = QVBoxLayout()

        x_input = QLineEdit("0")
        y_input = QLineEdit("0")
        diam_input = QLineEdit("5")
        depth_input = QLineEdit("16")

        form_layout = QFormLayout()
        form_layout.addRow("X:", x_input)
        form_layout.addRow("Y:", y_input)
        form_layout.addRow("Диаметр:", diam_input)
        form_layout.addRow("Глубина:", depth_input)
        layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        cancel_btn = QPushButton("Отмена")
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        dialog.setLayout(layout)

        def save():
            try:
                self.save_state("Добавление отверстия")  # ←
                x_str = x_input.text().strip()
                y_str = y_input.text().strip()
                diam = diam_input.text().strip()
                depth = depth_input.text().strip()

                # Проверяем диаметр и глубину
                try:
                    float(diam)
                except:
                    QMessageBox.critical(dialog, "Ошибка", "Диаметр должен быть числом!")
                    return
                try:
                    float(depth)
                except:
                    QMessageBox.critical(dialog, "Ошибка", "Глубина должна быть числом!")
                    return

                # Получаем размеры детали
                try:
                    L_val = float(evaluate_expression(str(self.panel_data.get("PanelLength", 0)), 0, 0))
                except:
                    L_val = 0.0
                try:
                    W_val = float(evaluate_expression(str(self.panel_data.get("PanelWidth", 0)), 0, 0))
                except:
                    W_val = 0.0

                # Вычисляем координаты
                x_val = evaluate_expression(x_str, L_val, W_val)
                y_val = evaluate_expression(y_str, L_val, W_val)

                # Проверка: только для "Торцевое"
                if hole_type == "Horizontal Hole":
                    tolerance = 0.1
                    is_on_edge = (
                        abs(x_val) < tolerance or
                        abs(x_val - L_val) < tolerance or
                        abs(y_val) < tolerance or
                        abs(y_val - W_val) < tolerance
                    )
                    if not is_on_edge:
                        QMessageBox.warning(
                            dialog,
                            "Ошибка",
                            f"Торцевое отверстие должно быть на торце:\n\n"
                            f"• Правый: X ≈ 0\n"
                            f"• Левый: X ≈ {L_val:.0f}\n"
                            f"• Верхний: Y ≈ 0\n"
                            f"• Нижний: Y ≈ {W_val:.0f}"
                        )
                        return

                new_op = {
                    "TypeName": hole_type,
                    "X1": x_str,
                    "Y1": y_str,
                    "Diameter": diam,
                    "Depth": depth
                }
                self.cad_operations.append(new_op)
                self.refresh_plot()
                dialog.accept()

            except Exception as e:
                QMessageBox.critical(dialog, "Ошибка", f"Не удалось сохранить: {e}")

        save_btn.clicked.connect(save)
        cancel_btn.clicked.connect(dialog.reject)
        dialog.exec_()


    def edit_panel_properties(self):
        """
        Диалог для редактирования параметров детали: имя, размеры, толщина
        """
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFormLayout

        dialog = QDialog(self)
        dialog.setWindowTitle("Параметры детали")
        dialog.resize(300, 200)

        layout = QFormLayout()

        name_input = QLineEdit(self.panel_data.get("PanelName", ""))
        length_input = QLineEdit(str(self.panel_data.get("PanelLength", "")))
        width_input = QLineEdit(str(self.panel_data.get("PanelWidth", "")))
        thickness_input = QLineEdit(str(self.panel_data.get("PanelThickness", "")))

        layout.addRow("Имя:", name_input)
        layout.addRow("Длина:", length_input)
        layout.addRow("Ширина:", width_input)
        layout.addRow("Толщина:", thickness_input)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        cancel_btn = QPushButton("Отмена")
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

        dialog.setLayout(layout)

        def save():
            try:
                # Конвертируем строки → числа
                def to_float(text):
                    if not text.strip():
                        return 0.0
                    return float(text.strip().replace(',', '.'))

                self.panel_data["PanelName"] = name_input.text().strip()
                self.panel_data["PanelLength"] = to_float(length_input.text())
                self.panel_data["PanelWidth"] = to_float(width_input.text())
                self.panel_data["PanelThickness"] = to_float(thickness_input.text())

                self.refresh_plot()
                dialog.accept()
            except ValueError:
                QMessageBox.critical(dialog, "Ошибка", "Введите корректные числовые значения!")
            except Exception as e:
                QMessageBox.critical(dialog, "Ошибка", f"Ошибка сохранения: {e}")

        save_btn.clicked.connect(save)
        cancel_btn.clicked.connect(dialog.reject)

        dialog.exec_()

    def open_xml(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Открыть XML", "", "XML Files (*.xml)")
        if not file_path:
            return
        self.file_path = file_path
        self.panel_data, self.cad_operations = xml_handler.load_xml(file_path)
        self.file_path = file_path
        self.update_window_title()  # ← Новый метод
        self.refresh_plot()

    def refresh_plot(self):
        try:
            length = float(self.panel_data.get("PanelLength", 0))
            width = float(self.panel_data.get("PanelWidth", 0))
            if length > 0 and width > 0:
                self.plot.draw_operations(
                    self.cad_operations,
                    length,
                    width
                )
            else:
                self.plot.clear_plot()
                self.plot.ax.text(0.5, 0.5, 'Укажите размеры детали', transform=self.plot.ax.transAxes, ha='center')
                self.plot.draw()
        except Exception as e:
            print(f"Ошибка: {e}")

    def update_window_title(self):
        """
        Обновляет заголовок окна: имя программы + путь к файлу
        """
        base_title = "Редактор УП — Минимализм"
        if self.file_path:
            self.setWindowTitle(f"{base_title} | {self.file_path}")
        else:
            self.setWindowTitle(base_title)


    def edit_operation(self, idx):
        """
        Диалог редактирования отверстия.
        Для "Торцевое" — строгая проверка: только на торце.
        """
        if idx >= 0:
            op = self.cad_operations[idx]
            if op["TypeName"] == "Path":
                self.edit_path_dialog(idx)
                return
            elif op["TypeName"] == "Line":
                self.edit_line_dialog(idx)
                return

        dialog = QDialog(self)
        dialog.setWindowTitle("Редактировать отверстие")
        dialog.resize(300, 300)
        layout = QVBoxLayout()

        type_combo = QComboBox()
        type_combo.addItems([
            "Верхняя плоскость",
            "Нижняя плоскость",
            "Торцевое"
        ])

        x_input = QLineEdit("0")
        y_input = QLineEdit("0")
        diam_input = QLineEdit("5")
        depth_input = QLineEdit("16")

        form_layout = QFormLayout()
        form_layout.addRow("Тип:", type_combo)
        form_layout.addRow("X:", x_input)
        form_layout.addRow("Y:", y_input)
        form_layout.addRow("Диаметр:", diam_input)
        form_layout.addRow("Глубина:", depth_input)
        layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        delete_btn = QPushButton("Удалить")
        cancel_btn = QPushButton("Отмена")
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        dialog.setLayout(layout)

        # Заполняем при редактировании
        if idx >= 0:
            op = self.cad_operations[idx]
            type_combo.setCurrentText(display_type(op["TypeName"]))
            x_input.setText(op.get("X1", "0"))
            y_input.setText(op.get("Y1", "0"))
            diam_input.setText(op.get("Diameter", "5"))
            depth_input.setText(op.get("Depth", "16"))
            delete_btn.setVisible(True)
        else:
            delete_btn.setVisible(False)

        def save():
            try:
                self.save_state("Редактирование отверстия")  # ← Сохраняем состояние
                type_display = type_combo.currentText()
                type_internal = internal_type(type_display)
                x_str = x_input.text().strip()
                y_str = y_input.text().strip()
                diam = diam_input.text().strip()
                depth = depth_input.text().strip()

                # Проверяем диаметр и глубину
                try:
                    float(diam)
                except:
                    QMessageBox.critical(dialog, "Ошибка", "Диаметр должен быть числом!")
                    return
                try:
                    float(depth)
                except:
                    QMessageBox.critical(dialog, "Ошибка", "Глубина должна быть числом!")
                    return

                # Получаем размеры детали
                try:
                    L_val = float(evaluate_expression(str(self.panel_data.get("PanelLength", 0)), 0, 0))
                except:
                    L_val = 0.0
                try:
                    W_val = float(evaluate_expression(str(self.panel_data.get("PanelWidth", 0)), 0, 0))
                except:
                    W_val = 0.0

                # Вычисляем X и Y
                x_val = evaluate_expression(x_str, L_val, W_val)
                y_val = evaluate_expression(y_str, L_val, W_val)

                # Проверка: только для "Торцевое"
                if type_internal == "Horizontal Hole":
                    tolerance = 0.1
                    is_on_edge = (
                        abs(x_val) < tolerance or           # Правый торец: X ≈ 0
                        abs(x_val - L_val) < tolerance or   # Левый торец: X ≈ L
                        abs(y_val) < tolerance or           # Верхний торец: Y ≈ 0
                        abs(y_val - W_val) < tolerance      # Нижний торец: Y ≈ W
                    )
                    if not is_on_edge:
                        QMessageBox.warning(
                            dialog,
                            "Ошибка",
                            f"Торцевое отверстие должно быть на торце:\n\n"
                            f"• Правый: X ≈ 0\n"
                            f"• Левый: X ≈ {L_val:.0f}\n"
                            f"• Верхний: Y ≈ 0\n"
                            f"• Нижний: Y ≈ {W_val:.0f}"
                        )
                        return  # ❌ Блокируем сохранение

                new_op = {
                    "TypeName": type_internal,
                    "X1": x_str,
                    "Y1": y_str,
                    "Diameter": diam,
                    "Depth": depth
                }

                if idx == -1:
                    self.cad_operations.append(new_op)
                else:
                    self.cad_operations[idx] = new_op

                self.refresh_plot()
                dialog.accept()

            except Exception as e:
                QMessageBox.critical(dialog, "Ошибка", f"Не удалось сохранить: {e}")

        def delete():
            if idx >= 0:
                reply = QMessageBox.question(dialog, "Удалить?", "Удалить это отверстие?",
                                            QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.save_state("Удаление отверстия")
                    del self.cad_operations[idx]
                    self.refresh_plot()
                    dialog.accept()

        save_btn.clicked.connect(save)
        delete_btn.clicked.connect(delete)
        cancel_btn.clicked.connect(dialog.reject)
        dialog.exec_()
        

    def edit_path_dialog(self, idx=-1):
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, \
            QTableWidget, QTableWidgetItem, QMessageBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Редактирование пути фрезеровки" if idx >= 0 else "Добавить путь фрезеровки")
        dialog.resize(700, 500)

        layout = QVBoxLayout()
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Тип", "X1", "Y1", "Radius", "Напр."])
        table.setRowCount(0)

        # Заполняем таблицу, если редактируем
        if idx >= 0:
            op = self.cad_operations[idx]
            vertexes = op.get("Vertexes", [])
            for i, v in enumerate(vertexes):
                row = table.rowCount()
                table.insertRow(row)
                if i == 0:
                    type_combo = QComboBox()
                    type_combo.addItems(["Point"])
                    type_combo.setEnabled(False)
                    table.setCellWidget(row, 0, type_combo)
                else:
                    type_combo = QComboBox()
                    type_combo.addItems(["Line", "Arc"])
                    type_combo.setCurrentText(v["type"])
                    table.setCellWidget(row, 0, type_combo)
                table.setItem(row, 1, QTableWidgetItem(v.get("X1", "0")))
                table.setItem(row, 2, QTableWidgetItem(v.get("Y1", "0")))
                if v["type"] == "Arc":
                    table.setItem(row, 3, QTableWidgetItem(v.get("Radius", "0")))
                    dir_combo = QComboBox()
                    dir_combo.addItems(["0", "1"])
                    dir_combo.setCurrentText(v.get("Direction", "1"))
                    table.setCellWidget(row, 4, dir_combo)
                else:
                    table.setItem(row, 3, QTableWidgetItem(""))
                    table.setItem(row, 4, QTableWidgetItem(""))

        # Кнопки добавления
        btn_layout = QHBoxLayout()
        btn_add_point = QPushButton("Начальная точка")
        btn_add_line = QPushButton("Добавить Line")
        btn_add_arc = QPushButton("Добавить Arc")
        btn_delete_vertex = QPushButton("Удалить вершину")
        btn_layout.addWidget(btn_add_point)
        btn_layout.addWidget(btn_add_line)
        btn_layout.addWidget(btn_add_arc)
        btn_layout.addWidget(btn_delete_vertex)

        # Поля ширины и глубины
        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("Ширина:"))
        width_input = QLineEdit("8")
        width_layout.addWidget(width_input)
        width_layout.addWidget(QLabel("Глубина:"))
        depth_input = QLineEdit("17")
        width_layout.addWidget(depth_input)

        # Кнопка "Удалить весь путь" — только при редактировании
        btn_delete_path = QPushButton("Удалить весь путь")
        if idx >= 0:
            btn_delete_path.setVisible(True)
            op = self.cad_operations[idx]
            width_input.setText(op.get("Width", "8"))
            depth_input.setText(op.get("Depth", "17"))
        else:
            btn_delete_path.setVisible(False)

        # Кнопки OK/Cancel
        btn_ok = QPushButton("Сохранить")
        btn_cancel = QPushButton("Отмена")
        btn_layout.addStretch()
        btn_layout.addWidget(btn_delete_path)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        
        layout.addWidget(QLabel("Вершины пути:"))
        layout.addWidget(table)
        layout.addLayout(width_layout)
        layout.addLayout(btn_layout)
        dialog.setLayout(layout)

        # Функции добавления вершин
        def add_vertex(vertex_type, x="0", y="0", radius="", direction="1"):
            row = table.rowCount()
            table.insertRow(row)
            if vertex_type == "Point":
                type_combo = QComboBox()
                type_combo.addItems(["Point"])
                type_combo.setEnabled(False)
                table.setCellWidget(row, 0, type_combo)
                table.setItem(row, 1, QTableWidgetItem(x))
                table.setItem(row, 2, QTableWidgetItem(y))
                table.setItem(row, 3, QTableWidgetItem(""))
                table.setItem(row, 4, QTableWidgetItem(""))
            else:
                type_combo = QComboBox()
                type_combo.addItems(["Line", "Arc"])
                type_combo.setCurrentText(vertex_type)
                table.setCellWidget(row, 0, type_combo)
                table.setItem(row, 1, QTableWidgetItem(x))
                table.setItem(row, 2, QTableWidgetItem(y))
                table.setItem(row, 3, QTableWidgetItem(radius))
                dir_combo = QComboBox()
                dir_combo.addItems(["0", "1"])
                dir_combo.setCurrentText(direction)
                table.setCellWidget(row, 4, dir_combo)

        # Привязка кнопок
        btn_add_point.clicked.connect(lambda: add_vertex("Point", "0", "0"))
        btn_add_line.clicked.connect(lambda: add_vertex("Line", "0", "0"))
        btn_add_arc.clicked.connect(lambda: add_vertex("Arc", "0", "0", "0", "1"))
        btn_delete_vertex.clicked.connect(lambda: table.removeRow(table.currentRow()))

        # Обработчик сохранения
        def on_ok():
            self.save_state("Редактирование пути фрезеровки")  # ←
            if table.rowCount() == 0:
                QMessageBox.warning(dialog, "Ошибка", "Добавьте хотя бы начальную точку")
                return

            vertexes = []
            for row in range(table.rowCount()):
                item0 = table.cellWidget(row, 0)
                x_item = table.item(row, 1)
                y_item = table.item(row, 2)
                radius_item = table.item(row, 3)
                dir_item = table.cellWidget(row, 4)
                if not x_item or not y_item:
                    continue
                x = x_item.text().strip()
                y = y_item.text().strip()
                if row == 0:
                    vertexes.append({"type": "Point", "X1": x, "Y1": y, "Z1": "0.00", "VertexType": "0"})
                else:
                    base = {"X1": x, "Y1": y, "Z1": "0.00", "VertexType": "0"}
                    t = item0.currentText()
                    if t == "Line":
                        base["type"] = "Line"
                    elif t == "Arc":
                        base["type"] = "Arc"
                        base["Radius"] = radius_item.text().strip() if radius_item else "0"
                        base["Direction"] = dir_item.currentText() if dir_item else "1"
                    vertexes.append(base)

            new_op = {
                "TypeName": "Path",
                "Width": width_input.text().strip(),
                "Depth": depth_input.text().strip(),
                "Correction": "2", "CorrectionExtra": "0", "Close": "0",
                "Empty": "0", "Relative": "0", "Enable": "1", "Vertexes": vertexes
            }

            if idx >= 0:
                self.cad_operations[idx] = new_op
                self.refresh_plot()
                dialog.accept()  # Закрываем диалог
            else:
                self.cad_operations.append(new_op)
                self.refresh_plot()
                dialog.accept()

        # Кнопка "Удалить весь путь"
        def on_delete_path():
            if idx < 0:
                return
            reply = QMessageBox.question(
                dialog, "Удалить путь?",
                "Вы действительно хотите удалить весь путь?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.save_state("Удаление пути фрезеровки")  # ←
                del self.cad_operations[idx]
                self.refresh_plot()
                dialog.accept()  # Закрываем диалог

        btn_ok.clicked.connect(on_ok)
        btn_cancel.clicked.connect(dialog.reject)
        btn_delete_path.clicked.connect(on_delete_path)  # Подключаем отдельный обработчик

        dialog.exec_()

    def update_panel_data(self):
        """Обновляет panel_data при изменении полей ввода"""
        try:
            self.save_state("Изменение параметров детали")  # ←
            # Сохраняем имя
            self.panel_data["PanelName"] = self.name_input.text().strip()

            # Конвертируем строку в число (поддержка запятой)
            def to_float(text):
                if not text.strip():
                    return 0.0
                return float(text.strip().replace(',', '.'))

            self.panel_data["PanelLength"] = to_float(self.length_input.text())
            self.panel_data["PanelWidth"] = to_float(self.width_input.text())
            self.panel_data["PanelThickness"] = to_float(self.thickness_input.text())

            # Обновляем чертёж (и заголовок)
            self.refresh_plot()

        except Exception as e:
            print(f"Ошибка обновления данных детали: {e}")
            QMessageBox.critical(self, "Ошибка", f"Некорректные данные: {e}")


    def save_xml(self):
        """
        Всегда показывает диалог 'Сохранить как...' — даже если файл уже был сохранён.
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить XML",
            "",  # Папка по умолчанию
            "XML Files (*.xml);;All Files (*)"
        )
        if not file_path:
            return  # Пользователь отменил сохранение

        # Добавляем расширение .xml, если не указано
        if not file_path.lower().endswith('.xml'):
            file_path += '.xml'

        try:
            xml_handler.save_xml(file_path, self.panel_data, self.cad_operations)
            # Обновляем текущий путь (если захочешь добавить "Сохранить" позже)
            self.file_path = file_path
            QMessageBox.information(self, "Сохранено", f"Файл успешно сохранён!\n{file_path}")
            self.file_path = file_path
            self.update_window_title()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл:\n{e}")

    def save_state(self, action_name="Изменение"):
        """
        Сохраняет текущее состояние в стеке отмены.
        """
        import copy
        state = {
            "panel_data": copy.deepcopy(self.panel_data),
            "cad_operations": copy.deepcopy(self.cad_operations),
            "action": action_name
        }
        self.undo_stack.append(state)
        if len(self.undo_stack) > self.max_undo_steps:
            self.undo_stack.pop(0)  # Удаляем самый старый            


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    win = EditorWindow()
    win.show()
    app.exec()