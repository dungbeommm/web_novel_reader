"""TTS Module — Edge TTS + Google Translate TTS (gTTS) + Cloud Providers.

Edge TTS: mien phi, khong can API key, chat luong Neural cao.
  - vi-VN-HoaiMyNeural (Nu) — mac dinh
  - vi-VN-NamMinhNeural (Nam)

Google Translate TTS (gTTS): mien phi, khong can API key.
  - Giong tieng Viet tu Google Translate
  - pip install gtts

Cloud TTS (tuy chon, can API key):
  - Google Cloud TTS
  - Azure Cognitive Services TTS
  - OpenAI TTS
  - Gemini TTS (Google)

Module ho tro:
  - MP3 output
  - Dieu chinh toc do
  - Cache audio LRU
  - Export danh sach giong ra JSON
"""

import asyncio
import io
import json
import logging
from typing import Optional

import config
from core.cloud_tts import GoogleCloudTTSProvider, AzureTTSProvider, OpenAITTSProvider
from core.capcut_tts import CapcutTTSProvider, HAS_REQUESTS as HAS_CAPCUT
from core.gemini_tts import GeminiTTSProvider

logger = logging.getLogger(__name__)

# ── Edge TTS ──
HAS_EDGE_TTS = False
try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    logger.warning("edge-tts chua cai dat. Chay: pip install edge-tts")

# ── gTTS (Google Translate TTS — free, no API key) ──
HAS_GTTS = False
try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    logger.info("gtts chua cai dat. Chay: pip install gtts")


def _clamp_speed(speed: float) -> float:
    try:
        speed = float(speed)
    except (TypeError, ValueError):
        return 1.0
    return max(0.5, min(5.0, speed))


def _speed_to_rate_string(speed: float) -> str:
    return f"{(speed - 1.0) * 100:+.0f}%"


def _pitch_to_hz_string(pitch: float) -> str:
    hz = (pitch - 1.0) * 50
    return f"{hz:+.0f}Hz"


# =====================================================================
# Edge TTS Provider
# =====================================================================

class EdgeTTSProvider:
    """Microsoft Edge TTS — giong tieng Viet Neural."""

    VOICES = {
        "vi-VN-HoaiMyNeural": {
            "name": "HoaiMy — Nu (Edge Neural)",
            "gender": "FEMALE",
            "tier": "Neural",
            "language": "vi-VN",
            "provider": "Edge TTS",
            "icon": "edge",
        },
        "vi-VN-NamMinhNeural": {
            "name": "NamMinh — Nam (Edge Neural)",
            "gender": "MALE",
            "tier": "Neural",
            "language": "vi-VN",
            "provider": "Edge TTS",
            "icon": "edge",
        },
    }

    @property
    def voice_list(self) -> list[dict]:
        result = []
        for voice_id, info in self.VOICES.items():
            result.append({
                "voice_id": f"edge:{voice_id}",
                "name": info["name"],
                "gender": info["gender"],
                "tier": info["tier"],
                "language": info["language"],
                "provider": info["provider"],
                "icon": info["icon"],
                "needs_api_key": False,
            })
        return result

    def get_default_voice(self) -> str:
        return "edge:vi-VN-HoaiMyNeural"

    async def synthesize(
        self, text: str, voice_id: str, speed: float = 1.0, **kwargs
    ) -> Optional[bytes]:
        if not HAS_EDGE_TTS:
            logger.error("Edge TTS chua cai dat")
            return None
        if voice_id not in self.VOICES:
            logger.error(f"Voice khong ton tai: {voice_id}")
            return None

        text = (text or "").strip()
        if not text:
            return None

        speed = _clamp_speed(speed)
        rate = _speed_to_rate_string(speed)
        pitch_val = max(0.5, min(2.0, float(kwargs.get("pitch", 1.0))))
        pitch = _pitch_to_hz_string(pitch_val)

        try:
            communicate = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch)
            audio_buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])
            data = audio_buffer.getvalue()
            return data or None
        except Exception as e:
            logger.error(f"Edge TTS loi ({voice_id}): {e}")
            return None


# =====================================================================
# Google Translate TTS Provider (gTTS) — Free, no API key
# =====================================================================

class GttsTTSProvider:
    """Google Translate TTS — giong tieng Viet mien phi, khong can API key.

    Su dung thu vien gTTS (pip install gtts) de truy cap Google Translate
    TTS API. Ho tro nhieu ngon ngu, bao gom tieng Viet (vi).
    Chat luong: Standard (giong Google Translate).
    """

    VOICES = {
        "vi": {
            "name": "Google Translate — Tiếng Việt",
            "gender": "FEMALE",
            "tier": "Standard",
            "language": "vi-VN",
            "provider": "Google TTS (Free)",
            "icon": "gtts",
        },
        "vi-tld-com.vn": {
            "name": "Google TTS — Tiếng Việt (VN)",
            "gender": "FEMALE",
            "tier": "Standard",
            "language": "vi-VN",
            "provider": "Google TTS (Free)",
            "icon": "gtts",
        },
    }

    TLD_MAP = {
        "vi": "com",
        "vi-tld-com.vn": "com.vn",
    }

    @property
    def voice_list(self) -> list[dict]:
        if not HAS_GTTS:
            return []
        result = []
        for voice_id, info in self.VOICES.items():
            result.append({
                "voice_id": f"gtts:{voice_id}",
                "name": info["name"],
                "gender": info["gender"],
                "tier": info["tier"],
                "language": info["language"],
                "provider": info["provider"],
                "icon": info["icon"],
                "needs_api_key": False,
            })
        return result

    def get_default_voice(self) -> str:
        return "gtts:vi" if HAS_GTTS else ""

    async def synthesize(
        self, text: str, voice_id: str, speed: float = 1.0, **kwargs
    ) -> Optional[bytes]:
        if not HAS_GTTS:
            logger.error("gTTS chua cai dat")
            return None

        text = (text or "").strip()
        if not text:
            return None

        tld = self.TLD_MAP.get(voice_id, "com")
        speed = _clamp_speed(speed)
        slow = speed < 0.8

        try:
            def _do_gtts():
                tts = gTTS(text=text, lang="vi", tld=tld, slow=slow)
                buf = io.BytesIO()
                tts.write_to_fp(buf)
                return buf.getvalue()

            data = await asyncio.to_thread(_do_gtts)
            return data or None
        except Exception as e:
            logger.error(f"gTTS loi ({voice_id}): {e}")
            return None


