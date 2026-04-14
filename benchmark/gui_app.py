import os
import sys
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .runner import BenchmarkRunner


def extract_answer(output_text: str) -> str:
    """
    Best-effort extraction for a clean "answer" view.
    Falls back to a clipped raw output if no answer marker is found.
    """
    if not output_text:
        return ""

    lines = output_text.splitlines()

    def _collect_from(start_idx: int, first_line_after_colon: str) -> str:
        collected: List[str] = []
        if first_line_after_colon.strip():
            collected.append(first_line_after_colon.rstrip())
        for j in range(start_idx + 1, len(lines)):
            ln = lines[j]
            if ln.startswith("I rkllm:"):
                break
            if ln.startswith("User:") and "Answer:" not in ln:
                break
            if ln.startswith("Assistant:") or ln.startswith("assistant:"):
                break
            collected.append(ln.rstrip())
        return "\n".join(collected).strip()

    # Prefer "Answer:" (common in current RKLLM demo output)
    for i in range(len(lines) - 1, -1, -1):
        ln = lines[i]
        if "Answer:" in ln:
            pos = ln.rfind("Answer:")
            after = ln[pos + len("Answer:") :].lstrip()
            ans = _collect_from(i, after)
            if ans:
                return ans
            break

    # Fallback: look for "Assistant:" blocks
    for i in range(len(lines) - 1, -1, -1):
        ln = lines[i]
        if ln.startswith("Assistant:") or ln.startswith("assistant:"):
            pos = ln.find(":")
            after = ln[pos + 1 :].lstrip() if pos != -1 else ""
            ans = _collect_from(i, after)
            if ans:
                return ans
            break

    # Last resort: show a clipped raw output
    raw = output_text.strip()
    if len(raw) > 4000:
        return raw[:4000] + "\n... (clipped)"
    return raw


@dataclass
class TaskRecord:
    model_name: str
    task_id: Any
    prompt: str
    image_abs_path: Optional[str]
    success: bool
    duration_s: float
    raw_output: str
    extracted_answer: str


class QtEventSink(QObject):
    log = pyqtSignal(str)
    model_start = pyqtSignal(str, str, int, str)  # model_name, model_type, total_tasks, log_file
    task_start = pyqtSignal(str, object)  # model_name, task_dict
    task_end = pyqtSignal(str, object, bool, str, float, object, object)  # model, task, success, out, dur, mem, parsed
    model_end = pyqtSignal(str, str)  # model_name, status
    run_end = pyqtSignal(str)  # report_path
    progress_total = pyqtSignal(int)

    def on_log(self, msg: str):
        self.log.emit(msg)

    def on_model_start(self, model_name: str, model_type: str, total_tasks_for_model: int, log_file_path: str):
        self.model_start.emit(model_name, model_type, int(total_tasks_for_model), log_file_path)

    def on_task_start(self, model_name: str, task_dict: Dict[str, Any]):
        self.task_start.emit(model_name, task_dict)

    def on_task_end(
        self,
        model_name: str,
        task_dict: Dict[str, Any],
        success: bool,
        output_text: str,
        duration_s: float,
        mem_metrics_dict: Dict[str, Any],
        parsed_metrics_dict: Dict[str, Any],
    ):
        self.task_end.emit(model_name, task_dict, bool(success), output_text, float(duration_s), mem_metrics_dict, parsed_metrics_dict)

    def on_model_end(self, model_name: str, status: str):
        self.model_end.emit(model_name, status)

    def on_run_end(self, report_path: str):
        self.run_end.emit(report_path or "")


class BenchmarkWorker(QObject):
    finished = pyqtSignal()

    def __init__(self, workspace_root: str, config_path: str, target_models: List[str]):
        super().__init__()
        self.workspace_root = workspace_root
        self.config_path = config_path
        self.target_models = target_models
        self.cancel_event = threading.Event()
        self.sink = QtEventSink()

    def request_cancel(self):
        self.cancel_event.set()
        self.sink.on_log("[GUI] Stop requested. Will stop after current task finishes.")

    def run(self):
        try:
            runner = BenchmarkRunner(self.workspace_root, self.config_path)

            # Pre-compute total tasks for progress bar.
            total = 0
            models_to_run = self.target_models if self.target_models else list(runner.models_config.keys())
            for name in models_to_run:
                cfg = runner.models_config.get(name)
                if not cfg:
                    continue
                if cfg.type == "text":
                    total += len(runner.dataset.get_text_prompts())
                elif cfg.type == "vlm":
                    total += len(runner.dataset.get_vlm_tasks())
            self.sink.progress_total.emit(int(total))

            runner.run_all(models_to_run, event_sink=self.sink, cancel_event=self.cancel_event)
        except Exception as e:
            self.sink.on_log(f"[GUI] Worker exception: {e}")
        finally:
            self.finished.emit()


