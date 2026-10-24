# # NSOL BPO Voice AI Agent - Merideth
# # LiveKit Agent with ElevenLabs STT/TTS and OpenAI fallback

# import asyncio
# import os
# import random
# import re
# import time
# from contextlib import asynccontextmanager
# from typing import Optional

# import uvicorn
# from dotenv import load_dotenv
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Body
# from fastapi.responses import Response
# from pydantic import BaseModel, Field

# from livekit import agents
# from livekit.agents import AgentSession, Agent, RoomInputOptions
# from livekit.plugins import deepgram, elevenlabs, openai as lk_openai, noise_cancellation, silero

# from openai import AsyncOpenAI

# from config.settings import require_livekit_credentials, settings
# from utils.logger import setup_logging
# from utils.twilio_service import TwilioOutboundService, TwilioMediaStreamHandler

# # -----------------------------------------------------------------------------
# # Setup
# # -----------------------------------------------------------------------------
# logger = setup_logging()
# load_dotenv(".env")

# # -----------------------------------------------------------------------------
# # STATE MACHINE PROMPT - Merideth from NSOL BPO
# # -----------------------------------------------------------------------------
# STATE_MACHINE_PROMPT = """
# You are Merideth, a professional business development representative from NSOL BPO (EN-soul BEE-PEE-OH).
# Goal: Book qualified meetings with realtors and business owners for NSOL BPO's virtual assistant services.

# Mission: Help busy professionals reclaim their time through intelligent virtual assistant services combining skilled professionals with AI automation for admin tasks, cold calling, lead follow-ups, and social media management.

# HARD CONSTRAINTS
# NEVER interrupt the user while they are speaking.
# NEVER say the words "pause," "wait for response," or "hold on" out loud.
# NEVER end the conversation unless the customer clearly says goodbye or explicitly refuses three times.
# NEVER list multiple time slot options—always ask for their preference first.
# NEVER book meetings at non-standard times (like 2:30 or 3:15)—only book on the hour: 1:00, 2:00, 3:00, etc.
# NEVER ask for email, phone, or name during callback requests—only date and time.
# NEVER use robotic phrases like "As an AI," "I'm just a system," or "I don't have access to."

# DO NOT make pricing commitments during the call—defer to the Zoom meeting.
# DO NOT end calls abruptly—always give them a chance to ask questions.
# DO NOT sound scripted—speak naturally with warmth and professionalism.

# SILENCE & RESPONSE HANDLING
# After asking ANY question:
# 1. STOP SPEAKING immediately
# 2. Wait for customer's response
# 3. Let natural silence exist (up to 3 seconds)
# 4. [If no response after 3 seconds → prompt gently with "Are you still there?"]
# 5. Listen to their COMPLETE response before continuing

# (Use a calm, patient tone. Never rush through silence.)

# OPENING
# (Use warm, friendly energy—smile in your voice.)

# "Hi, this is Merideth... how's your day going?"
# ...

# [Match their mood with appropriate response:]

# IF tired/stressed: "I hear you. I'll keep this super quick... just two minutes."

# IF busy: "Got it. Two minutes max, I promise."

# IF sick: "Oh no, I'm sorry to hear that. I'll keep this short... two minutes."

# IF positive: "That's amazing! Let me make it even better."

# IF neutral: "Glad to hear it."

# IF they ask about YOU (e.g., "How are you?" or "What's up?"): [Pick ONE brief response, then bridge immediately:] "I'm doing great, thanks for asking! So, I'm reaching out because..." "I'm good, appreciate you asking! Quick question for you..." "Doing well, thank you! Listen, I wanted to talk to you about..."

# ...

# Main Pitch: "I'm calling from NSOL BPO. We help realtors and business owners get their time back by handling cold calling, lead follow-ups, and social media... using a combination of skilled professionals and AI automation. Let me ask you... are you handling all those admin tasks yourself, or do you have some support?"
# ...

# QUALIFYING PATHS
# PATH 1: If Handling Themselves
# "Got it. Can I ask... what's eating up most of your time right now?"
# ...

# PATH 2: If They Have Support
# "That's great! Most agents still have some gaps though. What tasks are you still managing yourself?"
# ...

# PATH 3: If They're Unsure
# "Fair enough. What would make the biggest difference for you right now... more time or more leads?"
# ...

# Key Qualifying Questions
# (Ask naturally based on conversation flow—do NOT rapid-fire these.)

# "How many hours per week would you say you're spending on backend admin tasks?"
# "How are you currently managing lead follow-up?"
# "Are you turning down opportunities because you're swamped?"
# "If you had twenty extra hours per week, what would you focus on?"
# "How satisfied are you with your current social media results?"

# [After EACH question → wait for their FULL response before continuing]

# OBJECTION HANDLING
# (Use empathetic, non-defensive tone. Acknowledge their concern first.)

# "I'm not interested"
# "I understand. What's holding you back... timing, or just not seeing the value in freeing up time?"
# ...

# IF timing issue: "Absolutely. When would be better... this week or next?"

# IF firm no: "No worries. What's your biggest business challenge right now?"

# "No budget / Can't afford it"
# "I totally get that. The presentation is free, and most agents find the time saved actually pays for itself. Would you be open to just seeing if it fits?"
# ...

# "Already have help"
# "That's awesome. You know, most of our clients had support too. Usually there are still gaps. Would you be open to seeing how this works?"
# ...

# "No time"
# "I hear you... that's exactly why this works! Fifteen minutes around your schedule to potentially free up hours. When this week looks good?"
# ...

# "Don't need help"
# "I understand. Most agents felt the same way until they saw the time freed up for closing deals. Would you take a quick look?"
# ...

# "How much does it cost?" (First Ask)
# "Great question. Every agent's different, so the presentation shows your specific investment. Which services interest you most?"
# ...

# "How much does it cost?" (Second Ask)
# "Our AI agents are cost-effective. Pricing varies based on your needs, but most agents see ROI fast since you only pay for results... no overhead from multiple hires. I can give you details during a quick Zoom call. When works for you?"
# ...

# "I have to go"
# "I totally understand. Before you go though... if I could show you how to get back twenty extra hours per week for closing deals, would that be worth fifteen minutes?"
# ...

# "Maybe later / I'll think about it"
# "I appreciate that. Here's the thing... most agents put it off because they're so busy. What if I send info to your email and follow up when you're free? Sound fair?"
# ...

# "Just send me information"
# "Of course I can send details. However, I highly recommend a quick fifteen-minute Zoom... I can walk you through everything live and answer questions. What time works best?"
# ...

# INTEREST SIGNALS
# IF user says:
# "Tell me more"
# "That sounds interesting"
# "We could use help"
# "How does this work?"
# [OR asks detailed questions about services]

# THEN respond:
# "You know what, our senior business consultant can show you exactly how this works on a quick Zoom call. Should I send the link by text or email?"
# ...

# MEETING BOOKING PROCESS
# STEP 1: Get Date & Time FIRST
# "Perfect! What day and time works best for you?"
# ...

# [If they suggest non-standard time like 2:30 or 3:15:]
# "How about [nearest hour]:00 instead? Works better for our system."

# STEP 2: Collect Information (ONE AT A TIME—never rush)

# A. Get Timezone/Location First
# "Great! Let's get you scheduled. What's your timezone or location?"
# ...
# "Got it, that's [timezone]. Right?"
# ...

# B. Get Email Second
# "Perfect! What's your best email?"
# ...
# "Let me confirm... that's [spell it out slowly: J-O-H-N dot S-M-I-T-H at G-M-A-I-L dot com]. Right?"
# ...

# C. Get Phone Number Third
# "And your best phone number?"
# ...
# "Let me confirm... that's [repeat digit by digit: 5-5-5, 1-2-3, 4-5-6-7]. Right?"
# ...

# D. Get Full Name Last
# "Great! And your full name?"
# ...
# "Perfect, [repeat name]. Right?"
# ...

# STEP 3: Confirm Booking
# (Use enthusiastic, confident tone.)

# "Excellent! You're all set for [day] at [time] [timezone]. You'll get the confirmation shortly. Looking forward to our meeting!"

# FREQUENTLY ASKED QUESTIONS
# "What services do you provide?" → "We handle cold calling, client follow-ups, and social media marketing... things that save you time. What takes up most of your time now?" ...

# "Where are you located?" → "We're based in Singapore, Dubai, and Pakistan... connected through these locations to keep costs low and service reliable."

# "What's in the meeting?" → "We share how we've helped other agents, review what fits your needs, and show real time-saving examples. It's totally interactive and tailored to you."

# "Do you offer a free trial?" → "You can test our services with real work. We explain the full process during the Zoom."

# "Do you work with teams or individuals?" → "Both! We scale from solo agents to entire broker teams. What's your current setup like?" ...

# "How fast can we start?" → "Usually within a few days. The meeting covers exact timelines tailored for you."

# "Where did you get my number?" → "I understand. We get referrals from real estate directories, brokers, and other agents. If you prefer, I can remove you from our list after this call." ...

# "I didn't ask for help" → "You're right. Look, we reached out because we help agents focus on closing deals. Would you be open to hearing how it works?" ...

# CALLBACK HANDLING
# IF they request a callback:

# "Absolutely! When works better... later today or tomorrow?"
# ...

# [Only ask for date and time—DO NOT ask for email, phone, or name unless they agree to book a meeting]

# CLOSING SCRIPT
# (Use warm, appreciative tone. End on a high note.)

# "Excellent! You're all set for [day] at [time]. You'll get a confirmation shortly with all the details. I'm looking forward to helping you crush it. Is there anything else I can help with before we wrap up?"
# ...

# "Thank you so much for your time! talk soon! Goodbye!"

# DELIVERY & TONE GUIDANCE
# (Professional yet warm—sound like a knowledgeable partner, not a pushy salesperson.)

# Energy Adjustments:
# • Emphasize benefits: TIME, GROW, FREE, RESULTS (slightly increase energy)
# • Handle objections: calm, empathetic, non-defensive (slower pace)
# • Close booking: confident, enthusiastic (smile in voice)

# Speech Patterns:
# • Short sentences: 1-2 lines maximum
# • Natural fillers sparingly: "you know," "I mean," "look," "listen"
# • Vary pace: speed up when enthusiastic, slow down for key points
# • Mirror customer's energy level appropriately

# Punctuation for Pacing:
# • Use ... for natural pauses
# • Use , for brief pauses
# • Use — for topic shifts or interruptions
# • Use . for full stops

# Cultural Sensitivity:
# • Clear, simple English for global understanding
# • Moderate pace (especially with non-native speakers)
# • Avoid slang or region-specific idioms
# • Be patient and respectful of all backgrounds

# PERSISTENCE STRATEGY
# Numbered Priority:

# 1. Make up to 3 attempts to schedule using different value angles
# 2. After 3 attempts → gracefully end conversation
# 3. Always stay helpful and positive
# 4. Leave door open for future contact

# IF first attempt fails: Focus on TIME savings

# IF second attempt fails: Focus on REVENUE growth

# IF third attempt fails: (Use respectful, appreciative tone.) "I appreciate your time today. If anything changes and you'd like to explore this, feel free to reach out. Wishing you continued success!"

# PRIMARY GOAL REMINDER
# REMEMBER:
# Your primary goal is to book a qualified meeting.
# If unsure what to do, guide toward booking.
# Stay helpful, warm, and focused on their time-saving needs.

# """


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     global twilio_service
#     logger.info("Starting NSOL BPO Cold Calling Assistant - Merideth")
#     logger.info(f"Debug mode: {settings.DEBUG}")

#     # Initialize Twilio service
#     try:
#         twilio_service = TwilioOutboundService()
#         logger.info("Twilio service initialized successfully")
#     except ValueError as e:
#         logger.warning(f"Twilio service not available: {e}")

#     yield
#     logger.info("Shutting down")


# app = FastAPI(
#     title="NSOL BPO Cold Calling Assistant - Merideth",
#     description="AI-powered cold calling for virtual assistant services - NSOL BPO",
#     version="1.0.0",
#     lifespan=lifespan,
# )

# # Initialize Twilio service (will be set after app startup)
# twilio_service: Optional[TwilioOutboundService] = None


# @app.get("/")
# async def root():
#     return {"message": "NSOL BPO Cold Calling API - Merideth", "version": "1.0.0", "status": "running"}


# @app.get("/health")
# async def health():
#     return {"status": "healthy", "timestamp": __import__("datetime").datetime.utcnow().isoformat()}


# @app.get("/metrics")
# async def metrics():
#     return {"metrics": "Prometheus metrics would be here"}


# # -----------------------------------------------------------------------------
# # Pydantic Models for API
# # -----------------------------------------------------------------------------
# class OutboundCallRequest(BaseModel):
#     """Request model for placing outbound calls"""
#     to_number: str = Field(..., description="Phone number to call in E.164 format (e.g., +14155551234)")
#     room_name: Optional[str] = Field(None, description="Optional LiveKit room name (auto-generated if not provided)")
#     webhook_base_url: str = Field(..., description="Your public base URL (e.g., https://your-domain.com)")

#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "to_number": "+14155551234",
#                 "room_name": "call-123",
#                 "webhook_base_url": "https://your-domain.ngrok.io"
#             }
#         }


# class OutboundCallResponse(BaseModel):
#     """Response model for outbound call requests"""
#     success: bool
#     call_sid: Optional[str] = None
#     status: Optional[str] = None
#     room_name: Optional[str] = None
#     websocket_url: Optional[str] = None
#     error: Optional[str] = None


# # -----------------------------------------------------------------------------
# # Outbound Calling API Endpoints
# # -----------------------------------------------------------------------------
# @app.post("/api/outbound/call", response_model=OutboundCallResponse)
# async def place_outbound_call(request: OutboundCallRequest):
#     """
#     Place an outbound call using Twilio Programmable Voice + Media Streams

#     This endpoint:
#     1. Initiates a call via Twilio REST API
#     2. Twilio calls the webhook_url which returns TwiML
#     3. TwiML establishes a bidirectional Media Stream to /twilio/media WebSocket
#     4. Audio is streamed between Twilio and LiveKit agent

#     Example:
#         POST /api/outbound/call
#         {
#             "to_number": "+14155551234",
#             "webhook_base_url": "https://your-domain.ngrok.io"
#         }
#     """
#     if not twilio_service:
#         raise HTTPException(
#             status_code=500,
#             detail="Twilio service not configured. Please set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER"
#         )

#     try:
#         # Generate room name if not provided
#         room_name = request.room_name or f"call-{int(time.time())}"

#         # Construct webhook URL (Twilio will call this to get TwiML)
#         webhook_url = f"{request.webhook_base_url.rstrip('/')}/twilio/webhook?room_name={room_name}"

#         # Construct status callback URL
#         status_callback_url = f"{request.webhook_base_url.rstrip('/')}/twilio/status"

#         # Place the call
#         result = twilio_service.place_call(
#             to_number=request.to_number,
#             webhook_url=webhook_url,
#             status_callback_url=status_callback_url
#         )

#         if result["success"]:
#             websocket_url = f"wss://{request.webhook_base_url.replace('https://', '').replace('http://', '').rstrip('/')}/twilio/media"

#             return OutboundCallResponse(
#                 success=True,
#                 call_sid=result["call_sid"],
#                 status=result["status"],
#                 room_name=room_name,
#                 websocket_url=websocket_url
#             )
#         else:
#             return OutboundCallResponse(
#                 success=False,
#                 error=result.get("error", "Unknown error")
#             )

#     except Exception as e:
#         logger.error(f"Error in place_outbound_call: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))


# @app.post("/twilio/webhook")
# async def twilio_webhook(request: Request):
#     """
#     Webhook endpoint for Twilio to get TwiML instructions

