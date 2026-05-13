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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_system_instruction():
    return """ನೀನು ಮೈಸೂರು ಮಂಡಿ ವ್ಯಾಪಾರಿ ರಾಜು. ಬಹಳ ಕೋಪಿ ಮತ್ತು ಜಗಳಗಾರ.
ನಿನ್ನ ಗುರಿ: ಗ್ರಾಹಕರಿಗೆ ಕಡಿಮೆ ಬೆಲೆಗೆ ಮಾರುವುದು.

ನಿಯಮಗಳು:
- ಕೇವಲ ಕನ್ನಡ ಲಿಪಿಯಲ್ಲಿ ಮಾತನಾಡು
- 15-20 ಪದಗಳಲ್ಲಿ ಉತ್ತರ ಕೊಡು
- ಯಾವಾಗಲೂ ಕೋಪದಲ್ಲಿರು"""

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/start_negotiation")
async def start_negotiation(quest_id: str = "quest-1"):
    contexts = {"quest-1": "ಮೈಸೂರು ಸಿಲ್ಕ್", "quest-2": "ಕ್ರೆಡಿಟ್ ಸಾಮಾನು", "quest-3": "ಕರಕುಶಲ ವಸ್ತುಗಳು"}
    prompt = f"{get_system_instruction()}\n\n{contexts.get(quest_id)} ಬಗ್ಗೆ ಕೋಪದಿಂದ ಮೊದಲು ಮಾತನಾಡು."

    model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.8, "max_output_tokens": 200})
    response = await asyncio.to_thread(model.generate_content, prompt)
    return {"text": response.text.strip()}


async def process_negotiation_turn(audio_bytes: bytes, quest_id: str, history_arr: list):
    prompt = f"""{get_system_instruction()}

Previous conversation: {str(history_arr[-5:]) if history_arr else "First turn"}

Listen to user's audio and respond naturally in Kannada.

Return ONLY valid JSON:
{{
  "user_transcript": "what user said",
  "agent_reply": "your short angry reply in Kannada",
  "score": 60,
  "feedback": "short feedback in English"
}}"""

    audio_part = {"mime_type": "audio/webm", "data": audio_bytes}

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={
                "temperature": 0.75,
                "max_output_tokens": 400,
                "response_mime_type": "application/json"
            }
        )
        response = await asyncio.to_thread(model.generate_content, [prompt, audio_part])
        
        raw = response.text.strip()
        
        # Clean JSON
        if "```" in raw:
            raw = raw.split("```")[1].strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()

        result = json.loads(raw)
        return result

    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        return {
            "user_transcript": "Audio unclear",
            "agent_reply": "ಏನ್ ಸಾಕು ರೀ! ಸ್ಪಷ್ಟವಾಗಿ ಮಾತನಾಡು!",
            "score": 40,
            "feedback": "Speak louder and clearer"
        }


@app.post("/negotiate")
async def negotiate(
    quest_id: str = Form(...),
    history: str = Form("[]"),
    audio: UploadFile = File(...)
):
    audio_bytes = await audio.read()
    
    if len(audio_bytes) < 1200:   # Lowered threshold
        return JSONResponse(status_code=400, content={"detail": "Speak longer"})

    history_arr = json.loads(history)
    result = await process_negotiation_turn(audio_bytes, quest_id, history_arr)

    return {
        "user_text": result.get("user_transcript", "Audio unclear"),
        "text": result.get("agent_reply", "Error"),
        "confidence": result.get("score", 50),
        "feedback": result.get("feedback", "Try again")
    }


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
