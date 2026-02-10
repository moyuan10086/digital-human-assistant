import json
import uuid
import base64
import os
import websockets
import asyncio
from volc_protocol import full_client_request, receive_message, MsgType

# Volcengine Configuration
# Default values are placeholders.
# PRODUCTION: Keys are passed from main.py (loaded from secrets.json) or env vars.
VOLC_APPID = os.environ.get("VOLC_TTS_APPID", "YOUR_TTS_APPID")
VOLC_TOKEN = os.environ.get("VOLC_TTS_TOKEN", "YOUR_TTS_TOKEN")
# Default cluster for general TTS (standard voices)
# Based on the screenshot, the service name is "语音合成大模型-字符版", but there is no explicit "cluster" name shown like "volcano_tts".
# However, usually the default cluster for standard TTS is 'volcano_tts'.
# If using specific voices like 'zh_female_wanqudashu_moon_bigtts', we should check if they need a different cluster.
# But 'BV700_streaming' is a "Standard" voice (Doubao).
# Wait, the error `[resource_id=volc.tts.default] requested resource not granted` suggests:
# 1. The default resource (cluster) `volc.tts.default` is being hit? No, we sent `volcano_tts`.
#    If we send `volcano_tts`, backend might map it to `volc.tts.default` internally if not found?
#    Or maybe we should use `volc.tts.default` explicitly? No, that's usually not a valid cluster name.
#
# 2. The screenshot shows "服务开通: 暂停".
#    CRITICAL: The service status is "暂停" (Paused)!
#    This is likely why it returns 403 Resource Not Granted.
#    User needs to click "开通" or "启用" in the console? Or "购买"?
#    Ah, it says "服务开通 暂停". This might mean it's suspended due to arrears or not activated.
#    But wait, user says "现在是这样的" showing the console.
#    If it is suspended, no code change can fix it.
#    However, maybe we can try another cluster name just in case?
#    Let's try to default to `BV700_streaming` (Doubao) which usually works with `volcano_tts`.
#    Wait, the screenshot shows voices like `zh_female_..._moon_bigtts`.
#    These are "BigTTS" voices.
#    Maybe we should use one of these valid voices instead of `BV700_streaming`?
#    `BV700_streaming` is the *old* standard voice? Or new?
#    Let's switch the default voice to one from the screenshot, e.g., `zh_female_meilinvyou_moon_bigtts` (魅力女友).
#    And keep cluster as `volcano_tts`.

VOLC_CLUSTER = "volcano_tts"

def get_cluster(voice: str) -> str:
    if voice.startswith("S_"):
         return "volcano_icl"
    
    # Check if it's a BigTTS voice (Moon/Sun series)
    # Most modern Doubao voices (like zh_female_meilinvyou_moon_bigtts) use volcano_tts
    # But some might require specific clusters?
    # Actually, standard documentation says "volcano_tts" covers most.
    # But if the user says "only one voice works", maybe we are forcing a default somewhere?
    
    return "volcano_tts"

async def generate_volc_tts_ws(text: str, output_path: str, voice: str = "zh_female_meilinvyou_moon_bigtts", app_id=None, token=None, cluster=None):
    """
    Generate audio using Volcengine WebSocket API (Binary Protocol)
    """
    endpoint = "wss://openspeech.bytedance.com/api/v1/tts/ws_binary"
    
    current_appid = app_id if app_id else VOLC_APPID
    current_token = token if token else VOLC_TOKEN
    current_cluster = cluster if cluster else get_cluster(voice)
    
    headers = {"Authorization": f"Bearer;{current_token}"}
    
    print(f"[VolcTTS] Requesting voice: {voice} on cluster: {current_cluster}") # Debug log
    
    try:
        # websockets >= 10.0 uses additional_headers
        async with websockets.connect(endpoint, additional_headers=headers) as websocket:
            request_json = {
                "app": {
                    "appid": current_appid,
                    "token": current_token,
                    "cluster": current_cluster
                },
                "user": {
                    "uid": str(uuid.uuid4())
                },
                "audio": {
                    "voice_type": voice,
                    "encoding": "mp3",
                    "speed_ratio": 1.0,
                    "volume_ratio": 1.0,
                    "pitch_ratio": 1.0,
                },
                "request": {
                    "reqid": str(uuid.uuid4()),
                    "text": text,
                    "text_type": "plain",
                    "operation": "submit",
                    "with_timestamp": 0
                }
            }
            
            # Send request
            await full_client_request(websocket, json.dumps(request_json).encode('utf-8'))
            
            # Receive audio
            audio_data = bytearray()
            while True:
                msg = await receive_message(websocket)
                
                if msg.type == MsgType.FrontEndResultServer:
                    continue
                elif msg.type == MsgType.AudioOnlyServer:
                    audio_data.extend(msg.payload)
                    if msg.sequence < 0: # Last message
                        break
                elif msg.type == MsgType.Error:
                    raise Exception(f"Volc Error: {msg.error_code} - {msg.payload.decode('utf-8', 'ignore')}")
                else:
                     # For debug
                     print(f"Received other msg type: {msg.type}")
 
                 
            if not audio_data:
                raise Exception("No audio data received")
                
            with open(output_path, "wb") as f:
                f.write(audio_data)
                
            return True

    except Exception as e:
        print(f"Volc TTS WS Failed: {e}")
        raise e

# Wrapper for synchronous call (if needed elsewhere, but we updated main.py to async)
def generate_volc_tts(text: str, output_path: str, voice: str = "zh_female_meilinvyou_moon_bigtts"):
    # This function is now just a bridge if called synchronously, 
    # but we should prefer calling the async version directly.
    # However, main.py uses run_in_executor which expects a sync function.
    # So we need to run the async function in a new loop here?
    # OR better: update main.py to await generate_volc_tts_ws directly!
    # Let's try to update main.py to use async await.
    pass