# =====================================================================
# Combined TTS Manager — Edge (primary) + Cloud TTS
# =====================================================================

class TTSManager:
    """Quan ly tat ca TTS providers: Edge TTS + gTTS + CapCut + Cloud TTS."""

    def __init__(self):
        self.edge = EdgeTTSProvider()
        self.gtts_prov = GttsTTSProvider()
        self.capcut_prov = CapcutTTSProvider()

        self._cloud_providers: dict[str, object] = {}
        gcloud = GoogleCloudTTSProvider(config.GOOGLE_TTS_API_KEY)
        if gcloud.is_configured():
            self._cloud_providers["gcloud"] = gcloud
        azure = AzureTTSProvider(config.AZURE_TTS_KEY, config.AZURE_TTS_REGION)
        if azure.is_configured():
            self._cloud_providers["azure"] = azure
        openai_prov = OpenAITTSProvider(config.OPENAI_API_KEY)
        if openai_prov.is_configured():
            self._cloud_providers["openai"] = openai_prov
        gemini_prov = GeminiTTSProvider(config.GEMINI_API_KEY)
        if gemini_prov.is_configured():
            self._cloud_providers["gemini"] = gemini_prov

    async def ensure_probed(self) -> bool:
        return True

    async def get_all_voices(self) -> dict[str, dict]:
        voices: dict[str, dict] = {}
        for v in self.edge.voice_list:
            voices[v["voice_id"]] = v
        for v in self.gtts_prov.voice_list:
            voices[v["voice_id"]] = v
        for v in self.capcut_prov.voice_list:
            voices[v["voice_id"]] = v
        for prov in self._cloud_providers.values():
            for v in prov.voice_list:
                voices[v["voice_id"]] = v
        return voices

    @property
    def voice_list(self) -> list[dict]:
        result = list(self.edge.voice_list)
        result.extend(self.gtts_prov.voice_list)
        result.extend(self.capcut_prov.voice_list)
        for prov in self._cloud_providers.values():
            result.extend(prov.voice_list)
        return result

    def default_voice(self) -> str:
        return self.edge.get_default_voice()

    async def synthesize(
        self, text: str, voice_key: str, speed: float = 1.0, **kwargs
    ) -> Optional[bytes]:
        if not voice_key or ":" not in voice_key:
            voice_key = self.default_voice()
            if not voice_key:
                return None

        provider, voice_id = voice_key.split(":", 1)

        if provider == "edge":
            return await self.edge.synthesize(text, voice_id, speed, **kwargs)
        if provider == "gtts":
            return await self.gtts_prov.synthesize(text, voice_id, speed, **kwargs)
        if provider == "capcut":
            return await self.capcut_prov.synthesize(text, voice_id, speed, **kwargs)
        if provider in self._cloud_providers:
            return await self._cloud_providers[provider].synthesize(
                text, voice_key, speed, **kwargs
            )

        logger.warning(f"Provider '{provider}' not available, falling back to Edge TTS")
        default_voice = self.edge.get_default_voice().split(":", 1)[-1]
        return await self.edge.synthesize(text, default_voice, speed)

    async def synthesize_to_file(
        self, text: str, output_path: str, voice_key: str,
        speed: float = 1.0, **kwargs
    ) -> bool:
        audio_data = await self.synthesize(text, voice_key, speed, **kwargs)
        if not audio_data:
            return False
        try:
            with open(output_path, "wb") as f:
                f.write(audio_data)
            return True
        except Exception as e:
            logger.error(f"Khong the ghi file {output_path}: {e}")
            return False

    def export_all_to_json(self) -> str:
        voices = {v["voice_id"]: v for v in self.voice_list}

        provider_names = ["Edge TTS (Microsoft Neural)", "Google TTS (Free)", "CapCut TTS"]
        cloud_names = {"gcloud": "Google Cloud TTS", "azure": "Azure TTS", "openai": "OpenAI TTS", "gemini": "Gemini TTS"}
        for key in self._cloud_providers:
            provider_names.append(cloud_names.get(key, key))

        return json.dumps({
            "providers": provider_names,
            "defaultVoice": self.default_voice(),
            "totalVoices": len(voices),
            "cloudProviders": list(self._cloud_providers.keys()),
            "voices": voices,
        }, ensure_ascii=False, indent=2)


# =====================================================================
# Singleton
# =====================================================================

_tts_instance: Optional[TTSManager] = None


def get_tts() -> TTSManager:
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = TTSManager()
    return _tts_instance
