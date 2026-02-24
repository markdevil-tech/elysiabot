"""
Weather service using OpenWeatherMap free API.
"""
import aiohttp
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

WEATHER_EMOJIS = {
    "Clear": "☀️",
    "Clouds": "☁️",
    "Rain": "🌧️",
    "Drizzle": "🌦️",
    "Thunderstorm": "⛈️",
    "Snow": "🌨️",
    "Mist": "🌫️",
    "Fog": "🌫️",
    "Haze": "🌫️",
    "Smoke": "🌫️",
}


class WeatherService:
    BASE_URL = "https://api.openweathermap.org/data/2.5"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def get_current_weather(self, city: str = "Jakarta") -> Optional[Dict]:
        """Get current weather for a city."""
        if not self.api_key:
            return {"error": "API key belum diset. Minta owner set OPENWEATHER_API_KEY."}

        try:
            url = f"{self.BASE_URL}/weather"
            params = {
                "q": city,
                "appid": self.api_key,
                "units": "metric",
                "lang": "id"
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return {"error": f"Gagal ambil data cuaca (HTTP {resp.status})"}
                    data = await resp.json()

            main_weather = data["weather"][0]["main"]
            emoji = WEATHER_EMOJIS.get(main_weather, "🌤️")

            return {
                "city": data["name"],
                "temp": round(data["main"]["temp"]),
                "feels_like": round(data["main"]["feels_like"]),
                "humidity": data["main"]["humidity"],
                "description": data["weather"][0]["description"],
                "main": main_weather,
                "emoji": emoji,
                "wind_speed": round(data["wind"]["speed"] * 3.6, 1),  # m/s to km/h
                "summary": (
                    f"{emoji} {data['name']}: {data['weather'][0]['description']}, "
                    f"suhu {round(data['main']['temp'])}°C (terasa {round(data['main']['feels_like'])}°C), "
                    f"kelembapan {data['main']['humidity']}%, "
                    f"angin {round(data['wind']['speed'] * 3.6, 1)} km/jam"
                )
            }
        except Exception as e:
            logger.error(f"Weather API error: {e}")
            return {"error": f"Gagal mengambil data cuaca: {str(e)}"}

    async def get_forecast(self, city: str = "Jakarta", hours: int = 12) -> Optional[Dict]:
        """Get weather forecast."""
        if not self.api_key:
            return {"error": "API key belum diset."}

        try:
            url = f"{self.BASE_URL}/forecast"
            params = {
                "q": city,
                "appid": self.api_key,
                "units": "metric",
                "lang": "id",
                "cnt": hours // 3  # API returns data in 3-hour intervals
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return {"error": f"Gagal ambil forecast (HTTP {resp.status})"}
                    data = await resp.json()

            forecasts = []
            for item in data["list"]:
                main_weather = item["weather"][0]["main"]
                emoji = WEATHER_EMOJIS.get(main_weather, "🌤️")
                forecasts.append({
                    "time": item["dt_txt"],
                    "temp": round(item["main"]["temp"]),
                    "description": item["weather"][0]["description"],
                    "emoji": emoji,
                })

            summary_parts = [f"{f['time'].split(' ')[1][:5]} {f['emoji']} {f['temp']}°C {f['description']}" for f in forecasts]
            return {
                "city": data["city"]["name"],
                "forecasts": forecasts,
                "summary": f"Prakiraan cuaca {data['city']['name']}:\n" + "\n".join(summary_parts)
            }
        except Exception as e:
            logger.error(f"Forecast API error: {e}")
            return {"error": str(e)}
