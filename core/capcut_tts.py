"""CapCut TTS Provider — Free TTS using CapCut's API.

Uses the CapCut common_task API to synthesize text to speech.
No API key required. Supports many Vietnamese voices.

Flow: build SSML -> sign payload with RSA -> POST /lv/v1/common_task/new
     -> poll /lv/v1/common_task/query -> extract audio URL -> download MP3.

Based on https://github.com/K07VN/capcut-tts-api
"""

import asyncio
import base64
import hashlib
import json
import logging
import random
import secrets
import time
import uuid
from copy import deepcopy
from typing import Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

HAS_REQUESTS = False
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    logger.info("requests chua cai dat. Chay: pip install requests")

BASE = "https://editor-api-sg.capcutapi.com"

DEFAULT_DEVICE = {
    "aid": "359289",
    "app_name": "CapCut",
    "appvr": "8.7.0",
    "version_name": "8.7.0",
    "version_code": "8.7.0",
    "channel": "capcutpc_google",
    "device_platform": "mac",
    "device_type": "MacBookPro17,1",
    "device_brand": "MacBookPro17,1",
    "os_version": "15.7.4",
    "device_id": "7647183892936328721",
    "iid": "7647185302080423697",
    "region": "VN",
    "loc": "VN",
    "lan": "vi-VN",
    "pf": "3",
    "tdid": "7647183892936328721",
}