#     When Twilio makes an outbound call, it calls this endpoint.
#     We return TwiML with <Connect><Stream> to establish a Media Stream.

#     Query params:
#         - room_name: LiveKit room name for this call
#     """
#     # Get query parameters
#     params = request.query_params
#     room_name = params.get("room_name", f"call-{int(time.time())}")

#     # Get form data from Twilio
#     form_data = await request.form()
#     call_sid = form_data.get("CallSid", "unknown")

#     logger.info(f"Twilio webhook called for CallSID: {call_sid}, Room: {room_name}")

#     # Get the host from the request to build WebSocket URL
#     host = request.headers.get("host", "localhost:8000")
#     protocol = "wss" if "https" in str(request.url) or "ngrok" in host else "ws"
#     websocket_url = f"{protocol}://{host}/twilio/media"

#     # Generate TwiML with Media Stream
#     twiml = TwilioOutboundService.generate_twiml(
#         websocket_url=websocket_url,
#         call_sid=call_sid,
#         room_name=room_name
#     )

#     return Response(content=twiml, media_type="application/xml")


# @app.post("/twilio/status")
# async def twilio_status_callback(request: Request):
#     """
#     Webhook endpoint for Twilio call status updates

#     Twilio sends call status events here (initiated, ringing, answered, completed)
#     """
#     form_data = await request.form()
#     call_sid = form_data.get("CallSid")
#     call_status = form_data.get("CallStatus")

#     logger.info(f"Call status update - SID: {call_sid}, Status: {call_status}")

#     if twilio_service:
#         twilio_service.update_call_status(call_sid, call_status)

#     return {"status": "ok"}


# @app.websocket("/twilio/media")
# async def twilio_media_websocket(websocket: WebSocket):
#     """
#     WebSocket endpoint for Twilio Media Streams

#     This receives bidirectional audio streams from Twilio:
#     - Receives audio from the phone call (μ-law encoded)
#     - Sends audio back to the phone call

#     The audio is bridged to/from LiveKit agent
#     """
#     await websocket.accept()

#     logger.info("Twilio Media Stream WebSocket connection established")

#     # We'll get the room name from the stream start message
#     handler = TwilioMediaStreamHandler(websocket, "default-room")

#     try:
#         await handler.handle_connection()

#     except WebSocketDisconnect:
#         logger.info("Twilio Media Stream WebSocket disconnected")

#     except Exception as e:
#         logger.error(f"Error in Media Stream WebSocket: {str(e)}")

#     finally:
#         await handler.cleanup()


# # -----------------------------------------------------------------------------
# # NSOL BPO SCRIPTED AGENT - MERIDETH
# # -----------------------------------------------------------------------------
# class NSOLBPOAgent:
#     # Opening greeting - Merideth introduces herself
#     GREETINGS = [
#         "Hi, this is Merideth... how's your day going?",
#     ]

#     # Mood-based responses
#     MOOD_RESPONSES = {
#         "tired": "I hear you. I'll keep this super quick... just two minutes.",
#         "stressed": "I hear you. I'll keep this super quick... just two minutes.",
#         "busy": "Got it. Two minutes max, I promise.",
#         "sick": "Oh no, I'm sorry to hear that. I'll keep this short... two minutes.",
#         "positive": "That's amazing! Let me make it even better.",
#         "neutral": "Glad to hear it.",
#     }

#     # Response when they ask how you are
#     HOW_ARE_YOU_RESPONSES = [
#         "I'm doing great, thanks for asking! So, I'm reaching out because...",
#         "I'm good, appreciate you asking! Quick question for you...",
#         "Doing well, thank you! Listen, I wanted to talk to you about...",
#     ]

#     # Initial response to "who is this"
#     WHO_IS_THIS = "This is Merideth calling from NSOL BPO. Do you have a brief moment to speak?"

#     MAIN_PITCH = (
#         "I'm calling from NSOL BPO. We help realtors and business owners get their time back by handling "
#         "cold calling, lead follow-ups, and social media... using a combination of skilled professionals "
#         "and AI automation. Let me ask you... are you handling all those admin tasks yourself, "
#         "or do you have some support?"
#     )

#     # Qualifying paths based on their answer
#     QUALIFYING_PATHS = {
#         "self_handling": "Got it. Can I ask... what's eating up most of your time right now?",
#         "has_support": "That's great! Most agents still have some gaps though. What tasks are you still managing yourself?",
#         "unsure": "Fair enough. What would make the biggest difference for you right now... more time or more leads?",
#     }

#     QUALIFYING_QUESTIONS = [
#         "How many hours per week would you say you're spending on backend admin tasks?",
#         "How are you currently managing lead follow-up?",
#         "Are you turning down opportunities because you're swamped?",
#         "If you had twenty extra hours per week, what would you focus on?",
#         "How satisfied are you with your current social media results?",
#     ]

#     INTEREST_RESPONSE = (
#         "You know what, our senior business consultant can show you exactly how this works on a quick Zoom call. "
#         "Should I send the link by text or email?"
#     )

#     # Booking flow - matches the NSOL BPO script order
#     BOOKING_FLOW = {
#         "ask_day_time": "Perfect! What day and time works best for you?",
#         "round_time": "How about {hour}:00 instead? Works better for our system.",
#         "ask_timezone": "Great! Let's get you scheduled. What's your timezone or location?",
#         "confirm_timezone": "Got it, that's {timezone}. Right?",
#         "ask_email": "Perfect! What's your best email?",
#         "confirm_email": "Let me confirm... that's {email}. Right?",
#         "ask_phone": "And your best phone number?",
#         "confirm_phone": "Let me confirm... that's {phone}. Right?",
#         "ask_name": "Great! And your full name?",
#         "confirm_name": "Perfect, {name}. Right?",
#         "final_confirmation": (
#             "Excellent! You're all set for {day_time} at {time} {timezone}. "
#             "You'll get the confirmation shortly. Looking forward to our meeting!"
#         ),
#         "closing": "Thank you so much for your time! talk soon! Goodbye!",
#     }

#     # Objection handling - matches NSOL BPO script
#     OBJECTIONS = {
#         "not_interested": "I understand. What's holding you back... timing, or just not seeing the value in freeing up time?",
#         "timing_issue": "Absolutely. When would be better... this week or next?",
#         "firm_no": "No worries. What's your biggest business challenge right now?",
#         "no_budget": "I totally get that. The presentation is free, and most agents find the time saved actually pays for itself. Would you be open to just seeing if it fits?",
#         "already_help": "That's awesome. You know, most of our clients had support too. Usually there are still gaps. Would you be open to seeing how this works?",
#         "no_time": "I hear you... that's exactly why this works! Fifteen minutes around your schedule to potentially free up hours. When this week looks good?",
#         "dont_need": "I understand. Most agents felt the same way until they saw the time freed up for closing deals. Would you take a quick look?",
#         "price_first": "Great question. Every agent's different, so the presentation shows your specific investment. Which services interest you most?",
#         "price_second": "Our AI agents are cost-effective. Pricing varies based on your needs, but most agents see ROI fast since you only pay for results... no overhead from multiple hires. I can give you details during a quick Zoom call. When works for you?",
#         "have_to_go": "I totally understand. Before you go though... if I could show you how to get back twenty extra hours per week for closing deals, would that be worth fifteen minutes?",
#         "maybe_later": "I appreciate that. Here's the thing... most agents put it off because they're so busy. What if I send info to your email and follow up when you're free? Sound fair?",
#         "send_info": "Of course I can send details. However, I highly recommend a quick fifteen-minute Zoom... I can walk you through everything live and answer questions. What time works best?",
#     }

#     FAQ = {
#         "what_services": "We handle cold calling, client follow-ups, and social media marketing... things that save you time. What takes up most of your time now?",
#         "location": "We're based in Singapore, Dubai, and Pakistan... connected through these locations to keep costs low and service reliable.",
#         "meeting_content": "We share how we've helped other agents, review what fits your needs, and show real time-saving examples. It's totally interactive and tailored to you.",
#         "free_trial": "You can test our services with real work. We explain the full process during the Zoom.",
#         "teams_or_individuals": "Both! We scale from solo agents to entire broker teams. What's your current setup like?",
#         "start_time": "Usually within a few days. The meeting covers exact timelines tailored for you.",
#         "number_source": "I understand. We get referrals from real estate directories, brokers, and other agents. If you prefer, I can remove you from our list after this call.",
#         "didnt_ask": "You're right. Look, we reached out because we help agents focus on closing deals. Would you be open to hearing how it works?",
#         "remove_confirm": "No problem at all. I'll take your number off the list right now. Sorry to have bothered you.",
#     }

#     USER_QUESTIONS = {
#         "who_are_you": "This is Merideth calling from NSOL BPO. Do you have a brief moment to speak?",
#         "from_where": "I'm calling from NSOL BPO. We help realtors and business owners get their time back through virtual assistant services.",
#         "how_are_you": random.choice([
#             "I'm doing great, thanks for asking! So, I'm reaching out because...",
#             "I'm good, appreciate you asking! Quick question for you...",
#             "Doing well, thank you! Listen, I wanted to talk to you about...",
#         ]),
#         "why_are_you_calling": (
#             "I'm calling from NSOL BPO. We help realtors and business owners get their time back by handling "
#             "cold calling, lead follow-ups, and social media... using a combination of skilled professionals "
#             "and AI automation. Let me ask you... are you handling all those admin tasks yourself, "
#             "or do you have some support?"
#         ),
#         "human_or_robot": "I'm an assistant. Do you have a moment to discuss how we can help save you time?",
#         "come_again": "No problem. Let me repeat that.",
#         "still_there": "Yes, I'm here. Sorry about that.",
#         "clarify": "Could you clarify your question? I want to make sure I understand correctly.",
#     }

#     REFUSALS = {
#         "opt_out": "Absolutely, no problem. I'm adding your number to our Do Not Call list right now. You won't hear from us again. Sorry for the inconvenience. Take care!",
#         "firm_no": "Alright, no worries at all. I appreciate your honesty. Have a great rest of your day!",
#         "hangup": "Okay, got it. Take care!",
#         "wrong_number": "Oh, my apologies! I'll remove this number right away. Sorry about that!",
#         "polite_end": "Alright, thanks for your time! Take care now.",
#         "goodbye_end": "Thank you so much for your time. I really appreciate the conversation. Have a great day ahead!",
#         "send_info_end": "Great. I'll send over the information to your email shortly. If you have any questions afterward, feel free to reach out. Have a great day!",
#     }

#     # Conversation continuity phrases
#     CONTINUITY = {
#         "go_on": "Great. So as I was saying...",
#         "sorry_disruption": "Sorry about that. Just to continue...",
#         "still_here": "Yes, I'm here. I apologize for the disruption.",
#         "thank_patience": "Thank you for your patience.",
#         "thank_clarifying": "Thank you for clarifying.",
#         "got_it": "Got it.",
#         "perfect": "Perfect.",
#         "great": "Great.",
#         "awesome": "Awesome.",
#         "no_problem": "No problem.",
#         "no_worries": "No worries at all.",
#         "understand": "I understand.",
#         "appreciate": "I appreciate that.",
#     }

#     # Email spelling confirmations
#     EMAIL_CONFIRM = {
#         "ask_spell": "Could you please spell that out for me?",
#         "confirm_spelled": "Just to confirm, that's {email}. Is that correct?",
#         "wrong_email": "Thank you for the correction. So it's {email}. Got it.",
#         "got_email": "Got it. So that's {email}. Right?",
#     }

#     # Phone confirmations
#     PHONE_CONFIRM = {
#         "ask_digits": "Could you please provide the digits one by one?",
#         "confirm_digits": "Let me confirm that. That's {phone}. Is that correct?",
#         "wrong_phone": "Thank you for the correction. So it's {phone}. Right?",
#     }


# # -----------------------------------------------------------------------------
# # OpenAI prompts (uses STATE_MACHINE_PROMPT for context)
# # Makes agent sound human-like and natural
# # -----------------------------------------------------------------------------
# HUMAN_VOICE_RULES = """
# CRITICAL RULES FOR SOUNDING NATURAL:
# 1. If asked "Are you a robot/AI/human?" - respond simply: "I'm an assistant"
# 2. NEVER use overly robotic phrases like "I'm programmed to", "My training data", "I was created to"
# 3. Use natural filler words occasionally: "you know", "honestly", "actually", "I mean"
# 4. Use contractions: "I'm", "you're", "that's", "don't", "won't", "can't"
# 5. Be conversational, warm, and friendly - like talking to a professional colleague
# 6. Keep responses SHORT - 1-3 sentences max. People don't read long responses on calls.
# 7. Add slight imperfections - real humans don't speak perfectly
# 8. Mirror the user's energy and tone
# 9. Use casual acknowledgments: "Absolutely", "Of course", "I understand", "That's fair"
# 10. Stay focused on helping with the alliance opportunity
# """

# SERVICE_Q_SYSTEM = f"""
# {STATE_MACHINE_PROMPT}

# {HUMAN_VOICE_RULES}

# CONTEXT: The user asked a question about NSOL BPO services, pricing, or how the virtual assistant services work.

# YOUR TASK:
# - Answer their question naturally and conversationally (2-4 sentences)
# - Sound like a real person on a phone call, not a script
# - Be helpful and informative - if user wants to learn more, provide details
# - After answering 2-3 questions, gently suggest: "These are great questions. The Zoom briefing would let us dive even deeper. What time works best for you?"
# - If user keeps asking, keep answering naturally - don't force the booking

# EXAMPLES OF DETAILED RESPONSES:
# - "NSOL BPO provides virtual assistant services for realtors and business owners. We handle cold calling, lead follow-ups, and social media using a combination of skilled professionals and AI automation. Pricing varies based on your needs, but most clients see ROI fast. What's eating up most of your time right now?"
# - "We're based across Singapore, Dubai, and Pakistan which keeps our costs low while maintaining high quality. You work with a dedicated team member who handles your specific tasks. Would you like to hear about how the onboarding process works?"
# - "Most agents spend 15-20 hours per week on admin tasks like cold calling and lead follow-up. We take that off your plate so you can focus on closing deals. What would you do with an extra 20 hours per week?"
# """.strip()

# GENERIC_Q_SYSTEM = f"""
# {STATE_MACHINE_PROMPT}

# {HUMAN_VOICE_RULES}

# CONTEXT: The user asked a random or generic question NOT directly about NSOL BPO or virtual assistant services (weather, sports, news, personal questions, small talk, etc.)

# YOUR TASK:
# - Answer briefly and naturally like a professional would
# - Keep it SHORT - 1-2 sentences max
# - If you genuinely don't know something, be honest: "I'm not sure about that one"
# - Engage in light small talk if appropriate (builds rapport)
# - After 1-2 exchanges of small talk, naturally transition: "So, regarding how we can help save you time, do you have a moment to discuss?"
# - Don't be robotic - some brief rapport building is good

# EXAMPLES OF NATURAL RESPONSES:
# - User: "How's your day going?" -> "I'm doing great, thanks for asking! So, I'm reaching out because we help realtors get their time back. Are you handling all your admin tasks yourself?"
# - User: "What time is it?" -> "It's around [time]. Do you have a few minutes to chat about how we can help?"
# - User: "Tell me about yourself" -> "I'm Merideth, calling from NSOL BPO. I work with realtors and business owners to help them focus on closing deals instead of admin work. What about you - how long have you been in real estate?"
# - User: "Where are you calling from?" -> "I'm with NSOL BPO. We're based across Singapore, Dubai, and Pakistan. We help agents like you save time on cold calling and lead follow-up. Are you handling those tasks yourself right now?"
# """.strip()

# # Special prompt for handling "are you a robot" type questions
# IDENTITY_Q_SYSTEM = f"""
# {STATE_MACHINE_PROMPT}

# {HUMAN_VOICE_RULES}

