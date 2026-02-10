import json
import os
import subprocess
import uuid
import asyncio
import time
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import edge_tts
import shutil
from fastapi.staticfiles import StaticFiles
import websockets
import gzip
import aiohttp # Import aiohttp for WSMsgType

import logging

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Import Volcengine TTS helper (using absolute import assuming run from root)
try:
    from backend.volc_tts import generate_volc_tts_ws
except ImportError:
    try:
        from volc_tts import generate_volc_tts_ws
    except:
        pass

# Load Configuration from secrets.json if available
SECRETS_FILE = os.path.abspath("secrets.json")
config = {}

if os.path.exists(SECRETS_FILE):
    try:
        with open(SECRETS_FILE, "r", encoding="utf-8") as f:
            content = ""
            for line in f:
                stripped = line.strip()
                if not stripped.startswith("//") and not stripped.startswith("#"):
                    content += line

            config = json.loads(content)
            print(f"Loaded configuration from {SECRETS_FILE}")
    except Exception as e:
        print(f"Error loading secrets.json: {e}")

# Volcengine Configuration (Load from config or use defaults/env vars)
# Default values are placeholders or fallback for development.
# PRODUCTION: Use secrets.json to override these.

# TTS Configuration
VOLC_TTS_APPID = config.get("VOLC_TTS_APPID", config.get("VOLC_APPID", os.environ.get("VOLC_TTS_APPID", "YOUR_TTS_APP_ID")))
VOLC_TTS_TOKEN = config.get("VOLC_TTS_TOKEN", config.get("VOLC_TOKEN", os.environ.get("VOLC_TTS_TOKEN", "YOUR_TTS_TOKEN")))
VOLC_TTS_CLUSTER = config.get("VOLC_TTS_CLUSTER", "volcano_tts")

# ASR Configuration
VOLC_ASR_APPID = config.get("VOLC_ASR_APPID", config.get("VOLC_APPID", os.environ.get("VOLC_ASR_APPID", "YOUR_ASR_APP_ID")))
VOLC_ASR_TOKEN = config.get("VOLC_ASR_TOKEN", config.get("VOLC_TOKEN", os.environ.get("VOLC_ASR_TOKEN", "YOUR_ASR_TOKEN")))
VOLC_ASR_CLUSTER = config.get("VOLC_ASR_CLUSTER", "volcengine_streaming_common")
VOLC_ASR_RESOURCE_ID = config.get("VOLC_ASR_RESOURCE_ID", config.get("VOLC_RESOURCE_ID", "volc.bigasr.sauc.duration"))

# Realtime Config
VOLC_REALTIME_APPID = config.get("VOLC_REALTIME_APPID", config.get("VOLC_APPID", os.environ.get("VOLC_REALTIME_APPID", "YOUR_REALTIME_APP_ID")))
VOLC_REALTIME_TOKEN = config.get("VOLC_REALTIME_TOKEN", config.get("VOLC_TOKEN", os.environ.get("VOLC_REALTIME_TOKEN", "YOUR_REALTIME_TOKEN")))
VOLC_REALTIME_RESOURCE_ID = config.get("VOLC_REALTIME_RESOURCE_ID", "volc.speech.dialog")

# Common URL (Usually same, but good to be explicit)
VOLC_URL = config.get("VOLC_URL", "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel")

TEMP_DIR = os.path.abspath("temp")
AVATARS_DIR = os.path.abspath("avatars")
HISTORY_FILE = os.path.join(AVATARS_DIR, "history.json")
CHAT_HISTORY_FILE = os.path.join(AVATARS_DIR, "chat_history.json")
CONFIG_FILE = os.path.join(AVATARS_DIR, "config.json")
CONVERSATIONS_FILE = os.path.join(AVATARS_DIR, "conversations.json")
MESSAGES_FILE = os.path.join(AVATARS_DIR, "messages.json")

# Ensure directories exist
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(AVATARS_DIR, exist_ok=True)

ffmpeg_system = shutil.which("ffmpeg")
if ffmpeg_system:
    FFMPEG_PATH = ffmpeg_system
