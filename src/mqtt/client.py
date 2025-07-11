"""
MQTT AI Server implementation.

This module contains the main MQTT server that handles communication with IoT devices
and processes audio through the AI services.
Simplified for embedded device compatibility.
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
from ..ai_services.base import AIServiceProcessingError


class MQTTAIServer:
    """
    MQTT AI Server for handling streaming speech-to-speech communication with IoT devices.
    
    This server:
    1. Connects to an MQTT broker
    2. Listens for audio requests from IoT devices
    3. Processes audio through AI services (e.g., OpenAI Realtime API)
    4. Sends audio responses back to devices
    
    Simplified for embedded device compatibility.
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
        """Start the MQTT AI Server."""
        logger.info("Starting MQTT AI Server")
        
        # Initialize AI service
        await self.ai_service.initialize()
        
        # Connect to MQTT broker
        await self._connect_mqtt()
        
        # Start health check if enabled
        if self.server_config.get("enable_health_checks", True):
            health_interval = self.server_config.get("health_check_interval", 30)
            asyncio.create_task(self._health_check_loop(health_interval))
        
        self._running = True
        logger.info("MQTT AI Server started successfully")
    
    async def stop(self) -> None:
        """Stop the MQTT AI Server."""
        logger.info("Stopping MQTT AI Server")
        self._running = False
        
        # Disconnect from MQTT broker
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        # Clean up AI service
        await self.ai_service.cleanup()
        
        logger.info("MQTT AI Server stopped")
    
    async def _connect_mqtt(self) -> None:
        """Connect to MQTT broker."""
        logger.info(f"Connecting to MQTT broker at {self.mqtt_config['host']}:{self.mqtt_config['port']}")
        
        # Create MQTT client
        self.mqtt_client = mqtt.Client(client_id=self._client_id)
        
        # Set credentials if provided
        if self.mqtt_config.get("username") and self.mqtt_config.get("password"):
            self.mqtt_client.username_pw_set(
                self.mqtt_config["username"],
                self.mqtt_config["password"]
            )
        
        # Setup callbacks
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_disconnect = self._on_disconnect
        self.mqtt_client.on_message = self._on_message
        self.mqtt_client.on_subscribe = self._on_subscribe
        
        # Enable TLS if configured
        if self.mqtt_config.get("use_tls", False):
            self.mqtt_client.tls_set()
        
        # Connect to broker
        try:
            self.mqtt_client.connect(
                self.mqtt_config["host"],
                self.mqtt_config["port"],
                self.mqtt_config.get("keepalive", 60)
            )
            
            # Start the loop in a separate thread
            self.mqtt_client.loop_start()
            
            # Store event loop for async operations
            self._loop = asyncio.get_event_loop()
            
            logger.info("MQTT connection initiated")
            
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise
    
    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Dict[str, int], rc: int) -> None:
        """Callback for when the client connects to the broker."""
        if rc == 0:
            logger.info("Connected to MQTT broker successfully")
            
            # Subscribe to request topics
            client.subscribe(self.request_topic_pattern, qos=1)
            logger.info(f"Subscribed to {self.request_topic_pattern}")
            
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
        """Handle simplified audio request from IoT device."""
        device_id = request.device_id
        session_id = request.session_id
        
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
            
            # Create simplified AI service request
            ai_request = AudioRequest(
                audio_data=request.audio_data,  # Already raw PCM16 bytes
                session_id=session_id,
                device_id=device_id
            )
            
            # Process through AI service
            async for response_chunk in self.ai_service.process_audio_stream(ai_request):
                # Create simplified response message
                response_msg = AudioResponseMessage.create(
                    request_message=request,
                    audio_data=response_chunk.audio_data  # Already raw PCM16 bytes
                )
                
                # Send response
                await self._send_audio_response(response_msg)
            
            self._message_stats["requests_processed"] += 1
            logger.info(f"Completed audio request for device {device_id}")
            
        except AIServiceProcessingError as e:
            logger.warning(f"Client error processing audio request: {e}")
            await self._send_error_response(request, "PROCESSING_ERROR", str(e))
            self._message_stats["errors"] += 1
        except Exception as e:
            logger.error(f"Error processing audio request: {e}")
            await self._send_error_response(request, "PROCESSING_ERROR", str(e))
            self._message_stats["errors"] += 1
        
        finally:
            # Remove from active sessions
            self._active_sessions.discard(session_id)
    
    async def _send_audio_response(self, response: AudioResponseMessage) -> None:
        """Send audio response to IoT device."""
        try:
            # Format response topic
            response_topic = self.response_topic_template.format(device_id=response.device_id)
            
            # Publish response
            if self.mqtt_client:
                result = self.mqtt_client.publish(
                    response_topic,
                    response.to_json(),
                    qos=1
                )
                
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    self._message_stats["responses_sent"] += 1
                    logger.debug(f"Sent audio response to {response.device_id}")
                else:
                    logger.error(f"Failed to send audio response: {result.rc}")
            else:
                logger.error("MQTT client not available for sending response")
                
        except Exception as e:
            logger.error(f"Error sending audio response: {e}")
    
    async def _send_error_response(
        self, 
        original_request: AudioRequestMessage, 
        error_code: str, 
        error_message: str
    ) -> None:
        """Send error response to IoT device."""
        try:
            # Create error message
            error_msg = ErrorMessage.create(
                device_id=original_request.device_id,
                error_code=error_code,
                error_message=error_message,
                original_message=original_request,
                session_id=original_request.session_id
            )
            
            # Format response topic
            response_topic = self.response_topic_template.format(device_id=original_request.device_id)
            
            # Publish error
            if self.mqtt_client:
                result = self.mqtt_client.publish(
                    response_topic,
                    error_msg.to_json(),
                    qos=1
                )
                
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    logger.debug(f"Sent error response to {original_request.device_id}")
                else:
                    logger.error(f"Failed to send error response: {result.rc}")
            else:
                logger.error("MQTT client not available for sending error")
                
        except Exception as e:
            logger.error(f"Error sending error response: {e}")
    
    async def _health_check_loop(self, interval: int) -> None:
        """Periodic health check loop."""
        while self._running:
            try:
                # Perform health check
                await self._send_health_check()
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                await asyncio.sleep(interval)
    
    async def _send_health_check(self) -> None:
        """Send health check message."""
        try:
            # Check AI service health
            ai_healthy = await self.ai_service.health_check()
            status = "healthy" if ai_healthy else "unhealthy"
            
            # Create health message
            health_msg = self._create_health_message(status)
            
            # Send health message
            if self.mqtt_client:
                result = self.mqtt_client.publish(
                    self.health_topic,
                    health_msg.to_json(),
                    qos=0
                )
                
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    logger.debug(f"Sent health check: {status}")
                else:
                    logger.warning(f"Failed to send health check: {result.rc}")
                    
        except Exception as e:
            logger.error(f"Error sending health check: {e}")
    
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
    
    @asynccontextmanager
    async def run_context(self):
        """Context manager for running the server."""
        try:
            await self.start()
            yield self
        finally:
            await self.stop() 