"""A Wayland window that prints what is done to it, one JSON line an event. Run by test_gnome_shell.py."""

import json
import sys

from PySide6.QtWidgets import QApplication, QPlainTextEdit, QVBoxLayout, QWidget


def say(**what):
    print(json.dumps(what), flush=True)


class Pad(QWidget):
    def __init__(self, title: str, editable: bool):
        super().__init__()
        self.setWindowTitle(title)
        if editable:
            self.edit = QPlainTextEdit()
            self.edit.textChanged.connect(lambda: say(event="text", text=self.edit.toPlainText()))
            QVBoxLayout(self).addWidget(self.edit)

    def mousePressEvent(self, event):
        say(event="press", x=event.position().x(), y=event.position().y())

    def wheelEvent(self, event):
        say(event="wheel", angle=event.angleDelta().y())

    def keyPressEvent(self, event):
        say(event="key", key=event.key(), modifiers=event.modifiers().value)


app = QApplication(sys.argv)
pad = Pad(sys.argv[1], editable=len(sys.argv) > 2)
pad.resize(400, 300)
pad.show()
sys.exit(app.exec())
