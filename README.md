# NSOL BPO Voice Calling Agent

A Python prototype combining a scripted LiveKit voice worker with a FastAPI service for Twilio outbound calls, webhooks, and media streams.

## Implemented components

- Scripted LiveKit conversation flow with Deepgram STT, ElevenLabs TTS, Silero VAD, and an optional OpenAI response path
- FastAPI endpoints for starting outbound calls and receiving Twilio webhooks/status callbacks
- Twilio Media Streams WebSocket handling and audio-format conversion utilities

**Integration status:** The code and previous run guide do not establish that Twilio media streams are connected end to end with the LiveKit agent. Treat phone-call behavior as a prototype until verified with real service accounts and a controlled test number.

## Requirements

- Python 3.10 or newer
- LiveKit credentials to run the agent worker
- Twilio credentials and a public HTTPS webhook endpoint to initiate calls
- Provider credentials for the configured speech/model services

## Install and configure

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Fill the required variables in `.env`. The worker requires `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET`; it now fails clearly instead of using placeholder credentials. The FastAPI service can run without Twilio credentials, but outbound-call requests require Twilio account credentials and a reachable webhook.

## Run

Run the FastAPI API locally, bound to loopback:

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Run the LiveKit worker separately after configuring its credentials:

```bash
python main.py
```

The `POST /api/outbound/call` endpoint can place billable calls. Its test script now requires an explicit destination number; no outbound call was made as part of this repository review. Public webhook URLs must use HTTPS and be reachable by Twilio.

## Tests

```bash
python -m pip install -r requirements-test.txt
python -m pytest -q
```

Tests validate safe configuration defaults and required LiveKit credentials. They do not place calls or exercise provider/network integrations.

## Security and limitations

- `.env` is ignored by Git. Do not commit provider keys, phone numbers, customer data, or generated audio.
- Debug mode is disabled and the API binds to localhost by default. Configure network exposure deliberately for webhooks.
- Twilio and provider usage may incur charges; configure provider limits before running live workflows.
- The repository does not establish end-to-end phone/media/agent operation, and no public deployment is documented.
- The scripted sales workflow is a prototype, not proof of regulatory compliance or consent for calling recipients.
