"""Dialog to add / edit team members (agents)."""
from PyQt5 import QtCore, QtWidgets

from ..models import Agent

COLORS = ["#89b4fa", "#a6e3a1", "#f9e2af", "#f38ba8", "#f5c2e7", "#cba6f7",
          "#94e2d5", "#fab387"]

ROLE_PRESETS = {
    "planner": "You are the planner. Break the task into clear, ordered steps. "
               "Be concrete and brief.",
    "coder": "You are the coder. Write correct, runnable Python. Explain only "
             "briefly after the code.",
    "reviewer": "You are the reviewer. Find bugs, edge cases and unclear steps. "
                "Be specific and concise.",
    "writer": "You are the writer. Turn rough notes into clear, well organised "
              "prose.",
    "researcher": "You are the researcher. Gather facts, list options and state "
                  "the trade offs.",
    "artist": "You are the visual artist. Describe images precisely: subject, "
              "composition, colour, light.",
    "leader": "You lead a team of agents. Read their answers and produce one "
              "clear final answer.",
}


class AgentDialog(QtWidgets.QDialog):
    def __init__(self, store, agent=None, parent=None):
        super(AgentDialog, self).__init__(parent)
        self.store = store
        self.agent = agent
        self.setWindowTitle("Edit Agent" if agent else "Add Agent")
        self.setMinimumWidth(540)
        self._build()
        self._load()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        self.name = QtWidgets.QLineEdit()
        self.name.setPlaceholderText("Coder, Reviewer, Artist ...")

        self.role = QtWidgets.QComboBox()
        self.role.setEditable(True)
        self.role.addItems(sorted(ROLE_PRESETS))
        self.role.currentTextChanged.connect(self._on_role)

        self.api = QtWidgets.QComboBox()
        self.api.currentIndexChanged.connect(self._update_hint)

        self.enabled = QtWidgets.QCheckBox("Take part in team runs")
        self.enabled.setChecked(True)

        self.leader = QtWidgets.QCheckBox("Leader (writes the final answer)")
        self.leader.toggled.connect(self._on_leader)

        self.color_btn = QtWidgets.QPushButton()
        self.color_btn.setFixedSize(64, 26)
        self.color_btn.clicked.connect(self._pick_color)
        self._color = COLORS[0]

        self.system = QtWidgets.QPlainTextEdit()
        self.system.setPlaceholderText(
            "Role prompt. This is what makes the agent different.")
        self.system.setMinimumHeight(130)

        grid.addWidget(QtWidgets.QLabel("Name"), 0, 0)
        grid.addWidget(self.name, 0, 1)
        grid.addWidget(QtWidgets.QLabel("Role"), 1, 0)
        grid.addWidget(self.role, 1, 1)
        grid.addWidget(QtWidgets.QLabel("Chat API"), 2, 0)
        grid.addWidget(self.api, 2, 1)
        grid.addWidget(QtWidgets.QLabel("Colour"), 3, 0)
        grid.addWidget(self.color_btn, 3, 1)
        grid.addWidget(self.enabled, 4, 1)
        grid.addWidget(self.leader, 5, 1)
        grid.addWidget(QtWidgets.QLabel("System prompt"), 6, 0,
                       QtCore.Qt.AlignTop)
        grid.addWidget(self.system, 6, 1)
        grid.setColumnStretch(1, 1)
        root.addLayout(grid)

        self.hint = QtWidgets.QLabel()
        self.hint.setStyleSheet("color:#6c7086; font-size:11px;")
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.button(QtWidgets.QDialogButtonBox.Save).setText("Save")
        buttons.button(QtWidgets.QDialogButtonBox.Save).setObjectName("Primary")
        buttons.button(QtWidgets.QDialogButtonBox.Cancel).setText("Cancel")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _paint_swatch(self):
        self.color_btn.setStyleSheet(
            "background:{0}; color:#11111b; border-radius:6px;"
            "border:1px solid #45475a; font-weight:600;".format(self._color))
        self.color_btn.setText(self._color)

    def _pick_color(self):
        from PyQt5 import QtGui
        chosen = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(self._color), self, "Agent colour")
        if chosen.isValid():
            self._color = chosen.name()
            self._paint_swatch()

    def _load(self):
        self.api.addItem("(use the chat's API)", "")
        for profile in self.store.chat_apis():
            self.api.addItem(profile.label(), profile.id)

        agent = self.agent or Agent()
        self.name.setText(agent.name)
        self.role.setEditText(agent.role)
        self.system.setPlainText(agent.system or ROLE_PRESETS.get(agent.role, ""))
        self.enabled.setChecked(bool(agent.enabled))
        self.leader.setChecked(bool(agent.is_leader))
        self._color = agent.color or COLORS[0]
        self._paint_swatch()

        api_index = self.api.findData(agent.api_id)
        self.api.setCurrentIndex(api_index if api_index >= 0 else 0)
        self._update_hint()

    def _on_role(self, role):
        if role in ROLE_PRESETS:
            self.system.setPlainText(ROLE_PRESETS[role])

    def _on_leader(self, on):
        if on:
            self.enabled.setChecked(True)

    def _update_hint(self):
        api_id = self.api.currentData()
        if not api_id:
            self.hint.setText("Uses whichever chat API the current chat has.")
        else:
            profile = self.store.api_by_id(api_id)
            if profile is not None:
                self.hint.setText(
                    "Uses '{0}' -> {1}".format(profile.name,
                                               profile.model or "no model"))

    def _save(self):
        agent = self.agent or Agent()
        agent.name = self.name.text().strip() or "Agent"
        agent.role = self.role.currentText().strip() or "assistant"
        agent.system = self.system.toPlainText().strip()
        agent.api_id = self.api.currentData() or ""
        agent.enabled = self.enabled.isChecked()
        agent.is_leader = self.leader.isChecked()
        agent.color = self._color
        if self.agent is None:
            self.store.agents.append(agent)
        self.result_agent = agent
        self.accept()