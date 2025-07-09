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
from typing import Optional, List


class SimpleIoTClient:
    """Simple IoT client for testing the MQTT AI Agent server."""
    
    def __init__(self, device_id: str, broker_host: str = "broker.emqx.io", broker_port: int = 1883):
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
        self.error_received = False
        self.should_exit = False
    
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
    
    def _on_connect(self, client: mqtt.Client, userdata, flags, rc, properties=None) -> None:
        """Callback for connection."""
        if rc == 0:
            print(f"Device {self.device_id} connected successfully")
            self.connected = True
            
            # Subscribe to response topic
            client.subscribe(self.response_topic, qos=1)
            print(f"Subscribed to {self.response_topic}")
        else:
            print(f"Failed to connect with result code {rc}")
    
    def _on_disconnect(self, client: mqtt.Client, userdata, rc, properties=None) -> None:
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
                
                # Set flags to exit immediately on error
                self.error_received = True
                self.should_exit = True
                print("Error received - client will exit")
                
        except Exception as e:
            print(f"Error processing message: {e}")
    
    def send_audio_chunk(
        self, 
        audio_chunk: bytes, 
        session_id: str,
        chunk_id: int,
        total_chunks: int,
        language: Optional[str] = None,
        voice: Optional[str] = None,
        instructions: Optional[str] = None
    ) -> bool:
        """Send an audio chunk to the server."""
        
        # Create audio request message
        request = AudioRequestMessage.create(
            device_id=self.device_id,
            audio_data=audio_chunk,
            session_id=session_id,
            audio_format="mp3",
            language=language,
            voice=voice,
            instructions=instructions,
            chunk_id=chunk_id,
            total_chunks=total_chunks
        )
        
        # Publish to request topic
        result = self.client.publish(
            self.request_topic,
            request.to_json(),
            qos=1
        )
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"Sent audio chunk {chunk_id}/{total_chunks} (session: {session_id}) - {len(audio_chunk)} bytes")
            return True
        else:
            print(f"Failed to send audio chunk: {result.rc}")
            return False


def load_and_chunk_audio(chunk_size: int = 8192) -> List[bytes]:
    """Load the test.mp3 audio file and split it into chunks."""
    # Path to the test audio file
    audio_file_path = Path(__file__).parent.parent / "audio" / "test.mp3"
    
    if not audio_file_path.exists():
        raise FileNotFoundError(f"Test audio file not found at: {audio_file_path}")
    
    # Read the MP3 file
    with open(audio_file_path, 'rb') as f:
        audio_data = f.read()
    
    print(f"Loaded test audio file: {audio_file_path}")
    print(f"Audio file size: {len(audio_data)} bytes")
    
    # Split into chunks
    chunks = []
    for i in range(0, len(audio_data), chunk_size):
        chunk = audio_data[i:i + chunk_size]
        chunks.append(chunk)
    
    print(f"Split audio into {len(chunks)} chunks of ~{chunk_size} bytes each")
    return chunks


async def main():
    """Main example function."""
    print("MQTT AI Agent - Simple IoT Client Example")
    print("==========================================")
    
    # Configuration
    device_id = "test-device-001"
    broker_host = "broker.emqx.io"  # Public MQTT broker for testing
    broker_port = 1883
    
    # Create and connect client
    client = SimpleIoTClient(device_id, broker_host, broker_port)
    
    try:
        client.connect()
        
        # Load and chunk test audio data
        audio_chunks = load_and_chunk_audio(chunk_size=8192)  # 8KB chunks
        
        print(f"\nSending test audio request in {len(audio_chunks)} chunks...")
        
        # Create session ID
        session_id = f"session-{int(time.time())}"
        
        # Send audio chunks
        for i, chunk in enumerate(audio_chunks):
            if client.should_exit:
                print("Stopping due to error - exiting early")
                break
                
            success = client.send_audio_chunk(
                audio_chunk=chunk,
                session_id=session_id,
                chunk_id=i,
                total_chunks=len(audio_chunks),
                language="en",
                voice="alloy",
                instructions="Please respond briefly to this voice message."
            )
            
            if not success:
                print(f"Failed to send chunk {i}, stopping")
                break
            
            # Small delay between chunks to simulate streaming
            await asyncio.sleep(0.1)
        
        if not client.should_exit:
            print(f"All chunks sent successfully. Session ID: {session_id}")
            print("Waiting for response...")
            
            # Wait for response or error
            timeout = 30
            start_time = time.time()
            while (not client.should_exit and 
                   client.responses_received == 0 and 
                   (time.time() - start_time) < timeout):
                await asyncio.sleep(0.5)
            
            if client.error_received:
                print(f"\nError received - exiting immediately")
            elif client.responses_received > 0:
                print(f"\nReceived {client.responses_received} response(s)")
            else:
                print("\nTimeout: No response received")
        
        # If no error, wait briefly for any additional messages
        if not client.should_exit:
            print("\nWaiting for additional messages (3 seconds)...")
            await asyncio.sleep(3)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("\nDisconnecting...")
        client.disconnect()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main()) 