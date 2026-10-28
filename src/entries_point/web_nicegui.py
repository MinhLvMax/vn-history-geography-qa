"""Entrypoint - Chạy VNHisChat dưới dạng giao diện web NiceGUI.

Chạy: python -m src.entries_point.web_nicegui rồi mở http://localhost:8080
"""

import sys
from pathlib import Path

# Đảm bảo thư mục cha chứa agent có mặt trong sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.bootstrap import Bootstrap


# NiceGUI yêu cầu guard này vì có thể khởi chạy lại module trong tiến trình con
if __name__ in {"__main__", "__mp_main__"}:
    Bootstrap().run_web()
