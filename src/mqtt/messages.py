"""
MQTT message format definitions.

This module defines the simplified message formats used for communication between IoT devices and the AI server.
Optimized for embedded devices with minimal processing overhead.
"""

import json
import base64
import time
import uuid
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Union


class MessageType(Enum):
    """Enumeration of MQTT message types."""
    AUDIO_REQUEST = "audio_request"
    AUDIO_RESPONSE = "audio_response"
    HEALTH_CHECK = "health_check"
    ERROR = "error"
    SESSION_START = "session_start"
    SESSION_END = "session_end"


@dataclass
class AudioMessage:
    """Base class for audio messages in MQTT communication."""
    
    message_id: str
    device_id: str
    timestamp: float
    message_type: MessageType
    session_id: str
    
    def __post_init__(self) -> None:
        """Ensure message_id and timestamp are set."""
        if not self.message_id:
            self.message_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for JSON serialization."""
        data = asdict(self)
        data["message_type"] = self.message_type.value
        return data
    
    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioMessage":
        """Create message from dictionary."""
        # Convert message_type back to enum
        if "message_type" in data:
            data["message_type"] = MessageType(data["message_type"])
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> "AudioMessage":
        """Create message from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class AudioRequestMessage(AudioMessage):
    """Simplified audio request message from IoT device to AI server."""
    
    audio_data: bytes  # Raw PCM16 audio data (24kHz, mono, 16-bit)
    
    def __post_init__(self) -> None:
        super().__post_init__()
        self.message_type = MessageType.AUDIO_REQUEST
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for JSON serialization."""
        data = super().to_dict()
        # Encode audio data as base64 for JSON transport
        data["audio_data"] = base64.b64encode(self.audio_data).decode()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioRequestMessage":
        """Create AudioRequestMessage from dictionary."""
        # Convert message_type back to enum
        if "message_type" in data:
            data["message_type"] = MessageType(data["message_type"])
        
        # Decode base64 audio data back to bytes
        if "audio_data" in data and isinstance(data["audio_data"], str):
            data["audio_data"] = base64.b64decode(data["audio_data"])
        
        return cls(**data)
    
    @classmethod
    def create(
        cls,
        device_id: str,
        audio_data: bytes,
        session_id: str = "",
        **kwargs: Any
    ) -> "AudioRequestMessage":
        """Create a simplified audio request message."""
        
        return cls(
            message_id=str(uuid.uuid4()),
            device_id=device_id,
            timestamp=time.time(),
            message_type=MessageType.AUDIO_REQUEST,
            session_id=session_id or str(uuid.uuid4()),
            audio_data=audio_data
        )


@dataclass
class AudioResponseMessage(AudioMessage):
    """Simplified audio response message from AI server to IoT device."""
    
    audio_data: bytes  # Raw PCM16 audio response (24kHz, mono, 16-bit)
    
    def __post_init__(self) -> None:
        super().__post_init__()
        self.message_type = MessageType.AUDIO_RESPONSE
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for JSON serialization."""
        data = super().to_dict()
        # Encode audio data as base64 for JSON transport
        data["audio_data"] = base64.b64encode(self.audio_data).decode()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioResponseMessage":
        """Create AudioResponseMessage from dictionary."""
        # Convert message_type back to enum
        if "message_type" in data:
            data["message_type"] = MessageType(data["message_type"])
        
        # Decode base64 audio data back to bytes
        if "audio_data" in data and isinstance(data["audio_data"], str):
            data["audio_data"] = base64.b64decode(data["audio_data"])
        
        return cls(**data)
    
    @classmethod
    def create(
        cls,
        request_message: AudioRequestMessage,
        audio_data: bytes,
        **kwargs: Any
    ) -> "AudioResponseMessage":
        """Create a simplified audio response message from a request."""
        
        return cls(
            message_id=str(uuid.uuid4()),
            device_id=request_message.device_id,
            timestamp=time.time(),
            message_type=MessageType.AUDIO_RESPONSE,
            session_id=request_message.session_id,
            audio_data=audio_data
        )


@dataclass
class ErrorMessage(AudioMessage):
    """Error message for communication issues."""
    
    error_code: str
    error_message: str
    original_message_id: Optional[str] = None
    
    def __post_init__(self) -> None:
        super().__post_init__()
        self.message_type = MessageType.ERROR
    
    @classmethod
    def create(
        cls,
        device_id: str,
        error_code: str,
        error_message: str,
        original_message: Optional[AudioMessage] = None,
        session_id: str = ""
    ) -> "ErrorMessage":
        """Create an error message."""
        return cls(
            message_id=str(uuid.uuid4()),
            device_id=device_id,
            timestamp=time.time(),
            message_type=MessageType.ERROR,
            session_id=session_id,
            error_code=error_code,
            error_message=error_message,
            original_message_id=original_message.message_id if original_message else None
        )


@dataclass
class HealthCheckMessage(AudioMessage):
    """Health check message for system monitoring."""
    
    status: str = "healthy"
    uptime_seconds: float = 0.0
    active_sessions: int = 0
    system_info: Optional[Dict[str, Any]] = None
    
    def __post_init__(self) -> None:
        super().__post_init__()
        self.message_type = MessageType.HEALTH_CHECK


class MessageParser:
    """Utility class for parsing MQTT messages."""
    
    @staticmethod
    def parse_message(payload: Union[str, bytes]) -> AudioMessage:
        """Parse MQTT payload into appropriate message type."""
        
        if isinstance(payload, bytes):
            payload = payload.decode('utf-8')
        
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON payload: {e}")
        
        message_type = data.get("message_type")
        if not message_type:
            raise ValueError("Missing message_type in payload")
        
        try:
            msg_type = MessageType(message_type)
        except ValueError:
            raise ValueError(f"Unknown message type: {message_type}")
        
        # Route to appropriate message class
        if msg_type == MessageType.AUDIO_REQUEST:
            return AudioRequestMessage.from_dict(data)
        elif msg_type == MessageType.AUDIO_RESPONSE:
            return AudioResponseMessage.from_dict(data)
        elif msg_type == MessageType.ERROR:
            return ErrorMessage.from_dict(data)
        elif msg_type == MessageType.HEALTH_CHECK:
            return HealthCheckMessage.from_dict(data)
        else:
            return AudioMessage.from_dict(data)
    
    @staticmethod
    def create_topic(device_id: str, message_type: MessageType, suffix: str = "") -> str:
        """Create MQTT topic for a device and message type."""
        base_topic = f"iot/{device_id}/{message_type.value}"
        return f"{base_topic}/{suffix}" if suffix else base_topic 