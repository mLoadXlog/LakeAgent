#!/usr/bin/env python3
#Version 1.2
#LakeAgent - multi-agent desktop desk
#Python + PyQt5
#Code by MCDS
#Build 2026/10/02
import os
import sys

if not getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5 import QtCore, QtWidgets  # noqa: E402

from lakeagent import __version__  # noqa: E402
from lakeagent.config import (PROBLEMS, Store,  # noqa: E402
                             data_dir_summary, ensure_dirs)
from lakeagent.ui import theme  # noqa: E402
from lakeagent.ui.main_window import MainWindow  # noqa: E402
from lakeagent.ui.themes import ThemeManager  # noqa: E402


def report_problems(window):
    """Tell the user where things went wrong instead of failing quietly."""
    if not PROBLEMS:
        return
    text = "\n".join("- " + item for item in PROBLEMS[-6:])
    QtWidgets.QMessageBox.warning(
        window, "LakeAgent - storage",
        "Some folders could not be used:\n\n{0}\n\n"
        "Your chats are stored here:\n{1}\n\n"
        "Set LAKEAGENT_HOME to choose a different folder."
        .format(text, data_dir_summary()))


def main():
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("LakeAgent")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")

    ensure_dirs()
    store = Store()
    themes = ThemeManager(store)
    theme.use(themes.current())
    app.setStyleSheet(theme.stylesheet(themes.font_size(),
                                       themes.font_family()))

    window = MainWindow(store)
    window.show()
    report_problems(window)

    # first run: theme menu, font, first API
    if not store.settings.get("setup_done", False):
        window.open_setup_wizard()
        if not store.chat_apis():
            window._warn_no_apis()
        report_problems(window)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()