import gzip
import json
import uuid
import websockets
import asyncio
from typing import Dict, Any, Optional
import logging
import copy

try:
    import backend.volc_realtime_protocol as protocol
except ImportError:
    try:
        import volc_realtime_protocol as protocol
    except ImportError:
        from backend import volc_realtime_protocol as protocol

logger = logging.getLogger(__name__)

# 默认配置模板
DEFAULT_START_SESSION_REQ = {
    "asr": {
        "extra": {
            "end_smooth_window_ms": 1500,
        },
    },
    "tts": {
        "speaker": "zh_male_yunzhou_jupiter_bigtts", # 默认音色
        "audio_config": {
            "channel": 1,
            "format": "pcm",
            "sample_rate": 24000
        },
    },
    "dialog": {
        "bot_name": "广东技术师范大学的AI助教",
        "system_role": "你是由广东技术师范大学和立源云共同开发的AI助教。你不是豆包，不是字节跳动的产品。",
        "speaking_style": "请用通俗易懂、简短的语言与用户进行交互，避免长篇大论。回答时请不要包含时间戳或其他无关的元数据。",
        "location": {
          "city": "广州",
        },
        "extra": {
            "strict_audit": False,
            "audit_response": "支持客户自定义安全审核回复话术。",
            "recv_timeout": 10,
            "input_mod": "audio"
        }
    }
}

class RealtimeDialogClient:
    def __init__(self, 
                 app_id: str, 
                 access_token: str, 
                 resource_id: str = "volc.speech.dialog",
                 base_url: str = "wss://openspeech.bytedance.com/api/v3/realtime/dialogue",
                 session_id: str = None):
        
        self.app_id = app_id
        self.access_token = access_token
        self.resource_id = resource_id
        self.base_url = base_url
        self.session_id = session_id or str(uuid.uuid4())
        self.ws = None
        self.logid = ""
        self.seq = 1
        
    async def __aenter__(self):
        # Default connect without voice override if used in context manager directly
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def connect(self, voice: str = None, system_prompt: str = None, speaking_style: str = None):
        headers = {
            "X-Api-App-ID": self.app_id,
            "X-Api-Access-Key": self.access_token,
            "X-Api-App-Key": "PlgvMymc7f3tQnJ6",  # Fixed value from documentation
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Connect-Id": str(uuid.uuid4()),
        }
        
        logger.info(f"Connecting to Realtime API: {self.base_url}")
        # Use additional_headers (correct parameter name for websockets library)
        try:
            self.ws = await websockets.connect(
                self.base_url,
                additional_headers=headers,
                ping_interval=None
            )
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise e
                 
        if not self.ws:
             raise Exception("Failed to connect to Volcengine due to library error")

        # websockets 16.0+ uses response.headers instead of response_headers
        try:
            self.logid = self.ws.response.headers.get("X-Tt-Logid")
        except AttributeError:
            # Fallback for older versions
            self.logid = getattr(self.ws, 'response_headers', {}).get("X-Tt-Logid", "")
        logger.info(f"Connected. Logid: {self.logid}")
        
        # 1. Send StartConnection
        try:
            req = bytearray(protocol.generate_header())
            req.extend(int(1).to_bytes(4, 'big')) # Seq 1
            payload = gzip.compress("{}".encode('utf-8'))
            req.extend(len(payload).to_bytes(4, 'big'))
            req.extend(payload)
            
            await self.ws.send(req)
            resp = await self.ws.recv()
            parsed = protocol.parse_response(resp)
            logger.info(f"StartConnection Response: {parsed}")
            
            if parsed.get('code') and parsed.get('code') != 0:
                logger.error(f"StartConnection Failed with code: {parsed.get('code')}")
                # Don't raise immediately, let's see if we can continue or if it's fatal
                # Usually fatal.
        except Exception as e:
            logger.error(f"StartConnection Error: {e}")
            raise e
        
        # 2. Send StartSession
        try:
            session_config = copy.deepcopy(DEFAULT_START_SESSION_REQ)

            # Override voice if provided
            if voice:
                logger.info(f"Setting Realtime Voice to: {voice}")
                session_config["tts"]["speaker"] = voice

            # Override system_role and speaking_style if provided
            if system_prompt:
                logger.info(f"Setting system_role to: {system_prompt}")
                session_config["dialog"]["system_role"] = system_prompt

            if speaking_style:
                logger.info(f"Setting speaking_style to: {speaking_style}")
                session_config["dialog"]["speaking_style"] = speaking_style

            payload_json = json.dumps(session_config)
            payload_bytes = gzip.compress(payload_json.encode('utf-8'))
            
            req = bytearray(protocol.generate_header())
            req.extend(int(100).to_bytes(4, 'big')) # Seq 100
            
            req.extend(len(self.session_id).to_bytes(4, 'big'))
            req.extend(self.session_id.encode('utf-8'))
            
            req.extend(len(payload_bytes).to_bytes(4, 'big'))
            req.extend(payload_bytes)
            
            await self.ws.send(req)
            resp = await self.ws.recv()
            parsed = protocol.parse_response(resp)
            logger.info(f"StartSession Response: {parsed}")
            
            if parsed.get('code') and parsed.get('code') != 0:
                logger.error(f"StartSession Failed: {parsed}")
        except Exception as e:
            logger.error(f"StartSession Error: {e}")
            raise e
        
    async def send_audio(self, audio_data: bytes):
        if not self.ws:
            return
            
        # Ref code: task_request
        # message_type=CLIENT_AUDIO_ONLY_REQUEST, serial_method=NO_SERIALIZATION
        req = bytearray(protocol.generate_header(
            message_type=protocol.CLIENT_AUDIO_ONLY_REQUEST,
            serial_method=protocol.NO_SERIALIZATION
        ))
        
        req.extend(int(200).to_bytes(4, 'big')) # Using 200 as per ref code
        
        req.extend(len(self.session_id).to_bytes(4, 'big'))
        req.extend(self.session_id.encode('utf-8'))
        
        payload_bytes = gzip.compress(audio_data)
        req.extend(len(payload_bytes).to_bytes(4, 'big'))
        req.extend(payload_bytes)
        
        await self.ws.send(req)
        
    async def receive(self):
        if not self.ws:
            return None
        return await self.ws.recv()
    
    async def parse_message(self, msg_data):
        return protocol.parse_response(msg_data)
        
    async def close(self):
        if self.ws:
            # Finish Session
            try:
                finish_req = bytearray(protocol.generate_header())
                finish_req.extend(int(102).to_bytes(4, 'big'))
                payload = gzip.compress("{}".encode('utf-8'))
                finish_req.extend(len(self.session_id).to_bytes(4, 'big'))
                finish_req.extend(self.session_id.encode('utf-8'))
                finish_req.extend(len(payload).to_bytes(4, 'big'))
                finish_req.extend(payload)
                await self.ws.send(finish_req)
            except:
                pass
                
            await self.ws.close()
