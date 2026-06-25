"""FastAPI server — API cho Web UI tai va nghe truyen."""

import asyncio
import logging
import os
import shutil
import tempfile
from collections import OrderedDict
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.http_client import HttpClient
from core.downloader import StoryDownloader
from core.site_registry import get_adapter_for_url, list_supported_sites
from core.local_tts import get_tts, HAS_EDGE_TTS, HAS_GTTS, HAS_CAPCUT
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Story Tool", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_active_downloads: dict[str, StoryDownloader] = {}
_tts = get_tts()

_tts_cache: "OrderedDict[str, bytes]" = OrderedDict()
_TTS_CACHE_MAX = 512


def _cache_key(voice_id: str, speed: float, pitch: float, text: str) -> str:
    return f"{voice_id}|{speed:.2f}|{pitch:.2f}|{text}"


def _cache_get(key: str) -> Optional[bytes]:
    data = _tts_cache.get(key)
    if data is not None:
        _tts_cache.move_to_end(key)
    return data


def _cache_put(key: str, data: bytes) -> None:
    _tts_cache[key] = data
    _tts_cache.move_to_end(key)
    while len(_tts_cache) > _TTS_CACHE_MAX:
        _tts_cache.popitem(last=False)


webui_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(webui_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=webui_dir), name="static")


