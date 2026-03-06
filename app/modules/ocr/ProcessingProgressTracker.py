import time
import threading
from datetime import datetime
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, asdict
from enum import Enum
import json


class ProcessingStage(Enum):
    """Processing stages for OCR workflow"""
    INITIALIZING = "initializing"
    LOADING_MODELS = "loading_models"
    PREPARING_IMAGES = "preparing_images"
    ANALYZING_LAYOUT = "analyzing_layout"
    DETECTING_TEXT = "detecting_text"
    RECOGNIZING_TEXT = "recognizing_text"
    GROUPING_PARAGRAPHS = "grouping_paragraphs"
    GENERATING_OUTPUT = "generating_output"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class StageInfo:
    """Information about a processing stage"""
    name: str
    description: str
    estimated_duration: float  # seconds
    weight: float  # percentage weight in total process (0-100)


@dataclass
class ProcessingState:
    """Current state of processing"""
    stage: ProcessingStage
    stage_progress: float  # 0-100 for current stage
    overall_progress: float  # 0-100 for entire process
    current_page: int
    total_pages: int
    message: str
    estimated_remaining: float  # seconds
    elapsed_time: float  # seconds
    start_time: str
    last_update: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'stage': self.stage.value,
            'stage_progress': round(self.stage_progress, 1),
            'overall_progress': round(self.overall_progress, 1),
            'current_page': self.current_page,
            'total_pages': self.total_pages,
            'message': self.message,
            'estimated_remaining': round(self.estimated_remaining, 1),
            'elapsed_time': round(self.elapsed_time, 1),
            'start_time': self.start_time,
            'last_update': self.last_update
        }


