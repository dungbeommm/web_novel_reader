"""Gemini TTS Provider — Google Gemini 2.5 Flash TTS.

Sử dụng Gemini generateContent API với speechConfig để tạo audio.
Cần GEMINI_API_KEY (env var). Trả về bytes WAV → convert sang MP3.

Voices: Aoede, Charon, Fenrir, Kore, Puck (đa ngôn ngữ, hỗ trợ tiếng Việt).
Model: gemini-2.5-flash-preview-tts
"""

import asyncio
import base64
import io
import json
import logging
import struct
import wave
from typing import Optional

logger = logging.getLogger(__name__)

HAS_HTTPX = False
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    pass

HAS_PYDUB = False
try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    pass

GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Retry config
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0
REQUEST_TIMEOUT = 60

# Throttle config — tránh vượt rate limit
MAX_CONCURRENT = 2        # Số request đồng thời tối đa
MIN_INTERVAL = 0.5        # Khoảng cách tối thiểu giữa các request (giây)
_semaphore: Optional[asyncio.Semaphore] = None
_last_request_time = 0.0
_throttle_lock: Optional[asyncio.Lock] = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    return _semaphore


def _get_throttle_lock() -> asyncio.Lock:
    global _throttle_lock
    if _throttle_lock is None:
        _throttle_lock = asyncio.Lock()
    return _throttle_lock


async def _throttle():
    """Đảm bảo khoảng cách tối thiểu giữa các request."""
    global _last_request_time
    lock = _get_throttle_lock()
    async with lock:
        import time
        now = time.monotonic()
        elapsed = now - _last_request_time
        if elapsed < MIN_INTERVAL:
            await asyncio.sleep(MIN_INTERVAL - elapsed)
        _last_request_time = time.monotonic()


