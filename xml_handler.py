# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
from xml.dom import minidom
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


def format_num(value):
    """
    Форматирует число: целые без .00, дробные — без лишних нулей.
    Пример: 123.00 → "123", 123.50 → "123.5", 123.45 → "123.45"
    """
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    if not value:
        return "0"
    try:
        f_val = float(value.replace(',', '.'))
        if f_val.is_integer():
            return str(int(f_val))
        else:
            return str(f_val).rstrip('0').rstrip('.')
    except:
        return value


def get_text(parent, tag, default):
    elem = parent.find(tag)
    if elem is not None and elem.text:
        return elem.text.strip()
    return default


def load_xml(file_path):
    """
    Загружает XML-файл в формате KDTPanelFormat.
    Полная поддержка Path с <Point>, <Line>, <Arc> внутри <Vertexes>.
    """
    tree = ET.parse(file_path)
    root = tree.getroot()

    panel_data = {}
    operations = []

    # === Читаем PANEL ===
    panel_elem = root.find("PANEL") or root.find("Panel")
    if panel_elem is None:
        raise ValueError("Не найден элемент <PANEL>")

    def get_text_local(parent, tag, default):
        elem = parent.find(tag)
        if elem is not None and elem.text:
            return elem.text.strip()
        return default

    panel_data["CoordinateSystem"] = get_text_local(panel_elem, "CoordinateSystem", "3")
    panel_data["PanelLength"] = get_text_local(panel_elem, "PanelLength", "0")
    panel_data["PanelWidth"] = get_text_local(panel_elem, "PanelWidth", "0")
    panel_data["PanelThickness"] = get_text_local(panel_elem, "PanelThickness", "0")
    panel_data["PanelName"] = get_text_local(panel_elem, "PanelName", "")
    panel_data["PanelOrderName"] = get_text_local(panel_elem, "PanelOrderName", "")
    panel_data["PanelMaterial"] = get_text_local(panel_elem, "PanelMaterial", "")
    panel_data["PanelTexture"] = get_text_local(panel_elem, "PanelTexture", "0")
    panel_data["PanelQuantity"] = get_text_local(panel_elem, "PanelQuantity", "1")
    panel_data["Inch"] = get_text_local(panel_elem, "Inch", "0")

    # Параметры из <Params>
    params_elem = panel_elem.find("Params")
    if params_elem is not None:
        for param in params_elem.findall("Param"):
            key = param.get("Key", "").strip().upper()
            value = param.get("Value", "0").strip()
            if key == "L":
                panel_data["PanelLength"] = value
            elif key == "W":
                panel_data["PanelWidth"] = value
            elif key == "T":
                panel_data["PanelThickness"] = value

    # === Читаем все CAD операции ===
    for cad_elem in root.findall("CAD"):
        op = {}

        for child in cad_elem:
            tag = child.tag
            text = child.text or ""
            op[tag] = text.strip()

        type_name = op.get("TypeName", "")

        # --- Обработка Path ---
        if type_name == "Path":
            vertexes = []
            vertexes_container = cad_elem.find("Vertexes")
            if vertexes_container is not None:
                for child in vertexes_container:
                    tag = child.tag.lower()
                    x1 = get_text(child, "X1", "0")
                    y1 = get_text(child, "Y1", "0")
                    z1 = get_text(child, "Z1", "0.00")
                    vtype = get_text(child, "VertexType", "0")

                    if tag == "point":
                        vertex = {
                            "type": "Point",
                            "X1": x1,
                            "Y1": y1,
                            "Z1": z1,
                            "VertexType": vtype
                        }
                        vertexes.append(vertex)
                    elif tag == "line":
                        vertex = {
                            "type": "Line",
                            "X1": x1,
                            "Y1": y1,
                            "Z1": z1,
                            "VertexType": vtype
                        }
                        vertexes.append(vertex)
                    elif tag == "arc":
                        radius = get_text(child, "Radius", "0")
                        direction = get_text(child, "Direction", "1")
                        vertex = {
                            "type": "Arc",
                            "X1": x1,
                            "Y1": y1,
                            "Z1": z1,
                            "VertexType": vtype,
                            "Radius": radius,
                            "Direction": direction
                        }
                        vertexes.append(vertex)

            if len(vertexes) > 0:
                # Копируем настройки пути
                settings = {
                    "Width": op.get("Width", "8"),
                    "Depth": op.get("Depth", "17"),
                    "Correction": op.get("Correction", "2"),
                    "CorrectionExtra": op.get("CorrectionExtra", "0"),
                    "Close": op.get("Close", "0"),
                    "Empty": op.get("Empty", "0"),
                    "Relative": op.get("Relative", "0"),
                    "Enable": op.get("Enable", "1")
                }
                op.update(settings)
                op["Vertexes"] = vertexes

        # --- Остальные типы ---
        elif type_name in ["Vertical Hole", "Back Vertical Hole", "Horizontal Hole", "Line"]:
            pass  # уже заполнено
        else:
            continue  # пропускаем неизвестные

        operations.append(op)

    return panel_data, operations


