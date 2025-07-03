# Docker Setup for MQTT AI Agent Server

This directory contains Docker configuration files to run the MQTT AI Agent Server using uv for dependency management.

## Files

- `Dockerfile` - Multi-stage Docker image using Python 3.11 and uv
- `docker-compose.yml` - Docker Compose configuration with environment variables
- `.dockerenv.example` - Example environment variables file

## Quick Start

1. **Set up environment variables**:
   ```bash
   cp .dockerenv.example .env
   ```
   
2. **Edit the `.env` file** and add your OpenAI API key:
   ```bash
   OPENAI_API_KEY=your_actual_openai_api_key_here
   ```

3. **Build and run with Docker Compose**:
   ```bash
   docker-compose up --build
   ```

4. **Run in detached mode** (background):
   ```bash
   docker-compose up -d --build
   ```

## Configuration

### Required Environment Variables

- `OPENAI_API_KEY` - Your OpenAI API key (required)

### Optional Environment Variables

#### MQTT Configuration
- `MQTT_HOST` - MQTT broker hostname (default: broker.emqx.io)
- `MQTT_PORT` - MQTT broker port (default: 1883)
- `MQTT_USERNAME` - MQTT username (optional)
- `MQTT_PASSWORD` - MQTT password (optional)
- `MQTT_CLIENT_ID` - MQTT client ID (default: mqtt-ai-server)
- `MQTT_USE_TLS` - Use TLS for MQTT (default: false)

#### OpenAI Configuration
- `OPENAI_MODEL` - OpenAI model to use (default: gpt-4o-realtime-preview)
- `OPENAI_BASE_URL` - OpenAI API base URL (default: wss://api.openai.com/v1/realtime)
- `OPENAI_VOICE` - Voice to use (default: alloy)
- `OPENAI_INSTRUCTIONS` - AI instructions (default: helpful assistant message)

#### Server Configuration
- `MAX_CONCURRENT_SESSIONS` - Maximum concurrent sessions (default: 50)
- `SESSION_TIMEOUT_SECONDS` - Session timeout in seconds (default: 300)
- `LOG_LEVEL` - Logging level (default: INFO)
- `ENABLE_HEALTH_CHECKS` - Enable health checks (default: true)
- `HEALTH_CHECK_INTERVAL` - Health check interval in seconds (default: 30)

## Usage

### Build Only
```bash
docker-compose build
```

### Run with Logs
```bash
docker-compose up
```

### Run in Background
```bash
docker-compose up -d
```

### View Logs
```bash
docker-compose logs -f mqtt-ai-server
```

### Stop the Server
```bash
docker-compose down
```

### Restart the Server
```bash
docker-compose restart
```

## Volumes

- `./logs:/app/logs` - Log files are mounted to local `logs` directory
- `./audio:/app/audio:ro` - Audio files are mounted read-only for testing

## Health Check

The container includes a health check that verifies connectivity to the MQTT broker. You can check the health status with:

```bash
docker-compose ps
```

## Troubleshooting

### Check Container Status
```bash
docker-compose ps
```

### View Container Logs
```bash
docker-compose logs mqtt-ai-server
```

### Access Container Shell
```bash
docker-compose exec mqtt-ai-server /bin/bash
```

### Test MQTT Connection
```bash
# From inside the container
python -c "import socket; socket.create_connection(('broker.emqx.io', 1883), timeout=5)"
```

## Development

### Using Local MQTT Broker

The `docker-compose.yml` includes a commented-out Mosquitto MQTT broker service. To use it:

1. Uncomment the `mosquitto` service in `docker-compose.yml`
2. Uncomment the `networks` section
3. Create a `mosquitto.conf` file with your broker configuration
4. Set `MQTT_HOST=mosquitto` in your `.env` file

### Building for Different Architectures

```bash
# Build for AMD64
docker buildx build --platform linux/amd64 -t mqtt-ai-server:amd64 .

# Build for ARM64
docker buildx build --platform linux/arm64 -t mqtt-ai-server:arm64 .
```

## Security Notes

- The container runs as a non-root user (`app`) for security
- Environment variables containing sensitive data (API keys, passwords) should be kept secure
- Consider using Docker secrets for production deployments
- The container uses Python 3.11 slim image for smaller attack surface 