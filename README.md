# NSOL BPO Voice Calling Agent

A Python prototype for outbound calling workflows. The repository contains a FastAPI service for initiating Twilio calls and receiving Twilio webhooks and media streams, alongside a scripted LiveKit voice agent for NSOL BPO conversations.

## What is implemented

- FastAPI endpoints for call placement, Twilio webhooks, status callbacks, and a media-stream WebSocket
- A scripted conversation flow for introductions, qualification questions, objection handling, and meeting details
- LiveKit Agents with Deepgram phone-call speech recognition, ElevenLabs speech output, Silero VAD, and an optional OpenAI response path for some questions
- Twilio call status handling and audio-format conversion utilities

**Integration status:** The existing run guide describes the Twilio-to-LiveKit audio connection as remaining work. Treat this repository as a prototype; the documentation does not establish that a complete phone-to-agent conversation works end to end.

## Stack

Python · FastAPI · LiveKit Agents · Twilio · Deepgram · ElevenLabs · Silero · OpenAI

## Setup

Install dependencies with `pip install -r requirements.txt`. Configure required provider credentials through local environment variables and never commit `.env` files or API credentials. The current `HOW_TO_RUN.md` contains credentials and outdated integration guidance; sanitize it before linking to or relying on that guide.

## Run

The API application is exposed as `main:app`; after local configuration, start it with:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The public webhook endpoints require a reachable HTTPS URL for Twilio callbacks. Review the integration-status note above before attempting a live call.