def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bytes:
    """Chuyển raw PCM (Linear16) sang WAV."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def _wav_to_mp3(wav_data: bytes) -> Optional[bytes]:
    """Chuyển WAV sang MP3 bằng pydub (cần ffmpeg)."""
    if not HAS_PYDUB:
        return None
    try:
        audio = AudioSegment.from_wav(io.BytesIO(wav_data))
        buf = io.BytesIO()
        audio.export(buf, format="mp3", bitrate="128k")
        return buf.getvalue()
    except Exception as e:
        logger.error(f"Gemini TTS: wav_to_mp3 error: {e}")
        return None


class GeminiTTSProvider:
    """Google Gemini TTS — sử dụng model gemini-2.5-flash-preview-tts."""

    VOICES = {
        "gemini:Kore": {
            "name": "Gemini Kore — Nữ, tự nhiên",
            "gender": "FEMALE",
            "tier": "Gemini AI",
            "language": "multilingual",
            "provider": "Gemini",
            "icon": "gemini",
            "needs_api_key": True,
        },
        "gemini:Aoede": {
            "name": "Gemini Aoede — Nữ, ấm áp",
            "gender": "FEMALE",
            "tier": "Gemini AI",
            "language": "multilingual",
            "provider": "Gemini",
            "icon": "gemini",
            "needs_api_key": True,
        },
        "gemini:Puck": {
            "name": "Gemini Puck — Nam, hội thoại",
            "gender": "MALE",
            "tier": "Gemini AI",
            "language": "multilingual",
            "provider": "Gemini",
            "icon": "gemini",
            "needs_api_key": True,
        },
        "gemini:Charon": {
            "name": "Gemini Charon — Nam, trầm",
            "gender": "MALE",
            "tier": "Gemini AI",
            "language": "multilingual",
            "provider": "Gemini",
            "icon": "gemini",
            "needs_api_key": True,
        },
        "gemini:Fenrir": {
            "name": "Gemini Fenrir — Nam, sâu",
            "gender": "MALE",
            "tier": "Gemini AI",
            "language": "multilingual",
            "provider": "Gemini",
            "icon": "gemini",
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
        if not self.is_configured():
            logger.error("Gemini TTS: GEMINI_API_KEY chưa cấu hình")
            return None
        if not HAS_HTTPX:
            logger.error("Gemini TTS: httpx chưa cài đặt")
            return None

        text = (text or "").strip()
        if not text:
            return None

        voice_name = voice_id.replace("gemini:", "", 1)
        if not any(voice_id == vid for vid in self.VOICES):
            logger.error(f"Gemini TTS: voice không hợp lệ: {voice_id}")
            return None

        url = GEMINI_API_URL.format(model=GEMINI_TTS_MODEL)
        url = f"{url}?key={self._api_key}"

        body = {
            "contents": [
                {
                    "parts": [
                        {"text": text}
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice_name
                        }
                    }
                }
            }
        }

        # Retry loop với exponential backoff + throttle
        last_error = None
        sem = _get_semaphore()
        for attempt in range(MAX_RETRIES):
            async with sem:
                await _throttle()
                try:
                    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                        resp = await client.post(url, json=body)

                        if resp.status_code == 429:
                            wait = RETRY_BACKOFF ** attempt
                            logger.warning(f"Gemini TTS: rate limited, retry sau {wait}s (lần {attempt + 1}/{MAX_RETRIES})")
                            await asyncio.sleep(wait)
                            continue

                        if resp.status_code != 200:
                            error_text = resp.text[:300]
                            logger.error(f"Gemini TTS: HTTP {resp.status_code} — {error_text}")
                            if resp.status_code in (400, 401, 403):
                                return None
                            last_error = f"HTTP {resp.status_code}"
                            await asyncio.sleep(RETRY_BACKOFF ** attempt)
                            continue

                        result = resp.json()
                        return self._extract_audio(result)

                except httpx.TimeoutException:
                    last_error = "timeout"
                    logger.warning(f"Gemini TTS: timeout (lần {attempt + 1}/{MAX_RETRIES})")
                    await asyncio.sleep(RETRY_BACKOFF ** attempt)
                except Exception as e:
                    last_error = str(e)
                    logger.error(f"Gemini TTS: lỗi request (lần {attempt + 1}/{MAX_RETRIES}): {e}")
                    await asyncio.sleep(RETRY_BACKOFF ** attempt)

        logger.error(f"Gemini TTS: thất bại sau {MAX_RETRIES} lần thử. Lỗi cuối: {last_error}")
        return None

    def _extract_audio(self, response: dict) -> Optional[bytes]:
        """Trích xuất audio từ Gemini API response, convert sang MP3."""
        try:
            candidates = response.get("candidates", [])
            if not candidates:
                logger.error("Gemini TTS: response không có candidates")
                return None

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                logger.error("Gemini TTS: response không có parts")
                return None

            inline_data = parts[0].get("inlineData", {})
            audio_b64 = inline_data.get("data", "")
            mime_type = inline_data.get("mimeType", "")

            if not audio_b64:
                logger.error("Gemini TTS: response không có audio data")
                return None

            raw_audio = base64.b64decode(audio_b64)

            # Gemini trả về PCM Linear16 24kHz
            if "L16" in mime_type or "pcm" in mime_type.lower() or "audio/L16" in mime_type:
                wav_data = _pcm_to_wav(raw_audio, sample_rate=24000)
                mp3_data = _wav_to_mp3(wav_data)
                if mp3_data:
                    return mp3_data
                # Fallback: trả WAV nếu không convert được MP3
                return wav_data

            # Nếu response đã là WAV
            if mime_type.startswith("audio/wav") or raw_audio[:4] == b"RIFF":
                mp3_data = _wav_to_mp3(raw_audio)
                if mp3_data:
                    return mp3_data
                return raw_audio

            # Nếu response đã là MP3
            if mime_type == "audio/mpeg" or raw_audio[:3] == b"ID3" or raw_audio[:2] == b"\xff\xfb":
                return raw_audio

            # Mặc định: coi là PCM raw → WAV → MP3
            wav_data = _pcm_to_wav(raw_audio, sample_rate=24000)
            mp3_data = _wav_to_mp3(wav_data)
            return mp3_data or wav_data

        except Exception as e:
            logger.error(f"Gemini TTS: lỗi extract audio: {e}")
            return None
