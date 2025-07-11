"""
Simple MQTT client example for IoT devices.

This example shows how an IoT device can send audio requests and receive responses
from the MQTT AI Agent server using the simplified message format.
Optimized for embedded device compatibility.
"""

import asyncio
import base64
import json
import sys
import time
from pathlib import Path
from typing import Optional, List

import paho.mqtt.client as mqtt

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mqtt.messages import AudioRequestMessage, AudioResponseMessage, ErrorMessage, MessageParser, MessageType


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
                print(f"Audio data size: {len(message.audio_data)} bytes")
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
    
    def send_audio_chunk(self, audio_chunk: bytes, session_id: str) -> bool:
        """Send a simplified audio chunk to the server."""
        
        # Create simplified audio request message
        request = AudioRequestMessage.create(
            device_id=self.device_id,
            audio_data=audio_chunk,
            session_id=session_id
        )
        
        # Publish to request topic
        result = self.client.publish(
            self.request_topic,
            request.to_json(),
            qos=1
        )
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"Sent audio chunk (session: {session_id}) - {len(audio_chunk)} bytes")
            return True
        else:
            print(f"Failed to send audio chunk: {result.rc}")
            return False


def convert_mp3_to_pcm16(mp3_data: bytes) -> bytes:
    """
    Convert MP3 data to PCM16 format for testing.
    In production, embedded devices would send PCM16 directly.
    """
    try:
        # Try to use pydub if available (for development/testing)
        from pydub import AudioSegment
        import io
        
        # Decode MP3 to AudioSegment
        audio_segment = AudioSegment.from_file(io.BytesIO(mp3_data), format="mp3")
        
        # Convert to PCM16 24kHz mono format (as expected by OpenAI)
        audio_segment = (
            audio_segment.set_frame_rate(24000)
            .set_channels(1)
            .set_sample_width(2)  # 2 bytes = 16-bit
        )
        
        return audio_segment.raw_data
        
    except ImportError:
        print("Warning: pydub not available for MP3 conversion. Using raw MP3 data.")
        print("Note: In production, embedded devices should send PCM16 directly.")
        return mp3_data


def load_and_convert_audio(chunk_size: int = 8192) -> List[bytes]:
    """
    Load the test.mp3 audio file, convert to PCM16, and split into chunks.
    This simulates what embedded devices would send (raw PCM16 chunks).
    """
    # Path to the test audio file
    audio_file_path = Path(__file__).parent.parent / "audio" / "test.mp3"
    
    if not audio_file_path.exists():
        raise FileNotFoundError(f"Test audio file not found at: {audio_file_path}")
    
    # Read the MP3 file
    with open(audio_file_path, 'rb') as f:
        mp3_data = f.read()
    
    print(f"Loaded test audio file: {audio_file_path}")
    print(f"MP3 file size: {len(mp3_data)} bytes")
    
    # Convert MP3 to PCM16 (simulating embedded device behavior)
    pcm16_data = convert_mp3_to_pcm16(mp3_data)
    print(f"Converted to PCM16 size: {len(pcm16_data)} bytes")
    
    # Split into chunks
    chunks = []
    for i in range(0, len(pcm16_data), chunk_size):
        chunk = pcm16_data[i:i + chunk_size]
        chunks.append(chunk)
    
    print(f"Split PCM16 audio into {len(chunks)} chunks of ~{chunk_size} bytes each")
    return chunks


async def main():
    """Main example function."""
    print("MQTT AI Agent - Simple IoT Client Example")
    print("=========================================")
    print("Testing simplified message format with raw PCM16 audio")
    print()
    
    # Configuration
    device_id = "test-device-001"
    broker_host = "broker.emqx.io"  # Public MQTT broker for testing
    broker_port = 1883
    
    # Create and connect client
    client = SimpleIoTClient(device_id, broker_host, broker_port)
    
    try:
        client.connect()
        
        # Load and convert test audio data to PCM16
        audio_chunks = load_and_convert_audio(chunk_size=8192)  # 8KB chunks
        
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
                session_id=session_id
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