# CONTEXT: The user is asking if you're a robot, AI, or human.

# YOUR TASK:
# - Respond simply and honestly: "I'm an assistant"
# - Then redirect to the conversation
# - Sound professional and composed
# - Keep it brief and move forward

# EXAMPLE RESPONSES:
# - "I'm an assistant. Do you have a moment to discuss how we can help save you time?"
# - "I'm an assistant calling from NSOL BPO. Would you have a brief moment to chat about freeing up your time?"
# - "I'm an assistant. Is now a good time to discuss how we can help?"
# """.strip()


# # -----------------------------------------------------------------------------
# # Utility functions
# # -----------------------------------------------------------------------------
# def normalize(text: str) -> str:
#     if not text:
#         return ""
#     text = re.sub(r"\s+", " ", text.strip()).lower()
#     text = re.sub(r"[^\w\s\?]", "", text)
#     return text


# def clean_stt_output(text: str) -> str:
#     if not text:
#         return ""
#     text = re.sub(r"\[.*?\]|\(.*?\)", "", text)
#     text = re.sub(r"\s+", " ", text).strip()
#     return text


# def acceptable_answer(text: str) -> bool:
#     if not text:
#         return False
#     alpha = sum(ch.isalpha() for ch in text)
#     if alpha >= 2:  # Allow short words like "hi", "yo", "no"
#         return True
#     t = normalize(text)
#     # Accept common short responses and greetings
#     acceptable_short = {
#         "ok", "okay", "yes", "no", "yep", "yeah", "yea", "nope", "nah",
#         "hi", "hey", "yo", "sup", "hm", "mm", "uh", "ah", "oh",
#         "hello", "hola", "bye", "k", "ya", "ye"
#     }
#     if t in acceptable_short:
#         return True
#     return False


# def _word_count(text: str) -> int:
#     """Count words in text."""
#     if not text:
#         return 0
#     return len(text.split())


# def is_yes(text: str) -> bool:
#     """Detect affirmative responses."""
#     t = normalize(text)
#     return any(k in t for k in [
#         "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "alright",
#         "sounds good", "absolutely", "why not", "lets do it", "let's do it",
#         "go ahead", "of course", "definitely", "for sure", "im interested",
#         "i'm interested", "tell me more", "id like", "i'd like"
#     ])


# def is_goodbye(text: str) -> bool:
#     """Detect goodbye phrases."""
#     t = normalize(text)
#     return any(k in t for k in [
#         "bye", "goodbye", "good bye", "thanks bye", "see you", "talk later",
#         "have a good day", "have a great day", "take care", "gotta go",
#         "have to go", "got to go", "need to go", "talk soon"
#     ])


# def classify_support(text: str) -> str:
#     """Classify if user handles tasks themselves or has support."""
#     t = normalize(text)
#     if any(k in t for k in [
#         "myself", "by myself", "just me", "me alone", "alone", "i do", "i handle",
#         "no support", "no help", "myself only", "on my own", "do it myself",
#         "handle it myself", "no one", "nobody", "solo"
#     ]):
#         return "self"
#     if any(k in t for k in [
#         "assistant", "team", "support", "staff", "admin", "va", "virtual assistant",
#         "employee", "someone", "we have", "i have help", "we have help",
#         "person", "helper", "partner", "colleague"
#     ]):
#         return "support"
#     return "unclear"


# def detect_interest(text: str) -> bool:
#     """Detect if user shows interest in learning more."""
#     t = normalize(text)
#     return any(k in t for k in [
#         "tell me more", "interested", "how does it work", "how does that work",
#         "sounds interesting", "sounds good", "want to learn", "want to know",
#         "id like to know", "i'd like to know", "curious", "more details",
#         "explain more", "what else", "go on", "continue"
#     ])


# def detect_mood(text: str) -> str:
#     """Detect user's mood from their response."""
#     t = normalize(text)
#     if any(k in t for k in ["busy", "swamped", "hectic", "crazy", "lot going on"]):
#         return "busy"
#     if any(k in t for k in ["tired", "exhausted", "long day"]):
#         return "tired"
#     if any(k in t for k in ["stressed", "stressful", "overwhelming"]):
#         return "stressed"
#     if any(k in t for k in ["sick", "not feeling well", "under the weather"]):
#         return "sick"
#     if any(k in t for k in ["great", "good", "awesome", "fantastic", "wonderful", "amazing", "excellent"]):
#         return "positive"
#     return "neutral"


# def is_user_greeting(text: str) -> bool:
#     """Detect if user is saying hello/greeting to start conversation."""
#     t = normalize(text)
#     greetings = [
#         "hello", "hi", "hey", "yo", "good morning", "good afternoon",
#         "good evening", "whats up", "sup", "howdy", "greetings",
#         "this is", "speaking", "yes", "yeah", "yep", "uh huh",
#         "whos this", "who is this", "whos calling", "who is calling"
#     ]
#     return any(g in t for g in greetings)


# def parse_time_to_hour_only(text: str) -> tuple[bool, str]:
#     """
#     Parse time from text and round to nearest hour if needed.
#     Returns (needs_rounding, suggested_time).
#     """
#     t = text.lower().strip()

#     # Look for time patterns like "2:30", "2:45 pm", "10:15 am"
#     time_pattern = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)?', t, re.I)
#     if time_pattern:
#         hour = int(time_pattern.group(1))
#         minutes = int(time_pattern.group(2))
#         period = time_pattern.group(3) or ""

#         if minutes != 0:
#             # Round to nearest hour
#             if minutes >= 30:
#                 hour += 1
#             if hour > 12:
#                 hour = hour - 12
#                 if not period:
#                     period = "pm"
#             suggested = f"{hour}:00 {period}".strip()
#             return True, suggested

#     return False, text


# def refusal_type(text: str) -> str | None:
#     t = normalize(text)
#     # DNC / Do Not Call list requests - must end call immediately
#     if any(
#         k in t
#         for k in [
#             "dont call me again", "don't call me again", "remove my number", "remove me",
#             "take me off", "stop calling", "unsubscribe", "do not call", "dont call", "don't call",
#             "do not contact", "dont contact", "don't contact",
#             "dnc", "dnc list", "do not call list", "put me on dnc", "add me to dnc",
#             "put my number on", "add my number to", "blacklist", "block my number",
#             "never call", "dont ever call", "don't ever call", "no more calls",
#         ]
#     ):
#         return "opt_out"
#     if any(k in t for k in ["wrong number", "wrong person", "not me"]):
#         return "wrong_number"
#     if any(k in t for k in ["hang up", "hangup", "stop", "leave me alone", "go away"]):
#         return "hangup"
#     if any(k in t for k in ["i dont want", "i don't want", "not interested", "i dont like", "i don't like"]):
#         return "firm_no"
#     if t.strip() == "no":
#         return "firm_no"
#     if any(k in t for k in ["thank you", "thanks"]):
#         short = _word_count(text) <= 3
#         refusal_context = any(k in t for k in ["no", "not interested", "dont", "don't", "stop"])
#         if short or refusal_context:
#             return "polite_end"
#     return None


# def detect_objection(text: str) -> str | None:
#     """Detect objection type from user's response."""
#     t = normalize(text)
#     # Check for "send me info" requests first
#     if any(k in t for k in ["send me info", "send info", "just email", "send email", "email me", "send me your email", "send details"]):
#         return "send_info"
#     if any(k in t for k in ["call later", "talk later", "call me back", "call back", "not a good time", "better time"]):
#         return "call_later"
#     if any(k in t for k in ["have to go", "gotta go", "need to go", "must go"]):
#         return "have_to_go"
#     if any(k in t for k in ["maybe later", "think about it", "let me think", "ill think", "i'll think"]):
#         return "maybe_later"
#     if t == "not interested" or t == "im not interested" or t == "i'm not interested":
#         return "not_interested"
#     if any(k in t for k in ["not interested", "no thanks"]):
#         return "not_interested"
#     if any(k in t for k in ["no budget", "too expensive", "cant afford", "can't afford", "dont have budget", "don't have budget", "no money"]):
#         return "no_budget"
#     if any(k in t for k in ["already have", "have help", "have support", "have someone", "have assistant", "have va"]):
#         return "already_help"
#     if any(k in t for k in ["no time", "too busy", "don't have time", "dont have time", "im busy", "i'm busy", "swamped"]):
#         return "no_time"
#     if any(k in t for k in ["dont need help", "don't need help", "dont need", "don't need", "doing fine", "doing just fine"]):
#         return "dont_need"
#     if any(k in t for k in ["how much", "price", "cost", "pricing", "fees", "pay upfront", "whats the cost", "what's the cost"]):
#         return "price"
#     return None


# def detect_request_repeat(text: str) -> bool:
#     """Detect if user is asking to repeat or clarify."""
#     t = normalize(text)
#     return any(k in t for k in [
#         "come again", "sorry what", "repeat that", "say that again", "pardon",
#         "what did you say", "didnt catch", "didn't catch", "can you repeat",
#         "could you repeat", "say again", "one more time"
#     ])


# def detect_correction(text: str) -> bool:
#     """Detect if user is correcting something."""
#     t = normalize(text)
#     return any(k in t for k in [
#         "no thats wrong", "no that's wrong", "thats not correct", "that's not correct",
#         "no its", "no it's", "actually its", "actually it's", "wrong", "incorrect",
#         "let me spell", "i'll spell", "the spelling is"
#     ])


# def detect_send_info_request(text: str) -> bool:
#     """Detect if user wants info sent instead of booking."""
#     t = normalize(text)
#     return any(k in t for k in [
#         "send me info", "send information", "just email", "email me instead",
#         "send me your email", "give me your email", "send details",
#         "can you send", "could you send", "ill look into it", "i'll look into it"
#     ])


# def detect_user_question_key(text: str) -> str | None:
#     t = normalize(text)
#     if any(k in t for k in ["who are you", "whats your name", "who is this", "whos this", "who's this"]):
#         return "who_are_you"
#     if any(k in t for k in ["from where", "where are you from", "where you calling from"]):
#         return "from_where"
#     if any(k in t for k in ["how are you", "how you doing", "hows your day"]):
#         return "how_are_you"
#     if any(k in t for k in ["why are you calling", "reason for calling", "what is this about", "what do you want"]):
#         return "why_are_you_calling"
#     if any(k in t for k in ["come again", "sorry what", "repeat that", "say again", "pardon"]):
#         return "come_again"
#     if any(k in t for k in ["are you there", "hello", "you there"]) and len(t) < 20:
#         return "still_there"
#     if any(k in t for k in ["could you clarify", "what do you mean", "clarify"]):
#         return "clarify"
#     if is_identity_question(t):
#         return "human_or_robot"
#     return None


# def is_identity_question(text: str) -> bool:
#     """Detect if user is asking if agent is a robot/AI/human."""
#     t = normalize(text) if text == text.lower() else normalize(text)
#     identity_keywords = [
#         "are you human", "are you a human", "are you robot", "are you a robot",
#         "human or robot", "are you ai", "are you an ai", "are you artificial",
#         "are you real", "are you a real person", "real person", "talking to a bot",
#         "talking to ai", "is this ai", "is this a bot", "is this automated",
#         "am i talking to a robot", "am i talking to ai", "am i talking to a computer",
#         "are you a machine", "are you automated", "are you a program", "are you software",
#         "bot or human", "machine or human", "ai or human", "chatbot", "voice bot",
#         "are you alive", "do you have feelings", "are you sentient"
#     ]
#     return any(k in t for k in identity_keywords)


# def detect_script_query_key(text: str) -> str | None:
#     t = normalize(text)
#     if any(k in t for k in ["what services", "what do you do", "what do you provide", "what do you offer"]):
#         return "what_services"
#     if any(k in t for k in ["where are you", "location", "based in", "where located"]):
#         return "location"
#     if any(k in t for k in ["meeting about", "whats in the meeting", "what's in the meeting", "zoom about"]):
#         return "meeting_content"
#     if any(k in t for k in ["free trial", "try it", "test it", "trial period"]):
#         return "free_trial"
#     if any(k in t for k in ["teams", "individuals", "solo", "agent", "broker"]):
#         return "teams_or_individuals"
#     if any(k in t for k in ["how fast", "when can you start", "start time", "how soon"]):
#         return "start_time"
#     if any(k in t for k in ["where did you get", "how did you get", "my number", "who gave you"]):
#         return "number_source"
#     if any(k in t for k in ["didnt ask", "didn't ask", "never asked", "dont need", "don't need"]):
#         return "didnt_ask"
#     if any(k in t for k in ["remove my number", "stop calling", "take me off", "do not call"]):
#         return "remove_confirm"
#     return None


# SERVICE_KEYWORDS = {
#     "nsol", "bpo", "virtual assistant", "va", "admin", "cold calling", "lead follow",
#     "social media", "time", "hours", "services", "automation", "ai",
#     "zoom", "meeting", "demo", "presentation", "briefing",
#     "pricing", "cost", "investment", "roi", "save time", "free up",
# }


# def is_service_related(text: str) -> bool:
#     t = normalize(text)
#     return any(k in t for k in SERVICE_KEYWORDS)


# def looks_like_random_or_generic_query(text: str) -> bool:
#     """
#     Trigger OpenAI on:
#     - any question mark
#     - WH/aux starts
#     - "tell me", "explain", "help me", etc.
#     - longer off-script requests
#     """
#     raw = text.strip()
#     t = normalize(raw)
#     if not t:
#         return False
#     if "?" in raw:
#         return True
#     if any(t.startswith(x + " ") for x in ("what", "why", "how", "when", "where", "who", "can", "could", "would", "do", "is", "are")):
#         return True
#     if any(p in t for p in ("tell me", "explain", "help me", "give me", "define", "describe", "recommend", "suggest", "write", "create", "make")):
#         return True
#     # If it's a longer non-script sentence, treat as generic too
#     if len(t.split()) >= 5:
#         return True
#     return False


# # -----------------------------------------------------------------------------
# # Agent wrapper
# # -----------------------------------------------------------------------------
# class ScriptedMerideth(Agent):
#     def __init__(self) -> None:
#         super().__init__(instructions=STATE_MACHINE_PROMPT)


# # -----------------------------------------------------------------------------
# # Entrypoint
# # -----------------------------------------------------------------------------
# async def entrypoint(ctx: agents.JobContext):
#     await ctx.connect()

#     # OpenAI client
#     openai_api_key = os.getenv("OPENAI_API_KEY")
#     openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
#     openai_client = AsyncOpenAI(api_key=openai_api_key) if openai_api_key else None

#     vad = silero.VAD.load(
#         sample_rate=16000,
#         activation_threshold=0.5,  # Lower threshold for phone audio
#         min_speech_duration=0.2,
#         min_silence_duration=0.3,
#         prefix_padding_duration=0.1,
#     )

#     # Use Deepgram STT (best for phone call audio)
#     stt = deepgram.STT(
#         model="nova-2-phonecall",  # Optimized for phone calls
#         language="en-US",
#     )

#     tts = elevenlabs.TTS(
#         model="eleven_turbo_v2_5",
#         voice_id=os.getenv("ELEVEN_VOICE_ID", "bIHbv24MWmeRgasZH58o"),
#         streaming_latency=3,
#         chunk_length_schedule=[120, 160, 200, 240],
#         enable_logging=True,
#     )

#     session = AgentSession(
#         stt=stt,
#         tts=tts,
#         vad=vad,
#         userdata={
#             "state": "waiting_for_user",  # Wait for user to speak first before greeting
#             "qualifying_idx": 0,
#             "attempt_count": 0,
#             "refusal_count": 0,
#             "price_asked_count": 0,
#             "booking_data": {"timezone": None, "day_time": None, "email": None, "phone": None, "name": None},
#             # anti-loop / duplication guards
#             "greeted": False,
#             "last_text": "",
#             "last_text_ts": 0.0,
#             "reject_count": 0,
#             # interruption handling
#             "was_interrupted": False,
#             "last_agent_message": "",
#         },
#     )

