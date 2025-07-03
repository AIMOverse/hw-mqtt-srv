"""
MQTT AI Agent Server - Main module

A streaming speech-to-speech AI Agent server for IoT devices using MQTT protocol.
"""

import asyncio
import signal
import sys
from pathlib import Path

from loguru import logger

from .config import Config, create_example_env_file
from .ai_services import OpenAIRealtimeService
from .mqtt import MQTTAIServer


def setup_logging(log_level: str = "INFO") -> None:
    """Setup logging configuration."""
    logger.remove()  # Remove default handler
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    logger.add(
        "logs/mqtt-ai-server.log",
        level=log_level,
        rotation="10 MB",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )


async def main_async() -> None:
    """Main entry point for the MQTT AI Agent server."""
    
    logger.info("Starting MQTT AI Agent Server")
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = Config.from_env()
        
        # Setup logging
        setup_logging(config.server.log_level)
        
        logger.info("Configuration loaded successfully")
        logger.debug(f"Config: {config.to_dict()}")
        
        # Create AI service
        logger.info("Initializing AI service...")
        ai_service = OpenAIRealtimeService({
            "api_key": config.openai.api_key,
            "model": config.openai.model,
            "base_url": config.openai.base_url,
            "voice": config.openai.voice,
            "instructions": config.openai.instructions
        })
        
        # Create MQTT server
        logger.info("Creating MQTT server...")
        mqtt_config = {
            "host": config.mqtt.host,
            "port": config.mqtt.port,
            "username": config.mqtt.username,
            "password": config.mqtt.password,
            "client_id": config.mqtt.client_id,
            "use_tls": config.mqtt.use_tls,
            "keepalive": config.mqtt.keepalive,
            "request_topic": config.mqtt.request_topic,
            "response_topic": config.mqtt.response_topic,
            "health_topic": config.mqtt.health_topic
        }
        
        server_config = {
            "max_concurrent_sessions": config.server.max_concurrent_sessions,
            "session_timeout_seconds": config.server.session_timeout_seconds,
            "enable_health_checks": config.server.enable_health_checks,
            "health_check_interval": config.server.health_check_interval
        }
        
        mqtt_server = MQTTAIServer(
            mqtt_config=mqtt_config,
            ai_service=ai_service,
            server_config=server_config
        )
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum: int, frame) -> None:
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            asyncio.create_task(mqtt_server.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start server
        logger.info("Starting MQTT AI server...")
        async with mqtt_server.run_context():
            logger.info("MQTT AI Agent Server is running. Press Ctrl+C to stop.")
            
            # Keep the server running
            try:
                while mqtt_server._running:
                    await asyncio.sleep(1)
                    
                    # Log statistics periodically
                    stats = mqtt_server.get_stats()
                    if stats["message_stats"]["requests_processed"] > 0:
                        logger.debug(f"Server stats: {stats}")
                        
            except asyncio.CancelledError:
                logger.info("Server shutdown requested")
        
        logger.info("MQTT AI Agent Server stopped gracefully")
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.info("Creating example environment file...")
        create_example_env_file()
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


def create_env_example() -> None:
    """Create an example .env file."""
    create_example_env_file()
    print("\nExample .env file created. Please:")
    print("1. Copy .env.example to .env")
    print("2. Update the values in .env with your actual configuration")
    print("3. Run the server again")


def main() -> None:
    """Entry point for console script."""
    # Create logs directory if it doesn't exist
    Path("logs").mkdir(exist_ok=True)
    
    # Check if .env file exists, if not create example
    if not Path(".env").exists() and not Path(".env.example").exists():
        logger.warning("No .env file found. Creating example...")
        create_env_example()
        sys.exit(0)
    
    # Run the server
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 