"""Utilities for fine-tuning OCR models on Vietnamese datasets."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass(slots=True)
class Sample:
    """Represents a single training sample for OCR fine-tuning."""

    image_path: Path
    transcription: str


@dataclass(slots=True)
class FineTuneConfig:
    """Configuration for Vietnamese OCR fine-tuning."""

    output_dir: Path
    pretrained_model: Optional[str] = None
    epochs: int = 10
    batch_size: int = 8
    learning_rate: float = 1e-4
    validation_split: float = 0.1
    seed: int = 42


class VietnameseFineTuner:
    """High-level wrapper around PaddleOCR or Tesseract fine-tuning flows."""

    def __init__(self, config: FineTuneConfig) -> None:
        self.config = config
        self.output_dir = self.config.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_dataset(self, dataset_root: Path | str) -> List[Sample]:
        """Load a dataset folder where each image has a matching `.txt` transcription."""

        root = Path(dataset_root)
        if not root.exists():
            raise FileNotFoundError(f"Dataset root does not exist: {root}")

        samples: List[Sample] = []
        for image_path in sorted(root.glob("**/*.png")):
            transcript_path = image_path.with_suffix(".txt")
            if not transcript_path.exists():
                continue
            text = transcript_path.read_text(encoding="utf-8").strip()
            samples.append(Sample(image_path=image_path, transcription=text))
        return samples

    def split_dataset(self, samples: Iterable[Sample]) -> tuple[List[Sample], List[Sample]]:
        """Split the dataset into train/validation according to ``validation_split``."""

        samples_list = list(samples)
        split_idx = int(len(samples_list) * (1 - self.config.validation_split))
        train_samples = samples_list[:split_idx]
        val_samples = samples_list[split_idx:]
        return train_samples, val_samples

    def export_for_paddleocr(self, samples: Iterable[Sample]) -> Path:
        """Export samples to PaddleOCR's expected label file format."""

        label_file = self.output_dir / "labels.txt"
        with label_file.open("w", encoding="utf-8") as f:
            for sample in samples:
                f.write(f"{sample.image_path}\t{sample.transcription}\n")
        return label_file

    def fine_tune_paddleocr(self, train_data: Path, val_data: Optional[Path] = None) -> Path:
        """Generate a PaddleOCR training command file for later execution."""

        config_path = self.output_dir / "paddle_config.yml"
        config_content = f"""
Global:
  use_gpu: true
  epoch_num: {self.config.epochs}
  save_model_dir: {self.output_dir / 'paddle_model'}
  save_epoch_step: 1
Optimizer:
  name: Adam
  lr:
    learning_rate: {self.config.learning_rate}
Train:
  dataset:
    name: SimpleDataSet
    data_dir: {train_data.parent}
    label_file_path: {train_data}
  loader:
    shuffle: true
    batch_size_per_card: {self.config.batch_size}
Eval:
  dataset:
    name: SimpleDataSet
    data_dir: {val_data.parent if val_data else train_data.parent}
    label_file_path: {val_data if val_data else train_data}
"""
        config_path.write_text(config_content.strip(), encoding="utf-8")
        return config_path

    def prepare_tesseract_training(self, samples: Iterable[Sample]) -> Path:
        """Create a box/tiff training set for Tesseract fine-tuning."""

        training_dir = self.output_dir / "tesseract"
        training_dir.mkdir(exist_ok=True)
        manifest = training_dir / "manifest.txt"
        with manifest.open("w", encoding="utf-8") as f:
            for idx, sample in enumerate(samples):
                f.write(f"{idx}\t{sample.image_path}\t{sample.transcription}\n")
        return manifest

    def document_workflow(self, dataset_root: Path | str) -> dict:
        """End-to-end helper returning all generated artefacts without launching training."""

        samples = self.load_dataset(dataset_root)
        train_samples, val_samples = self.split_dataset(samples)
        train_label_file = self.export_for_paddleocr(train_samples)
        val_label_file = self.export_for_paddleocr(val_samples)
        paddle_config = self.fine_tune_paddleocr(train_label_file, val_label_file)
        tesseract_manifest = self.prepare_tesseract_training(samples)
        return {
            "train_samples": train_samples,
            "val_samples": val_samples,
            "paddle_label_files": (train_label_file, val_label_file),
            "paddle_config": paddle_config,
            "tesseract_manifest": tesseract_manifest,
        }