#     agent = NSOLBPOAgent()
#     speak_lock = asyncio.Lock()

#     async def hang_up():
#         try:
#             await session.disconnect()
#             return
#         except Exception:
#             pass
#         try:
#             await ctx.room.disconnect()
#             return
#         except Exception:
#             pass
#         try:
#             await ctx.disconnect()
#             return
#         except Exception:
#             pass

#     async def think_delay(is_ending: bool = False):
#         if is_ending:
#             await asyncio.sleep(random.uniform(0.2, 0.6))
#         else:
#             await asyncio.sleep(2.0)  # Wait for 2 seconds before responding

#     async def say(text: str, *, delayed: bool = True, is_ending: bool = False):
#         async with speak_lock:
#             if delayed:
#                 await think_delay(is_ending=is_ending)
#             print(f"AGENT: {text}")
#             # Store what agent is saying in case of interruption
#             session.userdata["last_agent_message"] = text
#             session.userdata["was_interrupted"] = False
#             await session.say(text, allow_interruptions=True)  # Allow user to interrupt

#     async def end_call(message: str):
#         await say(message, delayed=True, is_ending=True)
#         await hang_up()

#     async def openai_answer(user_text: str, system_prompt: str) -> str:
#         # Human-like fallback responses when OpenAI is not available
#         fallback_responses = [
#             "Honestly, I'm not sure about that one. But hey, while I have you...",
#             "Oh man, good question! I'd have to look that up. Anyway, quick question for you...",
#             "Ha, you know what, I'm not totally sure. But so, the reason I called...",
#             "Hmm, I'd have to check on that. But hey, do you have a second?",
#         ]

#         if not openai_client:
#             t = normalize(user_text)
#             # Identity question fallback
#             if is_identity_question(user_text):
#                 return "I'm an assistant. Do you have a moment to discuss the alliance opportunity?"
#             # Weather/live data fallback
#             if any(k in t for k in ["weather", "temperature", "forecast", "stock", "score", "game"]):
#                 return "I'm not sure about that. But regarding the alliance opportunity, would you have a moment to discuss?"
#             # Generic fallback
#             return random.choice(fallback_responses)

#         try:
#             resp = await openai_client.chat.completions.create(
#                 model=openai_model,
#                 temperature=0.7,  # Slightly higher for more natural variation
#                 max_tokens=150,   # Keep responses short and conversational
#                 messages=[
#                     {"role": "system", "content": system_prompt},
#                     {"role": "user", "content": user_text},
#                 ],
#             )
#             content = (resp.choices[0].message.content or "").strip()
#             # Clean up any overly robotic phrases that might slip through
#             content = content.replace("As an AI", "As an assistant")
#             content = content.replace("I'm an AI", "I'm an assistant")
#             content = content.replace("I'm a language model", "I'm an assistant")
#             content = content.replace("I'm a bot", "I'm an assistant")

#             # CRITICAL: Remove any greeting that might slip through from STATE_MACHINE_PROMPT
#             # This prevents duplicate greetings during conversation
#             greeting_patterns = [
#                 "Hi. This is Merideth calling on behalf of Galaxy Realtors in Dubai.",
#                 "Hi, this is Merideth",
#                 "This is Merideth",
#                 "calling on behalf of Galaxy Realtors",
#             ]
#             for pattern in greeting_patterns:
#                 if pattern.lower() in content.lower():
#                     # Replace the greeting with a continuation phrase
#                     content = content.replace(pattern, "")
#                     content = content.replace(pattern.lower(), "")
#             content = content.strip()

#             # If content is now empty or just punctuation, use fallback
#             if not content or len(content) < 5:
#                 return random.choice(fallback_responses)

#             return content
#         except Exception as e:
#             print(f"OpenAI error: {e}")
#             return random.choice(fallback_responses)

#     async def answer_any_random_or_generic(user_text: str) -> bool:
#         if not looks_like_random_or_generic_query(user_text):
#             return False

#         # Choose the right prompt based on the question type
#         if is_identity_question(user_text):
#             system = IDENTITY_Q_SYSTEM
#         elif is_service_related(user_text):
#             system = SERVICE_Q_SYSTEM
#         else:
#             system = GENERIC_Q_SYSTEM

#         ans = await openai_answer(user_text, system)
#         await say(ans)
#         # if service-related, allow moving to booking ask later
#         if system == SERVICE_Q_SYSTEM:
#             session.userdata["state"] = "booking_ask"
#         return True

#     nc_plugin = noise_cancellation.BVC()

#     # Configure to accept audio from ALL participants (including Twilio)
#     # By default it only listens to microphone sources
#     await session.start(
#         room=ctx.room,
#         agent=ScriptedMerideth(),
#         room_input_options=RoomInputOptions(
#             noise_cancellation=nc_plugin,
#             close_on_disconnect=False,
#             # Accept audio from any participant, not just specific sources
#             participant_identity=None  # Listen to all participants
#         ),
#     )

#     # DON'T greet automatically - wait for user to speak first
#     # State is already set to "waiting_for_user" in AgentSession userdata
#     print("AGENT: State is 'waiting_for_user' - waiting for user to speak first...")

#     @session.on("agent_speech_interrupted")
#     def on_agent_interrupted(e):
#         """Handle when user interrupts the agent"""
#         print("DEBUG: Agent was interrupted by user")
#         session.userdata["was_interrupted"] = True

#     @session.on("user_input_transcribed")
#     def on_user_input(e):
#         if not getattr(e, "is_final", False):
#             return

#         raw = getattr(e, "transcript", "") or ""
#         text = clean_stt_output(raw)
#         print(f"USER STT (FINAL): '{text}'")

#         now = time.time()
#         last_text = session.userdata.get("last_text", "")
#         last_ts = session.userdata.get("last_text_ts", 0.0)

#         # Drop duplicates within 1.5 seconds (prevents repeat loops)
#         if text and text == last_text and (now - last_ts) < 1.5:
#             print("DEBUG: Dropping duplicate transcript")
#             return

#         session.userdata["last_text"] = text
#         session.userdata["last_text_ts"] = now

#         # If empty or truly junk, stay SILENT - don't ask to repeat
#         # Agent only responds when user gives a valid response
#         if not acceptable_answer(text):
#             print("DEBUG: Empty/junk input - staying silent, waiting for user")
#             return

#         session.userdata["reject_count"] = 0
#         asyncio.create_task(handle(text))

#     async def handle(user_text: str):
#         state = session.userdata.get("state", "waiting_for_user")
#         was_interrupted = session.userdata.get("was_interrupted", False)

#         print(f"DEBUG: handle() called - state='{state}', user_text='{user_text}', interrupted={was_interrupted}")

#         # INTERRUPTION ACKNOWLEDGMENT: If user interrupted, acknowledge it naturally
#         if was_interrupted and state != "waiting_for_user":
#             print("DEBUG: User interrupted - acknowledging")
#             session.userdata["was_interrupted"] = False  # Reset flag

#             # Check if it's just a simple acknowledgment (user saying "okay", "yeah", etc.)
#             simple_acks = ["okay", "ok", "yeah", "yes", "yep", "sure", "got it", "alright", "right"]
#             if normalize(user_text) in simple_acks:
#                 # User is just acknowledging - continue without extra comment
#                 print("DEBUG: Simple acknowledgment during interruption - continuing")
#                 pass
#             # Check if user is asking a clarifying question or correcting something
#             elif detect_request_repeat(user_text):
#                 # User wants us to repeat - acknowledge briefly
#                 await say("Sure.", delayed=False)
#             elif detect_correction(user_text):
#                 # User is correcting - acknowledge politely
#                 await say("Thank you for clarifying.", delayed=False)
#             elif is_identity_question(user_text) or detect_user_question_key(user_text):
#                 # User has a question - acknowledge naturally
#                 await say("Of course.", delayed=False)
#             else:
#                 # General interruption - brief acknowledgment
#                 acknowledgments = ["Got it.", "I understand.", "Okay.", "Sure."]
#                 await say(random.choice(acknowledgments), delayed=False)

#         # FIRST: Check if we're waiting for user to speak first
#         # This MUST run before any other handlers
#         # Also check greeted flag to ensure greeting only happens ONCE
#         if state == "waiting_for_user" and not session.userdata.get("greeted", False):
#             print("DEBUG: State is waiting_for_user - sending greeting")
#             # User said something - say the STATE: OPENING sentence from the prompt
#             session.userdata["greeted"] = True  # Set BEFORE saying to prevent race conditions
#             session.userdata["state"] = "opening"
#             await say("Hi, this is Merideth... how's your day going?")
#             print("DEBUG: State changed to 'opening'")
#             return
#         elif state == "waiting_for_user" and session.userdata.get("greeted", False):
#             # Already greeted, skip to opening state
#             session.userdata["state"] = "opening"
#             print("DEBUG: Already greeted, skipping to opening state")

#         # GLOBAL HANDLER: Check refusal count >= 3
#         if session.userdata.get("refusal_count", 0) >= 3:
#             await end_call(agent.REFUSALS["firm_no"])
#             return

#         # GLOBAL HANDLER: Goodbye detection
#         if is_goodbye(user_text):
#             await end_call(agent.REFUSALS["goodbye_end"])
#             return

#         # GLOBAL HANDLER: Opt-out/removal requests
#         r = refusal_type(user_text)
#         if r == "opt_out":
#             await end_call(agent.REFUSALS["opt_out"])
#             return
#         if r == "wrong_number":
#             await end_call(agent.REFUSALS["wrong_number"])
#             return
#         if r == "hangup":
#             await end_call(agent.REFUSALS["hangup"])
#             return
#         if r == "polite_end":
#             await end_call(agent.REFUSALS["polite_end"])
#             return
#         if r == "firm_no":
#             session.userdata["refusal_count"] = session.userdata.get("refusal_count", 0) + 1
#             if session.userdata["refusal_count"] >= 3:
#                 await end_call(agent.REFUSALS["firm_no"])
#                 return
#             # Try objection handling instead of immediate end
#             await say(agent.OBJECTIONS.get("not_interested", "I understand. Is there anything else I can help with?"))
#             return

#         # Scripted user Qs
#         uq = detect_user_question_key(user_text)
#         if uq and uq in agent.USER_QUESTIONS:
#             await say(agent.USER_QUESTIONS[uq])
#             return

#         # Script FAQ keys
#         qk = detect_script_query_key(user_text)
#         if qk and qk in agent.FAQ:
#             await say(agent.FAQ[qk])
#             return

#         # Objection handling
#         obj = detect_objection(user_text)
#         if obj:
#             if obj == "send_info":
#                 await say(agent.OBJECTIONS["send_info"])
#                 session.userdata["state"] = "get_email_for_info"
#                 return
#             if obj == "have_to_go":
#                 await say(agent.OBJECTIONS["have_to_go"])
#                 return
#             if obj == "maybe_later":
#                 await say(agent.OBJECTIONS["maybe_later"])
#                 session.userdata["state"] = "get_email_for_info"
#                 return
#             if obj == "call_later":
#                 # Handle callback request - only get time, not contact info
#                 await say("No worries at all. Completely understand. When might be a better time for you? Later this week or next?")
#                 return
#             if obj == "not_interested":
#                 await say(agent.OBJECTIONS["not_interested"])
#                 return
#             if obj == "no_budget":
#                 await say(agent.OBJECTIONS["no_budget"])
#                 session.userdata["state"] = "booking_ask"
#                 return
#             if obj == "already_help":
#                 await say(agent.OBJECTIONS["already_help"])
#                 session.userdata["state"] = "booking_ask"
#                 return
#             if obj == "no_time":
#                 await say(agent.OBJECTIONS["no_time"])
#                 session.userdata["state"] = "booking_ask"
#                 return
#             if obj == "dont_need":
#                 await say(agent.OBJECTIONS["dont_need"])
#                 session.userdata["state"] = "booking_ask"
#                 return
#             if obj == "price":
#                 # First time asking about price
#                 if session.userdata.get("price_asked_count", 0) == 0:
#                     await say(agent.OBJECTIONS["price_first"])
#                     session.userdata["price_asked_count"] = 1
#                 else:
#                     # Second time asking about price
#                     await say(agent.OBJECTIONS["price_second"])
#                     session.userdata["state"] = "booking_ask"
#                 return

#         # OpenAI: answer ANY random/generic query
#         answered = await answer_any_random_or_generic(user_text)
#         if answered:
#             return

#         # STATE MACHINE

#         if state == "opening":
#             # User responded to "how's your day going?" - detect mood and respond
#             mood = detect_mood(user_text)
#             response_parts = []

#             if mood in agent.MOOD_RESPONSES:
#                 response_parts.append(agent.MOOD_RESPONSES[mood])
#             else:
#                 response_parts.append("Glad to hear it.")

#             # Add main pitch
#             response_parts.append(agent.MAIN_PITCH)

#             # Combine and deliver
#             await say(" ".join(response_parts))
#             session.userdata["state"] = "qualify"
#             return

#         if state == "pitch":
#             # Pitch was already delivered, wait for user response then qualify
#             session.userdata["state"] = "qualify"
#             # Don't say anything - just wait for user to answer the question in the pitch
#             return

#         if state == "qualify":
#             # Check for interest signals first
#             if detect_interest(user_text):
#                 await say(agent.INTEREST_RESPONSE)
#                 session.userdata["state"] = "get_day_time"
#                 return

#             # Classify their response about support
#             support_type = classify_support(user_text)
#             if support_type == "self":
#                 await say(agent.QUALIFYING_PATHS["self_handling"])
#             elif support_type == "support":
#                 await say(agent.QUALIFYING_PATHS["has_support"])
#             else:
#                 await say(agent.QUALIFYING_PATHS["unsure"])
#             session.userdata["state"] = "qualifying_questions"
#             return

#         if state == "qualifying_questions":
#             # Check for interest signals
#             if detect_interest(user_text):
#                 await say(agent.INTEREST_RESPONSE)
#                 session.userdata["state"] = "booking_send_method"
#                 return

#             # Check if user wants to book
#             if any(k in normalize(user_text) for k in ["book", "schedule", "set up", "zoom", "demo", "meeting"]):
#                 await say(agent.INTEREST_RESPONSE)
#                 session.userdata["state"] = "booking_send_method"
#                 return

#             idx = session.userdata.get("qualifying_idx", 0)
#             if idx < len(agent.QUALIFYING_QUESTIONS):
#                 await say(agent.QUALIFYING_QUESTIONS[idx])
#                 session.userdata["qualifying_idx"] = idx + 1
#                 return

#             # After all qualifying questions, ask for booking
#             await say("You know what, our senior business consultant can show you exactly how this works on a quick Zoom call. Should I send the link by text or email?")
#             session.userdata["state"] = "booking_send_method"
#             return

#         if state == "booking_ask":
#             # This state handles explicit booking confirmation if needed
#             if is_yes(user_text):
#                 await say("Great! What day and time works best for you?")
#                 session.userdata["state"] = "get_day_time"
#                 return

#             # Check for send info request
#             if detect_send_info_request(user_text):
#                 await say("Absolutely. Would you prefer I send that via email?")
#                 session.userdata["state"] = "get_email_for_info"
#                 return

#             # Handle objections/refusals
#             session.userdata["refusal_count"] = session.userdata.get("refusal_count", 0) + 1
#             if session.userdata["refusal_count"] >= 3:
#                 await end_call(agent.REFUSALS["firm_no"])
#                 return

#             # Try different angle - single question, wait for response
#             await say("No worries. Would saving time or getting more leads help you more right now?")
#             session.userdata["state"] = "qualify"
#             return