else:
    FFMPEG_PATH = os.path.abspath("backend/ffmpeg/ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe")

print(f"Using FFmpeg at: {FFMPEG_PATH}")

# Helper to update history
def add_to_history(url: str, meta: dict = None):
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        except:
            pass

    new_history = []
    for item in history:
        if isinstance(item, str):
            new_history.append({"url": item, "meta": {}})
        else:
            new_history.append(item)
    history = new_history

    history = [item for item in history if item["url"] != url]

    history.insert(0, {
        "url": url,
        "meta": meta or {}
    })

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

app = FastAPI()

@app.get("/history")
async def get_history():
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                raw_history = json.load(f)
                for item in raw_history:
                    if isinstance(item, str):
                        url = item
                        if "localhost:8004" in url:
                            url = url.replace("http://localhost:8004", "")

                        if not any(h["url"] == url for h in history):
                            history.append({"url": url, "meta": {}})
                    else:
                        url = item["url"]
                        if "localhost:8004" in url:
                            url = url.replace("http://localhost:8004", "")
                        item["url"] = url

                        if not any(h["url"] == url for h in history):
                            history.append(item)
        except Exception as e:
            print(f"Error loading history: {e}")
            pass
        
    response = JSONResponse(content=history)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

def get_active_role_settings():
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except:
            pass

    if history and len(history) > 0:
        active_item = history[0]
        if isinstance(active_item, dict) and "meta" in active_item:
            meta = active_item["meta"]
            system_prompt = meta.get("systemPrompt")
            speaking_style = meta.get("speakingStyle")

            print(f"[Role Settings] system_prompt: {system_prompt}")
            print(f"[Role Settings] speaking_style: {speaking_style}")

            return {
                "system_prompt": system_prompt,
                "speaking_style": speaking_style
            }

    print("[Role Settings] No settings found, using defaults")
    return {"system_prompt": None, "speaking_style": None}

def save_chat_message(session_id: str, role: str, content: str):
    """Save a chat message to chat_history.json"""
    chat_history = []
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                chat_history = json.load(f)
        except:
            pass

    message = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "timestamp": time.time()
    }

    chat_history.append(message)

    with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(chat_history, f, ensure_ascii=False, indent=2)

@app.delete("/history")
async def delete_history_item(request: dict):
    url_to_delete = request.get("url")
    if not url_to_delete:
        return JSONResponse(status_code=400, content={"message": "URL is required"})

    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                raw_history = json.load(f)
                for item in raw_history:
                    if isinstance(item, str):
                        history.append({"url": item, "meta": {}})
                    else:
                        history.append(item)
        except:
            pass

    history = [item for item in history if item["url"] != url_to_delete]

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

    return history

@app.put("/history")
async def update_history_item(request: dict):
    url = request.get("url")
    meta = request.get("meta")

    if not url or meta is None:
        return JSONResponse(status_code=400, content={"message": "URL and meta are required"})

    add_to_history(url, meta)

    return {"status": "success"}

@app.post("/history/import")
async def import_history(file: UploadFile = File(...)):
    try:
        content = await file.read()
        imported_history = json.loads(content)
        
        if not isinstance(imported_history, list):
            return JSONResponse(status_code=400, content={"message": "Invalid format: must be a list"})

        valid_history = []
        for item in imported_history:
            if isinstance(item, dict) and "url" in item:
                valid_history.append(item)
            elif isinstance(item, str):
                valid_history.append({"url": item, "meta": {}})

        current_history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                current_history = json.load(f)

        existing_urls = {item["url"] if isinstance(item, dict) else item for item in current_history}

        for item in valid_history:
            url = item["url"]
            if url not in existing_urls:
                current_history.append(item)

        with open(HISTORY_FILE, "w") as f:
            json.dump(current_history, f, indent=4)

        return {"status": "success", "count": len(valid_history)}
        
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"message": "Invalid JSON file"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})

