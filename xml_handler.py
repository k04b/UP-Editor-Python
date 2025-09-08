import xml.etree.ElementTree as ET


def load_xml(filepath):
    """
    Загружает XML-файл станка.
    Возвращает: (panel_data, cad_operations)
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        panel_data = {}
        panel = root.find("PANEL")
        if panel is not None:
            panel_data["PanelLength"] = panel.findtext("PanelLength", "")
            panel_data["PanelWidth"] = panel.findtext("PanelWidth", "")
            panel_data["PanelThickness"] = panel.findtext("PanelThickness", "")
            panel_data["PanelName"] = panel.findtext("PanelName", "")
        else:
            raise ValueError("Не найден элемент <PANEL> в XML")

        cad_operations = []
        for cad in root.findall("CAD"):
            op = {
                "TypeNo": cad.findtext("TypeNo", ""),
                "TypeName": cad.findtext("TypeName", ""),
                "HoleType": cad.findtext("HoleType", ""),
                "X1": cad.findtext("X1", ""),
                "Y1": cad.findtext("Y1", ""),
                "Z1": cad.findtext("Z1", ""),
                "Quadrant": cad.findtext("Quadrant", ""),
                "Depth": cad.findtext("Depth", ""),
                "Diameter": cad.findtext("Diameter", ""),
                "Width": cad.findtext("Width", ""),
                "BeginX": cad.findtext("BeginX", ""),
                "BeginY": cad.findtext("BeginY", ""),
                "EndX": cad.findtext("EndX", ""),
                "EndY": cad.findtext("EndY", ""),
                "Correction": cad.findtext("Correction", ""),
                "Direction": cad.findtext("Direction", ""),
                "Enable": cad.findtext("Enable", "")
            }
            cad_operations.append(op)
        return panel_data, cad_operations
    except Exception as e:
        raise Exception(f"Ошибка при загрузке XML: {e}")


def save_xml(filepath, panel_data, cad_operations):
    """
    Сохраняет данные в XML-файл в формате станка.
    """
    try:
        root = ET.Element("KDTPanelFormat")
        panel = ET.SubElement(root, "PANEL")
        ET.SubElement(panel, "CoordinateSystem").text = "3"
        ET.SubElement(panel, "PanelLength").text = str(panel_data.get("PanelLength", ""))
        ET.SubElement(panel, "PanelWidth").text = str(panel_data.get("PanelWidth", ""))
        ET.SubElement(panel, "PanelThickness").text = str(panel_data.get("PanelThickness", ""))
        ET.SubElement(panel, "PanelName").text = str(panel_data.get("PanelName", ""))
        ET.SubElement(panel, "PanelOrderName").text = ""
        ET.SubElement(panel, "PanelMaterial").text = ""
        ET.SubElement(panel, "PanelTexture").text = "0"
        ET.SubElement(panel, "PanelQuantity").text = "1"
        ET.SubElement(panel, "Inch").text = "0"

        # Параметры L, W, T
        params = ET.SubElement(panel, "Params")
        try:
            l_val = float(panel_data.get("PanelLength", 0))
            w_val = float(panel_data.get("PanelWidth", 0))
            t_val = float(panel_data.get("PanelThickness", 0))
            ET.SubElement(params, "Param", Key="L", Value=f"{l_val:.2f}", Comment="Длина детали")
            ET.SubElement(params, "Param", Key="W", Value=f"{w_val:.2f}", Comment="Ширина детали")
            ET.SubElement(params, "Param", Key="T", Value=f"{t_val:.2f}", Comment="Толщина детали")
        except (ValueError, TypeError) as e:
            pass

        # Операции
        for op in cad_operations:
            cad = ET.SubElement(root, "CAD")
            ET.SubElement(cad, "TypeNo").text = op.get("TypeNo", "0")
            type_name = op.get("TypeName", "")
            ET.SubElement(cad, "TypeName").text = type_name

            if type_name == "Line":
                # Используем напрямую BeginX, BeginY, EndX, EndY, Width
                ET.SubElement(cad, "BeginX").text = op.get("BeginX", "0")
                ET.SubElement(cad, "BeginY").text = op.get("BeginY", "0")
                ET.SubElement(cad, "EndX").text = op.get("EndX", "0")
                ET.SubElement(cad, "EndY").text = op.get("EndY", "0")
                ET.SubElement(cad, "Width").text = op.get("Width", "0") or "0"
                ET.SubElement(cad, "Depth").text = op.get("Depth", "0") or "0"
                ET.SubElement(cad, "Correction").text = op.get("Correction", "1") or "1"
                ET.SubElement(cad, "Direction").text = op.get("Direction", "6") or "6"
            else:
                ET.SubElement(cad, "HoleType").text = "0"
                ET.SubElement(cad, "X1").text = op.get("X1", "")
                ET.SubElement(cad, "Y1").text = op.get("Y1", "")
                if type_name == "Horizontal Hole":
                    ET.SubElement(cad, "Z1").text = "8"
                ET.SubElement(cad, "Depth").text = op.get("Depth", "")
                ET.SubElement(cad, "Diameter").text = op.get("Diameter", "")
                ET.SubElement(cad, "Enable").text = "1"

        tree = ET.ElementTree(root)
        tree.write(filepath, encoding="utf-8", xml_declaration=True)

    except Exception as e:
        raise Exception(f"Не удалось сохранить XML: {e}")