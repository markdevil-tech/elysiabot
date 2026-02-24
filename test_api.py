"""Quick test to verify Ollama Cloud API connectivity."""
import asyncio
from ollama import AsyncClient


async def test():
    client = AsyncClient(
        host="https://api.ollama.com",
        headers={"Authorization": "Bearer 249a09425b0f4871bd091a3303a1178e.MIiRZMuorlzttUcMpuXnI244"}
    )
    try:
        response = await client.chat(
            model="gpt-oss:120b-cloud",
            messages=[{"role": "user", "content": "Say hi in one word"}],
            stream=False,
        )
        print(f"✅ API OK: {response.message.content[:100]}")
    except Exception as e:
        print(f"❌ API Error: {e}")


asyncio.run(test())