class ProcessingProgressTracker:
    """
    Real-time progress tracking for OCR operations.
    Provides detailed status updates including stage, progress, time estimates.
    """

    def __init__(self, total_pages: int = 1):
        """Initialize progress tracker"""
        self.total_pages = total_pages
        self.current_page = 0
        self.start_time = time.time()
        self.last_stage_start = time.time()

        # Stage definitions with estimated durations and weights
        self.stages = {
            ProcessingStage.INITIALIZING: StageInfo(
                "Başlatılıyor",
                "Sistem hazırlanıyor ve parametreler kontrol ediliyor",
                2.0, 5.0
            ),
            ProcessingStage.LOADING_MODELS: StageInfo(
                "Modeller Yükleniyor",
                "AI modelleri GPU'ya yükleniyor",
                3.0, 10.0
            ),
            ProcessingStage.PREPARING_IMAGES: StageInfo(
                "Görüntüler Hazırlanıyor",
                "PDF sayfaları işleniyor ve optimize ediliyor",
                1.0, 5.0
            ),
            ProcessingStage.ANALYZING_LAYOUT: StageInfo(
                "Layout Analizi",
                "Sayfa yapısı ve bölümler tespit ediliyor",
                2.0, 15.0
            ),
            ProcessingStage.DETECTING_TEXT: StageInfo(
                "Metin Bölgeleri Tespit Ediliyor",
                "Metin içeren alanlar belirleniyor",
                3.0, 20.0
            ),
            ProcessingStage.RECOGNIZING_TEXT: StageInfo(
                "Metin Tanınıyor",
                "OCR ile karakterler okunuyor",
                5.0, 35.0
            ),
            ProcessingStage.GROUPING_PARAGRAPHS: StageInfo(
                "Paragraflar Düzenleniyor",
                "Metinler paragraf halinde organize ediliyor",
                1.0, 5.0
            ),
            ProcessingStage.GENERATING_OUTPUT: StageInfo(
                "Çıktı Oluşturuluyor",
                "Markdown ve XML formatları hazırlanıyor",
                1.0, 3.0
            ),
            ProcessingStage.FINALIZING: StageInfo(
                "Tamamlanıyor",
                "Son kontroller ve metadata ekleniyor",
                0.5, 2.0
            ),
            ProcessingStage.COMPLETED: StageInfo(
                "Tamamlandı",
                "İşlem başarıyla tamamlandı",
                0.0, 0.0
            ),
            ProcessingStage.ERROR: StageInfo(
                "Hata",
                "İşlem sırasında hata oluştu",
                0.0, 0.0
            )
        }

        self.current_stage = ProcessingStage.INITIALIZING
        self.stage_progress = 0.0
        self.overall_progress = 0.0
        self.message = "İşlem başlatılıyor..."
        self.error_message = None

        # Callbacks for real-time updates
        self.update_callbacks: List[Callable[[ProcessingState], None]] = []

        # Thread safety
        self.lock = threading.Lock()

    def add_update_callback(self, callback: Callable[[ProcessingState], None]):
        """Add callback function to receive real-time updates"""
        with self.lock:
            self.update_callbacks.append(callback)

    def remove_update_callback(self, callback: Callable[[ProcessingState], None]):
        """Remove callback function"""
        with self.lock:
            if callback in self.update_callbacks:
                self.update_callbacks.remove(callback)

    def set_stage(self, stage: ProcessingStage, message: str = ""):
        """Set current processing stage"""
        with self.lock:
            self.current_stage = stage
            self.last_stage_start = time.time()
            self.stage_progress = 0.0

            if message:
                self.message = message
            else:
                self.message = self.stages[stage].description

            self._update_overall_progress()
            self._notify_callbacks()

    def update_stage_progress(self, progress: float, message: str = ""):
        """Update progress within current stage (0-100)"""
        with self.lock:
            self.stage_progress = max(0.0, min(100.0, progress))

            if message:
                self.message = message

            self._update_overall_progress()
            self._notify_callbacks()

    def set_page_progress(self, current_page: int, stage_progress: float = None, message: str = ""):
        """Update current page being processed"""
        with self.lock:
            self.current_page = current_page

            if stage_progress is not None:
                self.stage_progress = max(0.0, min(100.0, stage_progress))

            if message:
                self.message = message
            else:
                self.message = f"Sayfa {current_page}/{self.total_pages} işleniyor..."

            self._update_overall_progress()
            self._notify_callbacks()

    def increment_page(self, message: str = ""):
        """Move to next page"""
        self.set_page_progress(self.current_page + 1, message=message)

    def set_error(self, error_message: str):
        """Set error state"""
        with self.lock:
            self.current_stage = ProcessingStage.ERROR
            self.error_message = error_message
            self.message = f"Hata: {error_message}"
            self._notify_callbacks()

    def complete(self, message: str = "İşlem başarıyla tamamlandı!"):
        """Mark processing as completed"""
        with self.lock:
            self.current_stage = ProcessingStage.COMPLETED
            self.stage_progress = 100.0
            self.overall_progress = 100.0
            self.message = message
            self._notify_callbacks()

    def get_current_state(self) -> ProcessingState:
        """Get current processing state"""
        with self.lock:
            elapsed = time.time() - self.start_time
            estimated_remaining = self._calculate_estimated_remaining()

            return ProcessingState(
                stage=self.current_stage,
                stage_progress=self.stage_progress,
                overall_progress=self.overall_progress,
                current_page=self.current_page,
                total_pages=self.total_pages,
                message=self.message,
                estimated_remaining=estimated_remaining,
                elapsed_time=elapsed,
                start_time=datetime.fromtimestamp(self.start_time).isoformat(),
                last_update=datetime.now().isoformat()
            )

    def get_state_json(self) -> str:
        """Get current state as JSON string"""
        return json.dumps(self.get_current_state().to_dict(), ensure_ascii=False)

    def _update_overall_progress(self):
        """Calculate overall progress based on stage weights"""
        completed_weight = 0.0

        # Add weight of completed stages
        for stage in ProcessingStage:
            if stage == self.current_stage:
                break
            if stage in self.stages:
                completed_weight += self.stages[stage].weight

        # Add current stage progress
        if self.current_stage in self.stages:
            current_stage_weight = self.stages[self.current_stage].weight
            current_contribution = (self.stage_progress / 100.0) * current_stage_weight
            completed_weight += current_contribution

        self.overall_progress = min(100.0, completed_weight)

    def _calculate_estimated_remaining(self) -> float:
        """Calculate estimated remaining time"""
        if self.overall_progress <= 0:
            return 0.0

        elapsed = time.time() - self.start_time
        if self.overall_progress >= 100:
            return 0.0

        # Simple linear estimation based on current progress
        estimated_total = elapsed / (self.overall_progress / 100.0)
        remaining = estimated_total - elapsed

        return max(0.0, remaining)

    def _notify_callbacks(self):
        """Notify all registered callbacks about state change"""
        if not self.update_callbacks:
            return

        current_state = self.get_current_state()
        for callback in self.update_callbacks:
            try:
                callback(current_state)
            except Exception as e:
                print(f"⚠️ Progress callback error: {e}")

    def create_stage_tracker(self, stage: ProcessingStage, total_items: int = 1):
        """Create a sub-tracker for detailed stage progress"""
        return StageProgressTracker(self, stage, total_items)


