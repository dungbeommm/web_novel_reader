"""Cloud TTS Providers — Google Cloud, Azure, OpenAI.

Mỗi provider chỉ active khi có API key tương ứng (env var).
Tất cả trả về bytes MP3.
"""

import io
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

HAS_HTTPX = False
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    pass


class GoogleCloudTTSProvider:
    """Google Cloud Text-to-Speech API."""

    VOICES = {
        "gcloud:vi-VN-Neural2-A": {
            "name": "Google Neural2-A — Nữ, tự nhiên, đọc tin tức tốt",
            "gender": "FEMALE",
            "tier": "Neural2",
            "language": "vi-VN",
            "provider": "Google Cloud",
            "icon": "google",
            "needs_api_key": True,
        },
        "gcloud:vi-VN-Neural2-D": {
            "name": "Google Neural2-D — Nam, rõ ràng, ít robot",
            "gender": "MALE",
            "tier": "Neural2",
            "language": "vi-VN",
            "provider": "Google Cloud",
            "icon": "google",
            "needs_api_key": True,
        },
        "gcloud:vi-VN-Standard-A": {
            "name": "Google Standard-A — Nữ",
            "gender": "FEMALE",
            "tier": "Standard",
            "language": "vi-VN",
            "provider": "Google Cloud",
            "icon": "google",
            "needs_api_key": True,
        },
        "gcloud:vi-VN-Standard-B": {
            "name": "Google Standard-B — Nam",
            "gender": "MALE",
            "tier": "Standard",
            "language": "vi-VN",
            "provider": "Google Cloud",
            "icon": "google",
            "needs_api_key": True,
        },
        "gcloud:vi-VN-Wavenet-A": {
            "name": "Google WaveNet-A — Nữ, giọng phổ biến nhất",
            "gender": "FEMALE",
            "tier": "WaveNet",
            "language": "vi-VN",
            "provider": "Google Cloud",
            "icon": "google",
            "needs_api_key": True,
        },
        "gcloud:vi-VN-Wavenet-B": {
            "name": "Google WaveNet-B — Nam",
            "gender": "MALE",
            "tier": "WaveNet",
            "language": "vi-VN",
            "provider": "Google Cloud",
            "icon": "google",
            "needs_api_key": True,
        },
        "gcloud:vi-VN-Wavenet-C": {
            "name": "Google WaveNet-C — Nữ",
            "gender": "FEMALE",
            "tier": "WaveNet",
            "language": "vi-VN",
            "provider": "Google Cloud",
            "icon": "google",
            "needs_api_key": True,
        },
        "gcloud:vi-VN-Wavenet-D": {
            "name": "Google WaveNet-D — Nam, phù hợp video thuyết minh",
            "gender": "MALE",
            "tier": "WaveNet",
            "language": "vi-VN",
            "provider": "Google Cloud",
            "icon": "google",
            "needs_api_key": True,
        },
        "gcloud:vi-VN-Chirp3-HD-Aoede": {
            "name": "Google Chirp3-HD Aoede — Nữ, rất giống giọng người thật",
            "gender": "FEMALE",
            "tier": "Chirp3-HD",
            "language": "vi-VN",
            "provider": "Google Cloud",
            "icon": "google",
            "needs_api_key": True,
        },
        "gcloud:vi-VN-Chirp3-HD-Puck": {
            "name": "Google Chirp3-HD Puck — Nam, hội thoại tự nhiên",
            "gender": "MALE",
            "tier": "Chirp3-HD",
            "language": "vi-VN",
            "provider": "Google Cloud",
            "icon": "google",
            "needs_api_key": True,
        },
        "gcloud:vi-VN-Chirp3-HD-Charon": {
            "name": "Google Chirp3-HD Charon — Nam, trầm hơn",
            "gender": "MALE",
            "tier": "Chirp3-HD",
            "language": "vi-VN",
            "provider": "Google Cloud",
            "icon": "google",
            "needs_api_key": True,
        },
    }

    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    def is_configured(self) -> bool:
        return bool(self._api_key)

    @property
    def voice_list(self) -> list[dict]:
        if not self.is_configured():
            return []
        result = []
        for voice_id, info in self.VOICES.items():
            result.append({"voice_id": voice_id, **info})
        return result

    async def synthesize(
        self, text: str, voice_id: str, speed: float = 1.0, **kwargs
    ) -> Optional[bytes]:
        if not self.is_configured() or not HAS_HTTPX:
            return None

        voice_name = voice_id.replace("gcloud:", "", 1)
        pitch = kwargs.get("pitch", 1.0)
        is_chirp = "Chirp3" in voice_name

        if is_chirp:
            body = {
                "input": {"text": text},
                "voice": {
                    "languageCode": "vi-VN",
                    "name": voice_name,
                },
                "audioConfig": {
                    "audioEncoding": "MP3",
                    "speakingRate": speed,
                },
            }
            url = f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={self._api_key}"
        else:
            pitch_semitones = (pitch - 1.0) * 20
            body = {
                "input": {"text": text},
                "voice": {
                    "languageCode": "vi-VN",
                    "name": voice_name,
                },
                "audioConfig": {
                    "audioEncoding": "MP3",
                    "speakingRate": speed,
                    "pitch": pitch_semitones,
                },
            }
            url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={self._api_key}"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=body)
                if resp.status_code != 200:
                    logger.error(f"Google Cloud TTS error: {resp.status_code} {resp.text[:200]}")
                    return None
                import base64
                audio_content = resp.json().get("audioContent", "")
                return base64.b64decode(audio_content) if audio_content else None
        except Exception as e:
            logger.error(f"Google Cloud TTS error: {e}")
            return None