def save_xml(file_path, panel_data, operations):
    """
    Сохраняет данные в точном формате станка.
    - KDTPanelFormat
    - Vertexes → Point/Line/Arc
    - Без Z1 для Vertical Hole, Back Vertical Hole, Line
    - Числа без лишних .00
    """
    root = ET.Element("KDTPanelFormat")

    # === Блок PANEL ===
    panel = ET.SubElement(root, "PANEL")
    ET.SubElement(panel, "CoordinateSystem").text = panel_data.get("CoordinateSystem", "3")
    ET.SubElement(panel, "PanelLength").text = format_num(panel_data.get("PanelLength", "0"))
    ET.SubElement(panel, "PanelWidth").text = format_num(panel_data.get("PanelWidth", "0"))
    ET.SubElement(panel, "PanelThickness").text = format_num(panel_data.get("PanelThickness", "0"))

    ET.SubElement(panel, "PanelName").text = panel_data.get("PanelName", "") or None
    ET.SubElement(panel, "PanelOrderName").text = panel_data.get("PanelOrderName", "") or None
    ET.SubElement(panel, "PanelMaterial").text = panel_data.get("PanelMaterial", "") or None
    ET.SubElement(panel, "PanelTexture").text = panel_data.get("PanelTexture", "0")
    ET.SubElement(panel, "PanelQuantity").text = panel_data.get("PanelQuantity", "1")
    ET.SubElement(panel, "Inch").text = panel_data.get("Inch", "0")

    # === Params ===
    params = ET.SubElement(panel, "Params")
    L_val = format_num(panel_data.get("PanelLength", "0"))
    W_val = format_num(panel_data.get("PanelWidth", "0"))
    T_val = format_num(panel_data.get("PanelThickness", "0"))

    add_param(params, "Длина детали", "L", L_val)
    add_param(params, "Ширина детали", "W", W_val)
    add_param(params, "Толщина детали", "T", T_val)


    # === Операции CAD ===
    for op in operations:
        cad = ET.SubElement(root, "CAD")
        type_name = op.get("TypeName", "")

        # === TypeNo и TypeName ===
        type_no_map = {
            "Vertical Hole": "1",
            "Back Vertical Hole": "8",
            "Horizontal Hole": "2",
            "Line": "3",
            "Path": "7"
        }
        type_no = type_no_map.get(type_name, "1")
        ET.SubElement(cad, "TypeNo").text = type_no
        ET.SubElement(cad, "TypeName").text = type_name  # ⬅️ Обязательно добавляем!

        if type_name == "Path":
            # Настройки
            for key in ["Width", "Depth", "Correction", "CorrectionExtra", "Close", "Empty", "Relative", "Enable"]:
                val = op.get(key, "")
                if val:
                    ET.SubElement(cad, key).text = format_num(val)

            # Вершины
            vertexes_elem = ET.SubElement(cad, "Vertexes")
            for v in op.get("Vertexes", []):
                v_type = v["type"]
                if v_type == "Point":
                    el = ET.SubElement(vertexes_elem, "Point")
                    ET.SubElement(el, "X1").text = format_num(v["X1"])
                    ET.SubElement(el, "Y1").text = format_num(v["Y1"])
                    ET.SubElement(el, "Z1").text = format_num(v["Z1"])
                    ET.SubElement(el, "VertexType").text = v["VertexType"]
                elif v_type == "Line":
                    el = ET.SubElement(vertexes_elem, "Line")
                    ET.SubElement(el, "X1").text = format_num(v["X1"])
                    ET.SubElement(el, "Y1").text = format_num(v["Y1"])
                    ET.SubElement(el, "Z1").text = format_num(v["Z1"])
                    ET.SubElement(el, "VertexType").text = v["VertexType"]
                elif v_type == "Arc":
                    el = ET.SubElement(vertexes_elem, "Arc")
                    ET.SubElement(el, "X1").text = format_num(v["X1"])
                    ET.SubElement(el, "Y1").text = format_num(v["Y1"])
                    ET.SubElement(el, "Z1").text = format_num(v["Z1"])
                    ET.SubElement(el, "VertexType").text = v["VertexType"]
                    ET.SubElement(el, "Radius").text = format_num(v["Radius"])
                    ET.SubElement(el, "Direction").text = v["Direction"]

        elif type_name == "Line":
            for key in ["BeginX", "BeginY", "EndX", "EndY", "Width", "Depth", "Correction", "Direction", "Enable"]:
                val = op.get(key, "")
                if val:
                    ET.SubElement(cad, key).text = format_num(val)

        else:
            # Отверстия
            x1 = format_num(op.get("X1", "0"))
            y1 = format_num(op.get("Y1", "0"))
            depth = format_num(op.get("Depth", "0"))
            diameter = format_num(op.get("Diameter", "5"))
            hole_type = op.get("HoleType", "0")
            enable = op.get("Enable", "1")

            ET.SubElement(cad, "HoleType").text = hole_type
            ET.SubElement(cad, "X1").text = x1
            ET.SubElement(cad, "Y1").text = y1

            if type_name == "Horizontal Hole":
                z1 = format_num(op.get("Z1", "8.00"))
                ET.SubElement(cad, "Z1").text = z1

                try:
                    L_val_num = float(evaluate_expression(str(panel_data.get("PanelLength", 0)), 0, 0))
                    W_val_num = float(evaluate_expression(str(panel_data.get("PanelWidth", 0)), 0, 0))
                    x_val = evaluate_expression(x1, L_val_num, W_val_num)
                    y_val = evaluate_expression(y1, L_val_num, W_val_num)
                except:
                    x_val = 0.0
                    y_val = 0.0

                tolerance = 0.1
                quadrant = 0
                if abs(x_val) < tolerance:
                    quadrant = 2
                elif abs(x_val - L_val_num) < tolerance:
                    quadrant = 1
                elif abs(y_val) < tolerance:
                    quadrant = 4
                elif abs(y_val - W_val_num) < tolerance:
                    quadrant = 3

                if quadrant != 0:
                    ET.SubElement(cad, "Quadrant").text = str(quadrant)

            ET.SubElement(cad, "Depth").text = depth
            ET.SubElement(cad, "Diameter").text = diameter
            ET.SubElement(cad, "Enable").text = enable

    # Форматированный вывод
    rough_string = ET.tostring(root, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(reparsed.toprettyxml(indent="  "))


def add_param(parent, comment, key, value):
    param = ET.SubElement(parent, "Param")
    param.set("Comment", comment)
    param.set("Key", key)
    param.set("Value", str(value))