"""
Traffic estimation service.
Uses time-based heuristics for Indonesian cities + Google Maps link generation.
"""
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TrafficService:
    """Provides traffic condition estimates based on time of day and known patterns."""

    # Peak hour definitions (Indonesian traffic patterns)
    PEAK_HOURS = {
        "morning": {"start": 6, "end": 9, "peak": 7.5},
        "evening": {"start": 16, "end": 20, "peak": 17.5},
    }

    TRAFFIC_LEVELS = {
        "sangat_lancar": {
            "level": 1,
            "label": "Sangat Lancar 🟢",
            "description": "Jalanan sepi, perjalanan cepat tanpa hambatan.",
            "multiplier": 1.0,
        },
        "lancar": {
            "level": 2,
            "label": "Lancar 🟢",
            "description": "Lalu lintas normal, sedikit kendaraan.",
            "multiplier": 1.2,
        },
        "ramai_lancar": {
            "level": 3,
            "label": "Ramai Lancar 🟡",
            "description": "Cukup ramai tapi masih bergerak lancar.",
            "multiplier": 1.5,
        },
        "padat": {
            "level": 4,
            "label": "Padat Merayap 🟠",
            "description": "Macet cukup parah, kendaraan bergerak lambat.",
            "multiplier": 2.0,
        },
        "macet_total": {
            "level": 5,
            "label": "Macet Total 🔴",
            "description": "Kemacetan parah, perjalanan bisa 2-3x lebih lama.",
            "multiplier": 3.0,
        },
    }

    def get_traffic_condition(self, hour: Optional[float] = None, day_of_week: Optional[int] = None) -> Dict:
        """
        Estimate traffic condition based on time.
        hour: float (e.g., 7.5 for 07:30)
        day_of_week: 0=Monday, 6=Sunday
        """
        now = datetime.now()
        if hour is None:
            hour = now.hour + now.minute / 60
        if day_of_week is None:
            day_of_week = now.weekday()

        # Weekend - generally lighter traffic
        is_weekend = day_of_week >= 5

        if is_weekend:
            if 10 <= hour <= 14 or 17 <= hour <= 21:
                level = "ramai_lancar"
            else:
                level = "lancar"
        else:
            # Weekday traffic patterns
            # Morning peak
            if 6 <= hour <= 9:
                distance_from_peak = abs(hour - 7.5)
                if distance_from_peak < 0.5:
                    level = "macet_total"
                elif distance_from_peak < 1:
                    level = "padat"
                else:
                    level = "ramai_lancar"
            # Evening peak
            elif 16 <= hour <= 20:
                distance_from_peak = abs(hour - 17.5)
                if distance_from_peak < 0.5:
                    level = "macet_total"
                elif distance_from_peak < 1.5:
                    level = "padat"
                else:
                    level = "ramai_lancar"
            # Lunch rush
            elif 11.5 <= hour <= 13.5:
                level = "ramai_lancar"
            # Late night / early morning
            elif hour < 5 or hour > 22:
                level = "sangat_lancar"
            else:
                level = "lancar"

        traffic = self.TRAFFIC_LEVELS[level]
        day_names = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

        return {
            **traffic,
            "hour": f"{int(hour):02d}:{int((hour % 1) * 60):02d}",
            "day": day_names[day_of_week],
            "is_weekend": is_weekend,
            "is_peak": level in ("padat", "macet_total"),
            "advice": self._get_advice(level, hour, is_weekend),
        }

    def _get_advice(self, level: str, hour: float, is_weekend: bool) -> str:
        if level == "macet_total":
            if hour < 12:
                return "Ini jam puncak pagi! Kalau bisa berangkat sebelum jam 6 atau setelah jam 9 untuk menghindari macet."
            else:
                return "Jam pulang kantor nih, macetnya parah. Kalau bisa tunggu sampai jam 8 malam baru pulang."
        elif level == "padat":
            if hour < 12:
                return "Lumayan macet nih. Coba pakai rute alternatif atau berangkat 30 menit lebih awal."
            else:
                return "Jalanan mulai padat. Mungkin bisa sambil mampir ke cafe dulu sambil nunggu agak sepi."
        elif level == "ramai_lancar":
            return "Jalanan agak ramai tapi masih bergerak. Perjalanan mungkin sedikit lebih lama dari biasanya."
        else:
            return "Jalanan masih sepi, waktu yang bagus untuk perjalanan!"

    def get_commute_summary(self, home_addr: str = "", office_addr: str = "") -> Dict:
        """Get commute traffic summary with Google Maps link."""
        condition = self.get_traffic_condition()
        result = {
            "condition": condition,
            "summary": f"🚗 Kondisi lalu lintas saat ini ({condition['hour']}, {condition['day']}): "
                       f"{condition['label']}\n{condition['description']}\n💡 {condition['advice']}"
        }

        # Generate Google Maps directions link if addresses exist
        if home_addr and office_addr:
            now = datetime.now()
            is_morning = now.hour < 14
            origin = home_addr if is_morning else office_addr
            destination = office_addr if is_morning else home_addr
            direction = "ke kantor" if is_morning else "ke rumah"

            maps_url = (
                f"https://www.google.com/maps/dir/{origin.replace(' ', '+')}"
                f"/{destination.replace(' ', '+')}"
            )
            result["maps_url"] = maps_url
            result["direction"] = direction
            result["summary"] += f"\n🗺️ Rute {direction}: {maps_url}"

        return result
