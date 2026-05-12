import os
import asyncio
import json
import logging
import traceback
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

if os.environ.get("GEMINI_API_KEY"):
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    logger.info("Gemini configured")
else:
    logger.error("GEMINI_API_KEY missing!")

app = FastAPI(title="SkillScroll MVP API")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def get_system_instruction():
    return """ನೀನು ಮೈಸೂರು ಮಂಡಿ ವ್ಯಾಪಾರಿ 'ರಾಜು'. 
ನೀನು ಬಹಳ ಕೋಪಿ, ಅಸಹನೆಯ, ಜಗಳಗಾರ, ಲೋಭಿ ವ್ಯಕ್ತಿ.

ಕಟ್ಟುನಿಟ್ಟು ನಿಯಮಗಳು:
1. ನೀನು **ಕೇವಲ ಕನ್ನಡ ಲಿಪಿಯಲ್ಲಿ ಮಾತ್ರ** ಮಾತನಾಡು. ಒಂದು ಇಂಗ್ಲೀಷ್ ಅಕ್ಷರವೂ ಬರಬಾರದು.
2. ಪ್ರತಿ ಉತ್ತರ **15ರಿಂದ 20 ಪದಗಳ ಒಳಗೆ** ಇರಲಿ.
3. ಸರಳ ಗ್ರಾಮೀಣ ಕನ್ನಡ ಬಳಸು (ಅಂಕಿ, ಏನ್ ಸಾಕು, ಬೇಡ, ಕಡಿಮೆ ಹೇಳು, ಏನ್ ತಗೊಂಡಿದ್ದೀಯಾ ಇತ್ಯಾದಿ).
4. ಯಾವಾಗಲೂ ಕೋಪದಲ್ಲಿರು, ಬೆದರಿಕೆ ಹಾಕು, ಜಗಳ ಮಾಡು, ಕಡಿಮೆ ಬೆಲೆಗೆ ಒತ್ತಾಯಿಸು.
5. ಎಂದಿಗೂ role break ಮಾಡಬೇಡ."""

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/start_negotiation")
async def start_negotiation(quest_id: str = "quest-1"):
    contexts = {"quest-1": "ಮೈಸೂರು ಸಿಲ್ಕ್", "quest-2": "ಕ್ರೆಡಿಟ್ ಸಾಮಾನು", "quest-3": "ಕರಕುಶಲ ವಸ್ತುಗಳು"}
    prompt = f"{get_system_instruction()}\n\nಈಗ {contexts.get(quest_id, 'ಸಾಮಾನು')} ಬಗ್ಗೆ ಮೊದಲು ಬಹಳ ಕಡಿಮೆ ಬೆಲೆ ಹೇಳು. ಕೋಪದಿಂದ."

    model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.9, "max_output_tokens": 200})
    response = await asyncio.to_thread(model.generate_content, prompt)
    return {"text": response.text.strip()}


async def process_negotiation_turn(audio_bytes: bytes, quest_id: str, history_arr: list):
    # ... (I'll keep it shorter for now)
    prompt = f"""{get_system_instruction()}

ಹಿಂದಿನ ಸಂಭಾಷಣೆ: {str(history_arr[-4:])}

ಈಗ ಗ್ರಾಹಕನ ಆಡಿಯೋ ಕೇಳಿ. ಅವನು ಏನು ಹೇಳಿದ್ದಾನೆ ಅರ್ಥ ಮಾಡಿಕೊಂಡು ಕೋಪದಿಂದ ಉತ್ತರ ಕೊಡು.

Return only valid JSON:
{{"user_transcript": "...", "agent_reply": "...", "score": 45, "feedback": "..."}}"""

    audio_part = {"mime_type": "audio/webm", "data": audio_bytes}

    model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.85, "max_output_tokens": 400})
    response = await asyncio.to_thread(model.generate_content, [prompt, audio_part])

    raw = response.text.strip()
    # Clean markdown
    if "```" in raw:
        raw = raw.split("```")[1].strip()
    
    try:
        return json.loads(raw)
    except:
        return {
            "user_transcript": "Audio unclear",
            "agent_reply": raw[:150],
            "score": 40,
            "feedback": "ಸ್ಪಷ್ಟವಾಗಿ ಮಾತನಾಡು"
        }


@app.post("/negotiate")
async def negotiate(quest_id: str = Form(...), history: str = Form("[]"), audio: UploadFile = File(...)):
    audio_bytes = await audio.read()
    
    if len(audio_bytes) < 1500:   # Increased minimum size
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
