import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from gnostiq import cfg  # noqa: E402

DEFAULT = Path(__file__).resolve().parents[1] / cfg.FILENAME

SMALL = {
    "start = 2021-01-01": "start = 2023-07-01",
    "train_end = 2026-03-31": "train_end = 2024-12-31",
    "test_start = 2026-04-01": "test_start = 2025-04-01",
    "test_end = 2026-10-31": "test_end = 2025-06-30",
    'extra = ["gfs_seamless", "icon_seamless"]': 'extra = ["gfs_seamless"]',
    "lead_days = [1, 2, 3, 4, 5, 6, 7]": "lead_days = [1, 3]",
    "seeds = 3": "seeds = 1",
    "hidden = 64": "hidden = 16",
    "max_epochs = 300": "max_epochs = 6",
    "patience = 25": "patience = 3",
}


def write_cfg(tmp_path, edits=None):
    text = DEFAULT.read_text()
    for old, new in (edits or {}).items():
        assert old in text, f"fixture drift: {old!r} not in {cfg.FILENAME}"
        text = text.replace(old, new)
    p = tmp_path / cfg.FILENAME
    p.write_text(text)
    return p
