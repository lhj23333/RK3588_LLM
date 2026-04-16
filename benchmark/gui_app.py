import os
import re
import sys
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .runner import BenchmarkRunner


def _is_runtime_or_metric_line(line: str) -> bool:
    s = line.strip()
    lower = s.lower()
    if not s:
        return False
    if lower.startswith(("i rkllm:", "w rkllm:", "e rkllm:")):
        return True
    if lower.startswith(("rkllm init start", "rkllm init success")):
        return True
    if lower.startswith(("used npu cores", "model input num:", "input tensors:", "output tensors:", "model input height=")):
        return True
    if lower.startswith(("duration:", "output:", "stage", "prefill", "generate", "peak memory usage", "model init time")):
        return True
    if lower.startswith(("index=", "n_dims=", "dims=[", "size=", "fmt=", "type=")):
        return True
    if lower.startswith("--- task"):
        return True
    if lower.startswith("--------------------------------------------------"):
        return True
    return False


def _is_probable_runtime_fragment(line: str) -> bool:
    s = line.strip()
    lower = s.lower()
    if not s:
        return False
    if _is_runtime_or_metric_line(s):
        return True
    if lower.startswith(("i rk", "w rk", "e rk", "user", "assistant", "robot", "answer:", "---")):
        return True
    return False


def _is_stop_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    lower = s.lower()
    if _is_runtime_or_metric_line(s):
        return True
    if re.match(r"^(user|assistant|robot)\s*:\s*$", lower):
        return True
    if lower.startswith("user:") and "answer:" not in lower and "robot:" not in lower:
        return True
    if lower.startswith("assistant:"):
        return True
    return False


def _collect_answer_block(lines: List[str], start_idx: int, first_line_after_marker: str, partial: bool) -> str:
    collected: List[str] = []
    if first_line_after_marker.strip() and not _is_runtime_or_metric_line(first_line_after_marker):
        collected.append(first_line_after_marker.rstrip())
    for j in range(start_idx + 1, len(lines)):
        ln = lines[j]
        if _is_stop_line(ln):
            break
        collected.append(ln.rstrip())

    if partial:
        while collected and _is_probable_runtime_fragment(collected[-1]):
            collected.pop()

    return "\n".join(collected).strip()


def _extract_marked_answer(output_text: str, partial: bool) -> str:
    if not output_text:
        return ""

    lines = output_text.splitlines()

    for i in range(len(lines) - 1, -1, -1):
        ln = lines[i]
        lower = ln.lower()
        if "robot:" in lower:
            pos = lower.rfind("robot:")
            after = ln[pos + len("robot:") :].lstrip()
            ans = _collect_answer_block(lines, i, after, partial)
            if ans:
                return ans

    for i in range(len(lines) - 1, -1, -1):
        ln = lines[i]
        lower = ln.lower()
        if "answer:" in lower:
            pos = lower.rfind("answer:")
            after = ln[pos + len("answer:") :].lstrip()
            ans = _collect_answer_block(lines, i, after, partial)
            if ans:
                return ans
            break

    for i in range(len(lines) - 1, -1, -1):
        ln = lines[i]
        lower = ln.lower()
        if lower.startswith("assistant:"):
            pos = ln.find(":")
            after = ln[pos + 1 :].lstrip() if pos != -1 else ""
            ans = _collect_answer_block(lines, i, after, partial)
            if ans:
                return ans
            break

    return ""


def extract_stream_answer(output_text: str) -> str:
    return _extract_marked_answer(output_text, partial=True)


