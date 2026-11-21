from pathlib import Path
from fnmatch import fnmatch
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QFileDialog, QMessageBox, QScrollArea, QWidget)
from toolboxcli.data.catalog import find_tool
from toolboxcli.core.runners import RUNNERS, Step, Progress, Log, Done
from toolboxcli.core.platform import OUTPUT_ROOT, unique_path
from .common import label, button, run_job, reveal, error, configure_dialog


class ToolForm(QDialog):
    def __init__(self, parent, tool, selected=None):
        super().__init__(parent)
        self.tool = find_tool(tool.key)
        self.setWindowTitle(tool.label)
        configure_dialog(self, 780, 560, (560, 360))
        self.paths = {}
        self.fields = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)
        layout.addWidget(label(tool.label, "title"))
        layout.addWidget(label(tool.description, "subtitle", True))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        fields_panel = QWidget()
        form = QFormLayout(fields_panel)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        scroll.setWidget(fields_panel)
        form.setSpacing(16)
        for spec in self.tool.inputs:
            if spec.kind == "choice":
                field = QComboBox()
                field.addItems(spec.choices)
                form.addRow(spec.prompt, field)
            else:
                field = QLineEdit(spec.default)
                if spec.kind == "password":
                    field.setEchoMode(QLineEdit.EchoMode.Password)
                if spec.kind in ("file", "files", "folder"):
                    field.setReadOnly(True)
                    row = QHBoxLayout()
                    row.addWidget(field)
                    row.addWidget(button("Browse…", lambda _, s=spec, f=field: self.pick(s, f)))
                    form.addRow(spec.prompt, row)
                else:
                    form.addRow(spec.prompt, field)
            self.fields[spec.name] = field
            candidates = [str(p) for p in (selected or [])]
            patterns = [pattern for _, extensions in spec.filetypes for pattern in extensions.split()]
            if spec.kind == "folder" and len(candidates) == 1 and Path(candidates[0]).is_dir():
                self.paths[spec.name] = candidates[0]
                field.setText(candidates[0])
            elif spec.kind in ("file", "files") and candidates and all(
                    Path(p).is_file() and (not patterns or any(fnmatch(Path(p).name.lower(), pattern.lower()) for pattern in patterns)) for p in candidates):
                if spec.kind == "files" or len(candidates) == 1:
                    self.paths[spec.name] = candidates if spec.kind == "files" else candidates[0]
                    field.setText("; ".join(candidates))
        layout.addWidget(scroll, 1)
        layout.addWidget(label("Results are saved as new files in your output folder.", "muted"))
        if tool.key == "rename_by_date":
            layout.addWidget(label("This tool renames images in the selected folder and its subfolders.", "muted", True))
        layout.addWidget(button("Run tool", self.start, True))

    def pick(self, spec, field):
        filters = ";;".join(f"{name} ({extensions})" for name, extensions in spec.filetypes)
        if spec.kind == "folder":
            value = QFileDialog.getExistingDirectory(self, spec.prompt)
        elif spec.kind == "files":
            value, _ = QFileDialog.getOpenFileNames(self, spec.prompt, "", filters)
        else:
            value, _ = QFileDialog.getOpenFileName(self, spec.prompt, "", filters)
        if value:
            self.paths[spec.name] = value
            field.setText("; ".join(value) if isinstance(value, list) else value)

    def start(self):
        values = {}
        try:
            for spec in self.tool.inputs:
                field = self.fields[spec.name]
                if spec.kind in ("file", "files", "folder"):
                    if not self.paths.get(spec.name):
                        raise ValueError(spec.prompt)
                    values[spec.name] = self.paths[spec.name]
                else:
                    values[spec.name] = field.currentText() if spec.kind == "choice" else field.text()
                if spec.name in ("target_kb", "dpi"):
                    n = int(values[spec.name])
                    if n <= 0 or (spec.name == "dpi" and n > 600):
                        raise ValueError("Use a positive size and a DPI between 1 and 600.")
            if self.tool.key == "rename_by_date" and QMessageBox.question(
                self, "Rename original files?", "Rename images in this folder and all its subfolders?"
            ) != QMessageBox.StandardButton.Yes:
                return
        except ValueError as exc:
            error(self, exc)
            return
        output = self.parent().output_root

        def work(progress, message):
            token = OUTPUT_ROOT.set(Path(output))
            result = None
            try:
                if self.tool.key == "resize_pdf":
                    from .operations import compress_pdf
                    folder = Path(output) / "Compressed PDF"
                    folder.mkdir(parents=True, exist_ok=True)
                    destination = unique_path(folder / Path(values["file"]).name)
                    path, before, after, reached = compress_pdf(values["file"], destination, values["target_kb"], progress)
                    message(f"{before / 1024:,.1f} KB → {after / 1024:,.1f} KB")
                    message("Target reached." if reached else "Saved the smallest result. This document could not reach the requested target.")
                    return folder
                for event in RUNNERS[self.tool.key](**values):
                    if isinstance(event, Progress):
                        progress(event.done, event.total)
                    elif isinstance(event, (Step, Log)):
                        message(event.text)
                    elif isinstance(event, Done):
                        message(event.summary)
                        result = event.folder
            finally:
                OUTPUT_ROOT.reset(token)
            return result
        run_job(self, self.windowTitle(), work,
                lambda path: reveal(path) if path else None)
