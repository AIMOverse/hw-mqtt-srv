"""
AI Services package

Contains the abstract interface and concrete implementations for various AI service providers.
"""

from .base import AIServiceInterface, AudioRequest, AudioResponse
from .openai_realtime import OpenAIRealtimeService

__all__ = ["AIServiceInterface", "AudioRequest", "AudioResponse", "OpenAIRealtimeService"] 