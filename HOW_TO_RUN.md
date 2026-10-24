# How to Run - NSOL BPO AI Agent (Merideth)

## Twilio Outbound Calling Setup

This agent calls realtors and business owners to book meetings for NSOL BPO's virtual assistant services.

**Key Features:**
- Professional, warm conversational style
- Handles cold calling, lead follow-ups, and social media management services
- Natural objection handling and persistence strategy
- Books qualified meetings for virtual assistant services

## Setup (One Time)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Twilio credentials locally
Create a local `.env` file or set the required environment variables in your deployment environment. Configure `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM_NUMBER` with values from your Twilio account. Never commit real credentials. If any credentials were previously committed, rotate them; removing them from this file does not remove them from Git history.

### 3. Install ngrok (for webhook URL)
Download from: https://ngrok.com/download

## Running the System

### Terminal 1 - Start ngrok
```bash
ngrok http 8000
```
Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

### Terminal 2 - Start Server
```bash
# Windows
start_server.bat

# Or manually
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Wait until you see: `"Twilio service initialized successfully"`

### Terminal 3 - Make a Call
```bash
python test_outbound.py --to "+1YOUR_PHONE_NUMBER" --url "https://YOUR_NGROK_URL.ngrok.io"
```

Example:
```bash
python test_outbound.py --to "+14155551234" --url "https://abc123.ngrok.io"
```

## What Happens

1. ✅ Script calls your API: `POST /api/outbound/call`
2. ✅ Server uses Twilio to place the call
3. ✅ Your phone rings
4. ✅ When answered, Twilio calls webhook: `/twilio/webhook`
5. ✅ Server returns TwiML with Media Stream config
6. ✅ Twilio opens WebSocket: `/twilio/media`
7. ✅ Audio flows bidirectionally (μ-law ↔ PCM16 conversion)
8. ✅ LiveKit agent (Merideth) responds naturally
9. ✅ Agent can handle extended 10-minute conversations with detailed information

## Conversation Capabilities

**Merideth** follows a structured conversation flow:

### Opening (1-2 minutes)
- Greets with "Hi, this is Merideth... how's your day going?"
- Matches their mood appropriately
- Delivers main pitch about NSOL BPO services
- Asks if they handle admin tasks themselves or have support

### Qualifying (2-4 minutes)
- Asks targeted questions based on their situation
- "What's eating up most of your time right now?"
- "How many hours per week on backend admin tasks?"
- "How are you managing lead follow-up?"
- Detects interest signals and moves to booking

### Objection Handling
- Handles common objections naturally:
  - "I'm not interested" → timing vs value
  - "No budget" → free presentation, ROI focus
  - "Already have help" → gaps discussion
  - "No time" → time-saving benefits
  - "How much does it cost?" → two-tier response
- Maximum 3 attempts before graceful end

### Booking Process
- Gets day/time first (rounds to nearest hour)
- Collects timezone/location
- Gets email (spells out for confirmation)
- Gets phone number (digit by digit)
- Gets full name
- Final confirmation with enthusiasm

## Architecture

```
Phone Call ←→ Twilio ←→ WebSocket ←→ Your Server ←→ LiveKit Agent
              (Media Streams)         (FastAPI)      (AI Voice)
```

## API Endpoints

### Place Call
```bash
POST /api/outbound/call
{
  "to_number": "+14155551234",
  "webhook_base_url": "https://your-ngrok-url.ngrok.io"
}
```

### Webhooks (Twilio calls these)
- `POST /twilio/webhook` - Returns TwiML
- `WebSocket /twilio/media` - Audio streaming
- `POST /twilio/status` - Call status updates

### Other
- `GET /` - API info
- `GET /health` - Health check
- `GET /docs` - Interactive API docs

## What's Working Now

✅ Call placement via Twilio REST API  
✅ TwiML webhook handling  
✅ WebSocket Media Stream connection  
✅ Audio reception from Twilio  
✅ Audio format conversion (μ-law ↔ PCM16)  
✅ Audio buffering  

## Next Step: LiveKit Integration

To connect audio to your LiveKit agent, complete these steps in `utils/twilio_service.py`:

### 1. Connect to LiveKit Room
```python
# In connect_to_livekit() method
self.livekit_room = rtc.Room()
token = api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
token.with_identity(f"twilio-{self.call_sid}")
token.with_grants(api.VideoGrants(room_join=True, room=self.livekit_room_name))
await self.livekit_room.connect(settings.LIVEKIT_URL, token.to_jwt())
```

### 2. Publish Audio to Room
```python
# In handle_media() method - after audio conversion
frame = rtc.AudioFrame(
    data=pcm_audio,
    sample_rate=16000,
    num_channels=1,
    samples_per_channel=len(pcm_audio) // 2
)
await self.audio_track.capture_frame(frame)
```

### 3. Subscribe to Agent Audio
```python
# Add event handler
@self.livekit_room.on("track_subscribed")
def on_track_subscribed(track, publication, participant):
    if track.kind == rtc.TrackKind.KIND_AUDIO:
        asyncio.create_task(self.receive_agent_audio(track))

async def receive_agent_audio(self, track):
    async for event in rtc.AudioStream(track):
        if isinstance(event, rtc.AudioFrameEvent):
            pcm_audio = bytes(event.frame.data)
            await self.send_audio_to_twilio(pcm_audio, event.frame.sample_rate)
```

## File Structure

```
merideth-cold-caller/
├── main.py                      # FastAPI app + LiveKit agent + API endpoints
├── test_outbound.py            # Test script for making calls
├── start_server.bat            # Windows server start script
├── requirements.txt            # Python dependencies
├── .env                        # Configuration (your credentials)
├── config/
│   ├── __init__.py
│   └── settings.py            # Settings loader
└── utils/
    ├── __init__.py
    ├── logger.py              # Logging setup
    ├── twilio_service.py      # Twilio integration + Media Stream handler
    └── audio_converter.py     # μ-law ↔ PCM16 conversion
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Twilio service not configured" | Check `.env` has all TWILIO_* variables |
| "Connection refused" | Start server first (Terminal 2) |
| Webhook not reachable | Use ngrok HTTPS URL, ensure ngrok running |
| Phone doesn't ring | Check phone format: +1234567890 |
| No audio | Complete LiveKit integration above |

## Monitor Your Calls

- **Server logs**: Terminal 2
- **ngrok requests**: http://localhost:4040
- **Twilio console**: https://console.twilio.com/monitor/logs/calls
- **Twilio debugger**: https://console.twilio.com/monitor/logs/debugger

## Quick Test Without Phone

```bash
curl -X POST "http://localhost:8000/api/outbound/call" \
  -H "Content-Type: application/json" \
  -d '{"to_number":"+14155551234","webhook_base_url":"https://your-ngrok.ngrok.io"}'
```

Expected response:
```json
{
  "success": true,
  "call_sid": "CAxxxxx",
  "status": "queued",
  "room_name": "call-xxxxx",
  "websocket_url": "wss://your-ngrok.ngrok.io/twilio/media"
}
```

## Cost Warning

⚠️ Twilio charges per minute for outbound calls. Check pricing: https://www.twilio.com/voice/pricing

## Support

- Server not starting? Check all dependencies installed
- Call failing? Check Twilio debugger
- Audio issues? Check server logs for conversion errors
- Integration help? See TODO comments in `utils/twilio_service.py`

That's it! You now have working Twilio outbound calling with Media Streams. 🚀
