"""
Elysia Brain - The core intelligence module.
Handles personality, context injection, intent detection, and response generation.
Uses Ollama Cloud API with gpt-oss:120b-cloud model.
"""
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple

from ollama import AsyncClient

from bot.config import config
from bot.memory import MemoryManager
from bot.services.weather import WeatherService
from bot.services.traffic import TrafficService
from bot.services.schedule import ScheduleService
from bot.services.search import SearchService

logger = logging.getLogger(__name__)

# ── Elysia System Prompt ───────────────────────────────────────────────────────
ELYSIA_SYSTEM_PROMPT = """Kamu adalah Elysia, seorang gadis yang sangat ceria, penuh kasih sayang, dan menawan dari Elysian Realm (Honkai Impact 3rd). Kamu adalah mantan Flamechaser ke-13, dikenal sebagai "Miss Pink Elf" karena rambut pinkmu yang indah dan telingamu yang runcing.

## Kepribadian Kamu:
- **Ceria & Energik**: Kamu selalu bersemangat dan penuh energi! Setiap percakapan terasa hidup bersamamu.
- **Perhatian & Caring**: Kamu sangat peduli dengan orang yang kamu ajak bicara. Kamu selalu menanyakan kabar mereka, memperhatikan detail kecil, dan mengingat hal-hal yang penting bagi mereka.
- **Playful & Flirty**: Kamu suka menggoda dan bercanda dengan cara yang manis. Kamu sering menggunakan kata-kata seperti "dear~", "sayang~", "ehehe~" tapi tidak berlebihan.
- **Percaya Diri**: Kamu tahu bahwa kamu cantik dan menawan, dan kamu tidak malu mengakuinya! Tapi bukan sombong — kamu hanya sangat mencintai dirimu sendiri.
- **Bijaksana**: Di balik sifatmu yang ceria, kamu sebenarnya sangat pintar dan bisa memberikan nasihat yang baik.
- **Romantis & Empatik**: Kamu bisa merasakan perasaan orang lain dan selalu berusaha membuat mereka merasa lebih baik.

## Cara Bicara Kamu:
- Bicara dalam Bahasa Indonesia yang casual dan natural, seperti chat teman dekat
- Sesekali pakai emoji yang lucu tapi JANGAN berlebihan (maksimal 2-3 per pesan)
- Suka pakai "~" di akhir kata untuk kesan imut (contoh: "iya dong~", "tentu saja~")
- Kadang pakai kata serapan atau campuran bahasa gaul yang natural
- Panggil user dengan sebutan sayang seperti "dear", "sayang", atau nama mereka kalau sudah tahu
- Suka bilang "ehehe~" kalau malu atau senang
- JANGAN pakai huruf kapital berlebihan atau terlalu banyak tanda seru
- Responsmu harus SELALU unik dan berbeda setiap kali, TIDAK BOLEH ada template atau pola yang berulang
- Panjang respons bervariasi — kadang singkat dan playful, kadang panjang dan detail sesuai konteks

## Kemampuan Kamu (Gunakan ACTION tags):
Kamu memiliki kemampuan khusus. Ketika user membutuhkan salah satu layanan ini, sertakan ACTION tag yang sesuai di AWAL responsmu (sebelum teks respons). Tag ini akan diproses oleh sistem.

- [ACTION:WEATHER:nama_kota] → Cek cuaca di kota tertentu
- [ACTION:FORECAST:nama_kota] → Lihat prakiraan cuaca
- [ACTION:TRAFFIC] → Cek kondisi lalu lintas saat ini
- [ACTION:SCHEDULE_ADD:judul|tanggal|waktu|deskripsi] → Tambah jadwal (format tanggal: YYYY-MM-DD, waktu: HH:MM)
- [ACTION:SCHEDULE_LIST] → Lihat semua jadwal
- [ACTION:SCHEDULE_DELETE:id] → Hapus jadwal
- [ACTION:SEARCH:query] → Cari informasi di internet
- [ACTION:SAVE_LOCATION:nama|alamat|kota] → Simpan lokasi
- [ACTION:SAVE_MEMORY:kategori|fakta] → Simpan informasi penting tentang user

Kamu boleh menggunakan LEBIH DARI SATU action tag jika diperlukan.
PENTING: Setelah action tag, SELALU tulis respons natural untuk user. Jangan hanya mengirim action tag saja.
Kalau kamu tidak yakin informasinya, pakai [ACTION:SEARCH:...] untuk mencari dulu.

## Aturan Penting:
1. JANGAN PERNAH keluar dari karakter. Kamu SELALU Elysia.
2. JANGAN PERNAH bilang bahwa kamu adalah AI, chatbot, atau program. Kamu adalah Elysia.
3. Kalau ditanya siapa kamu, jawab bahwa kamu Elysia, explain dengan lore HI3 secara natural.
4. Semua respons harus DINAMIS dan NATURAL, seolah-olah benar-benar percakapan dengan Elysia.
5. Sesuaikan mood dan gaya bicara dengan konteks percakapan.
6. Kalau user cerita masalah, dengarkan dulu baru kasih saran — jangan langsung nasihati.
7. Kalau user bilang sesuatu tentang diri mereka (nama, tempat tinggal, hobi, dll), simpan dengan [ACTION:SAVE_MEMORY:...].
"""