@app.post("/upload_avatar")
async def upload_avatar(file: UploadFile = File(...)):
    """Upload an image file as avatar"""
    try:
        ext = os.path.splitext(file.filename)[1].lower()
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']

        if ext not in allowed_extensions:
            return JSONResponse(
                status_code=400,
                content={"message": f"仅支持图片格式: {', '.join(allowed_extensions)}"}
            )

        file_id = str(uuid.uuid4())
        filename = f"{file_id}{ext}"
        file_path = os.path.join(AVATARS_DIR, filename)

        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        avatar_url = f"/avatars/{filename}"

        add_to_history(avatar_url, {
            "fit": "cover",
            "scale": 1.0,
            "ttsProvider": "volcengine",
            "volcVoice": "zh_female_meilinvyou_moon_bigtts",
            "phoneVoice": "zh_female_vv_jupiter_bigtts",
            "isWebSearchEnabled": True,
            "isVoiceReplyEnabled": True
        })

        return {
            "status": "success",
            "url": avatar_url,
            "filename": filename
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})

@app.post("/upload_user_avatar")
async def upload_user_avatar(file: UploadFile = File(...)):
    """Upload user avatar image (not added to digital human history)"""
    try:
        ext = os.path.splitext(file.filename)[1].lower()
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']

        if ext not in allowed_extensions:
            return JSONResponse(
                status_code=400,
                content={"message": f"仅支持图片格式: {', '.join(allowed_extensions)}"}
            )

        file_id = str(uuid.uuid4())
        filename = f"user_{file_id}{ext}"
        file_path = os.path.join(AVATARS_DIR, filename)

        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        avatar_url = f"/avatars/{filename}"

        return {
            "status": "success",
            "url": avatar_url,
            "filename": filename
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})

@app.post("/upload_ai_avatar")
async def upload_ai_avatar(file: UploadFile = File(...)):
    """Upload AI avatar image"""
    try:
        ext = os.path.splitext(file.filename)[1].lower()
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']

        if ext not in allowed_extensions:
            return JSONResponse(
                status_code=400,
                content={"message": f"仅支持图片格式: {', '.join(allowed_extensions)}"}
            )

        file_id = str(uuid.uuid4())
        filename = f"ai_avatar_{file_id}{ext}"
        file_path = os.path.join(AVATARS_DIR, filename)

        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        avatar_url = f"/avatars/{filename}"

        return {
            "status": "success",
            "url": avatar_url,
            "filename": filename
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})

@app.get("/config")
async def get_config():
    """Get configuration including AI avatar URL"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config
        except:
            pass
    return {"aiAvatarUrl": "/src/assets/vue.svg"}

@app.put("/config")
async def update_config(config: dict):
    """Update configuration"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/chat_history")
async def get_chat_history(session_id: str = None):
    """Get chat history, optionally filtered by session_id"""
    if not os.path.exists(CHAT_HISTORY_FILE):
        return []

    try:
        with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
            chat_history = json.load(f)

        if session_id:
            chat_history = [msg for msg in chat_history if msg.get("session_id") == session_id]

        return chat_history
    except:
        return []

@app.delete("/api/chat_history")
async def clear_chat_history(session_id: str = None):
    """Clear chat history, optionally for a specific session"""
    if not os.path.exists(CHAT_HISTORY_FILE):
        return {"status": "success", "message": "No history to clear"}

    try:
        if session_id:
            with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                chat_history = json.load(f)

            chat_history = [msg for msg in chat_history if msg.get("session_id") != session_id]

            with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(chat_history, f, ensure_ascii=False, indent=2)
        else:
            with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)

        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ==================== Conversation Management ====================

