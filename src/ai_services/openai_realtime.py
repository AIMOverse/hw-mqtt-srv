"""
OpenAI Realtime API service implementation.

This module implements the OpenAI Realtime API for direct speech-to-speech communication.
"""

import asyncio
import json
import base64
import time
from typing import AsyncIterator, Dict, Any, Optional, Union

import websockets
from loguru import logger

from .base import (
    AIServiceInterface, 
    AudioRequest, 
    AudioResponse,
    AIServiceConnectionError,
    AIServiceProcessingError,
    AIServiceRateLimitError
)


class OpenAIRealtimeService(AIServiceInterface):
    """
    OpenAI Realtime API service implementation.
    
    Provides direct speech-to-speech communication using OpenAI's Realtime API.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key")
        self.model = config.get("model", "gpt-4o-realtime-preview")
        # Base URL from configuration (supports environment variable OPENAI_BASE_URL)
        self.base_url = config.get("base_url", "wss://api.openai.com/v1/realtime")
        self.websocket: Optional[Any] = None
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
        
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
    
    async def initialize(self) -> None:
        """Initialize the OpenAI Realtime service."""
        logger.info("Initializing OpenAI Realtime service")
        # Test connection
        await self.health_check()
        logger.info("OpenAI Realtime service initialized successfully")
    
    async def cleanup(self) -> None:
        """Clean up OpenAI Realtime service resources."""
        logger.info("Cleaning up OpenAI Realtime service")
        
        # Close all active sessions
        for session_data in self._active_sessions.values():
            ws = session_data.get("websocket")
            if ws and ws.close_code is None:  # None means connection is still open
                await ws.close()
        
        self._active_sessions.clear()
        logger.info("OpenAI Realtime service cleanup completed")
    
    async def process_audio_stream(
        self, 
        audio_request: AudioRequest
    ) -> AsyncIterator[AudioResponse]:
        """
        Process streaming audio using OpenAI Realtime API.
        
        Args:
            audio_request: Audio data and configuration
            
        Yields:
            AudioResponse: Processed audio response chunks
        """
        session_key = self._create_session_key(audio_request.device_id, audio_request.session_id)
        start_time = time.time()
        
        try:
            # Get or create session
            session_data = await self._get_or_create_session(audio_request)
            websocket = session_data["websocket"]
            
            # Send audio data
            await self._send_audio_data(websocket, audio_request.audio_data)
            
            # Process responses
            chunk_id = 0
            async for response_chunk in self._receive_audio_responses(websocket, session_key):
                processing_time = (time.time() - start_time) * 1000
                
                yield AudioResponse(
                    audio_data=response_chunk["audio_data"],
                    format="mp3",
                    transcript=response_chunk.get("transcript", ""),
                    processing_time_ms=processing_time,
                    cost_estimate=await self.estimate_cost(len(audio_request.audio_data) / 16000),
                    session_id=audio_request.session_id,
                    chunk_id=chunk_id,
                    total_chunks=1,  # Unknown for streaming
                    metadata=response_chunk.get("metadata", {})
                )
                chunk_id += 1
                
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            # Remove failed session
            self._active_sessions.pop(session_key, None)
            if "Connection" in str(e):
                raise AIServiceConnectionError(f"Connection lost: {e}")
            else:
                raise AIServiceProcessingError(f"Processing failed: {e}")
    
    async def health_check(self) -> bool:
        """Check if OpenAI Realtime API is accessible."""
        try:
            # Use the configured base URL from environment
            realtime_url = f"{self.base_url}?model={self.model}"
            
            # Try different connection approaches for compatibility
            websocket = None
            
            # Method 1: Try with additional_headers (newer websockets)
            try:
                headers = [
                    ("Authorization", f"Bearer {self.api_key}"),
                    ("OpenAI-Beta", "realtime=v1")
                ]
                websocket = await websockets.connect(realtime_url, additional_headers=headers)
                logger.info("Connected with additional_headers")
            except (TypeError, AttributeError, Exception) as e:
                logger.debug(f"additional_headers method failed: {e}")
                
            # Method 2: Try with extra_headers (some versions)
            if not websocket:
                try:
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "OpenAI-Beta": "realtime=v1"
                    }
                    websocket = await websockets.connect(realtime_url, extra_headers=headers)
                    logger.info("Connected with extra_headers")
                except (TypeError, AttributeError, Exception) as e:
                    logger.debug(f"extra_headers method failed: {e}")
            
            # Method 3: Basic connection without custom headers
            if not websocket:
                try:
                    logger.warning("Trying basic connection - authentication may fail")
                    websocket = await websockets.connect(realtime_url)
                    logger.info("Connected with basic method")
                except Exception as e:
                    logger.error(f"Basic connection failed: {e}")
                    return False
            
            # Test the connection
            if websocket:
                try:
                    result = await self._test_websocket_connection(websocket)
                    await websocket.close()
                    return result
                except Exception as e:
                    logger.error(f"Connection test failed: {e}")
                    try:
                        await websocket.close()
                    except Exception:
                        pass  # Ignore close errors
                    return False
            
            return False
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def _test_websocket_connection(self, websocket: Any) -> bool:
        """Test WebSocket connection by sending a session update."""
        try:
            # Send a simple session update
            await websocket.send(json.dumps({
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": "You are a helpful assistant.",
                    "voice": "alloy"
                }
            }))
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(response)
            
            return data.get("type") == "session.created"
        except Exception as e:
            logger.error(f"WebSocket test failed: {e}")
            return False
    
    def get_supported_features(self) -> Dict[str, bool]:
        """Return supported features for OpenAI Realtime API."""
        return {
            "streaming": True,
            "voice_activity_detection": True,
            "speaker_diarization": False,
            "language_detection": True,
            "real_time_translation": False,
        }
    
    async def estimate_cost(self, audio_duration_seconds: float) -> float:
        """Estimate cost based on OpenAI Realtime API pricing."""
        # $0.24 per minute for input/output
        minutes = audio_duration_seconds / 60
        return round(minutes * 0.24, 4)
    
    async def _get_or_create_session(self, audio_request: AudioRequest) -> Dict[str, Any]:
        """Get existing session or create a new one."""
        session_key = self._create_session_key(audio_request.device_id, audio_request.session_id)
        
        if session_key in self._active_sessions:
            session_data = self._active_sessions[session_key]
            # Check if connection is still alive
            if session_data["websocket"].close_code is None:  # None means connection is still open
                return session_data
        
        # Create new session
        logger.info(f"Creating new OpenAI Realtime session for {session_key}")
        websocket = await self._create_websocket_connection()
        
        # Initialize session
        await self._initialize_session(websocket, audio_request)
        
        session_data = {
            "websocket": websocket,
            "created_at": time.time(),
            "device_id": audio_request.device_id,
            "session_id": audio_request.session_id
        }
        
        self._active_sessions[session_key] = session_data
        return session_data
    
    async def _create_websocket_connection(self) -> Any:
        """Create a new WebSocket connection to OpenAI Realtime API."""
        # Use the configured base URL from environment
        realtime_url = f"{self.base_url}?model={self.model}"
        
        # Try different connection approaches for compatibility
        websocket = None
        connection_error = None
        
        # Method 1: Try with additional_headers (newer websockets)
        try:
            headers = [
                ("Authorization", f"Bearer {self.api_key}"),
                ("OpenAI-Beta", "realtime=v1")
            ]
            websocket = await websockets.connect(realtime_url, additional_headers=headers)
            logger.debug("Connected with additional_headers")
            return websocket
        except (TypeError, AttributeError, Exception) as e:
            connection_error = e
            logger.debug(f"additional_headers method failed: {e}")
            
        # Method 2: Try with extra_headers (some versions)
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
            websocket = await websockets.connect(realtime_url, extra_headers=headers)
            logger.debug("Connected with extra_headers")
            return websocket
        except (TypeError, AttributeError, Exception) as e:
            connection_error = e
            logger.debug(f"extra_headers method failed: {e}")
        
        # Method 3: Basic connection without custom headers (will likely fail auth)
        try:
            logger.warning("Using basic connection - authentication may fail")
            websocket = await websockets.connect(realtime_url)
            logger.debug("Connected with basic method")
            return websocket
        except Exception as e:
            connection_error = e
            logger.error(f"All connection methods failed. Last error: {e}")
            
        raise AIServiceConnectionError(f"Failed to create WebSocket connection: {connection_error}")
    
    async def _initialize_session(
        self, 
        websocket: Any, 
        audio_request: AudioRequest
    ) -> None:
        """Initialize the OpenAI Realtime session."""
        voice = audio_request.voice or "alloy"
        additional_config = audio_request.additional_config or {}
        instructions = additional_config.get(
            "instructions", 
            "You are a helpful AI assistant responding to voice commands from IoT devices."
        )
        
        session_config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": instructions,
                "voice": voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                }
            }
        }
        
        await websocket.send(json.dumps(session_config))
        
        # Wait for session.created response
        response = await asyncio.wait_for(websocket.recv(), timeout=10)
        data = json.loads(response)
        
        if data.get("type") != "session.created":
            raise AIServiceProcessingError(f"Failed to create session: {data}")
    
    async def _send_audio_data(
        self, 
        websocket: Any, 
        audio_data: bytes
    ) -> None:
        """Send audio data to the OpenAI Realtime API."""
        # Convert MP3 to PCM16 if needed
        pcm_data = await self._convert_to_pcm16(audio_data)
        
        # Send audio data
        audio_message = {
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(pcm_data).decode()
        }
        
        await websocket.send(json.dumps(audio_message))
        
        # Commit the audio buffer
        await websocket.send(json.dumps({
            "type": "input_audio_buffer.commit"
        }))
        
        # Request response generation
        await websocket.send(json.dumps({
            "type": "response.create"
        }))
    
    async def _receive_audio_responses(
        self, 
        websocket: Any,
        session_key: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """Receive and process audio responses from OpenAI Realtime API."""
        try:
            while True:
                message = await asyncio.wait_for(websocket.recv(), timeout=30)
                data = json.loads(message)
                
                message_type = data.get("type")
                
                if message_type == "response.audio.delta":
                    # Audio chunk received
                    audio_base64 = data.get("delta", "")
                    if audio_base64:
                        audio_data = base64.b64decode(audio_base64)
                        # Convert PCM16 back to MP3
                        mp3_data = await self._convert_from_pcm16(audio_data)
                        
                        yield {
                            "audio_data": mp3_data,
                            "transcript": "",
                            "metadata": {"type": "audio_delta"}
                        }
                
                elif message_type == "response.audio_transcript.delta":
                    # Transcript chunk received
                    transcript = data.get("delta", "")
                    if transcript:
                        yield {
                            "audio_data": b"",
                            "transcript": transcript,
                            "metadata": {"type": "transcript_delta"}
                        }
                
                elif message_type == "response.done":
                    # Response completed
                    break
                
                elif message_type == "error":
                    error_msg = data.get("error", {}).get("message", "Unknown error")
                    logger.error(f"OpenAI Realtime API error: {error_msg}")
                    raise AIServiceProcessingError(f"API error: {error_msg}")
                    
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for response in session {session_key}")
        except Exception:
            logger.info(f"WebSocket connection closed for session {session_key}")
    
    async def _convert_to_pcm16(self, audio_data: bytes) -> bytes:
        """Convert audio data to PCM16 format (placeholder implementation)."""
        # TODO: Implement actual audio conversion using pydub or similar
        # For now, assume input is already in correct format
        return audio_data
    
    async def _convert_from_pcm16(self, pcm_data: bytes) -> bytes:
        """Convert PCM16 data to MP3 format (placeholder implementation)."""
        # TODO: Implement actual audio conversion using pydub or similar
        # For now, return as-is
        return pcm_data 