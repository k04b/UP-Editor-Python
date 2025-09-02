import xml.etree.ElementTree as ET


def load_xml(filepath):
    tree = ET.parse(filepath)
    root = tree.getroot()

    panel_data = {}
    panel = root.find("PANEL")
    if panel is not None:
        panel_data["PanelLength"] = panel.findtext("PanelLength", "")
        panel_data["PanelWidth"] = panel.findtext("PanelWidth", "")
        panel_data["PanelThickness"] = panel.findtext("PanelThickness", "")
        panel_data["PanelName"] = panel.findtext("PanelName", "")

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


def save_xml(filepath, panel_data, cad_operations):
    root = ET.Element("KDTPanelFormat")

    # Панель
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

    # Params
    params = ET.SubElement(panel, "Params")
    l_val = panel_data.get("PanelLength", "0")
    w_val = panel_data.get("PanelWidth", "0")
    t_val = panel_data.get("PanelThickness", "0")
    ET.SubElement(params, "Param", Key="L", Value=f"{float(l_val):.2f}", Comment="Длина детали")
    ET.SubElement(params, "Param", Key="W", Value=f"{float(w_val):.2f}", Comment="Ширина детали")
    ET.SubElement(params, "Param", Key="T", Value=f"{float(t_val):.2f}", Comment="Толщина детали")

    # CAD (вне PANEL!)
    for op in cad_operations:
        cad = ET.SubElement(root, "CAD")
        ET.SubElement(cad, "TypeNo").text = op.get("TypeNo", "0")
        ET.SubElement(cad, "TypeName").text = op["TypeName"]
        if op["TypeName"] == "Line":
            ET.SubElement(cad, "BeginX").text = op.get("X1", "").split(";")[0]
            ET.SubElement(cad, "BeginY").text = op.get("Y1", "").split(";")[0]
            ET.SubElement(cad, "EndX").text = op.get("X1", "").split(";")[1]
            ET.SubElement(cad, "EndY").text = op.get("Y1", "").split(";")[1]
            ET.SubElement(cad, "Width").text = op.get("Diameter", "0")
            ET.SubElement(cad, "Depth").text = op.get("Depth", "0")
            ET.SubElement(cad, "Correction").text = "1"
            ET.SubElement(cad, "Direction").text = "6"
        else:
            ET.SubElement(cad, "HoleType").text = "0"
            ET.SubElement(cad, "X1").text = op.get("X1", "")
            ET.SubElement(cad, "Y1").text = op.get("Y1", "")
            if op["TypeName"] == "Horizontal Hole":
                ET.SubElement(cad, "Z1").text = "8"
                # Здесь можно добавить Quadrant, если нужно
            ET.SubElement(cad, "Depth").text = op.get("Depth", "")
            ET.SubElement(cad, "Diameter").text = op.get("Diameter", "")
            ET.SubElement(cad, "Enable").text = "1"

    # Сохраняем
    tree = ET.ElementTree(root)
    with open(filepath, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)
