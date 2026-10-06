"""Left sidebar: chat list, API manager, team roster."""
from PyQt5 import QtCore, QtGui, QtWidgets

from .agent_dialog import AgentDialog
from .api_dialog import ApiDialog


class Sidebar(QtWidgets.QFrame):
    chatSelected = QtCore.pyqtSignal(str)
    chatChanged = QtCore.pyqtSignal()
    apiFocusRequested = QtCore.pyqtSignal(str)
    themeRequested = QtCore.pyqtSignal()

    def __init__(self, store, parent=None):
        super(Sidebar, self).__init__(parent)
        self.store = store
        self.setObjectName("Sidebar")
        self.setFixedWidth(268)
        self._build()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        head = QtWidgets.QWidget()
        head.setStyleSheet("background:transparent;")
        head_layout = QtWidgets.QVBoxLayout(head)
        head_layout.setContentsMargins(14, 14, 14, 8)
        head_layout.setSpacing(0)
        title = QtWidgets.QLabel("LakeAgent")
        title.setObjectName("AppTitle")
        head_layout.addWidget(title)
        sub = QtWidgets.QLabel("multi-agent desk")
        sub.setObjectName("AppSub")
        head_layout.addWidget(sub)
        root.addWidget(head)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._chats_tab(), "Chats")
        self.tabs.addTab(self._apis_tab(), "APIs")
        self.tabs.addTab(self._agents_tab(), "Team")
        root.addWidget(self.tabs, 1)

        foot = QtWidgets.QWidget()
        foot.setStyleSheet("background:transparent;")
        foot_layout = QtWidgets.QHBoxLayout(foot)
        foot_layout.setContentsMargins(12, 6, 12, 10)
        foot_layout.setSpacing(6)

        self.theme_button = QtWidgets.QPushButton("Theme")
        self.theme_button.setObjectName("Ghost")
        self.theme_button.setToolTip("Themes, fonts and background")
        self.theme_button.clicked.connect(self.themeRequested.emit)
        foot_layout.addWidget(self.theme_button)

        self.settings_button = QtWidgets.QPushButton("Settings")
        self.settings_button.setObjectName("Ghost")
        self.settings_button.clicked.connect(self._open_settings)
        foot_layout.addWidget(self.settings_button)

        self.about_button = QtWidgets.QPushButton("About")
        self.about_button.setObjectName("Ghost")
        foot_layout.addWidget(self.about_button)
        root.addWidget(foot)

    def _open_settings(self):
        parent = self.window()
        if hasattr(parent, "_open_settings"):
            parent._open_settings()

    # ---------------- chats ----------------
    def _tidy(self, widget):
        """Two line items, wrapped, no horizontal scrollbar."""
        widget.setWordWrap(True)
        widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        widget.setTextElideMode(QtCore.Qt.ElideRight)

    def _chats_tab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        row = QtWidgets.QHBoxLayout()
        self.new_chat = QtWidgets.QPushButton("+ New chat")
        self.new_chat.setObjectName("Primary")
        self.new_chat.clicked.connect(self._new_chat)
        row.addWidget(self.new_chat)
        self.delete_chat = QtWidgets.QPushButton("Delete")
        self.delete_chat.setObjectName("Danger")
        self.delete_chat.setToolTip("Delete the selected chat")
        self.delete_chat.clicked.connect(self._delete_chat)
        row.addWidget(self.delete_chat)
        layout.addLayout(row)

        self.chat_list = QtWidgets.QListWidget()
        self._tidy(self.chat_list)
        self.chat_list.itemSelectionChanged.connect(self._on_chat_selected)
        layout.addWidget(self.chat_list, 1)

        self.rename = QtWidgets.QPushButton("Rename")
        self.rename.setObjectName("Ghost")
        self.rename.clicked.connect(self._rename_chat)
        layout.addWidget(self.rename)
        return page

    def _new_chat(self):
        chat = self.store.add_chat()
        self.store.save()
        self.refresh_chats(chat.id)
        self.chatSelected.emit(chat.id)

    def _delete_chat(self):
        chat = self.store.active_chat
        answer = QtWidgets.QMessageBox.question(
            self, "Delete chat",
            "Delete '{0}' and all of its messages?".format(chat.title),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if answer != QtWidgets.QMessageBox.Yes:
            return
        if not self.store.remove_chat(chat.id):
            QtWidgets.QMessageBox.information(
                self, "Keep one chat", "At least one chat must stay.")
            return
        self.store.save()
        self.refresh_chats()
        self.chatSelected.emit(self.store.active_chat.id)

    def _rename_chat(self):
        chat = self.store.active_chat
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Rename chat", "Title:", QtWidgets.QLineEdit.Normal,
            chat.title)
        if ok and name.strip():
            chat.title = name.strip()
            self.store.save()
            self.refresh_chats()
            self.chatChanged.emit()

    def _on_chat_selected(self):
        items = self.chat_list.selectedItems()
        if items:
            self.chatSelected.emit(items[0].data(QtCore.Qt.UserRole))

    def refresh_chats(self, active_id=None):
        keep = active_id or self.store.active_chat.id
        self.chat_list.blockSignals(True)
        self.chat_list.clear()
        for chat in self.store.chats:
            count = len(chat.messages)
            label = "{0}\n{1} message{2}".format(
                chat.title, count, "" if count == 1 else "s")
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, chat.id)
            self.chat_list.addItem(item)
            if chat.id == keep:
                self.chat_list.setCurrentItem(item)
        self.chat_list.blockSignals(False)

    # ---------------- apis ----------------
    def _apis_tab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        row = QtWidgets.QHBoxLayout()
        add = QtWidgets.QPushButton("+ Add")
        add.setObjectName("Primary")
        add.clicked.connect(lambda: self._edit_api(None))
        row.addWidget(add)
        edit = QtWidgets.QPushButton("Edit")
        edit.setObjectName("Ghost")
        edit.clicked.connect(self._edit_selected_api)
        row.addWidget(edit)
        remove = QtWidgets.QPushButton("Remove")
        remove.setObjectName("Danger")
        remove.clicked.connect(self._remove_api)
        row.addWidget(remove)
        layout.addLayout(row)

        self.api_list = QtWidgets.QListWidget()
        self._tidy(self.api_list)
        self.api_list.itemDoubleClicked.connect(
            lambda _item: self._edit_selected_api())
        self.api_list.setIconSize(QtCore.QSize(16, 16))
        layout.addWidget(self.api_list, 1)

        self.api_note = QtWidgets.QLabel(
            "Chat APIs power text agents.\nImage APIs power the Image tab.")
        self.api_note.setWordWrap(True)
        self.api_note.setStyleSheet(
            "color:{0}; font-size:11px;".format("#6c7086"))
        layout.addWidget(self.api_note)
        return page

    def _edit_api(self, profile):
        dialog = ApiDialog(self.store, profile, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.store.save()
            self.refresh_apis()
            self.apiFocusRequested.emit("reload")
            self.chatChanged.emit()

    def _selected_api(self):
        items = self.api_list.selectedItems()
        return self.store.api_by_id(items[0].data(QtCore.Qt.UserRole)) \
            if items else None

    def _edit_selected_api(self):
        profile = self._selected_api()
        if profile is None:
            self._edit_api(None)
            return
        self._edit_api(profile)

    def _remove_api(self):
        profile = self._selected_api()
        if profile is None:
            return
        answer = QtWidgets.QMessageBox.question(
            self, "Remove API",
            "Remove '{0}'? Agents and chats using it will fall back to another."
            .format(profile.name),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if answer == QtWidgets.QMessageBox.Yes:
            self.store.remove_api(profile.id)
            self.store.save()
            self.refresh_apis()
            self.apiFocusRequested.emit("reload")
            self.chatChanged.emit()

    def refresh_apis(self):
        keep = self._selected_api()
        keep_id = keep.id if keep else None
        self.api_list.clear()
        for profile in self.store.apis:
            if profile.kind == "chat":
                mark, colour = "[chat]", "#89b4fa"
            else:
                mark, colour = "[image]", "#f5c2e7"
            ready = "ok" if profile.is_ready() else "no key"
            item = QtWidgets.QListWidgetItem(
                "{0}\n{1}  -  {2}".format(profile.name, mark, ready))
            item.setData(QtCore.Qt.UserRole, profile.id)
            item.setForeground(QtGui.QBrush(QtGui.QColor(colour)))
            item.setToolTip("{0}\n{1}".format(profile.base_url or "(no url)",
                                               profile.model or "(no model)"))
            self.api_list.addItem(item)
            if profile.id == keep_id:
                self.api_list.setCurrentItem(item)

    # ---------------- team ----------------
    def _agents_tab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        row = QtWidgets.QHBoxLayout()
        add = QtWidgets.QPushButton("+ Agent")
        add.setObjectName("Primary")
        add.clicked.connect(lambda: self._edit_agent(None))
        row.addWidget(add)
        edit = QtWidgets.QPushButton("Edit")
        edit.setObjectName("Ghost")
        edit.clicked.connect(self._edit_selected_agent)
        row.addWidget(edit)
        remove = QtWidgets.QPushButton("Remove")
        remove.setObjectName("Danger")
        remove.clicked.connect(self._remove_agent)
        row.addWidget(remove)
        layout.addLayout(row)

        self.agent_list = QtWidgets.QListWidget()
        self._tidy(self.agent_list)
        self.agent_list.itemDoubleClicked.connect(
            lambda _item: self._edit_selected_agent())
        self.agent_list.itemChanged.connect(lambda _item: self._toggle_agent())
        layout.addWidget(self.agent_list, 1)

        self.team_summary = QtWidgets.QLabel()
        self.team_summary.setWordWrap(True)
        self.team_summary.setStyleSheet(
            "color:{0}; font-size:11px;".format("#6c7086"))
        layout.addWidget(self.team_summary)

        reset = QtWidgets.QPushButton("Reset to default team")
        reset.setObjectName("Ghost")
        reset.clicked.connect(self._reset_agents)
        layout.addWidget(reset)
        return page

    def _edit_agent(self, agent):
        dialog = AgentDialog(self.store, agent, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.store.save()
            self.refresh_agents()
            self.chatChanged.emit()

    def _selected_agent(self):
        items = self.agent_list.selectedItems()
        if not items:
            return None
        return self.store.agent_by_id(items[0].data(QtCore.Qt.UserRole))

    def _edit_selected_agent(self):
        agent = self._selected_agent()
        if agent is None:
            self._edit_agent(None)
            return
        self._edit_agent(agent)

    def _remove_agent(self):
        agent = self._selected_agent()
        if agent is None:
            return
        self.store.agents = [a for a in self.store.agents if a.id != agent.id]
        if not self.store.agents:
            self.store.reset_agents()
        self.store.save()
        self.refresh_agents()
        self.chatChanged.emit()

    def _toggle_agent(self):
        for row in range(self.agent_list.count()):
            item = self.agent_list.item(row)
            agent = self.store.agent_by_id(item.data(QtCore.Qt.UserRole))
            if agent is None:
                continue
            flag = item.checkState(0) == QtCore.Qt.Checked
            if agent.enabled != flag:
                agent.enabled = flag
                self.store.save()
        self.refresh_team_summary()

    def _reset_agents(self):
        answer = QtWidgets.QMessageBox.question(
            self, "Reset team",
            "Replace the current team with Planner, Coder and Reviewer?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if answer == QtWidgets.QMessageBox.Yes:
            self.store.reset_agents()
            self.store.save()
            self.refresh_agents()
            self.chatChanged.emit()

    def refresh_agents(self):
        keep = self._selected_agent()
        keep_id = keep.id if keep else None
        self.agent_list.blockSignals(True)
        self.agent_list.clear()
        for agent in self.store.agents:
            flags = QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled
            item = QtWidgets.QListWidgetItem(agent.name)
            item.setFlags(flags)
            item.setCheckState(QtCore.Qt.Checked if agent.enabled
                              else QtCore.Qt.Unchecked)
            item.setData(QtCore.Qt.UserRole, agent.id)
            item.setForeground(QtGui.QBrush(QtGui.QColor(agent.color)))
            marks = []
            if agent.is_leader:
                marks.append("leader")
            if agent.api_id:
                profile = self.store.api_by_id(agent.api_id)
                marks.append(profile.name if profile else "missing api")
            if agent.role:
                marks.append(agent.role)
            item.setToolTip(" | ".join(marks) or agent.system[:160])
            self.agent_list.addItem(item)
            if agent.id == keep_id:
                self.agent_list.setCurrentItem(item)
        self.agent_list.blockSignals(False)
        self.refresh_team_summary()

    def refresh_team_summary(self):
        enabled = self.store.enabled_agents()
        leader = self.store.leader()
        if not enabled:
            text = "No agents enabled. Tick at least one."
        else:
            text = "{0} agent(s) enabled. Leader: {1}".format(
                len(enabled), leader.name if leader else "-")
        self.team_summary.setText(text)