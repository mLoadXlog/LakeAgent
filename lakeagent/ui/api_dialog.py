"""Dialog to add / edit / delete API profiles. Users can keep as many as they
like: chat models, image models, local endpoints, anything."""
from PyQt5 import QtWidgets

from ..models import (CHAT_KIND, IMAGE_KIND, IMAGE_PROVIDERS, ApiProfile)


class ApiDialog(QtWidgets.QDialog):
    def __init__(self, store, profile=None, parent=None):
        super(ApiDialog, self).__init__(parent)
        self.store = store
        self.profile = profile
        self.setWindowTitle("Edit API" if profile else "Add API")
        self.setMinimumSize(560, 520)
        self._build()
        self._load()

    # ---------- layout ----------
    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setVerticalSpacing(8)
        form.setHorizontalSpacing(10)
        root.addLayout(form)

        self.name = QtWidgets.QLineEdit()
        self.name.setPlaceholderText("Display name, e.g. DeepSeek")
        self.kind = QtWidgets.QComboBox()
        self.kind.addItems([CHAT_KIND, IMAGE_KIND])
        self.kind.currentTextChanged.connect(self._on_kind_change)

        self.base_url = QtWidgets.QLineEdit()
        self.base_url.setPlaceholderText("https://api.example.com  or  .../v1")
        self.base_url.textChanged.connect(self._update_preview)

        self.api_key = QtWidgets.QLineEdit()
        self.api_key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.api_key.setPlaceholderText("sk-...")
        self.show_key = QtWidgets.QCheckBox("Show")
        self.show_key.toggled.connect(
            lambda on: self.api_key.setEchoMode(
                QtWidgets.QLineEdit.Normal if on
                else QtWidgets.QLineEdit.Password))

        self.model = QtWidgets.QComboBox()
        self.model.setEditable(True)
        self.model.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.model.setMinimumWidth(240)
        self.fetch = QtWidgets.QPushButton("Fetch")
        self.fetch.setFixedWidth(66)
        self.fetch.clicked.connect(self._fetch_models)

        self.provider = QtWidgets.QComboBox()
        self.provider.addItems(IMAGE_PROVIDERS)
        self.provider.currentTextChanged.connect(self._update_preview)

        self.temperature = QtWidgets.QDoubleSpinBox()
        self.temperature.setRange(0.0, 2.0)
        self.temperature.setSingleStep(0.1)
        self.temperature.setDecimals(2)

        self.max_tokens = QtWidgets.QSpinBox()
        self.max_tokens.setRange(64, 200000)
        self.max_tokens.setSingleStep(128)

        self.timeout = QtWidgets.QSpinBox()
        self.timeout.setRange(10, 900)
        self.timeout.setSingleStep(10)
        self.timeout.setSuffix(" s")

        self.size = QtWidgets.QComboBox()
        self.size.setEditable(True)
        self.size.addItems(["512x512", "768x768", "1024x1024", "1024x576",
                            "576x1024"])

        self.negative = QtWidgets.QLineEdit()
        self.negative.setPlaceholderText("Things to avoid (image APIs only)")

        self.steps = QtWidgets.QSpinBox()
        self.steps.setRange(1, 150)

        self.cfg = QtWidgets.QSpinBox()
        self.cfg.setRange(1, 30)

        self.preview = QtWidgets.QLabel()
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet("color:#89b4fa; font-size:11px;")

        rows = [
            ("Name", self.name, 0),
            ("Kind", self.kind, 1),
            ("Base URL", self.base_url, 2),
        ]
        for label, widget, row in rows:
            form.addWidget(self._cap(label), row, 0)
            form.addWidget(widget, row, 1, 1, 3)

        key_row = QtWidgets.QHBoxLayout()
        key_row.addWidget(self.api_key)
        key_row.addWidget(self.show_key)
        form.addWidget(self._cap("API Key"), 3, 0)
        form.addLayout(key_row, 3, 1, 1, 3)

        model_row = QtWidgets.QHBoxLayout()
        model_row.addWidget(self.model)
        model_row.addWidget(self.fetch)
        form.addWidget(self._cap("Model"), 4, 0)
        form.addLayout(model_row, 4, 1, 1, 3)

        # these rows swap out depending on the kind, so keep every widget
        # addressable for _on_kind_change
        self.cap_provider = self._cap("Provider")
        self.cap_negative = self._cap("Negative")
        self.chat_caps = {}
        self.image_caps = {}
        chat_side = (("Temperature", self.temperature),
                     ("Max tokens", self.max_tokens),
                     ("Timeout", self.timeout))
        image_side = (("Size", self.size), ("Steps", self.steps),
                      ("CFG", self.cfg))
        for index, (label, widget) in enumerate(chat_side):
            self.chat_caps[label] = self._cap(label)
            form.addWidget(self.chat_caps[label], 6 + index, 0)
            form.addWidget(widget, 6 + index, 1)
        for index, (label, widget) in enumerate(image_side):
            self.image_caps[label] = self._cap(label)
            form.addWidget(self.image_caps[label], 6 + index, 2)
            form.addWidget(widget, 6 + index, 3)

        form.addWidget(self.cap_provider, 5, 0)
        form.addWidget(self.provider, 5, 1, 1, 3)
        form.addWidget(self.cap_negative, 9, 0)
        form.addWidget(self.negative, 9, 1, 1, 3)
        form.addWidget(self._cap("Resolved URL"), 10, 0)
        form.addWidget(self.preview, 10, 1, 1, 3)

        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)

        self.hint = QtWidgets.QLabel(
            "Chat kind talks to /v1/chat/completions.\n"
            "Image kind talks to /v1/images/generations, or the provider "
            "shape you pick.")
        self.hint.setStyleSheet("color:#6c7086; font-size:11px;")
        self.hint.setWordWrap(True)
        self.hint_text = (
            "Chat kind talks to /v1/chat/completions.\n"
            "Image kind talks to /v1/images/generations, or the provider "
            "shape you pick.")
        self.hint_text = (
            "Chat kind talks to /v1/chat/completions.\n"
            "Image kind talks to /v1/images/generations, or the provider "
            "shape you pick.")
        self.hint.setText(self.hint_text)
        root.addWidget(self.hint)
        root.addStretch(1)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.button(QtWidgets.QDialogButtonBox.Save).setText("Save")
        buttons.button(QtWidgets.QDialogButtonBox.Save).setObjectName("Primary")
        buttons.button(QtWidgets.QDialogButtonBox.Cancel).setText("Cancel")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ---------- state ----------
    def _load(self):
        p = self.profile
        if p is None:
            p = ApiProfile()
            p.temperature = 0.7
            p.max_tokens = 2048
        self.name.setText(p.name)
        self.kind.setCurrentText(p.kind)
        self.base_url.setText(p.base_url)
        self.api_key.setText(p.api_key)
        self.model.setEditText(p.model)
        self.provider.setCurrentText(p.provider)
        self.temperature.setValue(float(p.temperature))
        self.max_tokens.setValue(int(p.max_tokens))
        self.timeout.setValue(int(p.timeout))
        self.size.setEditText(p.image_size)
        self.steps.setValue(int(p.steps))
        self.cfg.setValue(int(p.cfg_scale))
        self.negative.setText(p.negative_prompt)
        self._on_kind_change(self.kind.currentText())

    def _collect(self):
        p = self.profile or ApiProfile()
        p.name = self.name.text().strip() or "Unnamed API"
        p.kind = self.kind.currentText()
        p.base_url = self.base_url.text().strip()
        p.api_key = self.api_key.text().strip()
        p.model = self.model.currentText().strip()
        p.provider = self.provider.currentText()
        p.temperature = round(self.temperature.value(), 2)
        p.max_tokens = self.max_tokens.value()
        p.timeout = self.timeout.value()
        p.image_size = self.size.currentText().strip()
        p.steps = self.steps.value()
        p.cfg_scale = self.cfg.value()
        p.negative_prompt = self.negative.text().strip()
        return p

    def _cap(self, text):
        label = QtWidgets.QLabel(text)
        label.setStyleSheet("color:#a6adc8;")
        return label

    def _on_kind_change(self, kind):
        is_image = kind == IMAGE_KIND
        chat_widgets = [self.temperature, self.max_tokens, self.timeout]
        chat_widgets += list(self.chat_caps.values())
        for widget in chat_widgets:
            widget.setVisible(not is_image)

        image_widgets = [self.provider, self.cap_provider, self.size,
                         self.steps, self.cfg, self.negative,
                         self.cap_negative]
        image_widgets += list(self.image_caps.values())
        for widget in image_widgets:
            widget.setVisible(is_image)

        self.fetch.setVisible(not is_image)
        self.hint.setText(self.hint_text if is_image else
                          "Chat kind talks to /v1/chat/completions. "
                          "Press Fetch to list the models.")
        self._update_preview()

    def _update_preview(self):
        if self.kind.currentText() == IMAGE_KIND:
            provider = self.provider.currentText()
            if provider == "Automatic1111":
                url = (self.base_url.text().strip().rstrip("/")
                       or "http://localhost:7860") + "/sdapi/v1/txt2img"
            elif provider == "Chat Multimodal":
                url = ApiProfile(base_url=self.base_url.text()).chat_url()
            elif provider == "Stability AI":
                url = self.base_url.text().strip() or \
                    "https://api.stability.ai/v1/generation/<model>/text-to-image"
            else:
                url = ApiProfile(base_url=self.base_url.text()).image_url()
        else:
            url = ApiProfile(base_url=self.base_url.text()).chat_url()
        self.preview.setText(url or "(add a base url)")

    def _fetch_models(self):
        profile = self._collect()
        if not profile.base_url or not profile.api_key:
            QtWidgets.QMessageBox.warning(
                self, "Need key and URL",
                "Fill Base URL and API Key first.")
            return
        self.fetch.setEnabled(False)
        self.fetch.setText("...")
        QtWidgets.QApplication.processEvents()

        from ..clients.llm import LLMClient
        try:
            models = LLMClient(profile).list_models()
        except Exception as exc:  # noqa: BLE001
            self.fetch.setEnabled(True)
            self.fetch.setText("Fetch")
            QtWidgets.QMessageBox.information(
                self, "Could not list models",
                "{0}\n\nYou can still type the model name by hand."
                .format(exc))
            return

        self.fetch.setEnabled(True)
        self.fetch.setText("Fetch")
        current = self.model.currentText().strip()
        self.model.clear()
        self.model.addItems(models)
        self.model.setEditText(current if current in models
                              else (models[0] if models else current))
        QtWidgets.QMessageBox.information(
            self, "Models", "Loaded {0} models.".format(len(models)))

    def _save(self):
        profile = self._collect()
        if not profile.base_url:
            QtWidgets.QMessageBox.warning(self, "Missing URL",
                                          "Base URL is required.")
            return
        if self.profile is None:
            self.store.add_api(profile)
        self.result_profile = profile
        self.accept()