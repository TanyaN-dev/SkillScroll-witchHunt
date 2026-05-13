import os
import asyncio
import json
import logging
from typing import Dict, Any

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import google.generativeai as genai
from dotenv import load_dotenv

from firebase_config import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
logger.info("✅ Gemini configured")

app = FastAPI(title="SkillScroll MVP API")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/start_negotiation")
async def start_negotiation(quest_id: str = "quest-1"):
    prompt = "ನೀನು ಮೈಸೂರು ಮಂಡಿ ವ್ಯಾಪಾರಿ ರಾಜು. ಕೋಪದಿಂದ ಮಾತನಾಡು. ಈಗ ಮೊದಲು ಮಾತನಾಡು."
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = await asyncio.to_thread(model.generate_content, prompt)
    return {"text": response.text.strip()}


async def process_negotiation_turn(audio_bytes: bytes, quest_id: str, history_arr: list):
    logger.info(f"🎤 Audio received: {len(audio_bytes)} bytes")

    if len(audio_bytes) < 1200:
        return {
            "user_transcript": "Too short",
            "agent_reply": "ಸ್ವಲ್ಪ ಹೆಚ್ಚು ಮಾತನಾಡಿ!",
            "score": 40,
            "feedback": "Speak 2-3 seconds"
        }

    prompt = """Listen to the audio and do two things:
1. Write exactly what the user said in Kannada.
2. Reply as an angry Mandi wholesaler in Kannada (short reply).

Return only JSON:
{"user_transcript": "what user said", "agent_reply": "your short angry reply", "score": 65, "feedback": "short feedback"}"""

    audio_part = {"mime_type": "audio/webm", "data": audio_bytes}

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={"temperature": 0.7, "max_output_tokens": 350}
        )
        
        response = await asyncio.to_thread(model.generate_content, [prompt, audio_part])
        
        raw = response.text.strip()
        if "```" in raw:
            raw = raw.split("```")[-2].strip()
            
        return json.loads(raw)

    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        return {
            "user_transcript": "Audio unclear",
            "agent_reply": "ಏನ್ ಸಾಕು ರೀ, ಸ್ಪಷ್ಟವಾಗಿ ಮಾತನಾಡಿ!",
            "score": 40,
            "feedback": "Speak clearly"
        }


@app.post("/negotiate")
async def negotiate(
    quest_id: str = Form(...),
    history: str = Form("[]"),
    audio: UploadFile = File(...)
):
    audio_bytes = await audio.read()
    logger.info(f"Received audio size: {len(audio_bytes)} bytes")

    history_arr = json.loads(history)
    result = await process_negotiation_turn(audio_bytes, quest_id, history_arr)

    return {
        "user_text": result.get("user_transcript", "Audio unclear"),
        "text": result.get("agent_reply", "Error"),
        "confidence": result.get("score", 50),
        "feedback": result.get("feedback", "Try again")
    }


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