@app.get("/")
async def index():
    resp = FileResponse(os.path.join(webui_dir, "index.html"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


# =====================================================================
# STORY API
# =====================================================================

@app.get("/api/chapter")
async def get_chapter(url: str = Query(...)):
    adapter = get_adapter_for_url(url)
    if not adapter:
        raise HTTPException(400, f"Khong ho tro site nay. Ho tro: {list_supported_sites()}")

    client = HttpClient()
    try:
        html = await client.fetch(url)
        chapter = await adapter.get_chapter(html, url)
        meta = await adapter.get_story_meta(html, url)
        return {
            "title": chapter.title,
            "content": chapter.content,
            "story_title": meta.title or chapter.story_title,
            "next_url": chapter.next_url,
            "chapter_url": url,
        }
    except Exception as e:
        raise HTTPException(500, f"Loi khi tai chuong: {e}")
    finally:
        await client.close()


@app.get("/api/sites")
async def get_sites():
    return {"sites": list_supported_sites()}


@app.websocket("/ws/download")
async def ws_download(ws: WebSocket):
    await ws.accept()
    url = ""
    try:
        data = await ws.receive_json()
        url = data.get("url", "")

        async def on_progress(progress):
            try:
                await ws.send_json({"type": "progress", "data": progress})
            except Exception:
                pass

        downloader = StoryDownloader(
            start_url=url,
            start_chapter=data.get("start_chapter", 1),
            max_chapters=data.get("max_chapters", 0),
            workers=data.get("workers", config.MAX_WORKERS),
            min_delay=data.get("min_delay", config.MIN_DELAY),
            max_delay=data.get("max_delay", config.MAX_DELAY),
            on_progress=on_progress,
        )
        _active_downloads[url] = downloader

        result = await downloader.download()
        story_dir = downloader.get_story_dir()
        await ws.send_json({
            "type": "done",
            "data": {
                "story_title": result.story_title,
                "total": result.total_downloaded,
                "errors": result.errors,
                "story_dir": os.path.basename(story_dir) if story_dir else "",
            },
        })
    except WebSocketDisconnect:
        logger.info("Client ngat ket noi")
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        _active_downloads.pop(url, None)


@app.get("/api/download-zip")
async def download_zip(folder: str = Query(...)):
    story_dir = os.path.join(config.DOWNLOAD_DIR, folder)
    if not os.path.isdir(story_dir):
        raise HTTPException(404, "Khong tim thay truyen")
    tmp = tempfile.mktemp(suffix=".zip")
    shutil.make_archive(tmp.replace(".zip", ""), "zip", story_dir)
    return FileResponse(tmp, filename=f"{folder}.zip", media_type="application/zip")


@app.get("/api/downloaded")
async def list_downloaded():
    if not os.path.isdir(config.DOWNLOAD_DIR):
        return {"stories": []}
    stories = []
    for name in os.listdir(config.DOWNLOAD_DIR):
        path = os.path.join(config.DOWNLOAD_DIR, name)
        if os.path.isdir(path):
            txt_count = sum(1 for f in os.listdir(path) if f.endswith(".txt"))
            has_epub = any(f.endswith(".epub") for f in os.listdir(path))
            stories.append({"folder": name, "chapters": txt_count, "has_epub": has_epub})
    return {"stories": stories}


# =====================================================================
# TTS API
# =====================================================================

@app.get("/api/tts/voices")
async def get_tts_voices():
    all_voices = await _tts.get_all_voices()
    return {
        "default": _tts.default_voice(),
        "total": len(all_voices),
        "cloudProviders": list(_tts._cloud_providers.keys()),
        "voices": all_voices,
    }


@app.get("/api/tts/languages")
async def get_tts_languages():
    all_voices = await _tts.get_all_voices()
    languages: dict[str, dict] = {}
    for voice_key, info in all_voices.items():
        lang = info.get("language", "unknown")
        if lang not in languages:
            languages[lang] = {"code": lang, "count": 0, "voices": []}
        languages[lang]["count"] += 1
        languages[lang]["voices"].append({
            "voiceId": voice_key,
            "name": info.get("name", ""),
            "provider": info.get("provider", ""),
        })
    return {"languages": list(languages.values()), "total": len(languages)}


@app.get("/api/tts/export")
async def tts_export_voices():
    return Response(
        content=_tts.export_all_to_json(),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=tts_voices.json"},
    )


@app.get("/api/tts/status")
async def tts_status():
    await _tts.ensure_probed()
    cloud_status = {}
    for key, prov in _tts._cloud_providers.items():
        cloud_status[key] = {
            "configured": prov.is_configured(),
            "voices": len(prov.voice_list),
        }
    return {
        "edge_available": HAS_EDGE_TTS,
        "gtts_available": HAS_GTTS,
        "capcut_available": HAS_CAPCUT,
        "cloud_providers": cloud_status,
        "total_voices": len(_tts.voice_list),
        "default_voice": _tts.default_voice(),
    }


@app.get("/api/tts/providers")
async def tts_providers():
    providers = {
        "edge": {"name": "Edge TTS (Microsoft Neural)", "configured": HAS_EDGE_TTS, "free": True},
        "gtts": {"name": "Google TTS (Free)", "configured": HAS_GTTS, "free": True, "voices": len(_tts.gtts_prov.voice_list)},
        "capcut": {"name": "CapCut TTS", "configured": HAS_CAPCUT, "free": True, "voices": len(_tts.capcut_prov.voice_list)},
    }
    cloud_map = {"gcloud": "Google Cloud TTS", "azure": "Azure TTS", "openai": "OpenAI TTS", "gemini": "Gemini TTS"}
    for key, name in cloud_map.items():
        prov = _tts._cloud_providers.get(key)
        providers[key] = {
            "name": name,
            "configured": prov.is_configured() if prov else False,
            "free": False,
            "voices": len(prov.voice_list) if prov else 0,
        }
    return {"providers": providers}


class TTSRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None
    speed: float = 1.0
    pitch: float = 1.0


def _parse_tts_request(req: TTSRequest):
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(400, "Text rong")
    if len(text) > 6000:
        raise HTTPException(400, "Doan qua dai (toi da 6000 ky tu)")
    voice_id = req.voice_id or _tts.default_voice()
    speed = max(0.5, min(5.0, req.speed or 1.0))
    pitch = max(0.5, min(2.0, req.pitch or 1.0))
    return text, voice_id, speed, pitch


@app.post("/api/tts/synthesize")
async def tts_synthesize(req: TTSRequest):
    text, voice_id, speed, pitch = _parse_tts_request(req)
    key = _cache_key(voice_id, speed, pitch, text)

    audio_data = _cache_get(key)
    if audio_data is None:
        for attempt in range(3):
            audio_data = await _tts.synthesize(text, voice_id, speed, pitch=pitch)
            if audio_data:
                break
            if attempt < 2:
                await asyncio.sleep(0.5 * (attempt + 1))
        if not audio_data:
            raise HTTPException(500, "TTS that bai. Edge: pip install edge-tts.")
        _cache_put(key, audio_data)

    return Response(
        content=audio_data,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=audio.mp3",
            "Cache-Control": "public, max-age=86400",
        },
    )


@app.post("/api/tts/save")
async def tts_save(req: TTSRequest):
    text, voice_id, speed, pitch = _parse_tts_request(req)

    audio_data = await _tts.synthesize(text, voice_id, speed, pitch=pitch)
    if not audio_data:
        raise HTTPException(500, "TTS that bai. Edge: pip install edge-tts.")

    return Response(
        content=audio_data,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "attachment; filename=tts_output.mp3",
            "Content-Length": str(len(audio_data)),
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("webui.app:app", host=config.HOST, port=config.PORT, reload=True)
