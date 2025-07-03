"""
Simple MQTT client example for IoT devices.

This example shows how an IoT device can send audio requests and receive responses
from the MQTT AI Agent server.
"""

import asyncio
import base64
import json
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mqtt.messages import AudioRequestMessage, AudioResponseMessage, ErrorMessage, MessageParser, MessageType
from typing import Optional


class SimpleIoTClient:
    """Simple IoT client for testing the MQTT AI Agent server."""
    
    def __init__(self, device_id: str, broker_host: str = "localhost", broker_port: int = 1883):
        self.device_id = device_id
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = mqtt.Client(
            client_id=f"iot-client-{device_id}"
        )
        
        # Setup callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        # Topics
        self.request_topic = f"iot/{device_id}/audio_request"
        self.response_topic = f"iot/{device_id}/audio_response"
        
        self.connected = False
        self.responses_received = 0
    
    def connect(self) -> None:
        """Connect to MQTT broker."""
        print(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}")
        self.client.connect(self.broker_host, self.broker_port, 60)
        self.client.loop_start()
        
        # Wait for connection
        timeout = 10
        start_time = time.time()
        while not self.connected and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        if not self.connected:
            raise ConnectionError("Failed to connect to MQTT broker")
    
    def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()
    
    def _on_connect(self, client: mqtt.Client, userdata, flags, rc) -> None:
        """Callback for connection."""
        if rc == 0:
            print(f"Device {self.device_id} connected successfully")
            self.connected = True
            
            # Subscribe to response topic
            client.subscribe(self.response_topic, qos=1)
            print(f"Subscribed to {self.response_topic}")
        else:
            print(f"Failed to connect with result code {rc}")
    
    def _on_disconnect(self, client: mqtt.Client, userdata, rc) -> None:
        """Callback for disconnection."""
        print(f"Device {self.device_id} disconnected")
        self.connected = False
    
    def _on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
        """Handle incoming messages."""
        try:
            message = MessageParser.parse_message(msg.payload)
            
            if message.message_type == MessageType.AUDIO_RESPONSE and isinstance(message, AudioResponseMessage):
                self.responses_received += 1
                print(f"\n--- Audio Response #{self.responses_received} ---")
                print(f"Session ID: {message.session_id}")
                print(f"Transcript: {message.transcript}")
                print(f"Processing time: {message.processing_time_ms:.2f}ms")
                print(f"Cost estimate: ${message.cost_estimate:.4f}")
                print(f"Audio data size: {len(message.get_audio_bytes())} bytes")
                print("----------------------------------------")
                
            elif message.message_type == MessageType.ERROR and isinstance(message, ErrorMessage):
                print(f"\n--- Error Response ---")
                print(f"Error code: {message.error_code}")
                print(f"Error message: {message.error_message}")
                print("----------------------")
                
        except Exception as e:
            print(f"Error processing message: {e}")
    
    def send_audio_request(
        self, 
        audio_data: bytes, 
        session_id: Optional[str] = None,
        language: Optional[str] = None,
        voice: Optional[str] = None,
        instructions: Optional[str] = None
    ) -> Optional[str]:
        """Send an audio request to the server."""
        
        # Create audio request message
        request = AudioRequestMessage.create(
            device_id=self.device_id,
            audio_data=audio_data,
            session_id=session_id or f"session-{int(time.time())}",
            audio_format="mp3",
            language=language,
            voice=voice,
            instructions=instructions
        )
        
        # Publish to request topic
        result = self.client.publish(
            self.request_topic,
            request.to_json(),
            qos=1
        )
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"Sent audio request (session: {request.session_id})")
            return request.session_id
        else:
            print(f"Failed to send audio request: {result.rc}")
            return None


def create_sample_audio() -> bytes:
    """Create a sample audio data for testing (placeholder)."""
    # This is just dummy data for testing
    # In a real scenario, this would be actual MP3 audio data
    sample_text = "Hello, this is a test audio message from an IoT device."
    return sample_text.encode('utf-8')


async def main():
    """Main example function."""
    print("MQTT AI Agent - Simple IoT Client Example")
    print("==========================================")
    
    # Configuration
    device_id = "test-device-001"
    broker_host = "localhost"  # Change to your MQTT broker
    broker_port = 1883
    
    # Create and connect client
    client = SimpleIoTClient(device_id, broker_host, broker_port)
    
    try:
        client.connect()
        
        # Create sample audio data
        audio_data = create_sample_audio()
        
        print(f"\nSending test audio request...")
        print(f"Audio data size: {len(audio_data)} bytes")
        
        # Send audio request
        session_id = client.send_audio_request(
            audio_data=audio_data,
            language="en",
            voice="alloy",
            instructions="Please respond briefly to this voice message."
        )
        
        if session_id:
            print(f"Request sent successfully. Session ID: {session_id}")
            print("Waiting for response...")
            
            # Wait for response
            timeout = 30
            start_time = time.time()
            while client.responses_received == 0 and (time.time() - start_time) < timeout:
                await asyncio.sleep(0.5)
            
            if client.responses_received > 0:
                print(f"\nReceived {client.responses_received} response(s)")
            else:
                print("\nTimeout: No response received")
        
        # Keep running for a bit to receive any additional messages
        print("\nWaiting for additional messages (5 seconds)...")
        await asyncio.sleep(5)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("\nDisconnecting...")
        client.disconnect()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main()) 