def load_conversations():
    if os.path.exists(CONVERSATIONS_FILE):
        try:
            with open(CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_conversations(conversations):
    with open(CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(conversations, f, ensure_ascii=False, indent=2)

def create_conversation(mode="phone", title=None):
    """Create a new conversation"""
    conversations = load_conversations()
    conv_id = str(uuid.uuid4())
    conversation = {
        "id": conv_id,
        "title": title or "新对话",
        "mode": mode,
        "created_at": time.time(),
        "updated_at": time.time(),
        "message_count": 0
    }
    conversations.append(conversation)
    save_conversations(conversations)
    return conv_id

def add_message_to_conversation(conv_id, role, content):
    """Add a message to conversation"""
    # Load messages
    messages = []
    if os.path.exists(MESSAGES_FILE):
        try:
            with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
                messages = json.load(f)
        except:
            messages = []

    # Add new message
    message = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv_id,
        "role": role,
        "content": content,
        "timestamp": time.time()
    }
    messages.append(message)

    # Save messages
    with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    # Update conversation
    conversations = load_conversations()
    for conv in conversations:
        if conv["id"] == conv_id:
            conv["message_count"] += 1
            conv["updated_at"] = time.time()
            # Auto-generate title from first user message using AI
            if conv["message_count"] == 1 and role == "user":
                try:
                    # Use AI to generate a concise title
                    title_prompt = f"请为以下对话生成一个简短的标题（不超过15个字）：\n用户：{content}\n\n只返回标题，不要其他内容。"
                    generated_title = chat_with_ark(title_prompt, use_search=False, system_prompt="你是一个标题生成助手。", speaking_style="")
                    # Clean up the title
                    generated_title = generated_title.strip().strip('"').strip("'")
                    # Add date prefix
                    date_str = time.strftime("%m/%d", time.localtime())
                    conv["title"] = f"{date_str} {generated_title}"
                except Exception as e:
                    print(f"Failed to generate title: {e}")
                    # Fallback to simple truncation
                    date_str = time.strftime("%m/%d", time.localtime())
                    conv["title"] = f"{date_str} {content[:15]}{'...' if len(content) > 15 else ''}"
            break
    save_conversations(conversations)

@app.get("/api/conversations")
async def get_conversations():
    """Get all conversations"""
    conversations = load_conversations()
    # Sort by updated_at descending
    conversations.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
    return conversations

@app.get("/api/conversations/{conv_id}/messages")
async def get_conversation_messages(conv_id: str):
    """Get messages for a specific conversation"""
    if not os.path.exists(MESSAGES_FILE):
        return []

    try:
        with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
            all_messages = json.load(f)

        # Filter messages for this conversation
        messages = [msg for msg in all_messages if msg.get("conversation_id") == conv_id]
        messages.sort(key=lambda x: x.get("timestamp", 0))
        return messages
    except:
        return []

@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    """Delete a conversation and its messages"""
    try:
        # Delete conversation
        conversations = load_conversations()
        conversations = [c for c in conversations if c["id"] != conv_id]
        save_conversations(conversations)

        # Delete messages
        if os.path.exists(MESSAGES_FILE):
            with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
                all_messages = json.load(f)
            all_messages = [m for m in all_messages if m.get("conversation_id") != conv_id]
            with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
                json.dump(all_messages, f, ensure_ascii=False, indent=2)

        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# Mount static files to serve avatars
app.mount("/avatars", StaticFiles(directory=AVATARS_DIR), name="avatars")

DIST_DIR = os.path.abspath("dist")
if os.path.exists(DIST_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")
    
    @app.get("/")
    async def serve_spa():
        return FileResponse(os.path.join(DIST_DIR, "index.html"))
        
    @app.get("/{full_path:path}")
    async def serve_spa_catchall(full_path: str):
        potential_path = os.path.join(DIST_DIR, full_path)
        if os.path.isfile(potential_path):
            return FileResponse(potential_path)
        return FileResponse(os.path.join(DIST_DIR, "index.html"))
    


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Avatar-Url", "X-Avatar-Meta"],
)

WAV2LIP_PATH = "backend/Wav2Lip"
WAV2LIP_PATH = "backend/Wav2Lip"
CHECKPOINT_PATH = "backend/checkpoints/wav2lip_gan.pth"

async def generate_audio_file(text: str, output_path: str, voice: str = "zh-CN-XiaoxiaoNeural"):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def run_wav2lip_inference(face_path: str, audio_path: str, output_path: str):
    inference_script = os.path.join(WAV2LIP_PATH, "inference.py")

    if not os.path.exists(inference_script):
        print(f"Error: Wav2Lip inference script not found at {inference_script}")
        return False

    try:
        python_executable = sys.executable

        cmd = [
            python_executable, inference_script,
            "--checkpoint_path", CHECKPOINT_PATH,
            "--face", face_path,
            "--audio", audio_path,
            "--outfile", output_path,
            "--resize_factor", "1",
            "--nosmooth"
        ]

        print(f"Executing Wav2Lip: {' '.join(cmd)}")

        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        print("Wav2Lip Output (Stdout):", result.stdout)
        print("Wav2Lip Output (Stderr):", result.stderr)
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"Wav2Lip execution failed with code {e.returncode}")
        print("Stdout:", e.stdout)
        print("Stderr:", e.stderr)
        return False
    except Exception as e:
        print(f"Unexpected error running Wav2Lip: {e}")
        return False