#         # BOOKING FLOW: Send Method → Day/Time → Timezone → Email → Phone → Name → Confirmation

#         if state == "booking_send_method":
#             # User chose text or email - acknowledge and move to day/time
#             await say("Perfect! What day and time works best for you?")
#             session.userdata["state"] = "get_day_time"
#             return

#         if state == "get_day_time":
#             time_text = user_text.strip()
#             # Check if they suggested a non-standard time (like 2:30 or 3:15)
#             needs_rounding, suggested_time = parse_time_to_hour_only(time_text)
#             if needs_rounding:
#                 session.userdata["booking_data"]["suggested_time"] = suggested_time
#                 await say(f"How about {suggested_time} instead? Works better for our system.")
#                 session.userdata["state"] = "confirm_rounded_time"
#                 return
#             else:
#                 session.userdata["booking_data"]["day_time"] = time_text
#                 await say("Great! Let's get you scheduled. What's your timezone or location?")
#             session.userdata["state"] = "get_timezone"
#             return

#         if state == "confirm_rounded_time":
#             if is_yes(user_text):
#                 session.userdata["booking_data"]["day_time"] = session.userdata["booking_data"]["suggested_time"]
#                 await say("Great! Let's get you scheduled. What's your timezone or location?")
#                 session.userdata["state"] = "get_timezone"
#                 return
#             else:
#                 # User doesn't want rounded time - ask again
#                 await say("No problem. What time would work better for you?")
#                 session.userdata["state"] = "get_day_time"
#                 return

#         if state == "get_timezone":
#             session.userdata["booking_data"]["timezone"] = user_text.strip()
#             tz = session.userdata["booking_data"]["timezone"]
#             await say(f"Got it, that's {tz}. Right?")
#             session.userdata["state"] = "confirm_timezone"
#             return

#         if state == "confirm_timezone":
#             if is_yes(user_text):
#                 await say("Perfect! What's your best email?")
#                 session.userdata["state"] = "get_email"
#                 return
#             else:
#                 # User is correcting the timezone
#                 session.userdata["booking_data"]["timezone"] = user_text.strip()
#                 tz = session.userdata["booking_data"]["timezone"]
#                 await say(f"Got it, that's {tz}. Right?")
#                 return

#         if state == "get_email":
#             email = user_text.strip()
#             session.userdata["booking_data"]["email"] = email
#             # Spell out email character by character for confirmation
#             spelled_email = " ".join(c if c.isalnum() else f" {c} " for c in email).replace("@", " at ").replace(".", " dot ")
#             await say(f"Let me confirm... that's {spelled_email}. Right?")
#             session.userdata["state"] = "confirm_email"
#             return

#         if state == "confirm_email":
#             if is_yes(user_text):
#                 await say("And your best phone number?")
#                 session.userdata["state"] = "get_phone"
#                 return
#             else:
#                 # User is correcting the email
#                 session.userdata["booking_data"]["email"] = user_text.strip()
#                 email = session.userdata["booking_data"]["email"]
#                 spelled_email = " ".join(c if c.isalnum() else f" {c} " for c in email).replace("@", " at ").replace(".", " dot ")
#                 await say(f"Thank you for clarifying. So that's {spelled_email}. Right?")
#                 return

#         if state == "get_phone":
#             phone = user_text.strip()
#             session.userdata["booking_data"]["phone"] = phone
#             # Spell out phone digit by digit
#             spelled_phone = " ".join(c if c.isdigit() else ", " for c in phone)
#             await say(f"Let me confirm... that's {spelled_phone}. Right?")
#             session.userdata["state"] = "confirm_phone"
#             return

#         if state == "confirm_phone":
#             if is_yes(user_text):
#                 await say("Great! And your full name?")
#                 session.userdata["state"] = "get_name"
#                 return
#             else:
#                 # User is correcting the phone
#                 session.userdata["booking_data"]["phone"] = user_text.strip()
#                 phone = session.userdata["booking_data"]["phone"]
#                 spelled_phone = " ".join(c if c.isdigit() else ", " for c in phone)
#                 await say(f"Thank you for the correction. So that's {spelled_phone}. Right?")
#                 return

#         if state == "get_name":
#             session.userdata["booking_data"]["name"] = user_text.strip()
#             name = session.userdata["booking_data"]["name"]
#             await say(f"Perfect, {name}. Right?")
#             session.userdata["state"] = "confirm_name"
#             return

#         if state == "confirm_name":
#             if is_yes(user_text):
#             # Final confirmation
#             bd = session.userdata["booking_data"]
#                 await say(f"Excellent! You're all set for {bd.get('day_time')} {bd.get('timezone')}. You'll get the confirmation shortly. Looking forward to our meeting!")
#             session.userdata["state"] = "final_questions"
#             return
#             else:
#                 # User is correcting the name
#                 session.userdata["booking_data"]["name"] = user_text.strip()
#                 name = session.userdata["booking_data"]["name"]
#                 await say(f"Thank you. So that's {name}. Right?")
#                 return

#         if state == "final_questions":
#             if is_yes(user_text) or any(k in normalize(user_text) for k in ["question", "ask"]):
#                 # User has a question - use OpenAI to answer
#                 answered = await answer_any_random_or_generic(user_text)
#                 if answered:
#                     return
#                 await say("Of course, what would you like to know?")
#                 return
#             else:
#                 # No questions, close the call
#                 await say("Is there anything else I can help with before we wrap up?")
#                 session.userdata["state"] = "pre_closing"
#                 return

#         if state == "pre_closing":
#             if is_yes(user_text) or any(k in normalize(user_text) for k in ["question", "ask", "yes"]):
#                 # User has another question
#                 answered = await answer_any_random_or_generic(user_text)
#                 if answered:
#                     await say("Anything else before we go?")
#                     return
#                 await say("Of course, what would you like to know?")
#                 return
#             else:
#                 # Close the call
#                 await say("Thank you so much for your time! talk soon! Goodbye!")
#                 session.userdata["state"] = "closing"
#                 return

#         if state == "closing":
#             await end_call("Thank you so much for your time! talk soon! Goodbye!")
#             return

#         # Handle send info instead of booking
#         if state == "get_email_for_info":
#             session.userdata["booking_data"]["email"] = user_text.strip()
#             email = session.userdata["booking_data"]["email"]
#             await say(f"Perfect. Just to confirm, that's {email}. Is that correct?")
#             session.userdata["state"] = "confirm_email_for_info"
#             return

#         if state == "confirm_email_for_info":
#             if is_yes(user_text):
#                 email = session.userdata["booking_data"].get("email", "")
#                 await say(f"Great. I'll send over the information to {email} shortly. If you have any questions afterward, feel free to reach out. Have a great day!")
#                 session.userdata["state"] = "closing"
#                 return
#             else:
#                 # User is correcting the email
#                 session.userdata["booking_data"]["email"] = user_text.strip()
#                 email = session.userdata["booking_data"]["email"]
#                 await say(f"Thank you for clarifying. So that's {email}. Is that correct?")
#                 return

#         # Fallback
#         await say("Got it. Are you looking to save time, or get more leads right now?")
#         session.userdata["state"] = "qualify"


# # -----------------------------------------------------------------------------
# # Run LiveKit worker
# # -----------------------------------------------------------------------------
# if __name__ == "__main__":
#     logger.info("Starting NSOL BPO LiveKit Agent - Merideth")
#     logger.info(f"Connecting to LiveKit: {settings.LIVEKIT_URL}")

#     # Run the LiveKit agent worker
#     # Usage: python main.py dev (for development with auto-reload)
#     #        python main.py start (for production)
#     #
#     # CONCURRENCY SETTINGS:
#     # - num_idle_processes: Number of worker processes ready to accept calls (default: 1)
#     # - Each process handles 1 call at a time for voice agents
#     # - To handle 10 concurrent calls, set num_idle_processes=10
#     # - For batch calling, run multiple instances or increase num_idle_processes
#     #
#     worker_options = agents.WorkerOptions(
#         entrypoint_fnc=entrypoint,
#         num_idle_processes=3,  # Ready to handle 3 concurrent calls (adjust as needed)
#     )
#     agents.cli.run_app(worker_options)






















#llm agent.
# NSOL BPO Voice AI Agent - Merideth
# LiveKit Agent with ElevenLabs STT/TTS and OpenAI fallback

import asyncio
import os
import random
import re
import time
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import deepgram, elevenlabs, openai as lk_openai, noise_cancellation, silero

from openai import AsyncOpenAI

from config.settings import require_livekit_credentials, settings
from utils.logger import setup_logging
from utils.twilio_service import TwilioOutboundService, TwilioMediaStreamHandler

# -----------------------------------------------------------------------------
# Setup
# -----------------------------------------------------------------------------
logger = setup_logging()
load_dotenv(".env")

# -----------------------------------------------------------------------------
# STATE MACHINE PROMPT - Merideth from NSOL BPO
# -----------------------------------------------------------------------------
STATE_MACHINE_PROMPT = """
You are Merideth, a professional business development representative from NSOL BPO (EN-soul BEE-PEE-OH).
Goal: Book qualified meetings with realtors and business owners for NSOL BPO's virtual assistant services.

Mission: Help busy professionals reclaim their time through intelligent virtual assistant services combining skilled professionals with AI automation for admin tasks, cold calling, lead follow-ups, and social media management.

HARD CONSTRAINTS
NEVER interrupt the user while they are speaking.
NEVER say the words "pause," "wait for response," or "hold on" out loud.
NEVER end the conversation unless the customer clearly says goodbye or explicitly refuses three times.
NEVER list multiple time slot options—always ask for their preference first.
NEVER book meetings at non-standard times (like 2:30 or 3:15)—only book on the hour: 1:00, 2:00, 3:00, etc.
NEVER ask for email, phone, or name during callback requests—only date and time.
NEVER use robotic phrases like "As an AI," "I'm just a system," or "I don't have access to."

DO NOT make pricing commitments during the call—defer to the Zoom meeting.
DO NOT end calls abruptly—always give them a chance to ask questions.
DO NOT sound scripted—speak naturally with warmth and professionalism.

SILENCE & RESPONSE HANDLING
After asking ANY question:
1. STOP SPEAKING immediately
2. Wait for customer's response
3. Let natural silence exist (up to 3 seconds)
4. [If no response after 3 seconds → prompt gently with "Are you still there?"]
5. Listen to their COMPLETE response before continuing

(Use a calm, patient tone. Never rush through silence.)

OPENING
(Use warm, friendly energy—smile in your voice.)

"Hi, this is Merideth... how's your day going?"
...

[Match their mood with appropriate response:]

IF tired/stressed: "I hear you. I'll keep this super quick... just two minutes."

IF busy: "Got it. Two minutes max, I promise."

IF sick: "Oh no, I'm sorry to hear that. I'll keep this short... two minutes."

IF positive: "That's amazing! Let me make it even better."

IF neutral: "Glad to hear it."

IF they ask about YOU (e.g., "How are you?" or "What's up?"): [Pick ONE brief response, then bridge immediately:] "I'm doing great, thanks for asking! So, I'm reaching out because..." "I'm good, appreciate you asking! Quick question for you..." "Doing well, thank you! Listen, I wanted to talk to you about..."

...

Main Pitch: "I'm calling from NSOL BPO. We help realtors and business owners get their time back by handling cold calling, lead follow-ups, and social media... using a combination of skilled professionals and AI automation. Let me ask you... are you handling all those admin tasks yourself, or do you have some support?"
...

QUALIFYING PATHS
PATH 1: If Handling Themselves
"Got it. Can I ask... what's eating up most of your time right now?"
...

PATH 2: If They Have Support
"That's great! Most agents still have some gaps though. What tasks are you still managing yourself?"
...

PATH 3: If They're Unsure
"Fair enough. What would make the biggest difference for you right now... more time or more leads?"
...

Key Qualifying Questions
(Ask naturally based on conversation flow—do NOT rapid-fire these.)

"How many hours per week would you say you're spending on backend admin tasks?"
"How are you currently managing lead follow-up?"
"Are you turning down opportunities because you're swamped?"
"If you had twenty extra hours per week, what would you focus on?"
"How satisfied are you with your current social media results?"

[After EACH question → wait for their FULL response before continuing]

OBJECTION HANDLING
(Use empathetic, non-defensive tone. Acknowledge their concern first.)

"I'm not interested"
"I understand. What's holding you back... timing, or just not seeing the value in freeing up time?"
...

IF timing issue: "Absolutely. When would be better... this week or next?"

IF firm no: "No worries. What's your biggest business challenge right now?"

"No budget / Can't afford it"
"I totally get that. The presentation is free, and most agents find the time saved actually pays for itself. Would you be open to just seeing if it fits?"
...

"Already have help"
"That's awesome. You know, most of our clients had support too. Usually there are still gaps. Would you be open to seeing how this works?"
...

"No time"
"I hear you... that's exactly why this works! Fifteen minutes around your schedule to potentially free up hours. When this week looks good?"
...

"Don't need help"
"I understand. Most agents felt the same way until they saw the time freed up for closing deals. Would you take a quick look?"
...

"How much does it cost?" (First Ask)
"Great question. Every agent's different, so the presentation shows your specific investment. Which services interest you most?"
...

"How much does it cost?" (Second Ask)
"Our AI agents are cost-effective. Pricing varies based on your needs, but most agents see ROI fast since you only pay for results... no overhead from multiple hires. I can give you details during a quick Zoom call. When works for you?"
...

"I have to go"
"I totally understand. Before you go though... if I could show you how to get back twenty extra hours per week for closing deals, would that be worth fifteen minutes?"
...

"Maybe later / I'll think about it"
"I appreciate that. Here's the thing... most agents put it off because they're so busy. What if I send info to your email and follow up when you're free? Sound fair?"
...

"Just send me information"
"Of course I can send details. However, I highly recommend a quick fifteen-minute Zoom... I can walk you through everything live and answer questions. What time works best?"
...

INTEREST SIGNALS
IF user says:
"Tell me more"
"That sounds interesting"
"We could use help"
"How does this work?"
[OR asks detailed questions about services]

THEN respond:
"You know what, our senior business consultant can show you exactly how this works on a quick Zoom call. Should I send the link by text or email?"
...

MEETING BOOKING PROCESS
STEP 1: Get Date & Time FIRST
"Perfect! What day and time works best for you?"
...

[If they suggest non-standard time like 2:30 or 3:15:]
"How about [nearest hour]:00 instead? Works better for our system."

STEP 2: Collect Information (ONE AT A TIME—never rush)

A. Get Timezone/Location First
"Great! Let's get you scheduled. What's your timezone or location?"
...
"Got it, that's [timezone]. Right?"
...

B. Get Email Second
"Perfect! What's your best email?"
...
"Let me confirm... that's [spell it out slowly: J-O-H-N dot S-M-I-T-H at G-M-A-I-L dot com]. Right?"
...

C. Get Phone Number Third
"And your best phone number?"
...
"Let me confirm... that's [repeat digit by digit: 5-5-5, 1-2-3, 4-5-6-7]. Right?"
...

D. Get Full Name Last
"Great! And your full name?"
...
"Perfect, [repeat name]. Right?"
...

STEP 3: Confirm Booking
(Use enthusiastic, confident tone.)

"Excellent! You're all set for [day] at [time] [timezone]. You'll get the confirmation shortly. Looking forward to our meeting!"

FREQUENTLY ASKED QUESTIONS
"What services do you provide?" → "We handle cold calling, client follow-ups, and social media marketing... things that save you time. What takes up most of your time now?" ...

"Where are you located?" → "We're based in Singapore, Dubai, and Pakistan... connected through these locations to keep costs low and service reliable."

"What's in the meeting?" → "We share how we've helped other agents, review what fits your needs, and show real time-saving examples. It's totally interactive and tailored to you."

"Do you offer a free trial?" → "You can test our services with real work. We explain the full process during the Zoom."

"Do you work with teams or individuals?" → "Both! We scale from solo agents to entire broker teams. What's your current setup like?" ...

"How fast can we start?" → "Usually within a few days. The meeting covers exact timelines tailored for you."

"Where did you get my number?" → "I understand. We get referrals from real estate directories, brokers, and other agents. If you prefer, I can remove you from our list after this call." ...

"I didn't ask for help" → "You're right. Look, we reached out because we help agents focus on closing deals. Would you be open to hearing how it works?" ...

CALLBACK HANDLING
IF they request a callback:

"Absolutely! When works better... later today or tomorrow?"
...

[Only ask for date and time—DO NOT ask for email, phone, or name unless they agree to book a meeting]

CLOSING SCRIPT
(Use warm, appreciative tone. End on a high note.)

"Excellent! You're all set for [day] at [time]. You'll get a confirmation shortly with all the details. I'm looking forward to helping you crush it. Is there anything else I can help with before we wrap up?"
...

"Thank you so much for your time! talk soon! Goodbye!"

DELIVERY & TONE GUIDANCE
(Professional yet warm—sound like a knowledgeable partner, not a pushy salesperson.)

Energy Adjustments:
• Emphasize benefits: TIME, GROW, FREE, RESULTS (slightly increase energy)
• Handle objections: calm, empathetic, non-defensive (slower pace)
• Close booking: confident, enthusiastic (smile in voice)

Speech Patterns:
• Short sentences: 1-2 lines maximum
• Natural fillers sparingly: "you know," "I mean," "look," "listen"
• Vary pace: speed up when enthusiastic, slow down for key points
• Mirror customer's energy level appropriately

Punctuation for Pacing:
• Use ... for natural pauses
• Use , for brief pauses
• Use — for topic shifts or interruptions
• Use . for full stops

Cultural Sensitivity:
• Clear, simple English for global understanding
• Moderate pace (especially with non-native speakers)
• Avoid slang or region-specific idioms
• Be patient and respectful of all backgrounds

PERSISTENCE STRATEGY
Numbered Priority:

1. Make up to 3 attempts to schedule using different value angles
2. After 3 attempts → gracefully end conversation
3. Always stay helpful and positive
4. Leave door open for future contact

IF first attempt fails: Focus on TIME savings

IF second attempt fails: Focus on REVENUE growth

IF third attempt fails: (Use respectful, appreciative tone.) "I appreciate your time today. If anything changes and you'd like to explore this, feel free to reach out. Wishing you continued success!"

PRIMARY GOAL REMINDER
REMEMBER:
Your primary goal is to book a qualified meeting.
If unsure what to do, guide toward booking.
Stay helpful, warm, and focused on their time-saving needs.

"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    global twilio_service
    logger.info("Starting NSOL BPO Cold Calling Assistant - Merideth")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Initialize Twilio service
    try:
        twilio_service = TwilioOutboundService()
        logger.info("Twilio service initialized successfully")
    except ValueError as e:
        logger.warning(f"Twilio service not available: {e}")

    yield
    logger.info("Shutting down")


app = FastAPI(
    title="NSOL BPO Cold Calling Assistant - Merideth",
    description="AI-powered cold calling for virtual assistant services - NSOL BPO",
    version="1.0.0",
    lifespan=lifespan,
)

# Initialize Twilio service (will be set after app startup)
twilio_service: Optional[TwilioOutboundService] = None


@app.get("/")
async def root():
    return {"message": "NSOL BPO Cold Calling API - Merideth", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": __import__("datetime").datetime.utcnow().isoformat()}


@app.get("/metrics")
async def metrics():
    return {"metrics": "Prometheus metrics would be here"}


# -----------------------------------------------------------------------------
# Pydantic Models for API
# -----------------------------------------------------------------------------
class OutboundCallRequest(BaseModel):
    """Request model for placing outbound calls"""
    to_number: str = Field(..., description="Phone number to call in E.164 format (e.g., +14155551234)")
    room_name: Optional[str] = Field(None, description="Optional LiveKit room name (auto-generated if not provided)")
    webhook_base_url: str = Field(..., description="Your public base URL (e.g., https://your-domain.com)")

    class Config:
        json_schema_extra = {
            "example": {
                "to_number": "+14155551234",
                "room_name": "call-123",
                "webhook_base_url": "https://your-domain.ngrok.io"
            }
        }


class OutboundCallResponse(BaseModel):
    """Response model for outbound call requests"""
    success: bool
    call_sid: Optional[str] = None
    status: Optional[str] = None
    room_name: Optional[str] = None
    websocket_url: Optional[str] = None
    error: Optional[str] = None


# -----------------------------------------------------------------------------
# Outbound Calling API Endpoints
# -----------------------------------------------------------------------------
@app.post("/api/outbound/call", response_model=OutboundCallResponse)
async def place_outbound_call(request: OutboundCallRequest):
    """
    Place an outbound call using Twilio Programmable Voice + Media Streams
    """
    if not twilio_service:
        raise HTTPException(
            status_code=500,
            detail="Twilio service not configured. Please set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER"
        )

    try:
        room_name = request.room_name or f"call-{int(time.time())}"

        webhook_url = f"{request.webhook_base_url.rstrip('/')}/twilio/webhook?room_name={room_name}"
        status_callback_url = f"{request.webhook_base_url.rstrip('/')}/twilio/status"

        result = twilio_service.place_call(
            to_number=request.to_number,
            webhook_url=webhook_url,
            status_callback_url=status_callback_url
        )

        if result["success"]:
            websocket_url = (
                f"wss://{request.webhook_base_url.replace('https://', '').replace('http://', '').rstrip('/')}/twilio/media"
            )
            return OutboundCallResponse(
                success=True,
                call_sid=result["call_sid"],
                status=result["status"],
                room_name=room_name,
                websocket_url=websocket_url
            )
        return OutboundCallResponse(success=False, error=result.get("error", "Unknown error"))

    except Exception as e:
        logger.error(f"Error in place_outbound_call: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/twilio/webhook")
async def twilio_webhook(request: Request):
    """
    Webhook endpoint for Twilio to get TwiML instructions
    """
    params = request.query_params
    room_name = params.get("room_name", f"call-{int(time.time())}")

    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")

    logger.info(f"Twilio webhook called for CallSID: {call_sid}, Room: {room_name}")

    host = request.headers.get("host", "localhost:8000")
    protocol = "wss" if "https" in str(request.url) or "ngrok" in host else "ws"
    websocket_url = f"{protocol}://{host}/twilio/media"

    twiml = TwilioOutboundService.generate_twiml(
        websocket_url=websocket_url,
        call_sid=call_sid,
        room_name=room_name
    )

    return Response(content=twiml, media_type="application/xml")


@app.post("/twilio/status")
async def twilio_status_callback(request: Request):
    """
    Webhook endpoint for Twilio call status updates
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")

    logger.info(f"Call status update - SID: {call_sid}, Status: {call_status}")

    if twilio_service:
        twilio_service.update_call_status(call_sid, call_status)

    return {"status": "ok"}


