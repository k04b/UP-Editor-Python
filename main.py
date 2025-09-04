import sys
from PyQt5.QtWidgets import QApplication
from editor_window import EditorWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EditorWindow()
    window.show()
    sys.exit(app.exec())