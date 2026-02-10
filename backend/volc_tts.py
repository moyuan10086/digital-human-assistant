import json
import uuid
import base64
import os
import websockets
import asyncio
from volc_protocol import full_client_request, receive_message, MsgType


VOLC_APPID = os.environ.get("VOLC_TTS_APPID", "YOUR_TTS_APPID")
VOLC_TOKEN = os.environ.get("VOLC_TTS_TOKEN", "YOUR_TTS_TOKEN")


VOLC_CLUSTER = "volcano_tts"

def get_cluster(voice: str) -> str:
    if voice.startswith("S_"):
         return "volcano_icl"
    
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
    pass