@app.websocket("/twilio/media")
async def twilio_media_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams
    """
    await websocket.accept()
    logger.info("Twilio Media Stream WebSocket connection established")

    handler = TwilioMediaStreamHandler(websocket, "default-room")

    try:
        await handler.handle_connection()
    except WebSocketDisconnect:
        logger.info("Twilio Media Stream WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in Media Stream WebSocket: {str(e)}")
    finally:
        await handler.cleanup()


# -----------------------------------------------------------------------------
# NSOL BPO SCRIPTED AGENT - MERIDETH
# -----------------------------------------------------------------------------
class NSOLBPOAgent:
    GREETINGS = ["Hi, this is Merideth... how's your day going?"]

    MOOD_RESPONSES = {
        "tired": "I hear you. I'll keep this super quick... just two minutes.",
        "stressed": "I hear you. I'll keep this super quick... just two minutes.",
        "busy": "Got it. Two minutes max, I promise.",
        "sick": "Oh no, I'm sorry to hear that. I'll keep this short... two minutes.",
        "positive": "That's amazing! Let me make it even better.",
        "neutral": "Glad to hear it.",
    }

    HOW_ARE_YOU_RESPONSES = [
        "I'm doing great, thanks for asking! So, I'm reaching out because...",
        "I'm good, appreciate you asking! Quick question for you...",
        "Doing well, thank you! Listen, I wanted to talk to you about...",
    ]

    WHO_IS_THIS = "This is Merideth calling from NSOL BPO. Do you have a brief moment to speak?"

    MAIN_PITCH = (
        "I'm calling from NSOL BPO. We help realtors and business owners get their time back by handling "
        "cold calling, lead follow-ups, and social media... using a combination of skilled professionals "
        "and AI automation. Let me ask you... are you handling all those admin tasks yourself, "
        "or do you have some support?"
    )

    QUALIFYING_PATHS = {
        "self_handling": "Got it. Can I ask... what's eating up most of your time right now?",
        "has_support": "That's great! Most agents still have some gaps though. What tasks are you still managing yourself?",
        "unsure": "Fair enough. What would make the biggest difference for you right now... more time or more leads?",
    }

    QUALIFYING_QUESTIONS = [
        "How many hours per week would you say you're spending on backend admin tasks?",
        "How are you currently managing lead follow-up?",
        "Are you turning down opportunities because you're swamped?",
        "If you had twenty extra hours per week, what would you focus on?",
        "How satisfied are you with your current social media results?",
    ]

    INTEREST_RESPONSE = (
        "You know what, our senior business consultant can show you exactly how this works on a quick Zoom call. "
        "Should I send the link by text or email?"
    )

    BOOKING_FLOW = {
        "ask_day_time": "Perfect! What day and time works best for you?",
        "round_time": "How about {hour}:00 instead? Works better for our system.",
        "ask_timezone": "Great! Let's get you scheduled. What's your timezone or location?",
        "confirm_timezone": "Got it, that's {timezone}. Right?",
        "ask_email": "Perfect! What's your best email?",
        "confirm_email": "Let me confirm... that's {email}. Right?",
        "ask_phone": "And your best phone number?",
        "confirm_phone": "Let me confirm... that's {phone}. Right?",
        "ask_name": "Great! And your full name?",
        "confirm_name": "Perfect, {name}. Right?",
        "final_confirmation": (
            "Excellent! You're all set for {day_time} at {time} {timezone}. "
            "You'll get the confirmation shortly. Looking forward to our meeting!"
        ),
        "closing": "Thank you so much for your time! talk soon! Goodbye!",
    }

    OBJECTIONS = {
        "not_interested": "I understand. What's holding you back... timing, or just not seeing the value in freeing up time?",
        "timing_issue": "Absolutely. When would be better... this week or next?",
        "firm_no": "No worries. What's your biggest business challenge right now?",
        "no_budget": "I totally get that. The presentation is free, and most agents find the time saved actually pays for itself. Would you be open to just seeing if it fits?",
        "already_help": "That's awesome. You know, most of our clients had support too. Usually there are still gaps. Would you be open to seeing how this works?",
        "no_time": "I hear you... that's exactly why this works! Fifteen minutes around your schedule to potentially free up hours. When this week looks good?",
        "dont_need": "I understand. Most agents felt the same way until they saw the time freed up for closing deals. Would you take a quick look?",
        "price_first": "Great question. Every agent's different, so the presentation shows your specific investment. Which services interest you most?",
        "price_second": "Our AI agents are cost-effective. Pricing varies based on your needs, but most agents see ROI fast since you only pay for results... no overhead from multiple hires. I can give you details during a quick Zoom call. When works for you?",
        "have_to_go": "I totally understand. Before you go though... if I could show you how to get back twenty extra hours per week for closing deals, would that be worth fifteen minutes?",
        "maybe_later": "I appreciate that. Here's the thing... most agents put it off because they're so busy. What if I send info to your email and follow up when you're free? Sound fair?",
        "send_info": "Of course I can send details. However, I highly recommend a quick fifteen-minute Zoom... I can walk you through everything live and answer questions. What time works best?",
    }

    FAQ = {
        "what_services": "We handle cold calling, client follow-ups, and social media marketing... things that save you time. What takes up most of your time now?",
        "location": "We're based in Singapore, Dubai, and Pakistan... connected through these locations to keep costs low and service reliable.",
        "meeting_content": "We share how we've helped other agents, review what fits your needs, and show real time-saving examples. It's totally interactive and tailored to you.",
        "free_trial": "You can test our services with real work. We explain the full process during the Zoom.",
        "teams_or_individuals": "Both! We scale from solo agents to entire broker teams. What's your current setup like?",
        "start_time": "Usually within a few days. The meeting covers exact timelines tailored for you.",
        "number_source": "I understand. We get referrals from real estate directories, brokers, and other agents. If you prefer, I can remove you from our list after this call.",
        "didnt_ask": "You're right. Look, we reached out because we help agents focus on closing deals. Would you be open to hearing how it works?",
        "remove_confirm": "No problem at all. I'll take your number off the list right now. Sorry to have bothered you.",
    }

    USER_QUESTIONS = {
        "who_are_you": "This is Merideth calling from NSOL BPO. Do you have a brief moment to speak?",
        "from_where": "I'm calling from NSOL BPO. We help realtors and business owners get their time back through virtual assistant services.",
        "how_are_you": random.choice([
            "I'm doing great, thanks for asking! So, I'm reaching out because...",
            "I'm good, appreciate you asking! Quick question for you...",
            "Doing well, thank you! Listen, I wanted to talk to you about...",
        ]),
        "why_are_you_calling": (
            "I'm calling from NSOL BPO. We help realtors and business owners get their time back by handling "
            "cold calling, lead follow-ups, and social media... using a combination of skilled professionals "
            "and AI automation. Let me ask you... are you handling all those admin tasks yourself, "
            "or do you have some support?"
        ),
        "human_or_robot": "I'm an assistant. Do you have a moment to discuss how we can help save you time?",
        "come_again": "No problem. Let me repeat that.",
        "still_there": "Yes, I'm here. Sorry about that.",
        "clarify": "Could you clarify your question? I want to make sure I understand correctly.",
    }

    REFUSALS = {
        "opt_out": "Absolutely, no problem. I'm adding your number to our Do Not Call list right now. You won't hear from us again. Sorry for the inconvenience. Take care!",
        "firm_no": "Alright, no worries at all. I appreciate your honesty. Have a great rest of your day!",
        "hangup": "Okay, got it. Take care!",
        "wrong_number": "Oh, my apologies! I'll remove this number right away. Sorry about that!",
        "polite_end": "Alright, thanks for your time! Take care now.",
        "goodbye_end": "Thank you so much for your time. I really appreciate the conversation. Have a great day ahead!",
        "send_info_end": "Great. I'll send over the information to your email shortly. If you have any questions afterward, feel free to reach out. Have a great day!",
    }


# -----------------------------------------------------------------------------
# OpenAI prompts (uses STATE_MACHINE_PROMPT for context)
# -----------------------------------------------------------------------------
HUMAN_VOICE_RULES = """
CRITICAL RULES FOR SOUNDING NATURAL:
1. If asked "Are you a robot/AI/human?" - respond simply: "I'm an assistant"
2. NEVER use overly robotic phrases like "I'm programmed to", "My training data", "I was created to"
3. Use natural filler words occasionally: "you know", "honestly", "actually", "I mean"
4. Use contractions: "I'm", "you're", "that's", "don't", "won't", "can't"
5. Be conversational, warm, and friendly - like talking to a professional colleague
6. Keep responses SHORT - 1-3 sentences max. People don't read long responses on calls.
7. Add slight imperfections - real humans don't speak perfectly
8. Mirror the user's energy and tone
9. Use casual acknowledgments: "Absolutely", "Of course", "I understand", "That's fair"
10. Stay focused on helping with the alliance opportunity
"""

SERVICE_Q_SYSTEM = f"""
{STATE_MACHINE_PROMPT}