@app.post("/animate")
async def animate_avatar(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    avatar_fit: str = Form("cover"),
    avatar_scale: float = Form(1.0)
):
    session_id = str(uuid.uuid4())
    ext = os.path.splitext(image.filename)[1].lower()
    if not ext:
        ext = ".png"
        
    image_path = os.path.join(TEMP_DIR, f"{session_id}_input{ext}")
    audio_path = os.path.join(TEMP_DIR, f"{session_id}_dummy.mp3")
    output_video_path = os.path.join(TEMP_DIR, f"{session_id}_loop.mp4")

    try:
        content = await image.read()
        with open(image_path, "wb") as f:
            f.write(content)

        dummy_text = "你好，我是数字人助手。我可以回答你的问题。"
        await generate_audio_file(dummy_text, audio_path)

        success = run_wav2lip_inference(image_path, audio_path, output_video_path)

        final_output_path = os.path.join(TEMP_DIR, f"{session_id}_loop.webm")
        
        if success:
            try:
                print("Applying alpha channel to video...")
                cmd = [
                    FFMPEG_PATH, "-y",
                    "-i", output_video_path,
                    "-loop", "1", "-i", image_path,
                    "-filter_complex",
                    "[1:v]scale=trunc(iw/2)*2:trunc(ih/2)*2[img_even];[0:v][img_even]scale2ref[vid_scaled][img_ref];[img_ref]format=rgba,alphaextract[alpha];[vid_scaled]format=rgba[vid];[vid][alpha]alphamerge",
                    "-c:v", "libvpx-vp9", "-b:v", "1M", "-auto-alt-ref", "0",
                    "-pix_fmt", "yuva420p",
                    "-shortest",
                    final_output_path
                ]

                print(f"Executing FFmpeg transparency merge: {' '.join(cmd)}")
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                print("FFmpeg Output:", result.stdout)

                output_video_path = final_output_path
                
            except subprocess.CalledProcessError as e:
                print(f"Alpha channel application failed (FFmpeg Error): {e.stderr}")
                pass
            except Exception as e:
                print(f"Alpha channel application failed: {e}")
                pass
        elif not success:
             print("Creating static WebM fallback...")
             try:
                 subprocess.run([
                    FFMPEG_PATH, "-y", "-loop", "1", "-i", image_path, "-i", audio_path,
                    "-c:v", "libvpx-vp9", "-b:v", "1M", "-pix_fmt", "yuva420p",
                    "-shortest", final_output_path
                ], check=True)
                 output_video_path = final_output_path
             except:
                 pass
        background_tasks.add_task(os.remove, image_path)
        background_tasks.add_task(os.remove, audio_path)

        if output_video_path.endswith(".webm"):
             final_filename = f"{session_id}_loop.webm"
        else:
             final_filename = f"{session_id}_loop.mp4"

        persist_path = os.path.join(AVATARS_DIR, final_filename)

        if os.path.abspath(output_video_path) != os.path.abspath(persist_path):
            shutil.move(output_video_path, persist_path)

        avatar_url = f"/avatars/{final_filename}"

        add_to_history(avatar_url, {
            "fit": avatar_fit,
            "scale": avatar_scale
        })

        media_type = "video/webm" if final_filename.endswith(".webm") else "video/mp4"

        # Wait for file system to sync
        await asyncio.sleep(0.1)

        response = FileResponse(persist_path, media_type=media_type)
        response.headers["X-Avatar-Url"] = avatar_url
        response.headers["X-Avatar-Meta"] = json.dumps({"fit": avatar_fit, "scale": avatar_scale})
        
        return response

    except Exception as e:
        print(f"Animate error: {e}")
        return JSONResponse(status_code=500, content={"message": str(e)})