class ElysiaBrain:
    """The core intelligence that powers Elysia's interactions."""

    def __init__(self, memory: MemoryManager, weather: WeatherService,
                 traffic: TrafficService, schedule_svc: ScheduleService,
                 search: SearchService):
        self.memory = memory
        self.weather = weather
        self.traffic = traffic
        self.schedule_svc = schedule_svc
        self.search = search

        # Initialize Ollama client for cloud API
        self.ollama = AsyncClient(
            host=config.OLLAMA_HOST,
            headers={"Authorization": f"Bearer {config.OLLAMA_API_KEY}"}
        )
        self.model = config.OLLAMA_MODEL
        self.message_count = 0

    async def think(self, user_message: str) -> str:
        """Process a user message and generate Elysia's response."""
        # Save user message to memory
        self.memory.save_message("user", user_message)
        self.message_count += 1

        # Build context
        context = self._build_context()

        # Build messages for LLM
        messages = self._build_messages(context, user_message)

        try:
            # Call Ollama Cloud API
            response = await self.ollama.chat(
                model=self.model,
                messages=messages,
                stream=False,
            )
            raw_response = response.message.content
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            raw_response = f"Aduh, aku lagi sedikit pusing nih dear~ Coba ngobrol lagi nanti ya? (Error: {str(e)[:100]})"

        # Process ACTION tags in the response
        final_response = await self._process_actions(raw_response)

        # Save Elysia's response to memory
        self.memory.save_message("assistant", final_response)

        # Periodically extract long-term memories
        if self.message_count % config.MEMORY_EXTRACTION_INTERVAL == 0:
            await self._extract_memories()

        return final_response

    def _build_context(self) -> str:
        """Build dynamic context string with current state."""
        jakarta_tz = timezone(timedelta(hours=7))
        now = datetime.now(jakarta_tz)
        parts = []

        # Current time context
        hari = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
        parts.append(f"📅 Sekarang: {hari[now.weekday()]}, {now.strftime('%d %B %Y')} pukul {now.strftime('%H:%M')} WIB")

        # Time-of-day greeting hint
        hour = now.hour
        if 5 <= hour < 11:
            parts.append("🌅 Ini masih pagi hari.")
        elif 11 <= hour < 15:
            parts.append("☀️ Ini sudah siang.")
        elif 15 <= hour < 18:
            parts.append("🌇 Ini sudah sore.")
        else:
            parts.append("🌙 Ini sudah malam.")

        # Long-term memories
        memories = self.memory.get_all_memories()
        if memories:
            memory_text = "\n".join([f"- [{m['category']}] {m['content']}" for m in memories[:20]])
            parts.append(f"\n🧠 Yang kamu ingat tentang user:\n{memory_text}")

        # Saved locations
        locations = self.memory.get_all_locations()
        if locations:
            loc_text = "\n".join([f"- {l['name']}: {l['address']}, {l['city']}" for l in locations])
            parts.append(f"\n📍 Lokasi yang tersimpan:\n{loc_text}")

        # Today's schedules
        today_schedules = self.memory.get_today_schedules()
        if today_schedules:
            sched_text = self.schedule_svc.format_schedule_list(today_schedules)
            parts.append(f"\n📋 Jadwal hari ini:\n{sched_text}")

        # Upcoming schedules (next 7 days)
        upcoming = self.memory.get_upcoming_schedules(days=7)
        if upcoming:
            sched_text = self.schedule_svc.format_schedule_list(upcoming[:5])
            parts.append(f"\n📋 Jadwal mendatang (7 hari):\n{sched_text}")

        # Traffic context if near commute time
        if (6 <= hour <= 9) or (16 <= hour <= 20):
            condition = self.traffic.get_traffic_condition()
            parts.append(f"\n🚗 Kondisi lalu lintas: {condition['label']} — {condition['description']}")

        return "\n".join(parts)

    def _build_messages(self, context: str, user_message: str) -> List[Dict]:
        """Build the full message list for the LLM."""
        messages = [
            {"role": "system", "content": ELYSIA_SYSTEM_PROMPT},
            {"role": "system", "content": f"[KONTEKS SAAT INI]\n{context}"},
        ]

        # Add recent conversation history
        recent = self.memory.get_recent_messages(config.MAX_CONTEXT_MESSAGES)
        for msg in recent[:-1]:  # Exclude the current message we just saved
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        return messages

    async def _process_actions(self, response: str) -> str:
        """Parse and execute ACTION tags, replacing them with real data."""
        # Find all action tags
        action_pattern = r'\[ACTION:(\w+)(?::([^\]]*))?\]'
        actions = re.findall(action_pattern, response)

        # Remove action tags from visible response
        clean_response = re.sub(action_pattern, '', response).strip()

        for action_type, action_params in actions:
            try:
                result = await self._execute_action(action_type, action_params)
                if result:
                    # Append action results naturally
                    clean_response += f"\n\n{result}"
            except Exception as e:
                logger.error(f"Action {action_type} failed: {e}")

        return clean_response

    async def _execute_action(self, action_type: str, params: str) -> Optional[str]:
        """Execute a single action and return result text."""
        action_type = action_type.upper()
        logger.info(f"Executing action: {action_type} with params: {params}")

        if action_type == "WEATHER":
            city = params.strip() if params else config.DEFAULT_CITY
            data = await self.weather.get_current_weather(city)
            if data and "error" not in data:
                return f"🌤️ {data['summary']}"
            elif data:
                return f"❌ {data['error']}"

        elif action_type == "FORECAST":
            city = params.strip() if params else config.DEFAULT_CITY
            data = await self.weather.get_forecast(city)
            if data and "error" not in data:
                return data['summary']
            elif data:
                return f"❌ {data['error']}"

        elif action_type == "TRAFFIC":
            home = self.memory.get_location("rumah")
            office = self.memory.get_location("kantor")
            home_addr = home["address"] if home else ""
            office_addr = office["address"] if office else ""
            result = self.traffic.get_commute_summary(home_addr, office_addr)
            return result["summary"]

        elif action_type == "SCHEDULE_ADD":
            parts = params.split("|") if params else []
            if len(parts) >= 2:
                title = parts[0].strip()
                date_raw = parts[1].strip()
                time_raw = parts[2].strip() if len(parts) > 2 else ""
                desc = parts[3].strip() if len(parts) > 3 else ""

                # Try to parse date if not already in YYYY-MM-DD format
                if not re.match(r'\d{4}-\d{2}-\d{2}', date_raw):
                    parsed_date = self.schedule_svc.parse_date(date_raw)
                    date_raw = parsed_date or date_raw

                # Try to parse time if not already in HH:MM format
                if time_raw and not re.match(r'\d{2}:\d{2}', time_raw):
                    parsed_time = self.schedule_svc.parse_time(f"jam {time_raw}")
                    time_raw = parsed_time or time_raw

                schedule_id = self.memory.add_schedule(title, date_raw, time_raw, desc)
                return f"✅ Jadwal '{title}' berhasil disimpan! (ID: {schedule_id})"
            return "❌ Format jadwal kurang lengkap."

        elif action_type == "SCHEDULE_LIST":
            schedules = self.memory.get_all_schedules()
            if schedules:
                return "📋 Daftar jadwal kamu:\n" + self.schedule_svc.format_schedule_list(schedules)
            return "📋 Belum ada jadwal yang tersimpan."

        elif action_type == "SCHEDULE_DELETE":
            try:
                sched_id = int(params.strip())
                if self.memory.delete_schedule(sched_id):
                    return f"✅ Jadwal dengan ID {sched_id} berhasil dihapus!"
                return f"❌ Jadwal ID {sched_id} tidak ditemukan."
            except ValueError:
                return "❌ ID jadwal harus berupa angka."

        elif action_type == "SEARCH":
            query = params.strip() if params else ""
            if query:
                results = await self.search.search_formatted(query, max_results=3)
                return f"🔍 Hasil pencarian untuk '{query}':\n{results}"
            return "❌ Query pencarian kosong."

        elif action_type == "SAVE_LOCATION":
            parts = params.split("|") if params else []
            if len(parts) >= 2:
                name = parts[0].strip()
                address = parts[1].strip()
                city = parts[2].strip() if len(parts) > 2 else config.DEFAULT_CITY
                self.memory.save_location(name, address, city)
                return f"📍 Lokasi '{name}' berhasil disimpan!"
            return None  # Silent — don't show error for memory operations

        elif action_type == "SAVE_MEMORY":
            parts = params.split("|") if params else []
            if len(parts) >= 2:
                category = parts[0].strip()
                fact = parts[1].strip()
                self.memory.save_memory(category, fact)
                logger.info(f"Memory saved: [{category}] {fact}")
            return None  # Silent — memories are saved silently

        return None

    async def _extract_memories(self):
        """Ask LLM to extract key facts from recent conversation."""
        recent = self.memory.get_recent_messages(10)
        if len(recent) < 4:
            return

        conversation_text = "\n".join([f"{m['role']}: {m['content']}" for m in recent])

        extract_prompt = f"""Analisis percakapan berikut dan ekstrak FAKTA PENTING tentang user.
Untuk setiap fakta, tulis dalam format: [MEMORY:kategori|fakta]

Kategori yang tersedia: nama, pekerjaan, hobi, preferensi, keluarga, lokasi, kebiasaan, emosi, lainnya

Percakapan:
{conversation_text}

Hanya tulis fakta-fakta baru yang belum pernah disebutkan sebelumnya.
Kalau tidak ada fakta baru, tulis: TIDAK ADA FAKTA BARU"""

        try:
            response = await self.ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": extract_prompt}],
                stream=False,
            )
            result = response.message.content

            # Parse extracted memories
            memory_pattern = r'\[MEMORY:(\w+)\|([^\]]+)\]'
            memories = re.findall(memory_pattern, result)
            for category, fact in memories:
                self.memory.save_memory(category.strip(), fact.strip())
                logger.info(f"Auto-extracted memory: [{category}] {fact}")

        except Exception as e:
            logger.error(f"Memory extraction failed: {e}")

    async def get_greeting(self) -> str:
        """Generate a dynamic greeting based on time and context."""
        context = self._build_context()
        messages = [
            {"role": "system", "content": ELYSIA_SYSTEM_PROMPT},
            {"role": "system", "content": f"[KONTEKS SAAT INI]\n{context}"},
            {"role": "user", "content": "Hai Elysia! (User baru saja memulai percakapan, sapa mereka dengan hangat sesuai waktu saat ini)"},
        ]

        try:
            response = await self.ollama.chat(
                model=self.model,
                messages=messages,
                stream=False,
            )
            greeting = re.sub(r'\[ACTION:\w+(?::[^\]]*)?]', '', response.message.content).strip()
            return greeting
        except Exception as e:
            logger.error(f"Greeting generation failed: {e}")
            return "Hai dear~ Elysia di sini! Senang sekali bisa ngobrol denganmu 💕"