class StageProgressTracker:
    """
    Sub-tracker for detailed progress within a specific stage
    """

    def __init__(self, main_tracker: ProcessingProgressTracker, stage: ProcessingStage, total_items: int):
        self.main_tracker = main_tracker
        self.stage = stage
        self.total_items = total_items
        self.current_item = 0

        # Set the stage in main tracker
        self.main_tracker.set_stage(stage)

    def update(self, current_item: int = None, message: str = ""):
        """Update progress within the stage"""
        if current_item is not None:
            self.current_item = current_item

        progress = (self.current_item / self.total_items) * 100.0 if self.total_items > 0 else 0.0

        if not message and self.total_items > 1:
            message = f"{self.current_item}/{self.total_items} tamamlandı"

        self.main_tracker.update_stage_progress(progress, message)

    def increment(self, message: str = ""):
        """Move to next item in stage"""
        self.update(self.current_item + 1, message)

    def complete(self, message: str = ""):
        """Complete the stage"""
        self.update(self.total_items, message)


# Usage examples and utility functions
class ProgressManager:
    """
    High-level manager for OCR progress tracking
    Integrates with SuryaProcessor for seamless progress updates
    """

    def __init__(self):
        self.current_tracker: Optional[ProcessingProgressTracker] = None
        self.global_callbacks: List[Callable[[ProcessingState], None]] = []

    def start_processing(self, total_pages: int) -> ProcessingProgressTracker:
        """Start new processing session"""
        self.current_tracker = ProcessingProgressTracker(total_pages)

        # Add global callbacks to new tracker
        for callback in self.global_callbacks:
            self.current_tracker.add_update_callback(callback)

        return self.current_tracker

    def get_current_tracker(self) -> Optional[ProcessingProgressTracker]:
        """Get current active tracker"""
        return self.current_tracker

    def add_global_callback(self, callback: Callable[[ProcessingState], None]):
        """Add callback that applies to all future processing sessions"""
        self.global_callbacks.append(callback)

        # Add to current tracker if active
        if self.current_tracker:
            self.current_tracker.add_update_callback(callback)

    def get_current_state_json(self) -> str:
        """Get current state as JSON, or empty state if no active processing"""
        if self.current_tracker:
            return self.current_tracker.get_state_json()

        # Return idle state
        idle_state = {
            'stage': 'idle',
            'stage_progress': 0.0,
            'overall_progress': 0.0,
            'current_page': 0,
            'total_pages': 0,
            'message': 'Sistem hazır',
            'estimated_remaining': 0.0,
            'elapsed_time': 0.0,
            'start_time': '',
            'last_update': datetime.now().isoformat()
        }

        return json.dumps(idle_state, ensure_ascii=False)


# Example callback function for real-time updates
def console_progress_callback(state: ProcessingState):
    """Example callback that prints progress to console"""
    print(f"🔄 [{state.stage.value}] {state.overall_progress:.1f}% - {state.message}")
    if state.total_pages > 1:
        print(f"   📄 Sayfa: {state.current_page}/{state.total_pages}")
    if state.estimated_remaining > 0:
        print(f"   ⏱️ Kalan süre: ~{state.estimated_remaining:.0f}s")


# Global progress manager instance
progress_manager = ProgressManager()