@app.post("/tts")
async def text_to_speech(
    background_tasks: BackgroundTasks,
    text: str = Form(...),
    voice: str = Form("zh-CN-XiaoxiaoNeural"),
    tts_provider: str = Form("microsoft")
):
    session_id = str(uuid.uuid4())
    audio_path = os.path.join(TEMP_DIR, f"{session_id}.mp3")

    try:
        if tts_provider == "volcengine":
            volc_voice = voice
            if voice.startswith("zh-CN-") or voice.startswith("en-US-"):
                volc_voice = "zh_female_meilinvyou_moon_bigtts"

            print(f"[TTS] Using Volcengine voice: {volc_voice}")

            start_time = time.time()
            await generate_volc_tts_ws(
                text,
                audio_path,
                volc_voice,
                app_id=VOLC_TTS_APPID,
                token=VOLC_TTS_TOKEN,
                cluster=VOLC_TTS_CLUSTER
            )
            duration = time.time() - start_time
            print(f"[TTS] Generation Time (Volcengine): {duration:.4f}s")
            
        else:
            start_time = time.time()
            for _ in range(3):
                try:
                    await generate_audio_file(text, audio_path, voice)
                    break
                except Exception as retry_err:
                    print(f"Edge TTS retry error: {retry_err}")
                    await asyncio.sleep(1)
            else:
                raise Exception("Edge TTS failed after 3 retries")
            duration = time.time() - start_time
            print(f"[TTS] Generation Time (Edge): {duration:.4f}s")

        background_tasks.add_task(os.remove, audio_path)

        return FileResponse(audio_path, media_type="audio/mpeg")
    except Exception as e:
        print(f"TTS Final Error: {e}")
        return JSONResponse(status_code=500, content={"message": str(e)})

# Adjust sys.path to allow importing from current directory
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from volc_asr import AsrWsClient, Config
import volc_asr as volc_module

from llm import chat_with_ark
from pydantic import BaseModel

try:
    from backend.volc_realtime import RealtimeDialogClient
except ImportError:
    try:
        from volc_realtime import RealtimeDialogClient
    except ImportError:
        pass

class ChatRequest(BaseModel):
    text: str
    use_search: bool = True
    session_id: str = None

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    print(f"Received chat request: {request.text}, use_search={request.use_search}")

    # Use existing conversation_id or create new one
    conversation_id = request.session_id
    if not conversation_id:
        conversation_id = create_conversation(mode="chat")
        print(f"[Chat] Created new conversation: {conversation_id}")
    else:
        print(f"[Chat] Using existing conversation: {conversation_id}")

    # Save user message
    add_message_to_conversation(conversation_id, "user", request.text)

    role_settings = get_active_role_settings()

    start_time = time.time()
    response_text = chat_with_ark(
        request.text,
        use_search=request.use_search,
        system_prompt=role_settings["system_prompt"],
        speaking_style=role_settings["speaking_style"]
    )
    duration = time.time() - start_time
    print(f"LLM Response: {response_text}")
    print(f"[LLM] Response Time: {duration:.4f}s")

    # Save AI response
    add_message_to_conversation(conversation_id, "assistant", response_text)

    return {"text": response_text, "session_id": conversation_id}

