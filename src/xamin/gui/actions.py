"""
GUI actions
"""

from types import SimpleNamespace

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QAction
from thatway import Config

__all__ = ("Actions",)


class Actions(SimpleNamespace):
    """The GUI actions

    Parameters
    ----------
    shortcuts
        The namespace for shortcuts associated with actions
    icons
        The namespace to use for icons (QIcon instances)
    parent
        The main window widget that controls the actions
    """

    def __init__(
        self, shortcuts: Config, icons: SimpleNamespace, parent: QWidget | None = None
    ):
        super().__init__()

        # Exit application action
        self.exit = QAction(icons.actions.application_exit, "Exit", parent=parent)
        self.exit.setShortcut(shortcuts.exit)
        self.exit.setStatusTip("Exit")
        self.exit.triggered.connect(parent.close)

        # Open application action
        self.open = QAction(icons.actions.document_open, "Open", parent=parent)
        self.open.setShortcut(shortcuts.open)
        self.open.setStatusTip("Open")
