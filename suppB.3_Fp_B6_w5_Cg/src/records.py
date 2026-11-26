"""Unpack recorded task inputs only when a fresh search needs them."""
from pathlib import Path
import zipfile

def ensure_tasks(stage):
    stage=Path(stage)
    if not (stage/'tasks').exists():
        with zipfile.ZipFile(stage/'task_records.zip') as archive:
            archive.extractall(stage)
