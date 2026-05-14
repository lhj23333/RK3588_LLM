import os
import re
import sys
import threading
from dataclasses import dataclass, field
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


def is_cancelled_output(output_text: str) -> bool:
    return str(output_text or "").lstrip().startswith("Cancelled by user")


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
    runtime_metrics: Dict[str, Any] = field(default_factory=dict)


class QtEventSink(QObject):
    log = pyqtSignal(str)
    model_start = pyqtSignal(str, str, int, str)
    task_start = pyqtSignal(str, object)
    task_stream = pyqtSignal(str, object, str)
    task_metric = pyqtSignal(str, object, object)
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

    def on_task_metric(self, model_name: str, task_dict: Dict[str, Any], metrics_dict: Dict[str, Any]):
        self.task_metric.emit(model_name, task_dict, metrics_dict)

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

    def __init__(
        self,
        workspace_root: str,
        config_path: str,
        target_models: List[str],
        run_mode: str = "benchmark",
        single_prompt: str = "",
    ):
        super().__init__()
        self.workspace_root = workspace_root
        self.config_path = config_path
        self.target_models = target_models
        self.run_mode = run_mode
        self.single_prompt = single_prompt
        self.cancel_event = threading.Event()
        self.sink = QtEventSink()

    def request_cancel(self):
        self.cancel_event.set()
        self.sink.on_log("[GUI] Stop requested. Stopping current task...")

    def run(self):
        try:
            runner = BenchmarkRunner(self.workspace_root, self.config_path)
            models_to_run = self.target_models if self.target_models else list(runner.models_config.keys())

            if self.run_mode == "single":
                text_models = [
                    name
                    for name in models_to_run
                    if runner.models_config.get(name) and runner.models_config[name].type == "text"
                ]
                self.sink.progress_total.emit(int(len(text_models)))
                runner.run_single_text(
                    text_models,
                    self.single_prompt,
                    event_sink=self.sink,
                    cancel_event=self.cancel_event,
                )
                return

            total = 0
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

    RUN_MODE_BENCHMARK = "benchmark"
    RUN_MODE_SINGLE = "single"

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
        self.run_mode = self.RUN_MODE_BENCHMARK

        self.records: List[TaskRecord] = []
        self.total_tasks_expected = 0
        self.tasks_completed = 0
        self._run_has_error = False
        self._stop_requested = False
        self._active_run_mode = self.RUN_MODE_BENCHMARK

        self._current_pixmap: Optional[QPixmap] = None
        self._current_image_path: Optional[str] = None
        self._current_task_key: Optional[str] = None
        self._display_task_key: Optional[str] = None
        self._history_view_locked = False
        self._stream_raw_by_task: Dict[str, str] = {}
        self._stream_answer_by_task: Dict[str, str] = {}
        self._task_prompt_by_key: Dict[str, str] = {}
        self._task_image_by_key: Dict[str, Optional[str]] = {}
        self._live_metrics_by_task: Dict[str, Dict[str, Any]] = {}
        self._final_metrics_by_task: Dict[str, Dict[str, Any]] = {}
        self._live_history_item: Optional[QListWidgetItem] = None

        self._worker_thread: Optional[QThread] = None
        self._worker: Optional[BenchmarkWorker] = None

        self.setWindowTitle("RK3588 Benchmark GUI")
        self.resize(1280, 820)

        self._build_ui()
        self._apply_styles()
        self._sync_mode_radio_buttons()
        self._refresh_mode_cards()

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

        text_desc = QLabel(
            "Text mode supports benchmark dataset prompts and single custom prompt inference. "
            "Image area is hidden."
        )
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

        self.btn_run_mode = QPushButton("Run Mode: Benchmark ON")
        self.btn_run_mode.setCheckable(True)
        self.btn_run_mode.setChecked(True)
        self.btn_run_mode.setProperty("role", "ghost")

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
        controls.addWidget(self.btn_run_mode)
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

        middle_panel = QFrame()
        middle_panel.setObjectName("PanelCard")
        middle_layout = QVBoxLayout()
        middle_layout.setContentsMargins(12, 12, 12, 12)
        middle_layout.setSpacing(6)
        middle_panel.setLayout(middle_layout)

        self.image_section = QWidget()
        image_layout = QVBoxLayout()
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(6)
        self.image_section.setLayout(image_layout)
        image_title = QLabel("Image")
        image_title.setObjectName("SectionTitle")
        image_layout.addWidget(image_title)

        self.image_label = QLabel("No image")
        self.image_label.setObjectName("ImagePreview")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(260)
        image_layout.addWidget(self.image_label, stretch=1)

        middle_layout.addWidget(self.image_section, stretch=2)

        prompt_title = QLabel("Prompt")
        prompt_title.setObjectName("SectionTitle")
        middle_layout.addWidget(prompt_title)
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setObjectName("PromptEdit")
        self.prompt_edit.setReadOnly(True)
        self.prompt_edit.setMaximumBlockCount(5000)
        self.prompt_edit.setPlaceholderText("Prompt will appear here...")
        middle_layout.addWidget(self.prompt_edit, stretch=1)

        answer_title = QLabel("Model Output (Extracted Answer)")
        answer_title.setObjectName("SectionTitle")
        middle_layout.addWidget(answer_title)
        self.answer_edit = QPlainTextEdit()
        self.answer_edit.setObjectName("AnswerEdit")
        self.answer_edit.setReadOnly(True)
        self.answer_edit.setMaximumBlockCount(20000)
        self.answer_edit.setPlaceholderText("Model output will appear here...")
        middle_layout.addWidget(self.answer_edit, stretch=2)

        h_split.addWidget(middle_panel)

        right_panel = QFrame()
        right_panel.setObjectName("PanelCard")
        right_panel.setMinimumWidth(320)
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(10)
        right_panel.setLayout(right_layout)

        runtime_title = QLabel("Runtime Performance")
        runtime_title.setObjectName("SectionTitle")
        right_layout.addWidget(runtime_title)

        runtime_hint = QLabel("Live profiler snapshots for the current task.")
        runtime_hint.setObjectName("ModeHint")
        runtime_hint.setWordWrap(True)
        right_layout.addWidget(runtime_hint)

        self.runtime_panel = QFrame()
        self.runtime_panel.setObjectName("MetricsPanel")
        runtime_layout = QVBoxLayout()
        runtime_layout.setContentsMargins(12, 12, 12, 12)
        runtime_layout.setSpacing(10)
        self.runtime_panel.setLayout(runtime_layout)

        self._runtime_value_labels: Dict[str, QLabel] = {}
        runtime_fields = [
            ("stage_status", "Stage / Status"),
            ("current_dram_mb", "Current DRAM"),
            ("init_dram_mb", "Init DRAM"),
            ("runtime_buffer_mb", "Runtime Buffer"),
            ("total_peak_mb", "Total Peak DRAM"),
            ("avg_cpu_usage_percent", "Avg Runtime CPU Usage"),
            ("generate_tps", "Generate TPS"),
            ("duration_s", "Duration"),
        ]
        for metric_key, label_text in runtime_fields:
            metric_card = QFrame()
            metric_card.setObjectName("MetricItem")
            metric_card_layout = QVBoxLayout()
            metric_card_layout.setContentsMargins(12, 10, 12, 10)
            metric_card_layout.setSpacing(4)
            metric_card.setLayout(metric_card_layout)

            title_label = QLabel(label_text)
            title_label.setObjectName("MetricLabel")
            value_label = QLabel("--")
            value_label.setObjectName("MetricValue")
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            if metric_key == "stage_status":
                value_label.setProperty("metricRole", "status")
            metric_card_layout.addWidget(title_label)
            metric_card_layout.addWidget(value_label)
            runtime_layout.addWidget(metric_card)
            self._runtime_value_labels[metric_key] = value_label
        right_layout.addWidget(self.runtime_panel)
        right_layout.addStretch(1)

        h_split.addWidget(right_panel)
        h_split.setStretchFactor(0, 0)
        h_split.setStretchFactor(1, 1)
        h_split.setStretchFactor(2, 0)

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
        self.btn_run_mode.toggled.connect(self._on_run_mode_toggled)
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
            QFrame#MetricsPanel {
                background: #f7fbff;
                border: 1px solid #d5e2f0;
                border-radius: 12px;
            }
            QFrame#MetricItem {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #ffffff, stop:1 #f2f8ff);
                border: 1px solid #d9e5f2;
                border-radius: 10px;
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
            QPushButton[role="ghost"]:checked {
                color: #ffffff;
                background: #2f70ad;
                border: 1px solid #215f9a;
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
            QPlainTextEdit:read-only {
                background: #f5f8fc;
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
            QLabel#MetricLabel {
                color: #5a6f86;
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.4px;
            }
            QLabel#MetricValue {
                color: #17324d;
                font-size: 18px;
                font-weight: 700;
                background: transparent;
                border: none;
                padding: 0px;
            }
            QLabel#MetricValue[metricRole="status"] {
                color: #215d93;
                font-size: 15px;
                font-weight: 700;
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

    def _infer_initial_mode(self) -> str:
        selected = [m for m in self.preselected_models if m != "all"]
        if not selected:
            return self.MODE_TEXT

        selected_types = {
            self._model_type_by_name.get(model_name)
            for model_name in selected
            if self._model_type_by_name.get(model_name)
        }
        if selected_types == {self.MODE_VLM}:
            return self.MODE_VLM
        return self.MODE_TEXT

    def _sync_mode_radio_buttons(self):
        self.radio_text.setChecked(self.current_mode == self.MODE_TEXT)
        self.radio_vlm.setChecked(self.current_mode == self.MODE_VLM)

    def _refresh_mode_cards(self):
        text_selected = self.radio_text.isChecked()
        vlm_selected = self.radio_vlm.isChecked()
        self.text_option_card.setProperty("selected", "true" if text_selected else "false")
        self.vlm_option_card.setProperty("selected", "true" if vlm_selected else "false")
        self.text_option_card.style().unpolish(self.text_option_card)
        self.text_option_card.style().polish(self.text_option_card)
        self.vlm_option_card.style().unpolish(self.vlm_option_card)
        self.vlm_option_card.style().polish(self.vlm_option_card)

        if text_selected:
            self.mode_hint_label.setText(
                "Text LLM page: ON = benchmark dataset mode, OFF = single custom prompt mode."
            )
            self.btn_enter_mode.setText("Enter Text LLM")
        else:
            self.mode_hint_label.setText("VLM page keeps the existing benchmark flow.")
            self.btn_enter_mode.setText("Enter VLM Benchmark")

    def _confirm_mode_selection(self):
        if self._worker is not None:
            QMessageBox.information(self, "Running", "Please stop or wait for the current run to finish.")
            return

        self.current_mode = self.MODE_VLM if self.radio_vlm.isChecked() else self.MODE_TEXT
        self._populate_model_list()
        self._apply_mode_specific_layout()
        self._refresh_run_mode_ui()
        self.stack.setCurrentWidget(self.page_benchmark)

    def _go_to_mode_selection(self):
        if self._worker is not None:
            QMessageBox.information(self, "Running", "Please stop or wait for the current run to finish.")
            return
        self.stack.setCurrentWidget(self.page_mode)

    def _populate_model_list(self):
        self.model_list.clear()
        selected_names = set(m for m in self.preselected_models if m != "all")
        has_explicit_selection = bool(selected_names)

        for model_name in sorted(self._all_models_config.keys()):
            model_type = self._model_type_by_name.get(model_name, "")
            if model_type != self.current_mode:
                continue

            item = QListWidgetItem(model_name)
            item.setToolTip(f"{model_name} ({model_type})")
            self.model_list.addItem(item)

            should_select = not has_explicit_selection or model_name in selected_names
            item.setSelected(should_select)

        if self.model_list.count() == 0:
            self._append_log(f"[GUI] No model found for mode: {self.current_mode}")

    def _apply_mode_specific_layout(self):
        is_text_mode = self.current_mode == self.MODE_TEXT
        self.mode_badge.setText("Mode: Text LLM" if is_text_mode else "Mode: VLM")
        self.image_section.setVisible(not is_text_mode)
        if is_text_mode:
            self._set_image(None)
        self._reset_task_display(clear_prompt=not (is_text_mode and self.run_mode == self.RUN_MODE_SINGLE))

    def _on_run_mode_toggled(self, checked: bool):
        self.run_mode = self.RUN_MODE_BENCHMARK if checked else self.RUN_MODE_SINGLE
        self._refresh_run_mode_ui()

    def _refresh_run_mode_ui(self):
        is_text_mode = self.current_mode == self.MODE_TEXT
        self.btn_run_mode.setVisible(is_text_mode)

        if not is_text_mode:
            self.run_mode = self.RUN_MODE_BENCHMARK
            self.btn_run_mode.blockSignals(True)
            self.btn_run_mode.setChecked(True)
            self.btn_run_mode.setText("Run Mode: Benchmark ON")
            self.btn_run_mode.blockSignals(False)
            self.prompt_edit.setReadOnly(True)
            self.prompt_edit.setPlaceholderText("Prompt will appear here...")
            self.btn_start.setText("Start")
            return

        is_benchmark = self.run_mode == self.RUN_MODE_BENCHMARK
        self.btn_run_mode.blockSignals(True)
        self.btn_run_mode.setChecked(is_benchmark)
        self.btn_run_mode.setText("Run Mode: Benchmark ON" if is_benchmark else "Run Mode: Single OFF")
        self.btn_run_mode.blockSignals(False)

        self.prompt_edit.setReadOnly(is_benchmark)
        self.prompt_edit.setPlaceholderText(
            "Prompt will appear here..." if is_benchmark else "Input custom prompt here for single inference..."
        )
        self.btn_start.setText("Start Benchmark" if is_benchmark else "Run Single")

    def _select_all_models(self):
        for i in range(self.model_list.count()):
            self.model_list.item(i).setSelected(True)

    def _select_none_models(self):
        self.model_list.clearSelection()

    def _selected_models(self) -> List[str]:
        return [item.text() for item in self.model_list.selectedItems()]

    def _clear_history(self):
        if self._worker is not None:
            QMessageBox.information(self, "Running", "Cannot clear history while a task is running.")
            return
        self.records.clear()
        self.history_list.clear()
        self._stream_raw_by_task.clear()
        self._stream_answer_by_task.clear()
        self._task_prompt_by_key.clear()
        self._task_image_by_key.clear()
        self._live_metrics_by_task.clear()
        self._final_metrics_by_task.clear()
        self._live_history_item = None
        self._reset_task_display(clear_prompt=(self.run_mode != self.RUN_MODE_SINGLE))
        self._clear_runtime_metrics()

    def _start(self):
        if self._worker is not None:
            QMessageBox.information(self, "Running", "A benchmark is already running.")
            return

        target_models = self._selected_models()
        if not target_models:
            QMessageBox.warning(self, "No model selected", "Please select at least one model.")
            return

        run_mode = self.RUN_MODE_BENCHMARK
        single_prompt = ""
        if self.current_mode == self.MODE_TEXT:
            run_mode = self.run_mode

        if run_mode == self.RUN_MODE_SINGLE:
            single_prompt = self.prompt_edit.toPlainText().strip()
            if not single_prompt:
                QMessageBox.warning(
                    self,
                    "Empty Prompt",
                    "Please input a custom prompt before starting single mode.",
                )
                return

        self._active_run_mode = run_mode
        self._run_has_error = False
        self._stop_requested = False
        self.tasks_completed = 0
        self.total_tasks_expected = 0
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.log_edit.clear()
        self.answer_edit.clear()
        self._clear_runtime_metrics()
        self._current_task_key = None
        self._display_task_key = None
        self._history_view_locked = False
        self._stream_raw_by_task.clear()
        self._stream_answer_by_task.clear()
        self._task_prompt_by_key.clear()
        self._task_image_by_key.clear()
        self._live_metrics_by_task.clear()
        self._final_metrics_by_task.clear()
        self._live_history_item = None
        self.records.clear()
        self.history_list.clear()

        if run_mode == self.RUN_MODE_BENCHMARK:
            self.prompt_edit.clear()
        else:
            self.prompt_edit.setPlainText(single_prompt)

        self._set_run_state(True)
        self._set_run_badge("running", "State: Running")
        self._append_log(
            f"[GUI] Starting {'single prompt' if run_mode == self.RUN_MODE_SINGLE else 'benchmark'} run."
        )

        self._worker_thread = QThread(self)
        self._worker = BenchmarkWorker(
            self.workspace_root,
            self.config_path,
            target_models,
            run_mode=run_mode,
            single_prompt=single_prompt,
        )
        self._worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)

        self._connect_worker_signals(self._worker.sink)
        self._worker_thread.start()

    def _connect_worker_signals(self, sink: QtEventSink):
        sink.log.connect(self._append_log)
        sink.progress_total.connect(self._on_progress_total)
        sink.model_start.connect(self._on_model_start)
        sink.task_start.connect(self._on_task_start)
        sink.task_stream.connect(self._on_task_stream)
        sink.task_metric.connect(self._on_task_metric)
        sink.task_end.connect(self._on_task_end)
        sink.model_end.connect(self._on_model_end)
        sink.run_end.connect(self._on_run_end)

    def _stop(self):
        if self._worker is None:
            return
        self._stop_requested = True
        self._set_run_badge("stopping", "State: Stopping")
        self.btn_stop.setEnabled(False)
        self._worker.request_cancel()

    def _set_run_state(self, running: bool):
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.btn_select_all.setEnabled(not running)
        self.btn_select_none.setEnabled(not running)
        self.btn_clear_history.setEnabled(not running)
        self.btn_back_mode.setEnabled(not running)
        self.btn_run_mode.setEnabled(not running)
        self.model_list.setEnabled(not running)
        self.prompt_edit.setReadOnly(running or self.run_mode == self.RUN_MODE_BENCHMARK)

    def _on_worker_finished(self):
        if self._worker is not None:
            self._worker.deleteLater()
        self._worker = None
        self._worker_thread = None
        self._set_run_state(False)
        self._refresh_run_mode_ui()

        if self._stop_requested:
            self._set_run_badge("ready", "State: Stopped")
        elif self._run_has_error:
            self._set_run_badge("error", "State: Error")
        else:
            self._set_run_badge("ready", "State: Ready")

    def _on_progress_total(self, total: int):
        self.total_tasks_expected = max(0, int(total))
        if self.total_tasks_expected <= 0:
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
        else:
            self.progress.setRange(0, self.total_tasks_expected)
            self.progress.setValue(0)
        self.tasks_completed = 0

    def _on_model_start(self, model_name: str, model_type: str, total_tasks_for_model: int, log_file_path: str):
        self._append_log(f"[GUI] Model start: {model_name} ({model_type}), tasks={total_tasks_for_model}")
        if log_file_path:
            self._append_log(f"[GUI] Raw log: {log_file_path}")

    def _on_model_end(self, model_name: str, status: str):
        self._append_log(f"[GUI] Model end: {model_name}, status={status}")
        if status and status not in ("Success", "Cancelled"):
            self._run_has_error = True

    def _on_run_end(self, report_path: str):
        if self._stop_requested:
            self._append_log("[GUI] Run stopped by user.")
        if report_path:
            self._append_log(f"[GUI] Benchmark report saved to: {report_path}")
        elif not self._stop_requested:
            self._append_log("[GUI] Single mode finished. No benchmark report generated.")

    def _on_task_start(self, model_name: str, task_dict: Dict[str, Any]):
        task_key = self._make_task_key(model_name, task_dict)
        self._current_task_key = task_key
        self._display_task_key = task_key
        self._history_view_locked = False
        self._stream_raw_by_task[task_key] = ""
        self._stream_answer_by_task[task_key] = ""
        self._live_metrics_by_task[task_key] = {"stage_status": "Running"}

        prompt = task_dict.get("prompt", "") or ""
        image_path = self._resolve_image_path(task_dict.get("image"))
        self._task_prompt_by_key[task_key] = prompt
        self._task_image_by_key[task_key] = image_path

        self.prompt_edit.setPlainText(prompt)
        self.answer_edit.clear()
        self._set_image(image_path)
        self._display_metrics(self._live_metrics_by_task[task_key])

        self._live_history_item = QListWidgetItem(self._format_history_title(model_name, task_dict, running=True))
        self._live_history_item.setData(Qt.UserRole, task_key)
        self.history_list.addItem(self._live_history_item)
        self.history_list.setCurrentItem(self._live_history_item)

    def _on_task_stream(self, model_name: str, task_dict: Dict[str, Any], text_chunk: str):
        task_key = self._make_task_key(model_name, task_dict)
        self._stream_raw_by_task[task_key] = self._stream_raw_by_task.get(task_key, "") + (text_chunk or "")
        answer = extract_stream_answer(self._stream_raw_by_task[task_key])
        if not answer:
            answer = self._stream_raw_by_task[task_key].strip()
        self._stream_answer_by_task[task_key] = answer

        if self._display_task_key == task_key and not self._history_view_locked:
            self.answer_edit.setPlainText(answer)
            self.answer_edit.verticalScrollBar().setValue(self.answer_edit.verticalScrollBar().maximum())

    def _on_task_metric(self, model_name: str, task_dict: Dict[str, Any], metrics_dict: Dict[str, Any]):
        task_key = self._make_task_key(model_name, task_dict)
        current = dict(self._live_metrics_by_task.get(task_key, {}))
        current.update(metrics_dict or {})
        current.setdefault("stage_status", "Running")
        self._live_metrics_by_task[task_key] = current

        if self._display_task_key == task_key:
            self._display_metrics(current)

    def _on_task_end(
        self,
        model_name: str,
        task_dict: Dict[str, Any],
        success: bool,
        output_text: str,
        duration_s: float,
        mem_metrics_dict: Dict[str, Any],
        parsed_metrics_dict: Dict[str, Any],
    ):
        task_key = self._make_task_key(model_name, task_dict)
        prompt = task_dict.get("prompt", "") or ""
        image_path = self._resolve_image_path(task_dict.get("image"))
        cancelled = (not success) and is_cancelled_output(output_text)
        extracted = extract_answer(output_text or "")

        metrics = {}
        metrics.update(parsed_metrics_dict or {})
        metrics.update(mem_metrics_dict or {})
        metrics["duration_s"] = duration_s
        if cancelled:
            metrics["stage_status"] = "Cancelled"
        else:
            metrics["stage_status"] = "Success" if success else "Failed"
        self._final_metrics_by_task[task_key] = metrics

        record = TaskRecord(
            model_name=model_name,
            task_id=task_dict.get("id"),
            prompt=prompt,
            image_abs_path=image_path,
            success=success,
            duration_s=duration_s,
            raw_output=output_text or "",
            extracted_answer=extracted,
            runtime_metrics=metrics,
        )
        self.records.append(record)

        if self._live_history_item is not None and self._live_history_item.data(Qt.UserRole) == task_key:
            self._live_history_item.setText(self._format_history_title(model_name, task_dict, running=False, success=success))
            self._live_history_item = None
        else:
            item = QListWidgetItem(self._format_history_title(model_name, task_dict, running=False, success=success))
            item.setData(Qt.UserRole, task_key)
            self.history_list.addItem(item)

        self.tasks_completed += 1
        if self.total_tasks_expected > 0:
            self.progress.setValue(min(self.tasks_completed, self.total_tasks_expected))

        if not success and not cancelled:
            self._run_has_error = True

        if self._display_task_key == task_key and not self._history_view_locked:
            self.prompt_edit.setPlainText(prompt)
            self.answer_edit.setPlainText(extracted)
            self._set_image(image_path)
            self._display_metrics(metrics)

    def _on_history_selected(self, row: int):
        if row < 0:
            return
        item = self.history_list.item(row)
        if not item:
            return
        task_key = item.data(Qt.UserRole)
        if not task_key:
            return

        self._history_view_locked = task_key != self._current_task_key
        self._display_task_key = task_key

        prompt = self._task_prompt_by_key.get(task_key, "")
        image_path = self._task_image_by_key.get(task_key)
        self.prompt_edit.setPlainText(prompt)
        self._set_image(image_path)

        for record in self.records:
            if self._make_task_key(record.model_name, {"id": record.task_id, "prompt": record.prompt, "image": record.image_abs_path}) == task_key:
                self.answer_edit.setPlainText(record.extracted_answer)
                self._display_metrics(record.runtime_metrics)
                return

        self.answer_edit.setPlainText(self._stream_answer_by_task.get(task_key, ""))
        self._display_metrics(self._live_metrics_by_task.get(task_key, {}))

    def _make_task_key(self, model_name: str, task_dict: Dict[str, Any]) -> str:
        task_id = task_dict.get("id", "")
        image = task_dict.get("image", "") or ""
        if image and os.path.isabs(str(image)):
            image = os.path.relpath(str(image), self.workspace_root)
        return f"{model_name}::{task_id}::{image}"

    def _format_history_title(self, model_name: str, task_dict: Dict[str, Any], running: bool = False, success: bool = True) -> str:
        task_id = task_dict.get("id", "?")
        prefix = "▶" if running else ("✓" if success else "✗")
        prompt = (task_dict.get("prompt", "") or "").replace("\n", " ").strip()
        if len(prompt) > 52:
            prompt = prompt[:52] + "..."
        return f"{prefix} {model_name} / {task_id}  {prompt}"

    def _resolve_image_path(self, image_path: Optional[str]) -> Optional[str]:
        if not image_path:
            return None
        image_path = str(image_path)
        if os.path.isabs(image_path):
            return image_path
        return os.path.join(self.workspace_root, image_path)

    def _set_image(self, image_abs_path: Optional[str]):
        self._current_image_path = image_abs_path
        self._current_pixmap = None

        if not image_abs_path:
            self.image_label.setText("No image")
            self.image_label.setPixmap(QPixmap())
            return

        if not os.path.exists(image_abs_path):
            self.image_label.setText(f"Image not found:\n{image_abs_path}")
            self.image_label.setPixmap(QPixmap())
            return

        pixmap = QPixmap(image_abs_path)
        if pixmap.isNull():
            self.image_label.setText(f"Failed to load image:\n{image_abs_path}")
            self.image_label.setPixmap(QPixmap())
            return

        self._current_pixmap = pixmap
        self._render_current_image()

    def _render_current_image(self):
        if self._current_pixmap is None or self._current_pixmap.isNull():
            return
        target_size = self.image_label.size()
        scaled = self._current_pixmap.scaled(target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled)
        self.image_label.setText("")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_current_image()

    def _reset_task_display(self, clear_prompt: bool = True):
        if clear_prompt:
            self.prompt_edit.clear()
        self.answer_edit.clear()
        self._set_image(None)
        self._clear_runtime_metrics()

    def _clear_runtime_metrics(self):
        for label in self._runtime_value_labels.values():
            label.setText("--")

    def _format_metric_value(self, key: str, value: Any) -> str:
        if value is None or value == "":
            # Keep compatibility with older parser/runtime key names.
            alias_map = {
                "current_dram_mb": ("current_memory_mb", "current_mem_mb"),
                "init_dram_mb": ("model_data_mb",),
                "runtime_buffer_mb": ("kv_cache_overhead_mb",),
                "generate_tps": ("avg_generate_tps",),
            }
            for alias in alias_map.get(key, ()):
                # Caller passes only value, so alias fallback is handled in _format_metrics_from_dict.
                pass
            return "--"

        if key == "stage_status":
            return str(value)
        if key in ("current_dram_mb", "init_dram_mb", "runtime_buffer_mb", "total_peak_mb"):
            try:
                return f"{float(value):.2f} MB"
            except Exception:
                return str(value)
        if key == "avg_cpu_usage_percent":
            try:
                return f"{float(value):.2f}%"
            except Exception:
                return str(value)
        if key == "generate_tps":
            try:
                return f"{float(value):.2f} tok/s"
            except Exception:
                return str(value)
        if key == "duration_s":
            try:
                return f"{float(value):.2f} s"
            except Exception:
                return str(value)
        return str(value)

    def _display_metrics(self, metrics: Dict[str, Any]):
        metrics = metrics or {}
        alias_map = {
            "current_dram_mb": ("current_dram_mb", "current_memory_mb", "current_mem_mb"),
            "init_dram_mb": ("init_dram_mb", "model_data_mb"),
            "runtime_buffer_mb": ("runtime_buffer_mb", "kv_cache_overhead_mb"),
            "total_peak_mb": ("total_peak_mb",),
            "avg_cpu_usage_percent": ("avg_cpu_usage_percent",),
            "generate_tps": ("generate_tps", "avg_generate_tps"),
            "duration_s": ("duration_s",),
            "stage_status": ("stage_status", "status", "stage"),
        }
        for key, label in self._runtime_value_labels.items():
            value = None
            for candidate in alias_map.get(key, (key,)):
                if candidate in metrics:
                    value = metrics.get(candidate)
                    break
            label.setText(self._format_metric_value(key, value))

    def _append_log(self, msg: str):
        self.log_edit.appendPlainText(str(msg))
        self.log_edit.verticalScrollBar().setValue(self.log_edit.verticalScrollBar().maximum())

    def _set_run_badge(self, state: str, text: str):
        self.run_badge.setText(text)
        self.run_badge.setProperty("state", state)
        self.run_badge.style().unpolish(self.run_badge)
        self.run_badge.style().polish(self.run_badge)

    def closeEvent(self, event):
        thread_running = self._worker_thread is not None and self._worker_thread.isRunning()
        if self._worker is not None or thread_running:
            QMessageBox.information(
                self,
                "Benchmark running",
                "A benchmark is still running.\n\n"
                "Please click Stop and wait for the current task to finish, then close the window.",
            )
            event.ignore()
            return
        super().closeEvent(event)


def run_gui(workspace_root: str, config_path: str, preselected_models: Optional[List[str]] = None):
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv)

    window = BenchmarkGui(workspace_root, config_path, preselected_models=preselected_models)
    window.show()

    if owns_app:
        sys.exit(app.exec_())
    return window


if __name__ == "__main__":
    workspace = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config = os.path.join(workspace, "conf", "models_config.yaml")
    run_gui(workspace, config)