class AzureTTSProvider:
    """Microsoft Azure Cognitive Services TTS."""

    VOICES = {
        "azure:vi-VN-HoaiMyNeural": {
            "name": "Azure HoaiMy — Nữ (Neural)",
            "gender": "FEMALE",
            "tier": "Neural",
            "language": "vi-VN",
            "provider": "Azure",
            "icon": "azure",
            "needs_api_key": True,
        },
        "azure:vi-VN-NamMinhNeural": {
            "name": "Azure NamMinh — Nam (Neural)",
            "gender": "MALE",
            "tier": "Neural",
            "language": "vi-VN",
            "provider": "Azure",
            "icon": "azure",
            "needs_api_key": True,
        },
    }

    def __init__(self, api_key: str = "", region: str = "southeastasia"):
        self._api_key = api_key
        self._region = region

    def is_configured(self) -> bool:
        return bool(self._api_key)

    @property
    def voice_list(self) -> list[dict]:
        if not self.is_configured():
            return []
        result = []
        for voice_id, info in self.VOICES.items():
            result.append({"voice_id": voice_id, **info})
        return result

    async def synthesize(
        self, text: str, voice_id: str, speed: float = 1.0, **kwargs
    ) -> Optional[bytes]:
        if not self.is_configured() or not HAS_HTTPX:
            return None

        voice_name = voice_id.replace("azure:", "", 1)
        pitch = kwargs.get("pitch", 1.0)
        rate_pct = f"{(speed - 1.0) * 100:+.0f}%"
        pitch_hz = f"{(pitch - 1.0) * 50:+.0f}Hz"

        ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='vi-VN'>
  <voice name='{voice_name}'>
    <prosody rate='{rate_pct}' pitch='{pitch_hz}'>{text}</prosody>
  </voice>
</speak>"""

        url = f"https://{self._region}.tts.speech.microsoft.com/cognitiveservices/v1"
        headers = {
            "Ocp-Apim-Subscription-Key": self._api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, content=ssml, headers=headers)
                if resp.status_code != 200:
                    logger.error(f"Azure TTS error: {resp.status_code}")
                    return None
                return resp.content or None
        except Exception as e:
            logger.error(f"Azure TTS error: {e}")
            return None


class OpenAITTSProvider:
    """OpenAI TTS API (tts-1, tts-1-hd)."""

    VOICES = {
        "openai:alloy": {
            "name": "OpenAI Alloy — Đa ngôn ngữ",
            "gender": "NEUTRAL",
            "tier": "Neural",
            "language": "multilingual",
            "provider": "OpenAI",
            "icon": "openai",
            "needs_api_key": True,
        },
        "openai:echo": {
            "name": "OpenAI Echo — Nam, trầm",
            "gender": "MALE",
            "tier": "Neural",
            "language": "multilingual",
            "provider": "OpenAI",
            "icon": "openai",
            "needs_api_key": True,
        },
        "openai:fable": {
            "name": "OpenAI Fable — Đa ngôn ngữ",
            "gender": "NEUTRAL",
            "tier": "Neural",
            "language": "multilingual",
            "provider": "OpenAI",
            "icon": "openai",
            "needs_api_key": True,
        },
        "openai:nova": {
            "name": "OpenAI Nova — Nữ, ấm áp",
            "gender": "FEMALE",
            "tier": "Neural",
            "language": "multilingual",
            "provider": "OpenAI",
            "icon": "openai",
            "needs_api_key": True,
        },
        "openai:onyx": {
            "name": "OpenAI Onyx — Nam, sâu",
            "gender": "MALE",
            "tier": "Neural",
            "language": "multilingual",
            "provider": "OpenAI",
            "icon": "openai",
            "needs_api_key": True,
        },
        "openai:shimmer": {
            "name": "OpenAI Shimmer — Nữ, rõ ràng",
            "gender": "FEMALE",
            "tier": "Neural",
            "language": "multilingual",
            "provider": "OpenAI",
            "icon": "openai",
            "needs_api_key": True,
        },
    }

    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    def is_configured(self) -> bool:
        return bool(self._api_key)

    @property
    def voice_list(self) -> list[dict]:
        if not self.is_configured():
            return []
        result = []
        for voice_id, info in self.VOICES.items():
            result.append({"voice_id": voice_id, **info})
        return result

    async def synthesize(
        self, text: str, voice_id: str, speed: float = 1.0, **kwargs
    ) -> Optional[bytes]:
        if not self.is_configured() or not HAS_HTTPX:
            return None

        pitch = kwargs.get("pitch", 1.0)
        if pitch != 1.0:
            logger.info(f"OpenAI TTS does not support pitch adjustment (pitch={pitch} ignored)")

        voice_name = voice_id.replace("openai:", "", 1)
        body = {
            "model": "tts-1",
            "input": text,
            "voice": voice_name,
            "speed": speed,
            "response_format": "mp3",
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/audio/speech",
                    json=body,
                    headers=headers,
                )
                if resp.status_code != 200:
                    logger.error(f"OpenAI TTS error: {resp.status_code} {resp.text[:200]}")
                    return None
                return resp.content or None
        except Exception as e:
            logger.error(f"OpenAI TTS error: {e}")
            return None
