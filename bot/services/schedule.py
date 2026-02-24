"""
Schedule management service.
Handles parsing natural language dates and managing events.
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)


class ScheduleService:
    """Parses and manages schedule entries from natural language."""

    # Indonesian day names
    HARI = {
        "senin": 0, "selasa": 1, "rabu": 2, "kamis": 3,
        "jumat": 4, "sabtu": 5, "minggu": 6,
    }

    # Relative date keywords
    RELATIVE_DATES = {
        "hari ini": 0,
        "besok": 1,
        "lusa": 2,
        "besok lusa": 2,
    }

    def parse_date(self, text: str) -> Optional[str]:
        """Try to parse a date from Indonesian natural language. Returns YYYY-MM-DD or None."""
        text_lower = text.lower().strip()
        now = datetime.now()

        # Check relative dates
        for keyword, days_offset in self.RELATIVE_DATES.items():
            if keyword in text_lower:
                target = now + timedelta(days=days_offset)
                return target.strftime("%Y-%m-%d")

        # Check day names (find next occurrence)
        for day_name, day_num in self.HARI.items():
            if day_name in text_lower:
                days_ahead = day_num - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                target = now + timedelta(days=days_ahead)
                return target.strftime("%Y-%m-%d")

        # Check explicit date patterns
        # DD/MM/YYYY or DD-MM-YYYY
        date_match = re.search(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', text_lower)
        if date_match:
            day, month, year = date_match.groups()
            try:
                return datetime(int(year), int(month), int(day)).strftime("%Y-%m-%d")
            except ValueError:
                pass

        # DD/MM or DD-MM (assume current year)
        date_match = re.search(r'(\d{1,2})[/\-](\d{1,2})(?!\d)', text_lower)
        if date_match:
            day, month = date_match.groups()
            try:
                return datetime(now.year, int(month), int(day)).strftime("%Y-%m-%d")
            except ValueError:
                pass

        # "tanggal DD" or "tgl DD"
        tgl_match = re.search(r'(?:tanggal|tgl)\s+(\d{1,2})', text_lower)
        if tgl_match:
            day = int(tgl_match.group(1))
            try:
                target = datetime(now.year, now.month, day)
                if target.date() < now.date():
                    if now.month == 12:
                        target = datetime(now.year + 1, 1, day)
                    else:
                        target = datetime(now.year, now.month + 1, day)
                return target.strftime("%Y-%m-%d")
            except ValueError:
                pass

        return None

    def parse_time(self, text: str) -> Optional[str]:
        """Try to parse time from text. Returns HH:MM or None."""
        text_lower = text.lower().strip()

        # "jam HH:MM" or "jam HH.MM" or "pukul HH:MM"
        time_match = re.search(r'(?:jam|pukul|pkl)\s*(\d{1,2})[:\.](\d{2})', text_lower)
        if time_match:
            h, m = int(time_match.group(1)), int(time_match.group(2))
            if 0 <= h <= 23 and 0 <= m <= 59:
                return f"{h:02d}:{m:02d}"

        # "jam HH" (just hour)
        time_match = re.search(r'(?:jam|pukul|pkl)\s*(\d{1,2})(?:\s|$|,|\.)', text_lower)
        if time_match:
            h = int(time_match.group(1))
            if 0 <= h <= 23:
                return f"{h:02d}:00"

        # "HH:MM" standalone
        time_match = re.search(r'(?<!\d)(\d{1,2}):(\d{2})(?!\d)', text_lower)
        if time_match:
            h, m = int(time_match.group(1)), int(time_match.group(2))
            if 0 <= h <= 23 and 0 <= m <= 59:
                return f"{h:02d}:{m:02d}"

        # Handle "pagi/siang/sore/malam" modifiers
        # "jam 8 pagi" vs "jam 8 malam"
        time_match = re.search(r'(?:jam|pukul)\s*(\d{1,2})\s*(pagi|siang|sore|malam)', text_lower)
        if time_match:
            h = int(time_match.group(1))
            period = time_match.group(2)
            if period in ("sore", "malam") and h < 12:
                h += 12
            if 0 <= h <= 23:
                return f"{h:02d}:00"

        return None

    def format_schedule_list(self, schedules: List[Dict]) -> str:
        """Format a list of schedules for display."""
        if not schedules:
            return "Tidak ada jadwal yang tercatat."

        lines = []
        for i, s in enumerate(schedules, 1):
            time_str = s.get("event_time", "")
            date_str = s.get("event_date", "")
            title = s.get("title", "")
            desc = s.get("description", "")

            line = f"{i}. 📅 {title}"
            if date_str:
                line += f" — {date_str}"
            if time_str:
                line += f" ⏰ {time_str}"
            if desc:
                line += f"\n   📝 {desc}"
            line += f" (ID: {s.get('id', '?')})"
            lines.append(line)

        return "\n".join(lines)
