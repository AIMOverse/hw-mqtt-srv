# MQTT AI Agent Server

A streaming speech-to-speech AI Agent server for IoT devices using MQTT protocol. This server enables IoT devices to send raw PCM16 audio streams and receive AI-generated audio responses in real-time.

**Optimized for embedded devices with minimal processing overhead.**

## 🚀 Features

- **Streaming Speech-to-Speech**: Direct audio-to-audio communication using OpenAI's Realtime API
- **MQTT Protocol**: Lightweight messaging for IoT devices with raw audio chunks
- **Simplified Message Format**: Minimal JSON schema optimized for embedded devices
- **Raw PCM16 Audio**: No base64 encoding required on embedded devices
- **Modular AI Services**: Easy-to-swap AI service providers (currently supports OpenAI Realtime API)
- **Session Management**: Handles multiple concurrent device sessions
- **Health Monitoring**: Built-in health checks and system monitoring
- **Configurable**: Environment-based configuration for easy deployment
- **Production Ready**: Async architecture with proper error handling and logging

## 🏗️ Architecture

```
IoT Device → MQTT Broker → AI Agent Server → OpenAI Realtime API
    ↑                                              ↓
    └──────────── Audio Response ←─────────────────┘
```

**Simplified Audio Flow:**
```
Device PCM16 → Server → OpenAI Realtime API → Server → Device PCM16
```

The server uses an abstract AI service interface, making it easy to swap between different providers:

- **Primary**: OpenAI Realtime API (direct speech-to-speech, ~300-500ms latency)
- **Future**: Modular pipeline (Soniox STT + DeepSeek LLM + OpenAI TTS)

## 📋 Requirements

- Python 3.11+
- OpenAI API key with Realtime API access
- MQTT broker (e.g., EMQX, Mosquitto)
- **Audio format**: Raw PCM16, 24kHz, mono, ~8KB chunks
- **Embedded devices**: No audio conversion libraries required

## 🛠️ Installation

### 1. Clone the repository
```bash
git clone <repository-url>
cd hw-mqtt-srv
```

### 2. Install dependencies
```bash
# Using UV (recommended)
uv sync
```

### 3. Create configuration
```bash
# Run once to create example configuration
python main.py

# Copy and edit the configuration
cp .env.example .env
# Edit .env with your actual values
```

### 4. Configure environment variables

Edit `.env` file with your settings:

```env
# MQTT Broker Settings
MQTT_HOST=broker.emqx.io
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_CLIENT_ID=mqtt-ai-server
MQTT_USE_TLS=false

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-realtime-preview
OPENAI_VOICE=alloy
OPENAI_INSTRUCTIONS=You are a helpful AI assistant responding to voice commands from IoT devices.

# Server Settings
MAX_CONCURRENT_SESSIONS=50
SESSION_TIMEOUT_SECONDS=300
LOG_LEVEL=INFO
```

## 🚀 Quick Start

### Start the server
```bash
python main.py
```

### Test with example client
```bash
python tests/simple_client.py
```

## 📡 MQTT Message Format

**Simplified for embedded devices - 60% smaller payloads!**

### Audio Request (IoT Device → Server)
```json
{
  "message_id": "uuid-1234",
  "device_id": "iot-device-001",
  "timestamp": 1704067200,
  "message_type": "audio_request",
  "session_id": "session-567",
  "audio_data": "raw_pcm16_bytes_as_base64"
}
```

### Audio Response (Server → IoT Device)
```json
{
  "message_id": "uuid-5678",
  "device_id": "iot-device-001", 
  "timestamp": 1704067202,
  "message_type": "audio_response",
  "session_id": "session-567",
  "audio_data": "raw_pcm16_bytes_as_base64"
}
```

## 🏷️ MQTT Topics

- **Request**: `iot/{device_id}/audio_request`
- **Response**: `iot/{device_id}/audio_response`  
- **Health**: `iot/server/health`

## 💡 Embedded Device Implementation

