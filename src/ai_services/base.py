"""
Abstract base class for AI services.

This module defines the interface that all AI service providers must implement,
making it easy to swap between different providers (OpenAI, DeepSeek, etc.).
Simplified for embedded device compatibility.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Optional, Dict, Any
import asyncio


@dataclass
class AudioRequest:
    """Simplified request object for audio processing."""
    
    audio_data: bytes  # Raw PCM16 audio data (24kHz, mono, 16-bit)
    session_id: str = ""
    device_id: str = ""


@dataclass 
class AudioResponse:
    """Simplified response object containing processed audio."""
    
    audio_data: bytes  # Raw PCM16 audio response (24kHz, mono, 16-bit)
    session_id: str = ""
    chunk_id: int = 0


class AIServiceInterface(ABC):
    """
    Abstract interface for AI service providers.
    
    This interface allows easy swapping between different AI service providers
    while maintaining a consistent API for the MQTT server.
    Simplified for embedded device compatibility.
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
            audio_request: Raw PCM16 audio data and session info
            
        Yields:
            AudioResponse: Processed PCM16 audio response chunks
        """
        # This should be implemented as an async generator that yields AudioResponse objects
        # Example implementation:
        # yield AudioResponse(audio_data=b"", session_id="", chunk_id=0)
        if False:  # This ensures the method is recognized as an async generator
            yield AudioResponse(audio_data=b"")
        raise NotImplementedError("Must be implemented as async generator")
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the AI service is healthy and responsive."""
        pass
    
    def get_supported_features(self) -> Dict[str, bool]:
        """Return supported features for this AI service."""
        return {
            "streaming": True,
            "voice_activity_detection": False,
            "speaker_diarization": False,
            "language_detection": False,
            "real_time_translation": False,
        }


# Exception classes for AI service errors
class AIServiceError(Exception):
    """Base exception for AI service errors."""
    pass


class AIServiceConnectionError(AIServiceError):
    """Exception raised when connection to AI service fails."""
    pass


class AIServiceProcessingError(AIServiceError):
    """Exception raised when audio processing fails."""
    pass


class AIServiceRateLimitError(AIServiceError):
    """Exception raised when rate limit is exceeded."""
    pass 