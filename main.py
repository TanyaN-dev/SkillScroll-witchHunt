import os
import asyncio
import json
import sys
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

# ====================== Logging ======================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Configure Gemini
gemini_key = os.environ.get("GEMINI_API_KEY")
if gemini_key:
    genai.configure(api_key=gemini_key)
    logger.info("✅ Gemini API configured successfully")
else:
    logger.error("❌ GEMINI_API_KEY is missing!")

app = FastAPI(title="SkillScroll MVP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====================== Strong System Instruction ======================
def get_system_instruction():
    return """ನೀನು ಮೈಸೂರು ಮಂಡಿಯ ರಾಜು. ಬಹಳ ಕೋಪಿ, ಅಸಹನೆಯುಳ್ಳ, ಲೋಭಿ ವ್ಯಾಪಾರಿ.
ನಿನ್ನ ಏಕೈಕ ಗುರಿ: ಬಹಳ ಕಡಿಮೆ ಬೆಲೆಗೆ ಖರೀದಿಸುವುದು ಅಥವಾ ಹೆಚ್ಚು ಬೆಲೆಗೆ ಮಾರುವುದು.

ಕಟ್ಟುನಿಟ್ಟಾದ ನಿಯಮಗಳು:
1. ನೀನು ಕೇವಲ ಕನ್ನಡ ಲಿಪಿಯಲ್ಲಿ ಮಾತ್ರ ಮಾತನಾಡಬೇಕು. ಒಂದು ಇಂಗ್ಲೀಷ್ ಅಕ್ಷರವೂ ಬರಬಾರದು.
2. ಪ್ರತಿ ಉತ್ತರ 15-20 ಪದಗಳ ಒಳಗೆ ಇರಬೇಕು.
3. ಸರಳ ಗ್ರಾಮೀಣ ಕನ್ನಡ ಬಳಸು (ಅಂಕಿ, ಏನ್ ಸಾಕು, ಬೇಡ, ಕಡಿಮೆ ಹೇಳು, ಇತ್ಯಾದಿ).
4. ಯಾವಾಗಲೂ ಕೋಪದಲ್ಲಿರು, ಜಗಳ ಮಾಡು, ಬೆದರಿಕೆ ಹಾಕು.
5. ಎಂದಿಗೂ role break ಮಾಡಬೇಡ."""

@app.get("/health")
async def health():
    return {"status": "healthy", "gemini": "configured"}

# ====================== Start Negotiation ======================
@app.get("/start_negotiation")
async def start_negotiation(quest_id: str = "quest-1"):
    context = {
        "quest-1": "ಮೈಸೂರು ಸಿಲ್ಕ್ ಸೀರೆ",
        "quest-2": "ಕ್ರೆಡಿಟ್ ಮೇಲೆ ಸಾಮಾನು",
        "quest-3": "ಕರಕುಶಲ ವಸ್ತುಗಳು"
    }.get(quest_id, "ಸಾಮಾನು")

    prompt = f"{get_system_instruction()}\n\nಈಗ {context} ಬಗ್ಗೆ ಮೊದಲು ಬಹಳ ಕಡಿಮೆ ಬೆಲೆ ಹೇಳಿ. ಕೋಪದಿಂದ ಮಾತನಾಡು."

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={
                "temperature": 0.85,
                "top_p": 0.92,
                "max_output_tokens": 200,
            }
        )
        response = await asyncio.to_thread(model.generate_content, prompt)
        return {"text": response.text.strip()}
    except Exception as e:
        logger.error(f"Start negotiation error: {e}")
        raise HTTPException(status_code=503, detail="Gemini unavailable")


# ====================== Process Negotiation Turn ======================
async def process_negotiation_turn(audio_bytes: bytes, quest_id: str, history_arr: list) -> Dict[str, Any]:
    context = {
        "quest-1": "ಮೈಸೂರು ಸಿಲ್ಕ್ ಸೀರೆಗೆ ಬಹಳ ಕಡಿಮೆ ಬೆಲೆ ಕೊಡುತ್ತಿದ್ದೀಯೆ",
        "quest-2": "ಕ್ರೆಡಿಟ್ ಮೇಲೆ ಸಾಮಾನು ಕೊಡಲು ನೀನು ಒಪ್ಪುತ್ತಿಲ್ಲ",
        "quest-3": "ಕರಕುಶಲ ವಸ್ತುಗಳಿಗೆ ಬಹಳ ಕಡಿಮೆ ಬೆಲೆ ಕೊಡುತ್ತಿದ್ದೀಯೆ"
    }.get(quest_id, "")

    history_text = "ಹಿಂದಿನ ಸಂಭಾಷಣೆ:\n"
    for msg in history_arr[-6:]:
        role = "ಗ್ರಾಹಕ" if msg.get("role") == "user" else "ನಾನು"
        try:
            text_content = msg["parts"][0]["text"]
            history_text += f"{role}: {text_content}\n"
        except:
            continue

    prompt = f"""{get_system_instruction()}

{context}

{history_text}

ಈಗ ಗ್ರಾಹಕನ ಆಡಿಯೋ ಕೇಳಿ ಅವನು ಏನು ಹೇಳಿದ್ದಾನೆ ಅರ್ಥಮಾಡಿಕೊಂಡು, ಕೋಪದಿಂದ ಉತ್ತರ ಕೊಡು."""

    audio_part = {"mime_type": "audio/webm", "data": audio_bytes}

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={
                "temperature": 0.82,
                "top_p": 0.9,
                "max_output_tokens": 300,
            }
        )
        response = await asyncio.to_thread(model.generate_content, [prompt, audio_part])
        
        raw_text = response.text.strip()

        # Clean if Gemini adds markdown
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        try:
            result = json.loads(raw_text.strip())
        except:
            result = {
                "user_transcript": "Audio unclear",
                "agent_reply": raw_text,
                "score": 50,
                "feedback": "ಬೆಲೆ ಇನ್ನೂ ಏರಿಸು"
            }
        return result

    except Exception as e:
        logger.error(f"Gemini error: {e}")
        raise HTTPException(status_code=503, detail="Gemini unavailable")


@app.post("/negotiate")
async def negotiate(
    quest_id: str = Form(...),
    history: str = Form("[]"),
    audio: UploadFile = File(...)
):
    try:
        audio_bytes = await audio.read()
        if len(audio_bytes) < 800:
            raise HTTPException(status_code=400, detail="Audio too short")

        history_arr = json.loads(history)
        gemini_result = await process_negotiation_turn(audio_bytes, quest_id, history_arr)

        return JSONResponse(content={
            "user_text": gemini_result.get("user_transcript", "Audio unclear"),
            "text": gemini_result.get("agent_reply", "Error generating reply"),
            "confidence": gemini_result.get("score", 50),
            "feedback": gemini_result.get("feedback", "ಬೆಲೆ ಇನ್ನೂ ಏರಿಸು")
        })

    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    except Exception as e:
        logger.error(f"Negotiate error: {e}")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
