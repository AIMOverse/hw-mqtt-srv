"""
MQTT AI Server implementation.

This module contains the main MQTT server that handles communication with IoT devices
and processes audio through the AI services.
"""

import asyncio
import time
from typing import Dict, Any, Optional, Set, Union
from contextlib import asynccontextmanager

import paho.mqtt.client as mqtt
from loguru import logger

from ..ai_services import AIServiceInterface, AudioRequest
from .messages import (
    MessageParser, 
    AudioRequestMessage, 
    AudioResponseMessage, 
    ErrorMessage,
    HealthCheckMessage,
    MessageType
)


class MQTTAIServer:
    """
    MQTT AI Server for handling streaming speech-to-speech communication with IoT devices.
    
    This server:
    1. Connects to an MQTT broker
    2. Listens for audio requests from IoT devices
    3. Processes audio through AI services (e.g., OpenAI Realtime API)
    4. Sends audio responses back to devices
    """
    
    def __init__(
        self,
        mqtt_config: Dict[str, Any],
        ai_service: AIServiceInterface,
        server_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the MQTT AI Server.
        
        Args:
            mqtt_config: MQTT broker configuration
            ai_service: AI service instance for processing audio
            server_config: Additional server configuration
        """
        self.mqtt_config = mqtt_config
        self.ai_service = ai_service
        self.server_config = server_config or {}
        
        # MQTT client
        self.mqtt_client: Optional[mqtt.Client] = None
        self._client_id = mqtt_config.get("client_id", "mqtt-ai-server")
        
        # Server state
        self._running = False
        self._start_time = time.time()
        self._active_sessions: Set[str] = set()
        self._message_stats = {
            "requests_processed": 0,
            "responses_sent": 0,
            "errors": 0
        }
        
        # Topics
        self.request_topic_pattern = mqtt_config.get("request_topic", "iot/+/audio_request")
        self.response_topic_template = mqtt_config.get("response_topic", "iot/{device_id}/audio_response")
        self.health_topic = mqtt_config.get("health_topic", "iot/server/health")
        
        # Processing settings
        self.max_concurrent_sessions = self.server_config.get("max_concurrent_sessions", 50)
        self.session_timeout_seconds = self.server_config.get("session_timeout_seconds", 300)
        
        # Event loop for thread-safe asyncio operations
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    async def start(self) -> None:
        """Start the MQTT AI server."""
        logger.info("Starting MQTT AI Server")
        
        try:
            # Store the current event loop for thread-safe operations
            self._loop = asyncio.get_running_loop()
            
            # Initialize AI service
            await self.ai_service.initialize()
            
            # Setup MQTT client
            await self._setup_mqtt_client()
            
            # Connect to broker
            await self._connect_to_broker()
            
            # Start background tasks
            asyncio.create_task(self._health_check_task())
            asyncio.create_task(self._session_cleanup_task())
            
            self._running = True
            logger.info("MQTT AI Server started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start MQTT AI Server: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop the MQTT AI server."""
        logger.info("Stopping MQTT AI Server")
        
        self._running = False
        
        # Disconnect MQTT client
        if self.mqtt_client:
            try:
                if hasattr(self.mqtt_client, 'is_connected') and self.mqtt_client.is_connected():
                    self.mqtt_client.disconnect()
                if hasattr(self.mqtt_client, 'loop_stop'):
                    self.mqtt_client.loop_stop()
            except Exception as e:
                logger.warning(f"Error during MQTT client disconnect: {e}")
        
        # Cleanup AI service
        await self.ai_service.cleanup()
        
        logger.info("MQTT AI Server stopped")
    
    @asynccontextmanager
    async def run_context(self):
        """Context manager for running the server."""
        await self.start()
        try:
            yield self
        finally:
            await self.stop()
    
    async def _setup_mqtt_client(self) -> None:
        """Setup the MQTT client with callbacks."""
        self.mqtt_client = mqtt.Client(
            client_id=self._client_id
        )
        
        # Set authentication if provided
        username = self.mqtt_config.get("username")
        password = self.mqtt_config.get("password")
        if username:
            self.mqtt_client.username_pw_set(username, password)
        
        # Set TLS if configured
        if self.mqtt_config.get("use_tls", False):
            self.mqtt_client.tls_set()
        
        # Set callbacks
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_disconnect = self._on_disconnect
        self.mqtt_client.on_message = self._on_message
        self.mqtt_client.on_subscribe = self._on_subscribe
        
        # Configure will message
        self.mqtt_client.will_set(
            self.health_topic,
            payload=self._create_health_message(status="offline").to_json(),
            qos=1,
            retain=True
        )
    
    async def _connect_to_broker(self) -> None:
        """Connect to the MQTT broker."""
        host = self.mqtt_config["host"]
        port = self.mqtt_config.get("port", 1883)
        keepalive = self.mqtt_config.get("keepalive", 60)
        
        logger.info(f"Connecting to MQTT broker at {host}:{port}")
        
        try:
            if self.mqtt_client is None:
                raise RuntimeError("MQTT client not initialized")
                
            self.mqtt_client.connect(host, port, keepalive)
            self.mqtt_client.loop_start()
            
            # Wait for connection
            timeout = 10
            start_time = time.time()
            while (hasattr(self.mqtt_client, 'is_connected') and 
                   not self.mqtt_client.is_connected() and 
                   (time.time() - start_time) < timeout):
                await asyncio.sleep(0.1)
            
            if (hasattr(self.mqtt_client, 'is_connected') and 
                not self.mqtt_client.is_connected()):
                raise ConnectionError("Failed to connect to MQTT broker within timeout")
                
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise
    
    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Dict[str, Any], rc: int) -> None:
        """Callback for when the client connects to the broker."""
        if rc == 0:
            logger.info("Connected to MQTT broker successfully")
            
            # Subscribe to request topics
            client.subscribe(self.request_topic_pattern, qos=1)
            
            # Publish health message
            health_message = self._create_health_message(status="online")
            client.publish(self.health_topic, health_message.to_json(), qos=1, retain=True)
            
        else:
            logger.error(f"Failed to connect to MQTT broker with result code {rc}")
    
    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        """Callback for when the client disconnects from the broker."""
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker (rc: {rc})")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def _on_subscribe(self, client: mqtt.Client, userdata: Any, mid: int, granted_qos: Any) -> None:
        """Callback for when subscription is acknowledged."""
        logger.info(f"Subscribed to topics successfully (mid: {mid})")
    
    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        """Callback for when a message is received."""
        if self._loop and not self._loop.is_closed():
            # Schedule the coroutine to run in the main event loop thread
            asyncio.run_coroutine_threadsafe(self._handle_message(msg), self._loop)
        else:
            logger.error("Event loop not available for handling message")
    
    async def _handle_message(self, msg: mqtt.MQTTMessage) -> None:
        """Handle incoming MQTT message."""
        try:
            # Parse message
            message = MessageParser.parse_message(msg.payload)
            
            # Route to appropriate handler
            if isinstance(message, AudioRequestMessage):
                await self._handle_audio_request(message)
            else:
                logger.warning(f"Unsupported message type: {type(message)}")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            self._message_stats["errors"] += 1
    
    async def _handle_audio_request(self, request: AudioRequestMessage) -> None:
        """Handle audio request from IoT device."""
        start_time = time.time()
        device_id = request.device_id
        session_id = request.session_id
        processing_time = 0.0  # Initialize processing_time
        
        logger.info(f"Processing audio request from device {device_id} (session: {session_id})")
        
        try:
            # Check concurrent sessions limit
            if len(self._active_sessions) >= self.max_concurrent_sessions:
                await self._send_error_response(
                    request, 
                    "CAPACITY_EXCEEDED", 
                    "Server at maximum capacity"
                )
                return
            
            # Add to active sessions
            self._active_sessions.add(session_id)
            
            # Create AI service request
            ai_request = AudioRequest(
                audio_data=request.get_audio_bytes(),
                format=request.audio_metadata.format,
                sample_rate=request.audio_metadata.sample_rate,
                channels=request.audio_metadata.channels,
                session_id=session_id,
                device_id=device_id,
                language=request.language,
                voice=request.voice,
                additional_config={
                    "instructions": request.instructions,
                    **(request.config or {})
                }
            )
            
            # Process through AI service
            async for response_chunk in self.ai_service.process_audio_stream(ai_request):
                processing_time = (time.time() - start_time) * 1000
                
                # Create response message
                response_msg = AudioResponseMessage.create(
                    request_message=request,
                    audio_data=response_chunk.audio_data,
                    transcript=response_chunk.transcript,
                    processing_time_ms=processing_time,
                    cost_estimate=response_chunk.cost_estimate,
                    chunk_id=response_chunk.chunk_id,
                    total_chunks=response_chunk.total_chunks,
                    metadata=response_chunk.metadata
                )
                
                # Send response
                await self._send_audio_response(response_msg)
            
            processing_time = (time.time() - start_time) * 1000
            self._message_stats["requests_processed"] += 1
            logger.info(f"Completed audio request for device {device_id} in {processing_time:.2f}ms")
            
        except Exception as e:
            logger.error(f"Error processing audio request: {e}")
            await self._send_error_response(request, "PROCESSING_ERROR", str(e))
            self._message_stats["errors"] += 1
        
        finally:
            # Remove from active sessions
            self._active_sessions.discard(session_id)
    
    async def _send_audio_response(self, response: AudioResponseMessage) -> None:
        """Send audio response to IoT device."""
        topic = self.response_topic_template.format(device_id=response.device_id)
        
        try:
            if self.mqtt_client is None:
                logger.error("MQTT client not available for publishing response")
                return
                
            result = self.mqtt_client.publish(
                topic,
                response.to_json(),
                qos=1
            )
            
            if hasattr(result, 'rc') and result.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.error(f"Failed to publish response: {result.rc}")
            else:
                self._message_stats["responses_sent"] += 1
                
        except Exception as e:
            logger.error(f"Error sending audio response: {e}")
    
    async def _send_error_response(
        self, 
        original_request: AudioRequestMessage, 
        error_code: str, 
        error_message: str
    ) -> None:
        """Send error response to IoT device."""
        error_msg = ErrorMessage.create(
            device_id=original_request.device_id,
            error_code=error_code,
            error_message=error_message,
            original_message=original_request,
            session_id=original_request.session_id
        )
        
        topic = self.response_topic_template.format(device_id=original_request.device_id)
        
        try:
            if self.mqtt_client is not None:
                self.mqtt_client.publish(topic, error_msg.to_json(), qos=1)
        except Exception as e:
            logger.error(f"Error sending error response: {e}")
    
    async def _health_check_task(self) -> None:
        """Background task for publishing health status."""
        while self._running:
            try:
                # Check AI service health
                ai_healthy = await self.ai_service.health_check()
                status = "healthy" if ai_healthy else "degraded"
                
                health_message = self._create_health_message(status)
                
                if self.mqtt_client is not None:
                    self.mqtt_client.publish(
                        self.health_topic,
                        health_message.to_json(),
                        qos=1,
                        retain=True
                    )
                
                # Wait before next health check
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in health check task: {e}")
                await asyncio.sleep(30)
    
    async def _session_cleanup_task(self) -> None:
        """Background task for cleaning up stale sessions."""
        while self._running:
            try:
                # For now, just log active sessions count
                if self._active_sessions:
                    logger.debug(f"Active sessions: {len(self._active_sessions)}")
                
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in session cleanup task: {e}")
                await asyncio.sleep(60)
    
    def _create_health_message(self, status: str = "healthy") -> HealthCheckMessage:
        """Create a health check message."""
        uptime = time.time() - self._start_time
        
        return HealthCheckMessage(
            message_id="",  # Will be auto-generated
            device_id="server",
            timestamp=time.time(),
            message_type=MessageType.HEALTH_CHECK,
            session_id="",
            status=status,
            uptime_seconds=uptime,
            active_sessions=len(self._active_sessions),
            system_info={
                "ai_service": type(self.ai_service).__name__,
                "supported_features": self.ai_service.get_supported_features(),
                "stats": self._message_stats.copy()
            }
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics."""
        return {
            "uptime_seconds": time.time() - self._start_time,
            "active_sessions": len(self._active_sessions),
            "is_running": self._running,
            "mqtt_connected": (hasattr(self.mqtt_client, 'is_connected') and 
                              self.mqtt_client.is_connected()) if self.mqtt_client else False,
            "message_stats": self._message_stats.copy()
        } 