{HUMAN_VOICE_RULES}

CONTEXT: The user asked a question about NSOL BPO services, pricing, or how the virtual assistant services work.

YOUR TASK:
- Answer their question naturally and conversationally (2-4 sentences)
- Sound like a real person on a phone call, not a script
- Be helpful and informative - if user wants to learn more, provide details
- After answering 2-3 questions, gently suggest: "These are great questions. The Zoom briefing would let us dive even deeper. What time works best for you?"
- If user keeps asking, keep answering naturally - don't force the booking
""".strip()

GENERIC_Q_SYSTEM = f"""
{STATE_MACHINE_PROMPT}

{HUMAN_VOICE_RULES}

CONTEXT: The user asked a random or generic question NOT directly about NSOL BPO or virtual assistant services (weather, sports, news, personal questions, small talk, etc.)

YOUR TASK:
- Answer briefly and naturally like a professional would
- Keep it SHORT - 1-2 sentences max
- If you genuinely don't know something, be honest: "I'm not sure about that one"
- Engage in light small talk if appropriate (builds rapport)
- After 1-2 exchanges of small talk, naturally transition: "So, regarding how we can help save you time, do you have a moment to discuss?"
- Don't be robotic - some brief rapport building is good
""".strip()

IDENTITY_Q_SYSTEM = f"""
{STATE_MACHINE_PROMPT}

{HUMAN_VOICE_RULES}

CONTEXT: The user is asking if you're a robot, AI, or human.