class BenchmarkGui(QMainWindow):
    def __init__(self, workspace_root: str, config_path: str, preselected_models: Optional[List[str]] = None):
        super().__init__()
        self.workspace_root = workspace_root
        self.config_path = config_path
        self.preselected_models = preselected_models or ["all"]

        self.records: List[TaskRecord] = []
        self.total_tasks_expected = 0
        self.tasks_completed = 0

        self._current_pixmap: Optional[QPixmap] = None
        self._current_image_path: Optional[str] = None
        self._current_task_key: Optional[str] = None  # e.g. "model#id"

        self._worker_thread: Optional[QThread] = None
        self._worker: Optional[BenchmarkWorker] = None

        self.setWindowTitle("RK3588 Benchmark GUI")
        self.resize(1200, 800)

        self._build_ui()
        self._load_models()

    def _build_ui(self):
        root = QWidget()
        root_layout = QVBoxLayout()
        root.setLayout(root_layout)
        self.setCentralWidget(root)

        # Top controls
        controls = QHBoxLayout()
        self.btn_select_all = QPushButton("Select All Models")
        self.btn_select_none = QPushButton("Clear Selection")
        self.btn_start = QPushButton("Start")
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setEnabled(False)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

        controls.addWidget(self.btn_select_all)
        controls.addWidget(self.btn_select_none)
        controls.addWidget(self.btn_start)
        controls.addWidget(self.btn_stop)
        controls.addWidget(self.progress, stretch=1)
        root_layout.addLayout(controls)

        # Main splitters: (top: history/details) + (bottom: log)
        v_split = QSplitter(Qt.Vertical)
        root_layout.addWidget(v_split, stretch=1)

        h_split = QSplitter(Qt.Horizontal)
        v_split.addWidget(h_split)

        # Left panel: model selection + history list
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)

        self.model_list = QListWidget()
        # ExtendedSelection:
        # - single click selects one (clears others)
        # - Ctrl/Shift enables multi selection
        # This avoids the "click one -> looks like all selected" confusion.
        self.model_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.model_list.setMinimumWidth(320)
        left_layout.addWidget(QLabel("Models"))
        left_layout.addWidget(self.model_list, stretch=1)

        self.history_list = QListWidget()
        self.history_list.setMinimumWidth(320)
        left_layout.addWidget(QLabel("History"))
        left_layout.addWidget(self.history_list, stretch=2)

        h_split.addWidget(left_panel)

        # Right panel: image + prompt + answer
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)

        self.image_label = QLabel("No image")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(260)
        self.image_label.setStyleSheet("QLabel { border: 1px solid #666; background: #111; color: #ddd; }")
        right_layout.addWidget(self.image_label, stretch=2)

        right_layout.addWidget(QLabel("Prompt"))
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setReadOnly(True)
        self.prompt_edit.setMaximumBlockCount(5000)
        right_layout.addWidget(self.prompt_edit, stretch=1)

        right_layout.addWidget(QLabel("Model Output (Extracted Answer)"))
        self.answer_edit = QPlainTextEdit()
        self.answer_edit.setReadOnly(True)
        self.answer_edit.setMaximumBlockCount(20000)
        right_layout.addWidget(self.answer_edit, stretch=2)

        h_split.addWidget(right_panel)
        h_split.setStretchFactor(0, 0)
        h_split.setStretchFactor(1, 1)

        # Log window
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumBlockCount(50000)
        v_split.addWidget(self.log_edit)
        v_split.setStretchFactor(0, 3)
        v_split.setStretchFactor(1, 1)

        # Signals
        self.btn_select_all.clicked.connect(self._select_all_models)
        self.btn_select_none.clicked.connect(self._select_none_models)
        self.btn_start.clicked.connect(self._start)
        self.btn_stop.clicked.connect(self._stop)
        self.history_list.currentRowChanged.connect(self._on_history_selected)

    def _is_running(self) -> bool:
        return self._worker_thread is not None and self._worker_thread.isRunning()

    def _load_models(self):
        # Load configs just for listing available models.
        runner = BenchmarkRunner(self.workspace_root, self.config_path)
        names = sorted(list(runner.models_config.keys()))
        self.model_list.clear()
        for n in names:
            self.model_list.addItem(n)

        if "all" in self.preselected_models:
            self._select_all_models()
        else:
            wanted = set(self.preselected_models)
            for i in range(self.model_list.count()):
                it = self.model_list.item(i)
                if it and it.text() in wanted:
                    it.setSelected(True)

    def _select_all_models(self):
        for i in range(self.model_list.count()):
            it = self.model_list.item(i)
            if it:
                it.setSelected(True)

    def _select_none_models(self):
        self.model_list.clearSelection()

    def _append_log(self, msg: str):
        self.log_edit.appendPlainText(msg.rstrip())
        sb = self.log_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_image(self, abs_path: Optional[str]):
        self._current_image_path = abs_path
        self._current_pixmap = None
        if not abs_path:
            self.image_label.setText("No image")
            self.image_label.setPixmap(QPixmap())
            return
        if not os.path.isfile(abs_path):
            self.image_label.setText(f"Image not found:\n{abs_path}")
            self.image_label.setPixmap(QPixmap())
            return

        pix = QPixmap(abs_path)
        if pix.isNull():
            self.image_label.setText(f"Failed to load image:\n{abs_path}")
            self.image_label.setPixmap(QPixmap())
            return

        self._current_pixmap = pix
        self._rescale_pixmap()

    def _rescale_pixmap(self):
        if not self._current_pixmap:
            return
        scaled = self._current_pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled)
        self.image_label.setText("")

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._rescale_pixmap()

    def _selected_models(self) -> List[str]:
        items = self.model_list.selectedItems()
        return [it.text() for it in items if it and it.text()]

    def _reset_run_state(self):
        self.records.clear()
        self.history_list.clear()
        self.prompt_edit.setPlainText("")
        self.answer_edit.setPlainText("")
        self._set_image(None)
        self.tasks_completed = 0
        self.total_tasks_expected = 0
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

    def _start(self):
        models = self._selected_models()
        if not models:
            QMessageBox.warning(self, "No models selected", "Please select at least one model to run.")
            return
        if self._is_running():
            QMessageBox.information(self, "Already running", "Benchmark is already running.")
            return

        self._reset_run_state()
        self.log_edit.clear()
        self._append_log(f"[GUI] Starting benchmark for {len(models)} model(s)...")

        # Create worker/thread
        self._worker = BenchmarkWorker(self.workspace_root, self.config_path, models)
        # Parent the thread to this window so it won't be garbage-collected early.
        self._worker_thread = QThread(self)
        self._worker.moveToThread(self._worker_thread)

        # Wire sink signals to UI slots
        sink = self._worker.sink
        sink.log.connect(self._append_log)
        sink.progress_total.connect(self._on_progress_total)
        sink.model_start.connect(self._on_model_start)
        sink.task_start.connect(self._on_task_start)
        sink.task_end.connect(self._on_task_end)
        sink.model_end.connect(self._on_model_end)
        sink.run_end.connect(self._on_run_end)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._on_thread_finished)

        # Toggle UI
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.model_list.setEnabled(False)
        self.btn_select_all.setEnabled(False)
        self.btn_select_none.setEnabled(False)

        self._worker_thread.start()

    def _stop(self):
        if self._worker is not None:
            self._worker.request_cancel()
        self.btn_stop.setEnabled(False)

    def _on_progress_total(self, total: int):
        self.total_tasks_expected = max(0, int(total))
        self.progress.setRange(0, max(1, self.total_tasks_expected))
        self.progress.setValue(0)
        self._append_log(f"[GUI] Total tasks expected: {self.total_tasks_expected}")

    def _on_model_start(self, model_name: str, model_type: str, total_tasks: int, log_file_path: str):
        self._append_log(f"[GUI] Model start: {model_name} ({model_type}), tasks={total_tasks}")
        self._append_log(f"[GUI] Raw log file: {log_file_path}")

    def _on_task_start(self, model_name: str, task_dict: Dict[str, Any]):
        prompt = str(task_dict.get("prompt", ""))
        tid = task_dict.get("id")
        self._current_task_key = f"{model_name}#{tid}"
        self.prompt_edit.setPlainText(prompt)
        self.answer_edit.setPlainText("Running...")

        img_rel = task_dict.get("image")
        if img_rel:
            abs_path = os.path.join(self.workspace_root, str(img_rel))
            self._set_image(abs_path)
        else:
            self._set_image(None)

        self._append_log(f"[GUI] Task start: [{model_name}] #{tid}")

    def _on_task_end(
        self,
        model_name: str,
        task_dict: Dict[str, Any],
        success: bool,
        output_text: str,
        duration_s: float,
        mem_metrics: Dict[str, Any],
        parsed_metrics: Dict[str, Any],
    ):
        tid = task_dict.get("id")
        task_key = f"{model_name}#{tid}"
        prompt = str(task_dict.get("prompt", ""))
        img_rel = task_dict.get("image")
        image_abs = os.path.join(self.workspace_root, str(img_rel)) if img_rel else None

        answer = extract_answer(output_text or "")
        rec = TaskRecord(
            model_name=model_name,
            task_id=tid,
            prompt=prompt,
            image_abs_path=image_abs,
            success=bool(success),
            duration_s=float(duration_s),
            raw_output=output_text or "",
            extracted_answer=answer,
        )
        self.records.append(rec)

        # Update detail panel only if this is still the "current" task.
        # (Protects against any future UI race / user selection changes.)
        if self._current_task_key == task_key:
            self.prompt_edit.setPlainText(rec.prompt)
            self.answer_edit.setPlainText(rec.extracted_answer)
            self._set_image(rec.image_abs_path)

        # Add to history list
        img_name = os.path.basename(image_abs) if image_abs else "text"
        status = "Success" if rec.success else "Error"
        label = f"[{model_name}] #{tid} {img_name} {rec.duration_s:.2f}s {status}"
        item = QListWidgetItem(label)
        # Store record index explicitly to avoid any row/index mismatch.
        item.setData(Qt.UserRole, len(self.records) - 1)
        self.history_list.addItem(item)
        self.history_list.setCurrentRow(self.history_list.count() - 1)

        # Progress
        self.tasks_completed += 1
        self.progress.setValue(self.tasks_completed)

        # Log summary line
        tps = ""
        try:
            if parsed_metrics and parsed_metrics.get("generate_tps", 0.0):
                tps = f", gen_tps={float(parsed_metrics.get('generate_tps')):.2f}"
        except Exception:
            tps = ""
        self._append_log(f"[GUI] Task end: [{model_name}] #{tid} {status}, {duration_s:.2f}s{tps}")

    def _on_model_end(self, model_name: str, status: str):
        self._append_log(f"[GUI] Model end: {model_name}, status={status}")

    def _on_run_end(self, report_path: str):
        if report_path:
            self._append_log(f"[GUI] Report updated: {report_path}")
        else:
            self._append_log("[GUI] Run finished.")

    def _on_history_selected(self, row: int):
        if row < 0:
            return
        item = self.history_list.item(row)
        if item is None:
            return
        rec_idx = item.data(Qt.UserRole)
        if not isinstance(rec_idx, int) or rec_idx < 0 or rec_idx >= len(self.records):
            return
        rec = self.records[rec_idx]
        self.prompt_edit.setPlainText(rec.prompt)
        self.answer_edit.setPlainText(rec.extracted_answer)
        self._set_image(rec.image_abs_path)

    def _on_worker_finished(self):
        self._append_log("[GUI] Worker finished.")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.model_list.setEnabled(True)
        self.btn_select_all.setEnabled(True)
        self.btn_select_none.setEnabled(True)

    def _on_thread_finished(self):
        # Only cleanup after the thread has actually stopped to avoid:
        # "QThread: Destroyed while thread is still running"
        self._append_log("[GUI] Thread finished.")
        if self._worker is not None:
            try:
                self._worker.deleteLater()
            except Exception:
                pass
        if self._worker_thread is not None:
            try:
                self._worker_thread.deleteLater()
            except Exception:
                pass
        self._worker = None
        self._worker_thread = None

    def closeEvent(self, event):  # noqa: N802
        # Prevent abort/crash if window is closed while worker thread is running.
        if self._is_running():
            QMessageBox.information(
                self,
                "Benchmark running",
                "Benchmark is still running.\n\n"
                "Please click Stop and wait for the current task to finish, then close the window.",
            )
            event.ignore()
            return
        super().closeEvent(event)


def run_gui(workspace_root: str, config_path: str, preselected_models: Optional[List[str]] = None):
    app = QApplication(sys.argv)
    win = BenchmarkGui(workspace_root, config_path, preselected_models=preselected_models)
    win.show()
    sys.exit(app.exec_())
