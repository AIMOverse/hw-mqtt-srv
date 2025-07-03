"""
Abstract base class for AI services.

This module defines the interface that all AI service providers must implement,
making it easy to swap between different providers (OpenAI, DeepSeek, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional, Dict, Any
import asyncio


@dataclass
class AudioRequest:
    """Request object for audio processing."""
    
    audio_data: bytes
    format: str = "mp3"
    sample_rate: int = 16000
    channels: int = 1
    session_id: str = ""
    device_id: str = ""
    language: Optional[str] = None
    voice: Optional[str] = None
    additional_config: Optional[Dict[str, Any]] = None


@dataclass 
class AudioResponse:
    """Response object containing processed audio and metadata."""
    
    audio_data: bytes
    format: str = "mp3"
    transcript: str = ""
    processing_time_ms: float = 0.0
    cost_estimate: float = 0.0
    session_id: str = ""
    chunk_id: int = 0
    total_chunks: int = 1
    metadata: Optional[Dict[str, Any]] = None


class AIServiceInterface(ABC):
    """
    Abstract interface for AI service providers.
    
    This interface allows easy swapping between different AI service providers
    while maintaining a consistent API for the MQTT server.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the AI service with configuration."""
        self.config = config
        self._session_cache: Dict[str, Any] = {}
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the AI service (connect to APIs, load models, etc.)."""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up resources (close connections, etc.)."""
        pass
    
    @abstractmethod
    async def process_audio_stream(
        self, 
        audio_request: AudioRequest
    ) -> AsyncIterator[AudioResponse]:
        """
        Process streaming audio and yield response chunks.
        
        Args:
            audio_request: Audio data and configuration
            
        Yields:
            AudioResponse: Processed audio response chunks
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the AI service is healthy and responsive."""
        pass
    
    def get_supported_features(self) -> Dict[str, bool]:
        """Return a dictionary of supported features."""
        return {
            "streaming": True,
            "voice_activity_detection": False,
            "speaker_diarization": False,
            "language_detection": False,
            "real_time_translation": False,
        }
    
    async def estimate_cost(self, audio_duration_seconds: float) -> float:
        """Estimate the cost for processing audio of given duration."""
        return 0.0
    
    def _create_session_key(self, device_id: str, session_id: str) -> str:
        """Create a unique session key for caching."""
        return f"{device_id}:{session_id}"
    
    def _get_session_data(self, device_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data from cache."""
        key = self._create_session_key(device_id, session_id)
        return self._session_cache.get(key)
    
    def _store_session_data(self, device_id: str, session_id: str, data: Dict[str, Any]) -> None:
        """Store session data in cache."""
        key = self._create_session_key(device_id, session_id)
        self._session_cache[key] = data
    
    def _clear_session_data(self, device_id: str, session_id: str) -> None:
        """Clear session data from cache."""
        key = self._create_session_key(device_id, session_id)
        self._session_cache.pop(key, None)


class AIServiceError(Exception):
    """Base exception for AI service errors."""
    pass


class AIServiceConnectionError(AIServiceError):
    """Exception raised when AI service connection fails."""
    pass


class AIServiceProcessingError(AIServiceError):
    """Exception raised when AI service processing fails."""
    pass


class AIServiceRateLimitError(AIServiceError):
    """Exception raised when AI service rate limit is exceeded."""
    pass 