TTS_SIGN_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAmTd34Lw4b7IuldSXh/zY
CMla+ITdGG5TeWz6ad+OySd4r+IrY45AoqrYUxhQ2dl+7z+i7r/5vEa8rr39BYfB
8AGMQLmZA8HmgpWBsqrn/V6daUALkKnkLb70Fn32CJigIuGXAYqxUdGuI340aC+0
v5Es3puJsHyzf01/AelE4Cdc6bZhQrASJLBh8R3BQToYClmDVSDUQk28o8sl/guA
Z4n303Vj+6Siv1HayPCdV6kpVVnMBAG4+umUbwGmn132N3fgpzLarFF3XyWmS1zh
D/J07iM/rP8GDO9IskHNHd2phrO0G6KzrcFAnTBHjVv+hCBEfzN/no3FNA9AuC36
mwIDAQAB
-----END PUBLIC KEY-----"""

# Vietnamese voices from Voice.json
CAPCUT_VI_VOICES = {
    "BV421_vivn_streaming": {
        "name": "Nhỏ Ngọt Ngào",
        "resource_id": "7252594014782755330",
        "gender": "FEMALE",
    },
    "vi_female_huong": {
        "name": "Giọng Nữ Phổ Thông",
        "resource_id": "7264854897953083905",
        "gender": "FEMALE",
    },
    "BV074_streaming_dsp": {
        "name": "Giọng Bé",
        "resource_id": "7550087831092251920",
        "gender": "FEMALE",
    },
    "BV074_streaming": {
        "name": "Cô Gái Hoạt Ngôn",
        "resource_id": "7102355709945188865",
        "gender": "FEMALE",
    },
    "vi-VN-HoaiMyNeural": {
        "name": "Hoai My (CapCut)",
        "resource_id": "7371666434650280464",
        "gender": "FEMALE",
    },
    "vi-VN-NamMinhNeural": {
        "name": "Nam Minh (CapCut)",
        "resource_id": "7371666524727153168",
        "gender": "MALE",
    },
    "BV075_streaming_vibrato_dsp": {
        "name": "Việt Méo",
        "resource_id": "7569450639810465040",
        "gender": "MALE",
    },
    "BV562_streaming": {
        "name": "Mai",
        "resource_id": "7483736254694035984",
        "gender": "FEMALE",
    },
    "multi_female_yangguangnv_uranus_bigtts": {
        "name": "Ban Mai",
        "resource_id": "7637456432522218773",
        "gender": "FEMALE",
    },
    "multi_female_richgirl_uranus_bigtts": {
        "name": "Review Phim new",
        "resource_id": "7637460351541447956",
        "gender": "FEMALE",
    },
    "multi_female_quanweinv_uranus_bigtts": {
        "name": "Bản Tin 1",
        "resource_id": "7637458743197732117",
        "gender": "FEMALE",
    },
    "multi_female_stokie_uranus_bigtts": {
        "name": "Review Phim 4",
        "resource_id": "7637456729696996628",
        "gender": "FEMALE",
    },
    "multi_female_sisi_uranus_bigtts": {
        "name": "Bản Tin nữ",
        "resource_id": "7637455857285860629",
        "gender": "FEMALE",
    },
    "multi_female_daqi_uranus_bigtts": {
        "name": "Review Phim 3",
        "resource_id": "7637451983389019409",
        "gender": "FEMALE",
    },
    "multi_female_kiwi_uranus_bigtts": {
        "name": "Sunny Idol",
        "resource_id": "7637457995882089749",
        "gender": "FEMALE",
    },
    "BV075_streaming_demon_dsp": {
        "name": "Kenny Đại Đế",
        "resource_id": "7569442422665661712",
        "gender": "MALE",
    },
    "BV075_streaming_robot_dsp": {
        "name": "Robot VN",
        "resource_id": "7538698409633516816",
        "gender": "MALE",
    },
    "multi_male_felipe_uranus_bigtts": {
        "name": "Giọng Nam Trầm",
        "resource_id": "7637456729696996628",
        "gender": "MALE",
    },
    "multi_female_peiqi_uranus_bigtts": {
        "name": "Giọng Gái Mới Lớn",
        "resource_id": "7637458789033151751",
        "gender": "FEMALE",
    },
    "multi_female_xinwenjieshuo_uranus_bigtts": {
        "name": "Nam bản tin",
        "resource_id": "7637455039719640327",
        "gender": "MALE",
    },
    "multi_female_tianmeijieshuo_uranus_bigtts": {
        "name": "Quên Tên Tự Test",
        "resource_id": "7637460417295469832",
        "gender": "FEMALE",
    },
    "BV075_streaming": {
        "name": "Thanh Niên Tự Tin",
        "resource_id": "7102355803792740865",
        "gender": "MALE",
    },
    "BV560_streaming": {
        "name": "Alex Đại Đế",
        "resource_id": "7483736167565758992",
        "gender": "MALE",
    },
}


# ── RSA PKCS#1 v1.5 (pure Python, no external crypto lib) ──

def _der_len(data, pos):
    first = data[pos]
    pos += 1
    if first < 0x80:
        return first, pos
    nbytes = first & 0x7F
    return int.from_bytes(data[pos:pos + nbytes], "big"), pos + nbytes


def _der_value(data, pos, tag):
    if data[pos] != tag:
        raise ValueError(f"bad DER tag: expected 0x{tag:02x}, got 0x{data[pos]:02x}")
    length, pos = _der_len(data, pos + 1)
    return data[pos:pos + length], pos + length


def _der_int(data, pos):
    raw, pos = _der_value(data, pos, 0x02)
    return int.from_bytes(raw.lstrip(b"\x00"), "big"), pos


def _rsa_public_numbers_from_pem(pem):
    b64 = "".join(line for line in pem.splitlines() if not line.startswith("-----"))
    der = base64.b64decode(b64)
    outer, pos = _der_value(der, 0, 0x30)
    if pos != len(der):
        raise ValueError("trailing data in public key")
    _, pos = _der_value(outer, 0, 0x30)
    bit_string, pos = _der_value(outer, pos, 0x03)
    if pos != len(outer) or not bit_string or bit_string[0] != 0:
        raise ValueError("bad subjectPublicKeyInfo")
    rsa_seq, pos = _der_value(bit_string[1:], 0, 0x30)
    if pos != len(bit_string[1:]):
        raise ValueError("trailing data in RSA public key")
    modulus, pos = _der_int(rsa_seq, 0)
    exponent, pos = _der_int(rsa_seq, pos)
    if pos != len(rsa_seq):
        raise ValueError("trailing integer data in RSA public key")
    return modulus, exponent


def _rsa_encrypt_pkcs1v15(message, pem=TTS_SIGN_PUBLIC_KEY_PEM):
    modulus, exponent = _rsa_public_numbers_from_pem(pem)
    key_len = (modulus.bit_length() + 7) // 8
    msg = message.encode("utf-8") if isinstance(message, str) else bytes(message)
    if len(msg) > key_len - 11:
        raise ValueError("message too long for RSA PKCS#1 v1.5")
    ps_len = key_len - len(msg) - 3
    ps = bytearray()
    while len(ps) < ps_len:
        chunk = secrets.token_bytes(ps_len - len(ps))
        ps.extend(b for b in chunk if b != 0)
    encoded = b"\x00\x02" + bytes(ps[:ps_len]) + b"\x00" + msg
    encrypted = pow(int.from_bytes(encoded, "big"), exponent, modulus).to_bytes(key_len, "big")
    return base64.b64encode(encrypted).decode("ascii")


# ── Request building helpers ──

def _compact_json(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _make_x_ss_stub(body_text):
    return hashlib.md5(body_text.encode("utf-8")).hexdigest()


def _make_trace_id():
    seed = uuid.uuid4().hex[:32]
    return f"00-{seed}-{seed[:16]}-01"


def _make_sign_header(url, appvr, device_time, tdid):
    path = url.split("?", 1)[0]
    sign_str = f"9e2c|{path[-7:]}|3|{appvr}|{device_time}|{tdid}|11ac"
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest()


def _escape_xml(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _make_tts_payload_sign(ssml, extra_info, device_id, app_id):
    ssml_md5 = hashlib.md5(ssml.encode("utf-8")).hexdigest()
    sign_input = f"appid:{app_id}&did:{device_id}&creditDisable:false&ssml:{ssml_md5}"
    if extra_info is not None:
        sign_input += f"&extraInfo:{extra_info}"
    return _rsa_encrypt_pkcs1v15(sign_input)


def _common_query(device, babi_param=None, include_region=True):
    q = {
        "app_name": device["app_name"],
        "device_type": device["device_type"],
        "os_version": device["os_version"],
        "channel": device["channel"],
        "version_name": device["version_name"],
        "device_brand": device["device_brand"],
        "device_id": device["device_id"],
        "iid": device["iid"],
        "version_code": device["version_code"],
        "device_platform": device["device_platform"],
        "aid": device["aid"],
    }
    if include_region:
        q["region"] = device["region"]
    if babi_param is not None:
        q["babi_param"] = _compact_json(babi_param)
    return q


def _base_headers(device, body_text, appid=False):
    now = str(int(time.time()))
    headers = {
        "content-type": "application/json",
        "appvr": device["appvr"],
        "ch": device["channel"],
        "device-time": now,
        "lan": device["lan"],
        "loc": device["loc"],
        "pf": device["pf"],
        "sign-ver": "1",
        "tdid": device["tdid"],
        "x-ss-stub": _make_x_ss_stub(body_text),
        "x-ss-dp": device["aid"],
        "x-khronos": now,
        "x-tt-trace-id": _make_trace_id(),
        "user-agent": "Cronet/TTNetVersion:1d7cc3b1 2025-07-16 QuicVersion:52c2b40d 2025-04-03",
        "accept-encoding": "gzip, deflate",
        "store-country-code": device["loc"].lower(),
        "store-country-code-src": "did",
        "is-dispatch-us-ttp": "0",
        "is-app-region-us-ttp": "0",
    }
    if appid:
        headers["app-sdk-version"] = device["appvr"]
        headers["appid"] = device["aid"]
    return headers


def _tts_new_body(text, voice, resource_id, rate, device):
    babi = {
        "feature_entrance": "editor",
        "feature_entrance_detail": "editor-feature-text_to_speech",
        "feature_key": "text_to_speech",
        "scenario": "video_editor",
    }
    voice_block = (
        f'    <voice name="{voice}" mock_tone_info="" platform="sami" '
        f'resource_id="{resource_id}" emotion="" emotion_scale="0" style="" role="" '
        f'moyin_emotion="" is_clone_tone="false" need_subtitle_timestamp="false">\n'
        f'        <prosody rate="{rate}">{_escape_xml(text)}</prosody>\n'
        f'    </voice>'
    )
    ssml = (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">\n'
        + voice_block
        + "\n</speak>"
    )
    extra_info = _compact_json({"benefit_info": {}})
    payload = {
        "audio_format": "mp3",
        "babi_param": _compact_json(babi),
        "credit_disable": False,
        "extra_info": extra_info,
        "need_merge_voice": False,
        "need_subtitle_timestamp": False,
        "scene": "text_to_speech",
        "ssml": ssml,
    }
    payload["sign"] = _make_tts_payload_sign(ssml, extra_info, device["device_id"], device["aid"])
    body = {
        "bind_id": str(uuid.uuid4()),
        "can_queue": True,
        "enter_from": "text_to_speech",
        "tasks": [
            {
                "context": str(uuid.uuid4()),
                "payload": _compact_json(payload),
                "req_key": "sami_text_to_speech",
                "task_version": "v3",
            }
        ],
    }
    return babi, body


def _query_body(task_id, token):
    return {
        "tasks": [
            {
                "bind_id": "",
                "id": task_id,
                "req_key": "sami_text_to_speech",
                "task_version": "v3",
                "token": token,
            }
        ]
    }


# ── Text chunking for CapCut's ~1500 char limit ──

_CAPCUT_MAX_CHARS = 800

def _split_text_for_capcut(text, max_len=_CAPCUT_MAX_CHARS):
    if len(text) <= max_len:
        return [text]

    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break

        split_at = -1
        for sep in ['. ', '.\n', '! ', '!\n', '? ', '?\n', '.​', '; ', ';\n']:
            idx = remaining.rfind(sep, 0, max_len)
            if idx > max_len // 3:
                split_at = idx + len(sep)
                break

        if split_at < 0:
            for sep in [', ', ',\n', ' - ', '\n']:
                idx = remaining.rfind(sep, 0, max_len)
                if idx > max_len // 3:
                    split_at = idx + len(sep)
                    break

        if split_at < 0:
            idx = remaining.rfind(' ', 0, max_len)
            split_at = idx + 1 if idx > max_len // 4 else max_len

        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()

    return [c for c in chunks if c]


# ── CapCut TTS Provider ──

def _generate_device_id():
    return str(random.randint(7000000000000000000, 7999999999999999999))


class CapcutTTSProvider:
    """CapCut TTS — giong tieng Viet chat luong cao, mien phi, khong can API key."""

    def __init__(self):
        self._device = deepcopy(DEFAULT_DEVICE)
        self._device["device_id"] = _generate_device_id()
        self._device["iid"] = _generate_device_id()
        self._device["tdid"] = _generate_device_id()

    @property
    def voice_list(self) -> list[dict]:
        if not HAS_REQUESTS:
            return []
        result = []
        for voice_type, info in CAPCUT_VI_VOICES.items():
            result.append({
                "voice_id": f"capcut:{voice_type}",
                "name": info["name"],
                "gender": info["gender"],
                "tier": "Neural",
                "language": "vi-VN",
                "provider": "CapCut TTS",
                "icon": "capcut",
                "needs_api_key": False,
            })
        return result

    def get_default_voice(self) -> str:
        return "capcut:BV074_streaming" if HAS_REQUESTS else ""

    async def synthesize(
        self, text: str, voice_id: str, speed: float = 1.0, **kwargs
    ) -> Optional[bytes]:
        if not HAS_REQUESTS:
            logger.error("requests chua cai dat cho CapCut TTS")
            return None

        text = (text or "").strip()
        if not text:
            return None

        voice_info = CAPCUT_VI_VOICES.get(voice_id)
        if not voice_info:
            logger.error(f"CapCut voice khong ton tai: {voice_id}")
            return None

        resource_id = voice_info["resource_id"]
        speed = max(0.5, min(5.0, float(speed or 1.0)))
        rate = f"{speed:.1f}"

        chunks = _split_text_for_capcut(text)
        if len(chunks) > 1:
            logger.info(f"CapCut TTS splitting text ({len(text)} chars) into {len(chunks)} chunks")

        audio_parts = []
        for i, chunk in enumerate(chunks):
            chunk_audio = None
            for attempt in range(2):
                try:
                    chunk_audio = await asyncio.to_thread(
                        self._synthesize_sync, chunk, voice_id, resource_id, rate
                    )
                    if chunk_audio:
                        break
                    if attempt == 0:
                        logger.info(f"CapCut TTS retry chunk {i+1}/{len(chunks)} with fresh device IDs")
                        self._device["device_id"] = _generate_device_id()
                        self._device["iid"] = _generate_device_id()
                        self._device["tdid"] = _generate_device_id()
                except Exception as e:
                    logger.error(f"CapCut TTS loi chunk {i+1}/{len(chunks)} ({voice_id}): {e}")
                    if attempt == 0:
                        self._device["device_id"] = _generate_device_id()
                        self._device["iid"] = _generate_device_id()
                        self._device["tdid"] = _generate_device_id()

            if not chunk_audio:
                logger.error(f"CapCut TTS failed on chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
                return None
            audio_parts.append(chunk_audio)

        if len(audio_parts) == 1:
            return audio_parts[0]

        return b"".join(audio_parts)

    def _synthesize_sync(self, text, voice, resource_id, rate):
        device = deepcopy(self._device)
        # Fresh device IDs per request to avoid anti-bot blocks
        device["device_id"] = _generate_device_id()
        device["iid"] = _generate_device_id()
        device["tdid"] = _generate_device_id()

        # Step 1: Create TTS task
        babi, body = _tts_new_body(text, voice, resource_id, rate, device)
        body_text = _compact_json(body)
        path = "/lv/v1/common_task/new"
        query = _common_query(device, babi, include_region=True)
        url = BASE + path + "?" + urlencode(query)
        headers = _base_headers(device, body_text, appid=True)
        headers["sign"] = _make_sign_header(
            url, device["appvr"], headers["device-time"], device["tdid"]
        )

        resp = requests.post(
            url, headers=headers, data=body_text.encode("utf-8"), timeout=30
        )
        if resp.status_code >= 400:
            logger.error(f"CapCut TTS new task HTTP {resp.status_code}: {resp.text[:300]}")
            return None

        data = resp.json()
        tasks = data.get("data", {}).get("tasks", [])
        if not tasks:
            logger.error(f"CapCut TTS no tasks in response: {data}")
            return None

        task_id = tasks[0].get("id")
        token = tasks[0].get("token")
        if not task_id or not token:
            logger.error(f"CapCut TTS missing task_id/token: {tasks[0]}")
            return None

        # Step 2: Poll for result
        for attempt in range(30):
            time.sleep(0.5 if attempt < 5 else 1.0)

            q_body = _query_body(task_id, token)
            q_body_text = _compact_json(q_body)
            q_path = "/lv/v1/common_task/query"
            q_query = _common_query(device, None, include_region=False)
            q_url = BASE + q_path + "?" + urlencode(q_query)
            q_headers = _base_headers(device, q_body_text, appid=True)
            q_headers["sign"] = _make_sign_header(
                q_url, device["appvr"], q_headers["device-time"], device["tdid"]
            )

            q_resp = requests.post(
                q_url, headers=q_headers, data=q_body_text.encode("utf-8"), timeout=30
            )
            if q_resp.status_code >= 400:
                continue

            q_data = q_resp.json()
            q_tasks = q_data.get("data", {}).get("tasks", [])
            if not q_tasks:
                continue

            status = q_tasks[0].get("status", "")
            if status == "processing" or status == "queueing":
                continue
            if status != "succeed":
                fail_reason = q_tasks[0].get("fail_reason", "")
                fail_msg = q_tasks[0].get("message", "")
                logger.error(
                    f"CapCut TTS task failed: status={status}, "
                    f"reason={fail_reason}, msg={fail_msg}, "
                    f"text_len={len(text)}, ssml_approx={len(_escape_xml(text)) + 350}"
                )
                return None

            # Extract audio URL from payload
            payload_str = q_tasks[0].get("payload", "")
            if not payload_str:
                logger.error("CapCut TTS no payload in result")
                return None

            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                logger.error(f"CapCut TTS invalid payload JSON")
                return None

            audio_url = payload.get("audio_url") or payload.get("url")
            if not audio_url:
                # CapCut returns audio URL inside audio_subtitles
                audio_subs = payload.get("audio_subtitles")
                if isinstance(audio_subs, list) and audio_subs:
                    audio_url = audio_subs[0].get("audio_url") or audio_subs[0].get("url")
                elif isinstance(audio_subs, dict):
                    audio_url = audio_subs.get("audio_url") or audio_subs.get("url")
            if not audio_url:
                # Try nested output structure
                output = payload.get("output")
                if isinstance(output, dict):
                    audio_url = output.get("audio_url") or output.get("url")
            if not audio_url:
                # Scan all string values for an audio URL (must contain audio-related path)
                def _looks_like_audio_url(u):
                    if not isinstance(u, str) or not u.startswith("http"):
                        return False
                    lower = u.lower()
                    return any(ext in lower for ext in ('.mp3', '.wav', '.ogg', '.m4a', '.aac', 'audio', 'tts'))

                for key, val in payload.items():
                    if _looks_like_audio_url(val):
                        audio_url = val
                        break
                    if isinstance(val, list):
                        for item in val:
                            if isinstance(item, dict):
                                for k2, v2 in item.items():
                                    if _looks_like_audio_url(v2):
                                        audio_url = v2
                                        break
                            if audio_url:
                                break

            if not audio_url:
                logger.error(f"CapCut TTS no audio URL in payload: {list(payload.keys())}")
                return None

            # Step 3: Download the MP3
            audio_resp = requests.get(audio_url, timeout=30)
            if audio_resp.status_code != 200:
                logger.error(f"CapCut TTS download failed: {audio_resp.status_code}")
                return None

            return audio_resp.content

        logger.error("CapCut TTS timeout waiting for task")
        return None