### Audio Format Requirements
- **Format**: Raw PCM16 audio data
- **Sample Rate**: 24kHz
- **Channels**: Mono (1 channel)
- **Bit Depth**: 16-bit
- **Chunk Size**: ~8KB for optimal performance

### Example Implementation (C/C++)
```c
// Capture audio from microphone as PCM16
uint8_t audio_buffer[8192];
capture_audio_pcm16(audio_buffer, sizeof(audio_buffer));

// Send directly via MQTT - no base64 encoding needed
mqtt_publish("iot/device001/audio_request", audio_buffer, sizeof(audio_buffer));
```

### Benefits for Embedded Devices
- **No Base64 encoding/decoding** required
- **No audio format conversion** needed
- **Minimal memory footprint**
- **60% smaller** message payloads
- **Faster processing** due to direct PCM16 handling

## 🔧 Configuration Options

### MQTT Settings
- `MQTT_HOST`: MQTT broker hostname
- `MQTT_PORT`: MQTT broker port (default: 1883)
- `MQTT_USERNAME/PASSWORD`: Authentication credentials
- `MQTT_USE_TLS`: Enable TLS encryption

### OpenAI Settings
- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `OPENAI_MODEL`: Model to use (default: gpt-4o-realtime-preview)
- `OPENAI_VOICE`: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
- `OPENAI_INSTRUCTIONS`: Default system instructions

### Server Settings
- `MAX_CONCURRENT_SESSIONS`: Maximum concurrent device sessions
- `SESSION_TIMEOUT_SECONDS`: Session timeout duration
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

## 🧪 Development

### Adding New AI Services

The server uses an abstract interface for AI services. To add a new provider:

1. Implement the `AIServiceInterface`:

```python
from src.ai_services import AIServiceInterface, AudioRequest, AudioResponse

class MyAIService(AIServiceInterface):
    async def process_audio_stream(self, request: AudioRequest) -> AsyncIterator[AudioResponse]:
        # Your implementation here
        pass
    
    async def health_check(self) -> bool:
        # Health check implementation
        pass
```

2. Update the main.py to use your service:

```python
# Replace OpenAIRealtimeService with your implementation
ai_service = MyAIService(config)
```

### Running Tests

```bash
# Install development dependencies
uv sync --group dev

# Run tests
pytest

# Run with coverage
pytest --cov=src
```

### Code Quality

```bash
# Format code
black src/ tests/
isort src/ tests/

# Type checking
mypy src/
```

## 📊 Performance

| Mode | End-to-End Latency | Memory Usage | Use Case |
|------|-------------------|--------------|----------|
| Simplified PCM16 | 300-500ms | ~50% less | Embedded devices |
| Legacy MP3 | 600-1000ms | Higher | Legacy systems |

## 🚨 Troubleshooting

### Common Issues

1. **Connection Refused**
   - Check MQTT broker is running and accessible
   - Verify MQTT_HOST and MQTT_PORT settings

2. **OpenAI API Errors**
   - Ensure OPENAI_API_KEY is set correctly
   - Check you have access to the Realtime API (currently in beta)

3. **High Latency**
   - Verify network connection to OpenAI services
   - Check server resources and concurrent session limits

4. **Audio Issues**
   - Ensure audio is in PCM16 format, 24kHz, mono
   - Keep chunks around 8KB for optimal performance
   - Verify audio data is not corrupted during transmission

### Logs

Logs are written to both console and `logs/mqtt-ai-server.log` with rotation.

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review existing GitHub issues
3. Create a new issue with detailed information

## 🗺️ Roadmap

- [ ] Alternative AI service providers (DeepSeek, Anthropic)
- [ ] WebRTC support for lower latency
- [ ] Embedded device SDKs (ESP32, Arduino)
- [ ] Kubernetes deployment manifests
- [ ] Grafana dashboards for monitoring
- [ ] Load testing tools
- [ ] Multi-language documentation