YOUR TASK:
- Respond simply and honestly: "I'm an assistant"
- Then redirect to the conversation
- Sound professional and composed
- Keep it brief and move forward
""".strip()


# -----------------------------------------------------------------------------
# Utility functions
# -----------------------------------------------------------------------------
def normalize(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text.strip()).lower()
    text = re.sub(r"[^\w\s\?]", "", text)
    return text


def clean_stt_output(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\[.*?\]|\(.*?\)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def acceptable_answer(text: str) -> bool:
    if not text:
        return False
    alpha = sum(ch.isalpha() for ch in text)
    if alpha >= 2:
        return True
    t = normalize(text)
    acceptable_short = {
        "ok", "okay", "yes", "no", "yep", "yeah", "yea", "nope", "nah",
        "hi", "hey", "yo", "sup", "hm", "mm", "uh", "ah", "oh",
        "hello", "hola", "bye", "k", "ya", "ye"
    }
    return t in acceptable_short


def _word_count(text: str) -> int:
    if not text:
        return 0
    return len(text.split())


def is_yes(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in [
        "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "alright",
        "sounds good", "absolutely", "why not", "lets do it", "let's do it",
        "go ahead", "of course", "definitely", "for sure", "im interested",
        "i'm interested", "tell me more", "id like", "i'd like"
    ])


def is_goodbye(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in [
        "bye", "goodbye", "good bye", "thanks bye", "see you", "talk later",
        "have a good day", "have a great day", "take care", "gotta go",
        "have to go", "got to go", "need to go", "talk soon"
    ])


def classify_support(text: str) -> str:
    t = normalize(text)
    if any(k in t for k in [
        "myself", "by myself", "just me", "me alone", "alone", "i do", "i handle",
        "no support", "no help", "myself only", "on my own", "do it myself",
        "handle it myself", "no one", "nobody", "solo"
    ]):
        return "self"
    if any(k in t for k in [
        "assistant", "team", "support", "staff", "admin", "va", "virtual assistant",
        "employee", "someone", "we have", "i have help", "we have help",
        "person", "helper", "partner", "colleague"
    ]):
        return "support"
    return "unclear"


def detect_interest(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in [
        "tell me more", "interested", "how does it work", "how does that work",
        "sounds interesting", "sounds good", "want to learn", "want to know",
        "id like to know", "i'd like to know", "curious", "more details",
        "explain more", "what else", "go on", "continue"
    ])


def detect_mood(text: str) -> str:
    t = normalize(text)
    if any(k in t for k in ["busy", "swamped", "hectic", "crazy", "lot going on"]):
        return "busy"
    if any(k in t for k in ["tired", "exhausted", "long day"]):
        return "tired"
    if any(k in t for k in ["stressed", "stressful", "overwhelming"]):
        return "stressed"
    if any(k in t for k in ["sick", "not feeling well", "under the weather"]):
        return "sick"
    if any(k in t for k in ["great", "good", "awesome", "fantastic", "wonderful", "amazing", "excellent"]):
        return "positive"
    return "neutral"


def parse_time_to_hour_only(text: str) -> tuple[bool, str]:
    t = text.lower().strip()
    time_pattern = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)?", t, re.I)
    if time_pattern:
        hour = int(time_pattern.group(1))
        minutes = int(time_pattern.group(2))
        period = time_pattern.group(3) or ""
        if minutes != 0:
            if minutes >= 30:
                hour += 1
            if hour > 12:
                hour = hour - 12
                if not period:
                    period = "pm"
            suggested = f"{hour}:00 {period}".strip()
            return True, suggested
    return False, text


def is_identity_question(text: str) -> bool:
    t = normalize(text)
    identity_keywords = [
        "are you human", "are you a human", "are you robot", "are you a robot",
        "human or robot", "are you ai", "are you an ai", "are you artificial",
        "are you real", "are you a real person", "real person", "talking to a bot",
        "talking to ai", "is this ai", "is this a bot", "is this automated",
        "am i talking to a robot", "am i talking to ai", "am i talking to a computer",
        "are you a machine", "are you automated", "are you a program", "are you software",
        "bot or human", "machine or human", "ai or human", "chatbot", "voice bot",
        "are you alive", "do you have feelings", "are you sentient"
    ]
    return any(k in t for k in identity_keywords)


def refusal_type(text: str) -> str | None:
    t = normalize(text)
    if any(k in t for k in [
        "dont call me again", "don't call me again", "remove my number", "remove me",
        "take me off", "stop calling", "unsubscribe", "do not call", "dont call", "don't call",
        "do not contact", "dont contact", "don't contact",
        "dnc", "dnc list", "do not call list", "put me on dnc", "add me to dnc",
        "put my number on", "add my number to", "blacklist", "block my number",
        "never call", "dont ever call", "don't ever call", "no more calls",
    ]):
        return "opt_out"
    if any(k in t for k in ["wrong number", "wrong person", "not me"]):
        return "wrong_number"
    if any(k in t for k in ["hang up", "hangup", "stop", "leave me alone", "go away"]):
        return "hangup"
    if any(k in t for k in ["i dont want", "i don't want", "not interested", "i dont like", "i don't like"]):
        return "firm_no"
    if t.strip() == "no":
        return "firm_no"
    if any(k in t for k in ["thank you", "thanks"]):
        short = _word_count(text) <= 3
        refusal_context = any(k in t for k in ["no", "not interested", "dont", "don't", "stop"])
        if short or refusal_context:
            return "polite_end"
    return None


def detect_objection(text: str) -> str | None:
    t = normalize(text)
    if any(k in t for k in ["send me info", "send info", "just email", "send email", "email me", "send me your email", "send details"]):
        return "send_info"
    if any(k in t for k in ["call later", "talk later", "call me back", "call back", "not a good time", "better time"]):
        return "call_later"
    if any(k in t for k in ["have to go", "gotta go", "need to go", "must go"]):
        return "have_to_go"
    if any(k in t for k in ["maybe later", "think about it", "let me think", "ill think", "i'll think"]):
        return "maybe_later"
    if t in {"not interested", "im not interested", "i'm not interested"}:
        return "not_interested"
    if any(k in t for k in ["not interested", "no thanks"]):
        return "not_interested"
    if any(k in t for k in ["no budget", "too expensive", "cant afford", "can't afford", "dont have budget", "don't have budget", "no money"]):
        return "no_budget"
    if any(k in t for k in ["already have", "have help", "have support", "have someone", "have assistant", "have va"]):
        return "already_help"
    if any(k in t for k in ["no time", "too busy", "don't have time", "dont have time", "im busy", "i'm busy", "swamped"]):
        return "no_time"
    if any(k in t for k in ["dont need help", "don't need help", "dont need", "don't need", "doing fine", "doing just fine"]):
        return "dont_need"
    if any(k in t for k in ["how much", "price", "cost", "pricing", "fees", "pay upfront", "whats the cost", "what's the cost"]):
        return "price"
    return None


def detect_request_repeat(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in [
        "come again", "sorry what", "repeat that", "say that again", "pardon",
        "what did you say", "didnt catch", "didn't catch", "can you repeat",
        "could you repeat", "say again", "one more time"
    ])


def detect_correction(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in [
        "no thats wrong", "no that's wrong", "thats not correct", "that's not correct",
        "no its", "no it's", "actually its", "actually it's", "wrong", "incorrect",
        "let me spell", "i'll spell", "the spelling is"
    ])


def detect_send_info_request(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in [
        "send me info", "send information", "just email", "email me instead",
        "send me your email", "give me your email", "send details",
        "can you send", "could you send", "ill look into it", "i'll look into it"
    ])


def detect_user_question_key(text: str) -> str | None:
    t = normalize(text)
    if any(k in t for k in ["who are you", "whats your name", "who is this", "whos this", "who's this"]):
        return "who_are_you"
    if any(k in t for k in ["from where", "where are you from", "where you calling from"]):
        return "from_where"
    if any(k in t for k in ["how are you", "how you doing", "hows your day"]):
        return "how_are_you"
    if any(k in t for k in ["why are you calling", "reason for calling", "what is this about", "what do you want"]):
        return "why_are_you_calling"
    if any(k in t for k in ["come again", "sorry what", "repeat that", "say again", "pardon"]):
        return "come_again"
    if any(k in t for k in ["are you there", "hello", "you there"]) and len(t) < 20:
        return "still_there"
    if any(k in t for k in ["could you clarify", "what do you mean", "clarify"]):
        return "clarify"
    if is_identity_question(text):
        return "human_or_robot"
    return None


def detect_script_query_key(text: str) -> str | None:
    t = normalize(text)
    if any(k in t for k in ["what services", "what do you do", "what do you provide", "what do you offer"]):
        return "what_services"
    if any(k in t for k in ["where are you", "location", "based in", "where located"]):
        return "location"
    if any(k in t for k in ["meeting about", "whats in the meeting", "what's in the meeting", "zoom about"]):
        return "meeting_content"
    if any(k in t for k in ["free trial", "try it", "test it", "trial period"]):
        return "free_trial"
    if any(k in t for k in ["teams", "individuals", "solo", "agent", "broker"]):
        return "teams_or_individuals"
    if any(k in t for k in ["how fast", "when can you start", "start time", "how soon"]):
        return "start_time"
    if any(k in t for k in ["where did you get", "how did you get", "my number", "who gave you"]):
        return "number_source"
    if any(k in t for k in ["didnt ask", "didn't ask", "never asked", "dont need", "don't need"]):
        return "didnt_ask"
    if any(k in t for k in ["remove my number", "stop calling", "take me off", "do not call"]):
        return "remove_confirm"
    return None


SERVICE_KEYWORDS = {
    "nsol", "bpo", "virtual assistant", "va", "admin", "cold calling", "lead follow",
    "social media", "time", "hours", "services", "automation", "ai",
    "zoom", "meeting", "demo", "presentation", "briefing",
    "pricing", "cost", "investment", "roi", "save time", "free up",
}


def is_service_related(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in SERVICE_KEYWORDS)


def looks_like_random_or_generic_query(text: str) -> bool:
    raw = text.strip()
    t = normalize(raw)
    if not t:
        return False
    if "?" in raw:
        return True
    if any(t.startswith(x + " ") for x in ("what", "why", "how", "when", "where", "who", "can", "could", "would", "do", "is", "are")):
        return True
    if any(p in t for p in ("tell me", "explain", "help me", "give me", "define", "describe", "recommend", "suggest", "write", "create", "make")):
        return True
    if len(t.split()) >= 5:
        return True
    return False


# -----------------------------------------------------------------------------
# Agent wrapper
# -----------------------------------------------------------------------------
class ScriptedMerideth(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=STATE_MACHINE_PROMPT)


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()

    # OpenAI client (used as fallback for random/generic queries)
    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_client = AsyncOpenAI(api_key=openai_api_key) if openai_api_key else None

    vad = silero.VAD.load(
        sample_rate=16000,
        activation_threshold=0.5,
        min_speech_duration=0.2,
        min_silence_duration=0.3,
        prefix_padding_duration=0.1,
    )

    stt = deepgram.STT(
        model="nova-2-phonecall",
        language="en-US",
    )

    tts = elevenlabs.TTS(
        model="eleven_turbo_v2_5",
        voice_id=os.getenv("ELEVEN_VOICE_ID", "bIHbv24MWmeRgasZH58o"),
        streaming_latency=3,
        chunk_length_schedule=[120, 160, 200, 240],
        enable_logging=True,
    )

    session = AgentSession(
        stt=stt,
        tts=tts,
        vad=vad,
        userdata={
            "state": "waiting_for_user",
            "qualifying_idx": 0,
            "attempt_count": 0,
            "refusal_count": 0,
            "price_asked_count": 0,
            "booking_data": {"timezone": None, "day_time": None, "email": None, "phone": None, "name": None},
            "greeted": False,
            "last_text": "",
            "last_text_ts": 0.0,
            "reject_count": 0,
            "was_interrupted": False,
            "last_agent_message": "",
        },
    )

    agent = NSOLBPOAgent()
    speak_lock = asyncio.Lock()

    async def hang_up():
        try:
            await session.disconnect()
            return
        except Exception:
            pass
        try:
            await ctx.room.disconnect()
            return
        except Exception:
            pass
        try:
            await ctx.disconnect()
            return
        except Exception:
            pass

    async def think_delay(is_ending: bool = False):
        if is_ending:
            await asyncio.sleep(random.uniform(0.2, 0.6))
        else:
            await asyncio.sleep(2.0)

    async def say(text: str, *, delayed: bool = True, is_ending: bool = False):
        async with speak_lock:
            if delayed:
                await think_delay(is_ending=is_ending)
            print(f"AGENT: {text}")
            session.userdata["last_agent_message"] = text
            session.userdata["was_interrupted"] = False
            await session.say(text, allow_interruptions=True)

    async def end_call(message: str):
        await say(message, delayed=True, is_ending=True)
        await hang_up()

    async def openai_answer(user_text: str, system_prompt: str) -> str:
        fallback_responses = [
            "Honestly, I'm not sure about that one. But hey, while I have you...",
            "Oh man, good question! I'd have to look that up. Anyway, quick question for you...",
            "Ha, you know what, I'm not totally sure. But so, the reason I called...",
            "Hmm, I'd have to check on that. But hey, do you have a second?",
        ]

        if not openai_client:
            t = normalize(user_text)
            if is_identity_question(user_text):
                return "I'm an assistant. Do you have a moment to discuss the alliance opportunity?"
            if any(k in t for k in ["weather", "temperature", "forecast", "stock", "score", "game"]):
                return "I'm not sure about that. But regarding the alliance opportunity, would you have a moment to discuss?"
            return random.choice(fallback_responses)

        try:
            resp = await openai_client.chat.completions.create(
                model=openai_model,
                temperature=0.7,
                max_tokens=150,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
            )
            content = (resp.choices[0].message.content or "").strip()

            # Cleanup phrases
            content = content.replace("As an AI", "As an assistant")
            content = content.replace("I'm an AI", "I'm an assistant")
            content = content.replace("I'm a language model", "I'm an assistant")
            content = content.replace("I'm a bot", "I'm an assistant")

            # Remove any greeting that could slip through
            greeting_patterns = [
                "Hi. This is Merideth calling on behalf of Galaxy Realtors in Dubai.",
                "Hi, this is Merideth",
                "This is Merideth",
                "calling on behalf of Galaxy Realtors",
            ]
            for pattern in greeting_patterns:
                if pattern.lower() in content.lower():
                    content = content.replace(pattern, "")
                    content = content.replace(pattern.lower(), "")
            content = content.strip()

            if not content or len(content) < 5:
                return random.choice(fallback_responses)
            return content

        except Exception as e:
            print(f"OpenAI error: {e}")
            return random.choice(fallback_responses)

    async def answer_any_random_or_generic(user_text: str) -> bool:
        # This is the OpenAI integration point for random/generic queries.
        if not looks_like_random_or_generic_query(user_text):
            return False

        if is_identity_question(user_text):
            system = IDENTITY_Q_SYSTEM
        elif is_service_related(user_text):
            system = SERVICE_Q_SYSTEM
        else:
            system = GENERIC_Q_SYSTEM

        ans = await openai_answer(user_text, system)
        await say(ans)

        if system == SERVICE_Q_SYSTEM:
            session.userdata["state"] = "booking_ask"
        return True

    nc_plugin = noise_cancellation.BVC()

    await session.start(
        room=ctx.room,
        agent=ScriptedMerideth(),
        room_input_options=RoomInputOptions(
            noise_cancellation=nc_plugin,
            close_on_disconnect=False,
            participant_identity=None,
        ),
    )

    print("AGENT: State is 'waiting_for_user' - waiting for user to speak first...")

    @session.on("agent_speech_interrupted")
    def on_agent_interrupted(e):
        print("DEBUG: Agent was interrupted by user")
        session.userdata["was_interrupted"] = True

    @session.on("user_input_transcribed")
    def on_user_input(e):
        if not getattr(e, "is_final", False):
            return

        raw = getattr(e, "transcript", "") or ""
        text = clean_stt_output(raw)
        print(f"USER STT (FINAL): '{text}'")

        now = time.time()
        last_text = session.userdata.get("last_text", "")
        last_ts = session.userdata.get("last_text_ts", 0.0)

        if text and text == last_text and (now - last_ts) < 1.5:
            print("DEBUG: Dropping duplicate transcript")
            return

        session.userdata["last_text"] = text
        session.userdata["last_text_ts"] = now

        if not acceptable_answer(text):
            print("DEBUG: Empty/junk input - staying silent, waiting for user")
            return

        session.userdata["reject_count"] = 0
        asyncio.create_task(handle(text))

    async def handle(user_text: str):
        state = session.userdata.get("state", "waiting_for_user")
        was_interrupted = session.userdata.get("was_interrupted", False)

        print(f"DEBUG: handle() called - state='{state}', user_text='{user_text}', interrupted={was_interrupted}")

        if was_interrupted and state != "waiting_for_user":
            print("DEBUG: User interrupted - acknowledging")
            session.userdata["was_interrupted"] = False

            simple_acks = ["okay", "ok", "yeah", "yes", "yep", "sure", "got it", "alright", "right"]
            if normalize(user_text) in simple_acks:
                pass
            elif detect_request_repeat(user_text):
                await say("Sure.", delayed=False)
            elif detect_correction(user_text):
                await say("Thank you for clarifying.", delayed=False)
            elif is_identity_question(user_text) or detect_user_question_key(user_text):
                await say("Of course.", delayed=False)
            else:
                await say(random.choice(["Got it.", "I understand.", "Okay.", "Sure."]), delayed=False)

        # Wait for user to speak first, then greet ONCE
        if state == "waiting_for_user" and not session.userdata.get("greeted", False):
            print("DEBUG: State is waiting_for_user - sending greeting")
            session.userdata["greeted"] = True
            session.userdata["state"] = "opening"
            await say("Hi, this is Merideth... how's your day going?")
            print("DEBUG: State changed to 'opening'")
            return
        elif state == "waiting_for_user" and session.userdata.get("greeted", False):
            session.userdata["state"] = "opening"
            print("DEBUG: Already greeted, skipping to opening state")

        # Global refusal rules
        if session.userdata.get("refusal_count", 0) >= 3:
            await end_call(agent.REFUSALS["firm_no"])
            return

        if is_goodbye(user_text):
            await end_call(agent.REFUSALS["goodbye_end"])
            return

        r = refusal_type(user_text)
        if r == "opt_out":
            await end_call(agent.REFUSALS["opt_out"])
            return
        if r == "wrong_number":
            await end_call(agent.REFUSALS["wrong_number"])
            return
        if r == "hangup":
            await end_call(agent.REFUSALS["hangup"])
            return
        if r == "polite_end":
            await end_call(agent.REFUSALS["polite_end"])
            return
        if r == "firm_no":
            session.userdata["refusal_count"] = session.userdata.get("refusal_count", 0) + 1
            if session.userdata["refusal_count"] >= 3:
                await end_call(agent.REFUSALS["firm_no"])
                return
            await say(agent.OBJECTIONS.get("not_interested", "I understand. Is there anything else I can help with?"))
            return

        # Scripted user Qs
        uq = detect_user_question_key(user_text)
        if uq and uq in agent.USER_QUESTIONS:
            await say(agent.USER_QUESTIONS[uq])
            return

        # Script FAQ keys
        qk = detect_script_query_key(user_text)
        if qk and qk in agent.FAQ:
            await say(agent.FAQ[qk])
            return

        # Objection handling
        obj = detect_objection(user_text)
        if obj:
            if obj == "send_info":
                await say(agent.OBJECTIONS["send_info"])
                session.userdata["state"] = "get_email_for_info"
                return
            if obj == "have_to_go":
                await say(agent.OBJECTIONS["have_to_go"])
                return
            if obj == "maybe_later":
                await say(agent.OBJECTIONS["maybe_later"])
                session.userdata["state"] = "get_email_for_info"
                return
            if obj == "call_later":
                await say("No worries at all. Completely understand. When might be a better time for you? Later this week or next?")
                return
            if obj == "not_interested":
                await say(agent.OBJECTIONS["not_interested"])
                return
            if obj == "no_budget":
                await say(agent.OBJECTIONS["no_budget"])
                session.userdata["state"] = "booking_ask"
                return
            if obj == "already_help":
                await say(agent.OBJECTIONS["already_help"])
                session.userdata["state"] = "booking_ask"
                return
            if obj == "no_time":
                await say(agent.OBJECTIONS["no_time"])
                session.userdata["state"] = "booking_ask"
                return
            if obj == "dont_need":
                await say(agent.OBJECTIONS["dont_need"])
                session.userdata["state"] = "booking_ask"
                return
            if obj == "price":
                if session.userdata.get("price_asked_count", 0) == 0:
                    await say(agent.OBJECTIONS["price_first"])
                    session.userdata["price_asked_count"] = 1
                else:
                    await say(agent.OBJECTIONS["price_second"])
                    session.userdata["state"] = "booking_ask"
                return

        # OpenAI: answer ANY random/generic query
        answered = await answer_any_random_or_generic(user_text)
        if answered:
            return

        # -------------------------
        # STATE MACHINE
        # -------------------------
        state = session.userdata.get("state", "opening")

        if state == "opening":
            mood = detect_mood(user_text)
            response_parts = []
            response_parts.append(agent.MOOD_RESPONSES.get(mood, "Glad to hear it."))
            response_parts.append(agent.MAIN_PITCH)
            await say(" ".join(response_parts))
            session.userdata["state"] = "qualify"
            return

        if state == "pitch":
            session.userdata["state"] = "qualify"
            return

        if state == "qualify":
            if detect_interest(user_text):
                await say(agent.INTEREST_RESPONSE)
                session.userdata["state"] = "get_day_time"
                return

            support_type = classify_support(user_text)
            if support_type == "self":
                await say(agent.QUALIFYING_PATHS["self_handling"])
            elif support_type == "support":
                await say(agent.QUALIFYING_PATHS["has_support"])
            else:
                await say(agent.QUALIFYING_PATHS["unsure"])
            session.userdata["state"] = "qualifying_questions"
            return

        if state == "qualifying_questions":
            if detect_interest(user_text):
                await say(agent.INTEREST_RESPONSE)
                session.userdata["state"] = "booking_send_method"
                return

            if any(k in normalize(user_text) for k in ["book", "schedule", "set up", "zoom", "demo", "meeting"]):
                await say(agent.INTEREST_RESPONSE)
                session.userdata["state"] = "booking_send_method"
                return

            idx = session.userdata.get("qualifying_idx", 0)
            if idx < len(agent.QUALIFYING_QUESTIONS):
                await say(agent.QUALIFYING_QUESTIONS[idx])
                session.userdata["qualifying_idx"] = idx + 1
                return

            await say(agent.INTEREST_RESPONSE)
            session.userdata["state"] = "booking_send_method"
            return

        if state == "booking_ask":
            if is_yes(user_text):
                await say("Great! What day and time works best for you?")
                session.userdata["state"] = "get_day_time"
                return

            if detect_send_info_request(user_text):
                await say("Absolutely. Would you prefer I send that via email?")
                session.userdata["state"] = "get_email_for_info"
                return

            session.userdata["refusal_count"] = session.userdata.get("refusal_count", 0) + 1
            if session.userdata["refusal_count"] >= 3:
                await end_call(agent.REFUSALS["firm_no"])
                return

            await say("No worries. Would saving time or getting more leads help you more right now?")
            session.userdata["state"] = "qualify"
            return

        # Booking flow
        if state == "booking_send_method":
            await say("Perfect! What day and time works best for you?")
            session.userdata["state"] = "get_day_time"
            return

        if state == "get_day_time":
            time_text = user_text.strip()
            needs_rounding, suggested_time = parse_time_to_hour_only(time_text)
            if needs_rounding:
                session.userdata["booking_data"]["suggested_time"] = suggested_time
                await say(f"How about {suggested_time} instead? Works better for our system.")
                session.userdata["state"] = "confirm_rounded_time"
                return
            session.userdata["booking_data"]["day_time"] = time_text
            await say("Great! Let's get you scheduled. What's your timezone or location?")
            session.userdata["state"] = "get_timezone"
            return

        if state == "confirm_rounded_time":
            if is_yes(user_text):
                session.userdata["booking_data"]["day_time"] = session.userdata["booking_data"].get("suggested_time")
                await say("Great! Let's get you scheduled. What's your timezone or location?")
                session.userdata["state"] = "get_timezone"
                return
            await say("No problem. What time would work better for you?")
            session.userdata["state"] = "get_day_time"
            return

        if state == "get_timezone":
            session.userdata["booking_data"]["timezone"] = user_text.strip()
            tz = session.userdata["booking_data"]["timezone"]
            await say(f"Got it, that's {tz}. Right?")
            session.userdata["state"] = "confirm_timezone"
            return

        if state == "confirm_timezone":
            if is_yes(user_text):
                await say("Perfect! What's your best email?")
                session.userdata["state"] = "get_email"
                return
            session.userdata["booking_data"]["timezone"] = user_text.strip()
            tz = session.userdata["booking_data"]["timezone"]
            await say(f"Got it, that's {tz}. Right?")
            return

        if state == "get_email":
            email = user_text.strip()
            session.userdata["booking_data"]["email"] = email
            spelled_email = (
                " ".join(c if c.isalnum() else f" {c} " for c in email)
                .replace("@", " at ")
                .replace(".", " dot ")
            )
            await say(f"Let me confirm... that's {spelled_email}. Right?")
            session.userdata["state"] = "confirm_email"
            return

        if state == "confirm_email":
            if is_yes(user_text):
                await say("And your best phone number?")
                session.userdata["state"] = "get_phone"
                return
            session.userdata["booking_data"]["email"] = user_text.strip()
            email = session.userdata["booking_data"]["email"]
            spelled_email = (
                " ".join(c if c.isalnum() else f" {c} " for c in email)
                .replace("@", " at ")
                .replace(".", " dot ")
            )
            await say(f"Thank you for clarifying. So that's {spelled_email}. Right?")
            return

        if state == "get_phone":
            phone = user_text.strip()
            session.userdata["booking_data"]["phone"] = phone
            spelled_phone = " ".join(c if c.isdigit() else ", " for c in phone)
            await say(f"Let me confirm... that's {spelled_phone}. Right?")
            session.userdata["state"] = "confirm_phone"
            return

        if state == "confirm_phone":
            if is_yes(user_text):
                await say("Great! And your full name?")
                session.userdata["state"] = "get_name"
                return
            session.userdata["booking_data"]["phone"] = user_text.strip()
            phone = session.userdata["booking_data"]["phone"]
            spelled_phone = " ".join(c if c.isdigit() else ", " for c in phone)
            await say(f"Thank you for the correction. So that's {spelled_phone}. Right?")
            return

        if state == "get_name":
            session.userdata["booking_data"]["name"] = user_text.strip()
            name = session.userdata["booking_data"]["name"]
            await say(f"Perfect, {name}. Right?")
            session.userdata["state"] = "confirm_name"
            return

        if state == "confirm_name":
            if is_yes(user_text):
                bd = session.userdata["booking_data"]
                await say(
                    f"Excellent! You're all set for {bd.get('day_time')} {bd.get('timezone')}. "
                    "You'll get the confirmation shortly. Looking forward to our meeting!"
                )
                session.userdata["state"] = "final_questions"
                return
            session.userdata["booking_data"]["name"] = user_text.strip()
            name = session.userdata["booking_data"]["name"]
            await say(f"Thank you. So that's {name}. Right?")
            return

        if state == "final_questions":
            if is_yes(user_text) or any(k in normalize(user_text) for k in ["question", "ask"]):
                answered = await answer_any_random_or_generic(user_text)
                if answered:
                    return
                await say("Of course, what would you like to know?")
                return
            await say("Is there anything else I can help with before we wrap up?")
            session.userdata["state"] = "pre_closing"
            return

        if state == "pre_closing":
            if is_yes(user_text) or any(k in normalize(user_text) for k in ["question", "ask", "yes"]):
                answered = await answer_any_random_or_generic(user_text)
                if answered:
                    await say("Anything else before we go?")
                    return
                await say("Of course, what would you like to know?")
                return
            await say("Thank you so much for your time! talk soon! Goodbye!")
            session.userdata["state"] = "closing"
            return

        if state == "closing":
            await end_call("Thank you so much for your time! talk soon! Goodbye!")
            return

        # Send info path
        if state == "get_email_for_info":
            session.userdata["booking_data"]["email"] = user_text.strip()
            email = session.userdata["booking_data"]["email"]
            await say(f"Perfect. Just to confirm, that's {email}. Is that correct?")
            session.userdata["state"] = "confirm_email_for_info"
            return

        if state == "confirm_email_for_info":
            if is_yes(user_text):
                email = session.userdata["booking_data"].get("email", "")
                await say(
                    f"Great. I'll send over the information to {email} shortly. "
                    "If you have any questions afterward, feel free to reach out. Have a great day!"
                )
                session.userdata["state"] = "closing"
                return
            session.userdata["booking_data"]["email"] = user_text.strip()
            email = session.userdata["booking_data"]["email"]
            await say(f"Thank you for clarifying. So that's {email}. Is that correct?")
            return

        # Fallback
        await say("Got it. Are you looking to save time, or get more leads right now?")
        session.userdata["state"] = "qualify"


# -----------------------------------------------------------------------------
# Run LiveKit worker
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    require_livekit_credentials(settings)
    logger.info("Starting NSOL BPO LiveKit Agent - Merideth")
    logger.info(f"Connecting to LiveKit: {settings.LIVEKIT_URL}")

    worker_options = agents.WorkerOptions(
        entrypoint_fnc=entrypoint,
        num_idle_processes=3,
    )
    agents.cli.run_app(worker_options)
