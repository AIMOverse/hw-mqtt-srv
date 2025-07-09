# Production Deployment Guide

This guide explains how to deploy the MQTT AI Agent Server with an integrated Mosquitto MQTT broker on AWS EC2 or any other server.

## 🏗️ Architecture

```
IoT Devices ←--→ Mosquitto MQTT Broker ←--→ AI Agent Server ←--→ OpenAI API
              (Port 1883)              (Internal Network)
```

Both services run in the same Docker Compose setup for simplified management.

## 🚀 Quick Deployment

### 1. Prerequisites

- Docker and Docker Compose installed
- Server with public IP (AWS EC2, etc.)
- OpenAI API key with Realtime API access

### 2. Configuration

Create a `.env` file in the project root:

```env
# Production Environment Configuration for MQTT AI Agent Server
# Copy this file to .env and update with your actual values

# =============================================================================
# MQTT Configuration
# =============================================================================
# Note: MQTT_HOST is set to 'mosquitto' in docker-compose.prod.yml (internal connection)
# External clients should connect to your server's IP/domain on port 1883

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

# =============================================================================
# OpenAI Configuration
# =============================================================================
# REQUIRED: Add your OpenAI API key here
OPENAI_API_KEY=your_openai_api_key_here

# OpenAI Model Settings
OPENAI_MODEL=gpt-4o-realtime-preview
OPENAI_BASE_URL=wss://api.openai.com/v1/realtime
OPENAI_VOICE=alloy
OPENAI_INSTRUCTIONS=You are a helpful AI assistant responding to voice commands from IoT devices.

# =============================================================================
# Server Configuration
# =============================================================================
MAX_CONCURRENT_SESSIONS=50
SESSION_TIMEOUT_SECONDS=300
LOG_LEVEL=INFO
ENABLE_HEALTH_CHECKS=true
HEALTH_CHECK_INTERVAL=30
```

### 3. Deploy

```bash
# Clone the repository
git clone <repository-url>
cd hw-mqtt-srv

# Create your environment file
cp .env.example .env
# Edit .env with your actual values (especially OPENAI_API_KEY)

# Start the services
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

## 🌐 Network Configuration

### Exposed Ports

- **1883**: MQTT broker (for IoT devices)
- **9001**: WebSocket MQTT (for web clients)

### AWS EC2 Security Group

Configure your security group to allow:
```
Type: Custom TCP
Port: 1883
Source: 0.0.0.0/0 (or restrict to your device IPs)
Description: MQTT

Type: Custom TCP  
Port: 9001
Source: 0.0.0.0/0 (or restrict as needed)
Description: MQTT WebSocket
```

## 🔧 AI Service Configuration

### Internal Communication

The AI Agent Server connects to the MQTT broker using:
```
MQTT_HOST=mosquitto  # Internal Docker network
MQTT_PORT=1883
```

### External Device Connection

IoT devices connect to:
```
MQTT_HOST=your-server-ip-or-domain
MQTT_PORT=1883
```

### Test Connection

```bash
# Test from outside the server
mosquitto_sub -h your-server-ip -t "iot/+/audio_request"

# Test from inside the server
docker-compose -f docker-compose.prod.yml exec mqtt-ai-server \
  python -c "import socket; socket.create_connection(('mosquitto', 1883), timeout=5); print('Connected!')"
```

## 🔐 Security Configuration

### Basic Authentication (Recommended)

1. Create password file:
```bash
# Create directory for config
mkdir -p mosquitto_config

# Create password file
docker run --rm -it eclipse-mosquitto:2.0 \
  mosquitto_passwd -c /tmp/passwd your-username
```

2. Update `mosquitto.conf`:
```conf
# Disable anonymous access
allow_anonymous false

# Enable password authentication
password_file /mosquitto/config/passwd
```

3. Mount the password file:
```yaml
# In docker-compose.prod.yml
volumes:
  - ./mosquitto.conf:/mosquitto/config/mosquitto.conf
  - ./mosquitto_config/passwd:/mosquitto/config/passwd