def extract_answer(output_text: str) -> str:
    answer = _extract_marked_answer(output_text, partial=False)
    if answer:
        return answer

    lines = output_text.splitlines()
    cleaned_lines: List[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            cleaned_lines.append("")
            continue
        if _is_runtime_or_metric_line(ln):
            continue
        if s.startswith("*") or s.startswith("["):
            continue
        if re.match(r"^(user|assistant|robot)\s*:\s*$", s.lower()):
            continue
        cleaned_lines.append(ln.rstrip())

    cleaned = "\n".join(cleaned_lines).strip()
    if cleaned:
        if len(cleaned) > 4000:
            return cleaned[:4000] + "\n... (clipped)"
        return cleaned

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
    model_start = pyqtSignal(str, str, int, str)
    task_start = pyqtSignal(str, object)
    task_stream = pyqtSignal(str, object, str)
    task_end = pyqtSignal(str, object, bool, str, float, object, object)
    model_end = pyqtSignal(str, str)
    run_end = pyqtSignal(str)
    progress_total = pyqtSignal(int)

    def on_log(self, msg: str):
        self.log.emit(msg)

    def on_model_start(self, model_name: str, model_type: str, total_tasks_for_model: int, log_file_path: str):
        self.model_start.emit(model_name, model_type, int(total_tasks_for_model), log_file_path)

    def on_task_start(self, model_name: str, task_dict: Dict[str, Any]):
        self.task_start.emit(model_name, task_dict)

    def on_task_stream(self, model_name: str, task_dict: Dict[str, Any], text_chunk: str):
        self.task_stream.emit(model_name, task_dict, text_chunk)

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
    MODE_TEXT = "text"
    MODE_VLM = "vlm"

    def __init__(self, workspace_root: str, config_path: str, preselected_models: Optional[List[str]] = None):
        super().__init__()
        self.workspace_root = workspace_root
        self.config_path = config_path
        self.preselected_models = preselected_models or ["all"]

        model_runner = BenchmarkRunner(self.workspace_root, self.config_path)
        self._all_models_config = model_runner.models_config
        self._model_type_by_name: Dict[str, str] = {
            model_name: str(model_cfg.type or "").strip().lower()
            for model_name, model_cfg in self._all_models_config.items()
        }

        self.current_mode = self._infer_initial_mode()

        self.records: List[TaskRecord] = []
        self.total_tasks_expected = 0
        self.tasks_completed = 0
        self._run_has_error = False
        self._stop_requested = False

        self._current_pixmap: Optional[QPixmap] = None
        self._current_image_path: Optional[str] = None
        self._current_task_key: Optional[str] = None
        self._display_task_key: Optional[str] = None
        self._history_view_locked = False
        self._stream_raw_by_task: Dict[str, str] = {}
        self._stream_answer_by_task: Dict[str, str] = {}
        self._task_prompt_by_key: Dict[str, str] = {}
        self._task_image_by_key: Dict[str, Optional[str]] = {}
        self._live_history_item: Optional[QListWidgetItem] = None

        self._worker_thread: Optional[QThread] = None
        self._worker: Optional[BenchmarkWorker] = None

        self.setWindowTitle("RK3588 Benchmark GUI")
        self.resize(1280, 820)

        self._build_ui()
        self._apply_styles()
        self._sync_mode_radio_buttons()

    def _build_ui(self):
        root = QWidget()
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)
        root.setLayout(root_layout)
        self.setCentralWidget(root)

        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack)

        self.page_mode = self._build_mode_page()
        self.page_benchmark = self._build_benchmark_page()

        self.stack.addWidget(self.page_mode)
        self.stack.addWidget(self.page_benchmark)
        self.stack.setCurrentWidget(self.page_mode)

    def _build_mode_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("ModePage")

        layout = QVBoxLayout()
        layout.setContentsMargins(56, 40, 56, 40)
        layout.setSpacing(14)
        page.setLayout(layout)

        eyebrow = QLabel("NPU BENCHMARK SUITE")
        eyebrow.setObjectName("ModeEyebrow")
        layout.addWidget(eyebrow)

        title = QLabel("RK3588 Benchmark Launcher")
        title.setObjectName("ModeTitle")
        layout.addWidget(title)

        subtitle = QLabel("Choose one model category, then enter a dedicated benchmark workspace.")
        subtitle.setObjectName("ModeSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        mode_card = QFrame()
        mode_card.setObjectName("ModeCard")
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(10)
        mode_card.setLayout(card_layout)

        self.radio_text = QRadioButton("Text LLM")
        self.radio_vlm = QRadioButton("Multimodal Model (VLM)")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.radio_text)
        self.mode_group.addButton(self.radio_vlm)

        self.text_option_card = QFrame()
        self.text_option_card.setObjectName("OptionCard")
        text_card_layout = QVBoxLayout()
        text_card_layout.setContentsMargins(12, 10, 12, 10)
        text_card_layout.setSpacing(4)
        self.text_option_card.setLayout(text_card_layout)

        text_desc = QLabel("Text mode focuses on prompt, model output, and task history. Image area is hidden.")
        text_desc.setObjectName("ModeHint")
        text_desc.setWordWrap(True)

        text_card_layout.addWidget(self.radio_text)
        text_card_layout.addWidget(text_desc)

        self.vlm_option_card = QFrame()
        self.vlm_option_card.setObjectName("OptionCard")
        vlm_card_layout = QVBoxLayout()
        vlm_card_layout.setContentsMargins(12, 10, 12, 10)
        vlm_card_layout.setSpacing(4)
        self.vlm_option_card.setLayout(vlm_card_layout)

        vlm_desc = QLabel("Multimodal mode keeps image, prompt, and output panels for VLM evaluation.")
        vlm_desc.setObjectName("ModeHint")
        vlm_desc.setWordWrap(True)

        vlm_card_layout.addWidget(self.radio_vlm)
        vlm_card_layout.addWidget(vlm_desc)

        self.mode_hint_label = QLabel("")
        self.mode_hint_label.setObjectName("ModeHint")
        self.mode_hint_label.setWordWrap(True)

        self.btn_enter_mode = QPushButton("Enter Benchmark")
        self.btn_enter_mode.setProperty("role", "primary")
        self.btn_enter_mode.clicked.connect(self._confirm_mode_selection)
        self.radio_text.toggled.connect(self._refresh_mode_cards)
        self.radio_vlm.toggled.connect(self._refresh_mode_cards)

        card_layout.addWidget(self.text_option_card)
        card_layout.addWidget(self.vlm_option_card)
        card_layout.addSpacing(10)
        card_layout.addWidget(self.mode_hint_label)
        card_layout.addSpacing(8)
        card_layout.addWidget(self.btn_enter_mode)

        layout.addWidget(mode_card)
        layout.addStretch(1)
        return page

    def _build_benchmark_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("BenchmarkPage")

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(8)
        page.setLayout(root_layout)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.btn_back_mode = QPushButton("Back to Mode Selection")
        self.btn_back_mode.setProperty("role", "ghost")
        self.btn_back_mode.clicked.connect(self._go_to_mode_selection)
        self.mode_badge = QLabel("Mode: -")
        self.mode_badge.setObjectName("ModeBadge")
        self.run_badge = QLabel("State: Ready")
        self.run_badge.setObjectName("RunBadge")
        self.run_badge.setProperty("state", "ready")
        mode_row.addWidget(self.btn_back_mode)
        mode_row.addWidget(self.mode_badge)
        mode_row.addWidget(self.run_badge)
        mode_row.addStretch(1)
        root_layout.addLayout(mode_row)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.btn_select_all = QPushButton("Select All Models")
        self.btn_select_none = QPushButton("Clear Selection")
        self.btn_clear_history = QPushButton("Clear History")
        self.btn_clear_history.setProperty("role", "ghost")
        self.btn_start = QPushButton("Start")
        self.btn_start.setProperty("role", "primary")
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setProperty("role", "danger")
        self.btn_stop.setEnabled(False)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

        controls.addWidget(self.btn_select_all)
        controls.addWidget(self.btn_select_none)
        controls.addWidget(self.btn_clear_history)
        controls.addWidget(self.btn_start)
        controls.addWidget(self.btn_stop)
        controls.addWidget(self.progress, stretch=1)
        root_layout.addLayout(controls)

        v_split = QSplitter(Qt.Vertical)
        v_split.setObjectName("MainVSplit")
        v_split.setHandleWidth(8)
        root_layout.addWidget(v_split, stretch=1)

        h_split = QSplitter(Qt.Horizontal)
        h_split.setObjectName("MainHSplit")
        h_split.setHandleWidth(8)
        v_split.addWidget(h_split)

        left_panel = QFrame()
        left_panel.setObjectName("PanelCard")
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(6)
        left_panel.setLayout(left_layout)

        self.model_list = QListWidget()
        self.model_list.setObjectName("ModelList")
        self.model_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.model_list.setMinimumWidth(320)
        model_title = QLabel("Models")
        model_title.setObjectName("SectionTitle")
        left_layout.addWidget(model_title)
        left_layout.addWidget(self.model_list, stretch=1)

        self.history_list = QListWidget()
        self.history_list.setObjectName("HistoryList")
        self.history_list.setMinimumWidth(320)
        history_title = QLabel("History")
        history_title.setObjectName("SectionTitle")
        left_layout.addWidget(history_title)
        left_layout.addWidget(self.history_list, stretch=2)
        h_split.addWidget(left_panel)

        right_panel = QFrame()
        right_panel.setObjectName("PanelCard")
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(6)
        right_panel.setLayout(right_layout)

        self.image_section = QWidget()
        image_layout = QVBoxLayout()
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(6)
        self.image_section.setLayout(image_layout)
        image_layout.addWidget(QLabel("Image"))

        self.image_label = QLabel("No image")
        self.image_label.setObjectName("ImagePreview")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(260)
        image_layout.addWidget(self.image_label, stretch=1)

        right_layout.addWidget(self.image_section, stretch=2)

        prompt_title = QLabel("Prompt")
        prompt_title.setObjectName("SectionTitle")
        right_layout.addWidget(prompt_title)
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setObjectName("PromptEdit")
        self.prompt_edit.setReadOnly(True)
        self.prompt_edit.setMaximumBlockCount(5000)
        self.prompt_edit.setPlaceholderText("Prompt will appear here...")
        right_layout.addWidget(self.prompt_edit, stretch=1)

        answer_title = QLabel("Model Output (Extracted Answer)")
        answer_title.setObjectName("SectionTitle")
        right_layout.addWidget(answer_title)
        self.answer_edit = QPlainTextEdit()
        self.answer_edit.setObjectName("AnswerEdit")
        self.answer_edit.setReadOnly(True)
        self.answer_edit.setMaximumBlockCount(20000)
        self.answer_edit.setPlaceholderText("Model output will appear here...")
        right_layout.addWidget(self.answer_edit, stretch=2)

        h_split.addWidget(right_panel)
        h_split.setStretchFactor(0, 0)
        h_split.setStretchFactor(1, 1)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setObjectName("LogEdit")
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumBlockCount(50000)
        self.log_edit.setPlaceholderText("Runtime logs...")
        v_split.addWidget(self.log_edit)
        v_split.setStretchFactor(0, 3)
        v_split.setStretchFactor(1, 1)

        self.btn_select_all.clicked.connect(self._select_all_models)
        self.btn_select_none.clicked.connect(self._select_none_models)
        self.btn_clear_history.clicked.connect(self._clear_history)
        self.btn_start.clicked.connect(self._start)
        self.btn_stop.clicked.connect(self._stop)
        self.history_list.currentRowChanged.connect(self._on_history_selected)

        return page

    def _apply_styles(self):
        self.setFont(QFont("Noto Sans", 10))
        self.setStyleSheet(
            """
            QMainWindow {
                background: #ecf1f7;
            }
            QWidget#ModePage {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #e8f0ff, stop:0.58 #eaf7ef, stop:1 #f6f8fc);
            }
            QWidget#BenchmarkPage {
                background: #ecf1f7;
            }
            QLabel#ModeEyebrow {
                color: #3e658d;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1px;
            }
            QLabel#ModeTitle {
                color: #152534;
                font-size: 32px;
                font-weight: 700;
            }
            QLabel#ModeSubtitle {
                color: #4e6073;
                font-size: 14px;
            }
            QFrame#ModeCard,
            QFrame#PanelCard {
                background: #ffffff;
                border: 1px solid #d0d9e4;
                border-radius: 14px;
            }
            QFrame#ModeCard {
                border: 1px solid #c9d8e9;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8fbff);
            }
            QFrame#OptionCard {
                border: 1px solid #d7e1ee;
                border-radius: 12px;
                background: #f9fbff;
            }
            QFrame#OptionCard[selected="true"] {
                border: 1px solid #5f92c5;
                background: #eaf3ff;
            }
            QLabel#ModeHint {
                color: #5c6e82;
                font-size: 12px;
            }
            QLabel#ModeBadge {
                color: #204f78;
                background: #deedf9;
                border: 1px solid #b3cee8;
                border-radius: 10px;
                padding: 6px 12px;
                font-weight: 700;
            }
            QLabel#RunBadge {
                color: #1f5f3f;
                background: #e3f5ea;
                border: 1px solid #b8e1c8;
                border-radius: 10px;
                padding: 6px 12px;
                font-weight: 700;
            }
            QLabel#RunBadge[state="running"] {
                color: #8b5600;
                background: #fff2df;
                border: 1px solid #f2d09f;
            }
            QLabel#RunBadge[state="stopping"] {
                color: #8e4d00;
                background: #ffe9cc;
                border: 1px solid #f4c585;
            }
            QLabel#RunBadge[state="error"] {
                color: #8f242b;
                background: #fde8ea;
                border: 1px solid #efc1c6;
            }
            QPushButton {
                background: #e6ecf4;
                color: #1f2937;
                border: 1px solid #c5d0de;
                border-radius: 9px;
                padding: 7px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #d8e4f2;
            }
            QPushButton:pressed {
                background: #c8d9ec;
            }
            QPushButton:disabled {
                color: #7f8a99;
                background: #eef2f7;
            }
            QPushButton[role="primary"] {
                color: #ffffff;
                background: #2469ac;
                border: 1px solid #1f5f9d;
            }
            QPushButton[role="primary"]:hover {
                background: #2f77bf;
            }
            QPushButton[role="primary"]:pressed {
                background: #215f9a;
            }
            QPushButton[role="danger"] {
                color: #ffffff;
                background: #cb5b55;
                border: 1px solid #b24b45;
            }
            QPushButton[role="danger"]:hover {
                background: #d76b65;
            }
            QPushButton[role="danger"]:pressed {
                background: #b34b46;
            }
            QPushButton[role="ghost"] {
                background: #f5f8fc;
                border: 1px solid #d1dbe8;
            }
            QListWidget,
            QPlainTextEdit {
                background: #fafcff;
                border: 1px solid #d4dfea;
                border-radius: 8px;
            }
            QPlainTextEdit {
                color: #1f2937;
                selection-background-color: #2f70ad;
                selection-color: #ffffff;
            }
            QListWidget {
                selection-background-color: #c8daf3;
            }
            QListWidget::item {
                color: #1f2937;
                padding: 7px 9px;
                border-radius: 6px;
            }
            QListWidget::item:hover {
                background: #e8f0fb;
            }
            QListWidget::item:selected {
                background: #2f70ad;
                color: #ffffff;
            }
            QListWidget::item:selected:!active {
                background: #4c86bd;
                color: #ffffff;
            }
            QLabel#SectionTitle {
                color: #2b4055;
                font-size: 12px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.4px;
            }
            QLabel#ImagePreview {
                border: 1px dashed #9ab3cd;
                border-radius: 10px;
                background: #f4f8fd;
                color: #5a728d;
            }
            QProgressBar {
                border: 1px solid #b8c8de;
                border-radius: 9px;
                text-align: center;
                background: #edf3fb;
                min-height: 24px;
                color: #29435b;
                font-weight: 700;
            }
            QProgressBar::chunk {
                border-radius: 8px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4f8dcb, stop:1 #66b29d);
            }
            QLabel {
                color: #243244;
            }
            QRadioButton {
                color: #1f2937;
                font-size: 14px;
                font-weight: 600;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 17px;
                height: 17px;
            }
            QRadioButton::indicator:unchecked {
                border: 1px solid #87a0bc;
                border-radius: 8px;
                background: #ffffff;
            }
            QRadioButton::indicator:checked {
                border: 1px solid #2f70ad;
                border-radius: 8px;
                background: #2f70ad;
            }
            QSplitter#MainHSplit::handle,
            QSplitter#MainVSplit::handle {
                background: #dde7f2;
                border-radius: 3px;
            }
            QSplitter#MainHSplit::handle:hover,
            QSplitter#MainVSplit::handle:hover {
                background: #c8d8ea;
            }
            """
        )

    def _set_run_state(self, state: str, text: str):
        self.run_badge.setText(text)
        self.run_badge.setProperty("state", state)
        self.run_badge.style().unpolish(self.run_badge)
        self.run_badge.style().polish(self.run_badge)
        self.run_badge.update()

    def _refresh_mode_cards(self):
        text_selected = self.radio_text.isChecked()
        vlm_selected = self.radio_vlm.isChecked()

        self.text_option_card.setProperty("selected", "true" if text_selected else "false")
        self.vlm_option_card.setProperty("selected", "true" if vlm_selected else "false")

        self.text_option_card.style().unpolish(self.text_option_card)
        self.text_option_card.style().polish(self.text_option_card)
        self.text_option_card.update()

        self.vlm_option_card.style().unpolish(self.vlm_option_card)
        self.vlm_option_card.style().polish(self.vlm_option_card)
        self.vlm_option_card.update()

    def _friendly_mode_name(self, mode: Optional[str] = None) -> str:
        target = (mode or self.current_mode or "").strip().lower()
        if target == self.MODE_VLM:
            return "Multimodal Model (VLM)"
        return "Text LLM"

    def _is_multimodal_mode(self) -> bool:
        return self.current_mode == self.MODE_VLM

    def _infer_initial_mode(self) -> str:
        if not self.preselected_models or "all" in self.preselected_models:
            return self.MODE_TEXT

        detected_types = set()
        for model_name in self.preselected_models:
            model_type = self._model_type_by_name.get(model_name)
            if model_type in (self.MODE_TEXT, self.MODE_VLM):
                detected_types.add(model_type)

        if len(detected_types) == 1:
            return next(iter(detected_types))
        return self.MODE_TEXT

    def _sync_mode_radio_buttons(self):
        if self.current_mode == self.MODE_VLM:
            self.radio_vlm.setChecked(True)
        else:
            self.radio_text.setChecked(True)

        if "all" in self.preselected_models:
            self.mode_hint_label.setText("CLI preselection: all models.")
        else:
            candidates = [name for name in self.preselected_models if name in self._model_type_by_name]
            if not candidates:
                self.mode_hint_label.setText("CLI preselection: no explicit model list.")
            else:
                preview = ", ".join(candidates[:4])
                if len(candidates) > 4:
                    preview += ", ..."
                self.mode_hint_label.setText(f"CLI preselection: {preview}")
        self._refresh_mode_cards()

    def _models_for_mode(self, mode: str) -> List[str]:
        normalized = (mode or "").strip().lower()
        names = [model_name for model_name, model_type in self._model_type_by_name.items() if model_type == normalized]
        return sorted(names)

    def _load_models_for_mode(self):
        names = self._models_for_mode(self.current_mode)
        self.model_list.clear()
        for model_name in names:
            self.model_list.addItem(model_name)

        if not names:
            return

        if "all" in self.preselected_models:
            self.model_list.clearSelection()
            self.model_list.setCurrentRow(-1)
            return

        wanted = {name for name in self.preselected_models if name in names}
        if not wanted:
            self.model_list.clearSelection()
            self.model_list.setCurrentRow(-1)
            return

        for i in range(self.model_list.count()):
            item = self.model_list.item(i)
            if item and item.text() in wanted:
                item.setSelected(True)
        self.model_list.setCurrentRow(-1)

    def _update_mode_badge(self):
        mode_name = self._friendly_mode_name()
        self.mode_badge.setText(f"Mode: {mode_name}")
        self.setWindowTitle(f"RK3588 Benchmark GUI - {mode_name}")

    def _apply_mode_specific_layout(self):
        show_image = self._is_multimodal_mode()
        self.image_section.setVisible(show_image)
        if not show_image:
            self._set_image(None)

    def _prepare_benchmark_page(self, mode: str) -> bool:
        normalized = (mode or self.MODE_TEXT).strip().lower()
        if normalized not in (self.MODE_TEXT, self.MODE_VLM):
            normalized = self.MODE_TEXT
        self.current_mode = normalized

        self._update_mode_badge()
        self._apply_mode_specific_layout()
        self._load_models_for_mode()

        if self.model_list.count() == 0:
            return False

        self._reset_run_state()
        self.log_edit.clear()
        self._set_run_state("ready", "State: Ready")
        self._append_log(f"[GUI] Ready for {self._friendly_mode_name()} benchmark.")
        return True

    def _confirm_mode_selection(self):
        mode = self.MODE_VLM if self.radio_vlm.isChecked() else self.MODE_TEXT
        if not self._prepare_benchmark_page(mode):
            QMessageBox.warning(
                self,
                "No available models",
                f"No models of type '{self._friendly_mode_name(mode)}' were found in config.",
            )
            return
        self.stack.setCurrentWidget(self.page_benchmark)

    def _go_to_mode_selection(self):
        if self._is_running():
            QMessageBox.information(self, "Benchmark running", "Stop the current run before changing mode.")
            return
        self._sync_mode_radio_buttons()
        self.stack.setCurrentWidget(self.page_mode)

    def _is_running(self) -> bool:
        return self._worker_thread is not None and self._worker_thread.isRunning()

    def _select_all_models(self):
        for i in range(self.model_list.count()):
            item = self.model_list.item(i)
            if item:
                item.setSelected(True)

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale_pixmap()

    def _selected_models(self) -> List[str]:
        items = self.model_list.selectedItems()
        return [item.text() for item in items if item and item.text()]

    def _history_item_payload(self, kind: str, task_key: str, record_index: Optional[int] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"kind": kind, "task_key": task_key}
        if record_index is not None:
            payload["record_index"] = int(record_index)
        return payload

    def _format_history_label(
        self,
        model_name: str,
        task_id: Any,
        prompt: str,
        image_abs_path: Optional[str],
        duration_s: Optional[float],
        status: str,
    ) -> str:
        duration_text = f" {float(duration_s):.2f}s" if duration_s is not None else ""
        if self._is_multimodal_mode() and image_abs_path:
            target = os.path.basename(image_abs_path)
        else:
            target = " ".join((prompt or "").split()) or "(empty prompt)"
            if len(target) > 28:
                target = target[:28] + "..."
        return f"[{model_name}] #{task_id} {target}{duration_text} {status}"

    def _upsert_live_history_item(self, model_name: str, task_id: Any, prompt: str, image_abs_path: Optional[str]):
        task_key = f"{model_name}#{task_id}"
        label = self._format_history_label(model_name, task_id, prompt, image_abs_path, None, "Running")
        if self._live_history_item is None:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, self._history_item_payload("live", task_key))
            self.history_list.addItem(item)
            self._live_history_item = item
            return
        self._live_history_item.setText(label)
        self._live_history_item.setData(Qt.UserRole, self._history_item_payload("live", task_key))

    def _finalize_live_history_item(
        self,
        model_name: str,
        task_id: Any,
        prompt: str,
        image_abs_path: Optional[str],
        duration_s: float,
        status: str,
        record_index: int,
    ):
        task_key = f"{model_name}#{task_id}"
        label = self._format_history_label(model_name, task_id, prompt, image_abs_path, duration_s, status)
        if self._live_history_item is not None:
            payload = self._live_history_item.data(Qt.UserRole)
            if isinstance(payload, dict) and payload.get("task_key") == task_key:
                self._live_history_item.setText(label)
                self._live_history_item.setData(Qt.UserRole, self._history_item_payload("record", task_key, record_index))
                self._live_history_item = None
                return

        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, self._history_item_payload("record", task_key, record_index))
        self.history_list.addItem(item)

    def _show_task_content(self, task_key: Optional[str], prompt: str, answer: str, image_abs_path: Optional[str]):
        self._display_task_key = task_key
        self.prompt_edit.setPlainText(prompt)
        self.answer_edit.setPlainText(answer)
        sb = self.answer_edit.verticalScrollBar()
        sb.setValue(sb.maximum())
        if self._is_multimodal_mode():
            self._set_image(image_abs_path)
        else:
            self._set_image(None)

    def _show_live_task(self):
        if not self._current_task_key:
            return
        self._history_view_locked = False
        prompt = self._task_prompt_by_key.get(self._current_task_key, "")
        answer = self._stream_answer_by_task.get(self._current_task_key, "")
        image_abs_path = self._task_image_by_key.get(self._current_task_key)
        self._show_task_content(self._current_task_key, prompt, answer, image_abs_path)

    def _clear_history(self):
        self.records.clear()
        live_payload = None
        if self._is_running() and self._current_task_key:
            live_payload = self._history_item_payload("live", self._current_task_key)
        live_label = None
        if live_payload is not None:
            live_prompt = self._task_prompt_by_key.get(self._current_task_key, "")
            live_image = self._task_image_by_key.get(self._current_task_key)
            model_name, _, task_id = self._current_task_key.partition("#")
            live_label = self._format_history_label(model_name, task_id, live_prompt, live_image, None, "Running")

        self.history_list.blockSignals(True)
        self.history_list.clear()
        self.history_list.clearSelection()
        self.history_list.setCurrentRow(-1)
        self._live_history_item = None
        if live_payload is not None and live_label is not None:
            self._live_history_item = QListWidgetItem(live_label)
            self._live_history_item.setData(Qt.UserRole, live_payload)
            self.history_list.addItem(self._live_history_item)
        self.history_list.blockSignals(False)

        if self._is_running() and self._current_task_key:
            self._show_live_task()
            return

        self._history_view_locked = False
        self._display_task_key = None
        self.prompt_edit.setPlainText("")
        self.answer_edit.setPlainText("")
        self._set_image(None)

    def _reset_run_state(self):
        self.records.clear()
        self.history_list.clear()
        self.history_list.clearSelection()
        self.history_list.setCurrentRow(-1)
        self._run_has_error = False
        self._stop_requested = False
        self._history_view_locked = False
        self._current_task_key = None
        self._display_task_key = None
        self._stream_raw_by_task.clear()
        self._stream_answer_by_task.clear()
        self._task_prompt_by_key.clear()
        self._task_image_by_key.clear()
        self._live_history_item = None
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
            QMessageBox.warning(
                self,
                "No models selected",
                f"Please select at least one {self._friendly_mode_name()} model to run.",
            )
            return
        if self._is_running():
            QMessageBox.information(self, "Already running", "Benchmark is already running.")
            return

        self._reset_run_state()
        self.log_edit.clear()
        self._set_run_state("running", "State: Running")
        self._append_log(f"[GUI] Starting {self._friendly_mode_name()} benchmark for {len(models)} model(s)...")

        self._worker = BenchmarkWorker(self.workspace_root, self.config_path, models)
        self._worker_thread = QThread(self)
        self._worker.moveToThread(self._worker_thread)

        sink = self._worker.sink
        sink.log.connect(self._append_log)
        sink.progress_total.connect(self._on_progress_total)
        sink.model_start.connect(self._on_model_start)
        sink.task_start.connect(self._on_task_start)
        sink.task_stream.connect(self._on_task_stream)
        sink.task_end.connect(self._on_task_end)
        sink.model_end.connect(self._on_model_end)
        sink.run_end.connect(self._on_run_end)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._on_thread_finished)

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_back_mode.setEnabled(False)
        self.model_list.setEnabled(False)
        self.btn_select_all.setEnabled(False)
        self.btn_select_none.setEnabled(False)

        self._worker_thread.start()

    def _stop(self):
        if self._worker is not None:
            self._stop_requested = True
            self._set_run_state("stopping", "State: Stopping")
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
        self._stream_raw_by_task[self._current_task_key] = ""
        self._stream_answer_by_task[self._current_task_key] = ""

        img_rel = task_dict.get("image")
        abs_path = os.path.join(self.workspace_root, str(img_rel)) if img_rel else None
        self._task_prompt_by_key[self._current_task_key] = prompt
        self._task_image_by_key[self._current_task_key] = abs_path
        self._upsert_live_history_item(model_name, tid, prompt, abs_path)
        if not self._history_view_locked:
            self._show_task_content(self._current_task_key, prompt, "", abs_path)

        self._append_log(f"[GUI] Task start: [{model_name}] #{tid}")

    def _on_task_stream(self, model_name: str, task_dict: Dict[str, Any], text_chunk: str):
        if not text_chunk:
            return
        tid = task_dict.get("id")
        task_key = f"{model_name}#{tid}"
        if self._current_task_key != task_key:
            return
        raw_text = self._stream_raw_by_task.get(task_key, "") + text_chunk
        self._stream_raw_by_task[task_key] = raw_text
        clean_answer = extract_stream_answer(raw_text)
        self._stream_answer_by_task[task_key] = clean_answer

        if self._history_view_locked or self._display_task_key != task_key:
            return

        self.answer_edit.setPlainText(clean_answer)
        sb = self.answer_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

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
        self._stream_raw_by_task[task_key] = output_text or ""
        self._stream_answer_by_task[task_key] = answer

        if self._current_task_key == task_key and not self._history_view_locked:
            self._show_task_content(task_key, rec.prompt, rec.extracted_answer, rec.image_abs_path)

        status = "Success" if rec.success else "Error"
        self._finalize_live_history_item(model_name, tid, rec.prompt, image_abs, rec.duration_s, status, len(self.records) - 1)

        self.tasks_completed += 1
        self.progress.setValue(self.tasks_completed)

        tps = ""
        try:
            if parsed_metrics and parsed_metrics.get("generate_tps", 0.0):
                tps = f", gen_tps={float(parsed_metrics.get('generate_tps')):.2f}"
        except Exception:
            tps = ""
        self._append_log(f"[GUI] Task end: [{model_name}] #{tid} {status}, {duration_s:.2f}s{tps}")

    def _on_model_end(self, model_name: str, status: str):
        self._append_log(f"[GUI] Model end: {model_name}, status={status}")
        if status in {"Crash/Error", "Failed", "Error"}:
            self._run_has_error = True
            self._set_run_state("error", "State: Error")

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
        payload = item.data(Qt.UserRole)
        if not isinstance(payload, dict):
            return
        kind = payload.get("kind")
        task_key = payload.get("task_key")
        if kind == "live" and isinstance(task_key, str) and task_key == self._current_task_key:
            self._show_live_task()
            return
        rec_idx = payload.get("record_index")
        if not isinstance(rec_idx, int) or rec_idx < 0 or rec_idx >= len(self.records):
            return
        rec = self.records[rec_idx]
        self._history_view_locked = True
        self._show_task_content(f"{rec.model_name}#{rec.task_id}", rec.prompt, rec.extracted_answer, rec.image_abs_path)

    def _on_worker_finished(self):
        self._append_log("[GUI] Worker finished.")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_back_mode.setEnabled(True)
        self.model_list.setEnabled(True)
        self.btn_select_all.setEnabled(True)
        self.btn_select_none.setEnabled(True)
        if self._run_has_error:
            self._set_run_state("error", "State: Error")
        elif self._stop_requested:
            self._set_run_state("ready", "State: Stopped")
        else:
            self._set_run_state("ready", "State: Completed")

    def _on_thread_finished(self):
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

    def closeEvent(self, event):
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
