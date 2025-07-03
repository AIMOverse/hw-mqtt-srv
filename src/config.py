"""
Configuration module for MQTT AI Agent Server.

This module handles loading configuration from environment variables and config files.
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv


@dataclass
class MQTTConfig:
    """MQTT broker configuration."""
    
    host: str
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: str = "mqtt-ai-server"
    use_tls: bool = False
    keepalive: int = 60
    request_topic: str = "iot/+/audio_request"
    response_topic: str = "iot/{device_id}/audio_response"
    health_topic: str = "iot/server/health"


@dataclass
class OpenAIConfig:
    """OpenAI API configuration."""
    
    api_key: str
    model: str = "gpt-4o-realtime-preview"
    base_url: str = "wss://api.openai.com/v1/realtime"
    voice: str = "alloy"
    instructions: str = "You are a helpful AI assistant responding to voice commands from IoT devices."


@dataclass
class ServerConfig:
    """Server configuration."""
    
    max_concurrent_sessions: int = 50
    session_timeout_seconds: int = 300
    log_level: str = "INFO"
    enable_health_checks: bool = True
    health_check_interval: int = 30


@dataclass
class Config:
    """Main configuration object."""
    
    mqtt: MQTTConfig
    openai: OpenAIConfig
    server: ServerConfig = field(default_factory=ServerConfig)
    
    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> "Config":
        """Load configuration from environment variables."""
        
        # Load .env file if specified
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()  # Load from default .env file
        
        # MQTT configuration
        mqtt_config = MQTTConfig(
            host=os.getenv("MQTT_HOST", "localhost"),
            port=int(os.getenv("MQTT_PORT", "1883")),
            username=os.getenv("MQTT_USERNAME"),
            password=os.getenv("MQTT_PASSWORD"),
            client_id=os.getenv("MQTT_CLIENT_ID", "mqtt-ai-server"),
            use_tls=os.getenv("MQTT_USE_TLS", "false").lower() == "true",
            keepalive=int(os.getenv("MQTT_KEEPALIVE", "60")),
            request_topic=os.getenv("MQTT_REQUEST_TOPIC", "iot/+/audio_request"),
            response_topic=os.getenv("MQTT_RESPONSE_TOPIC", "iot/{device_id}/audio_response"),
            health_topic=os.getenv("MQTT_HEALTH_TOPIC", "iot/server/health")
        )
        
        # OpenAI configuration
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        openai_config = OpenAIConfig(
            api_key=openai_api_key,
            model=os.getenv("OPENAI_MODEL", "gpt-4o-realtime-preview"),
            base_url=os.getenv("OPENAI_BASE_URL", "wss://api.openai.com/v1/realtime"),
            voice=os.getenv("OPENAI_VOICE", "alloy"),
            instructions=os.getenv(
                "OPENAI_INSTRUCTIONS", 
                "You are a helpful AI assistant responding to voice commands from IoT devices."
            )
        )
        
        # Server configuration
        server_config = ServerConfig(
            max_concurrent_sessions=int(os.getenv("MAX_CONCURRENT_SESSIONS", "50")),
            session_timeout_seconds=int(os.getenv("SESSION_TIMEOUT_SECONDS", "300")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            enable_health_checks=os.getenv("ENABLE_HEALTH_CHECKS", "true").lower() == "true",
            health_check_interval=int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))
        )
        
        return cls(
            mqtt=mqtt_config,
            openai=openai_config,
            server=server_config
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "mqtt": {
                "host": self.mqtt.host,
                "port": self.mqtt.port,
                "username": self.mqtt.username,
                "password": "***" if self.mqtt.password else None,
                "client_id": self.mqtt.client_id,
                "use_tls": self.mqtt.use_tls,
                "keepalive": self.mqtt.keepalive,
                "request_topic": self.mqtt.request_topic,
                "response_topic": self.mqtt.response_topic,
                "health_topic": self.mqtt.health_topic
            },
            "openai": {
                "api_key": "***",
                "model": self.openai.model,
                "base_url": self.openai.base_url,
                "voice": self.openai.voice,
                "instructions": self.openai.instructions
            },
            "server": {
                "max_concurrent_sessions": self.server.max_concurrent_sessions,
                "session_timeout_seconds": self.server.session_timeout_seconds,
                "log_level": self.server.log_level,
                "enable_health_checks": self.server.enable_health_checks,
                "health_check_interval": self.server.health_check_interval
            }
        }


def create_example_env_file(filename: str = ".env.example") -> None:
    """Create an example environment file."""
    
    content = """# MQTT AI Agent Server Configuration

# MQTT Broker Settings
MQTT_HOST=broker.emqx.io
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_CLIENT_ID=mqtt-ai-server
MQTT_USE_TLS=false
MQTT_KEEPALIVE=60

# MQTT Topics
MQTT_REQUEST_TOPIC=iot/+/audio_request
MQTT_RESPONSE_TOPIC=iot/{device_id}/audio_response
MQTT_HEALTH_TOPIC=iot/server/health

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-realtime-preview
OPENAI_BASE_URL=wss://api.openai.com/v1/realtime
OPENAI_VOICE=alloy
OPENAI_INSTRUCTIONS=You are a helpful AI assistant responding to voice commands from IoT devices.

# Server Settings
MAX_CONCURRENT_SESSIONS=50
SESSION_TIMEOUT_SECONDS=300
LOG_LEVEL=INFO
ENABLE_HEALTH_CHECKS=true
HEALTH_CHECK_INTERVAL=30
"""
    
    with open(filename, "w") as f:
        f.write(content)
    
    print(f"Example environment file created: {filename}")
    print("Please copy this to .env and update with your actual values.") 