```

4. Update environment variables:
```env
MQTT_USERNAME=your-username
MQTT_PASSWORD=your-password
```

### TLS/SSL (Production Recommended)

1. Obtain SSL certificates
2. Update `mosquitto.conf`:
```conf
# TLS Configuration
listener 8883
protocol mqtt
cafile /mosquitto/config/ca.crt
certfile /mosquitto/config/server.crt
keyfile /mosquitto/config/server.key
require_certificate false
```

3. Update environment:
```env
MQTT_PORT=8883
MQTT_USE_TLS=true
```

## 📊 Monitoring

### Health Checks

Both services have health checks:
```bash
# Check service health
docker-compose -f docker-compose.prod.yml ps

# View health check logs
docker-compose -f docker-compose.prod.yml logs mosquitto
docker-compose -f docker-compose.prod.yml logs mqtt-ai-server
```

### Logs

```bash
# View all logs
docker-compose -f docker-compose.prod.yml logs -f

# View specific service logs
docker-compose -f docker-compose.prod.yml logs -f mqtt-ai-server
docker-compose -f docker-compose.prod.yml logs -f mosquitto

# Mosquitto broker logs are also saved to: ./mosquitto_logs/
```

## 🔄 Management Commands

### Start Services
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Stop Services
```bash
docker-compose -f docker-compose.prod.yml down
```

### Restart Services
```bash
docker-compose -f docker-compose.prod.yml restart
```

### Update Services
```bash
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

### Clean Up
```bash
# Remove containers and networks
docker-compose -f docker-compose.prod.yml down

# Remove containers, networks, and volumes
docker-compose -f docker-compose.prod.yml down -v
```

## 🧪 Testing

### Test Client Configuration

Update your test client to connect to your server:

```python
# In tests/simple_client.py
client = SimpleIoTClient(
    device_id="test-device-001",
    broker_host="your-server-ip",  # Your EC2 public IP
    broker_port=1883
)
```

### Test with Mosquitto Clients

```bash
# Subscribe to responses
mosquitto_sub -h your-server-ip -t "iot/test-device-001/audio_response"

# Publish test message
mosquitto_pub -h your-server-ip -t "iot/test-device-001/audio_request" -m "test message"
```

## 🚨 Troubleshooting

### Common Issues

1. **Connection Refused**
   - Check if port 1883 is open in firewall/security group
   - Verify services are running: `docker-compose -f docker-compose.prod.yml ps`

2. **AI Service Can't Connect to Broker**
   - Check Docker network connectivity
   - Verify mosquitto service is healthy

3. **OpenAI API Errors**
   - Ensure OPENAI_API_KEY is set correctly
   - Check OpenAI API quota and access

### Debug Commands

```bash
# Check network connectivity
docker-compose -f docker-compose.prod.yml exec mqtt-ai-server ping mosquitto

# Check MQTT broker status
docker-compose -f docker-compose.prod.yml exec mosquitto netstat -ln

# View detailed logs
docker-compose -f docker-compose.prod.yml logs --tail=100 -f mqtt-ai-server
```

## 🔧 Customization

### Custom Mosquitto Configuration

Edit `mosquitto.conf` to customize:
- Authentication methods
- Access control lists (ACLs)
- Bridge connections
- Logging levels
- Performance settings

### Custom AI Service Configuration

Modify environment variables in `.env`:
- OpenAI model and voice settings
- Session management parameters
- Logging configuration
- Health check intervals

## 📈 Scaling

For high-load scenarios:

1. **Horizontal Scaling**: Deploy multiple AI service instances
2. **Load Balancing**: Use NGINX or AWS ALB
3. **MQTT Clustering**: Consider HiveMQ or VerneMQ
4. **Message Queuing**: Add Redis or RabbitMQ for queueing

## 🏥 Production Checklist

- [ ] SSL/TLS certificates configured
- [ ] Authentication enabled
- [ ] Firewall rules configured
- [ ] Log rotation configured
- [ ] Monitoring and alerting set up
- [ ] Backup strategy for persistent data
- [ ] Documentation updated with server details
- [ ] Test client connection from external network
- [ ] Health check endpoints verified 