@app.websocket("/ws/phone")
async def websocket_phone(websocket: WebSocket):
    await websocket.accept()
    print("[Phone] Frontend connected")

    voice = websocket.query_params.get("voice")
    if voice:
        print(f"[Phone] Requested Voice: {voice}")

    # Session tracking for chat history
    # Check if conversation_id is provided in query params
    conversation_id = websocket.query_params.get("conversation_id")
    if conversation_id:
        print(f"[Phone] Using existing conversation: {conversation_id}")
    else:
        conversation_id = create_conversation(mode="phone")
        print(f"[Phone] Created new conversation: {conversation_id}")

    current_user_text = ""
    current_ai_text = ""

    role_settings = get_active_role_settings()

    client = RealtimeDialogClient(
        app_id=VOLC_REALTIME_APPID,
        access_token=VOLC_REALTIME_TOKEN,
        resource_id=VOLC_REALTIME_RESOURCE_ID
    )

    try:
        await client.connect(
            voice=voice,
            system_prompt=role_settings["system_prompt"],
            speaking_style=role_settings["speaking_style"]
        )

        # Send conversation_id to frontend
        await websocket.send_text(json.dumps({
            "type": "conversation_init",
            "conversation_id": conversation_id
        }))

        async def frontend_to_volc():
            try:
                while True:
                    data = await websocket.receive_bytes()
                    if not data: break
                    await client.send_audio(data)
            except WebSocketDisconnect:
                print("[Phone] Frontend disconnected")
            except Exception as e:
                print(f"[Phone] Frontend->Volc error: {e}")

        async def volc_to_frontend():
            nonlocal current_user_text, current_ai_text
            try:
                while True:
                    msg = await client.receive()
                    if msg is None: break
                    
                    parsed = await client.parse_message(msg)
                    payload_msg = parsed.get('payload_msg')
                    
                    if isinstance(payload_msg, bytes):
                        # Audio data (PCM 24k)
                        await websocket.send_bytes(payload_msg)
                    elif isinstance(payload_msg, dict):
                        # Event
                        print(f"[Phone] Received event: {payload_msg}")

                        # Save user message when ASR completes
                        if 'asr' in payload_msg and 'result' in payload_msg['asr']:
                            # Handle SC/O version differences if needed, usually it's asr.result
                            pass
                        
                        # Note: Volcengine Realtime structure is a bit complex.
                        # Usually user text is in 'asr' -> 'text' or similar events?
                        # Actually, looking at docs/logs, the 'text' often comes in 'conversation' events or similar?
                        # Wait, the official response structure for user text is usually in 'asr' event?
                        # Let's look for 'asr_result' or similar.
                        # Based on typical logs: 
                        # {'type': 'asr_result', 'text': '...', 'is_final': True}
                        
                        # However, for the specific Realtime API (Doubao), the structure might be:
                        # Event: 'asr'
                        # Payload: { 'text': '...', 'is_final': ... }
                        
                        # Let's try to capture ANY text that looks like user input.
                        
                        # DEBUG: Let's inspect the payload structure in logs to be sure.
                        # But for now, let's implement a generic capture.
                        
                        # Capture User Text from ASR events
                        # Event structure: {'results': [{'text': '...', 'is_interim': False}]}
                        if 'results' in payload_msg and isinstance(payload_msg['results'], list):
                            if len(payload_msg['results']) > 0:
                                result = payload_msg['results'][0]
                                if result.get('text') and not result.get('is_interim'):
                                    user_text = result['text']
                                    if user_text != current_user_text:
                                        current_user_text = user_text
                                        add_message_to_conversation(conversation_id, "user", current_user_text)
                                        print(f"[Phone] Saved user message: {current_user_text}")
                        
                        # Capture AI Response
                        # Event structure: {'content': '...', 'question_id': '...', 'reply_id': '...'}
                        if 'content' in payload_msg and payload_msg.get('question_id'):
                            current_ai_text += payload_msg['content']

                        # Save AI response when no_content flag is set (end of response)
                        if payload_msg.get('no_content') and current_ai_text:
                            add_message_to_conversation(conversation_id, "assistant", current_ai_text)
                            print(f"[Phone] Saved AI message: {current_ai_text[:50]}...")
                            current_ai_text = ""

                        await websocket.send_json(payload_msg)
                        
            except Exception as e:
                print(f"[Phone] Volc->Frontend error: {e}")

        # Run tasks
        consumer_task = asyncio.create_task(frontend_to_volc())
        producer_task = asyncio.create_task(volc_to_frontend())
        
        done, pending = await asyncio.wait(
            [consumer_task, producer_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        
        for task in pending:
            task.cancel()
            
    except Exception as e:
        print(f"[Phone] Error: {e}")
    finally:
        await client.close()
        print("[Phone] Closed")

@app.websocket("/ws/asr")
async def websocket_asr(websocket: WebSocket):
    await websocket.accept()
    print("Frontend WebSocket connected")

    config = Config(VOLC_ASR_APPID, VOLC_ASR_TOKEN, VOLC_ASR_RESOURCE_ID)

    try:
        print("Initializing AsrWsClient...")
        async with AsrWsClient(VOLC_URL, config, segment_duration=200) as client:
            print("Creating connection to Volcengine...")
            await client.create_connection()
            print("Connection created.")

            print("Sending full client request...")
            await client.send_full_client_request()
            print("Full client request sent.")
            async def frontend_to_volc():
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        if not data:
                            break

                        print(f"Received audio chunk from frontend: {len(data)} bytes")

                        request = volc_module.RequestBuilder.new_audio_only_request(
                            client.seq,
                            data,
                            is_last=False
                        )
                        await client.conn.send_bytes(request)
                        print(f"Sent audio segment to Volcengine seq: {client.seq}")
                        client.seq += 1

                except WebSocketDisconnect:
                    print("Frontend disconnected (WebSocketDisconnect)")
                except Exception as e:
                    print(f"Frontend->Volc error: {type(e).__name__}: {e}")
                    import traceback
                    traceback.print_exc()

            async def volc_to_frontend():
                sent_utterances = set()
                last_sent_final = ""
                last_sent_interim = ""
                try:
                    async for msg in client.conn:
                        if msg.type == aiohttp.WSMsgType.BINARY:
                            response = volc_module.ResponseParser.parse_response(msg.data)

                            print(f"--- [ASR RESPONSE] Seq: {response.payload_sequence} | Event: {response.event} | Code: {response.code} ---")
                            if response.payload_msg:
                                print(f"Payload: {response.payload_msg}")
                            else:
                                print("Payload: None")
                            print("---------------------------------------------------------------")

                            if response.payload_msg and 'result' in response.payload_msg:
                                from datetime import datetime
                                print(f"[ASR] Result Received at: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
                                result = response.payload_msg['result']
                                text = result.get('text', '')
                                utterances = result.get('utterances', [])

                                new_finals = []
                                interim = ""

                                for u in utterances:
                                    if u.get('definite', False):
                                        fingerprint = f"{u.get('start_time')}_{u.get('end_time')}_{u.get('text')}"

                                        if fingerprint not in sent_utterances:
                                            new_finals.append(u['text'])
                                            sent_utterances.add(fingerprint)
                                    else:
                                        interim = u['text']

                                if new_finals:
                                    last_sent_final = new_finals[-1]

                                if interim and last_sent_final:
                                    import re
                                    def clean(s): return re.sub(r'[^\w\u4e00-\u9fa5]', '', s)

                                    cleaned_last = clean(last_sent_final)
                                    cleaned_interim = clean(interim)

                                    if cleaned_last == cleaned_interim or cleaned_last.startswith(cleaned_interim):
                                        print(f"DUPLICATE FILTERED: interim='{interim}' vs last_final='{last_sent_final}'")
                                        interim = ""

                                if new_finals or (interim and interim != last_sent_interim):
                                    print(f"ASR UPDATE: finals={new_finals}, interim='{interim}'")

                                if new_finals or (interim != last_sent_interim):
                                    last_sent_interim = interim
                                    await websocket.send_json({
                                        "type": "asr_update",
                                        "text": text,
                                        "finals": new_finals,
                                        "interim": interim
                                    })

                            if response.is_last_package or response.code != 0:
                                print(f"Volcengine finished. Last: {response.is_last_package}, Code: {response.code}")
                                break
                        else:
                            print(f"Volcengine non-binary message: {msg.type}")
                except Exception as e:
                    print(f"Volc->Frontend error: {e}")
                    import traceback
                    traceback.print_exc()

            # Run concurrently
            consumer_task = asyncio.create_task(frontend_to_volc())
            producer_task = asyncio.create_task(volc_to_frontend())
            
            done, pending = await asyncio.wait(
                [consumer_task, producer_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            
            for task in pending:
                task.cancel()

    except Exception as e:
        print(f"ASR Error: {e}")
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
