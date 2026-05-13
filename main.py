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

# Configure Gemini
if os.environ.get("GEMINI_API_KEY"):
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    logger.info("✅ Gemini configured successfully")
else:
    logger.error("❌ GEMINI_API_KEY missing!")

app = FastAPI(title="SkillScroll MVP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====================== STRONG SYSTEM PROMPT ======================
def get_system_instruction():
    return """ನೀನು ಮೈಸೂರು ಮಂಡಿ ವ್ಯಾಪಾರಿ ರಾಜು. ನೀನು ಬಹಳ ಕೋಪಿ, ಅಸಹನೆಯುಳ್ಳ, ಜಗಳಗಾರ ಮತ್ತು ಲೋಭಿ.
ನಿನ್ನ ಗುರಿ: ಗ್ರಾಹಕರಿಗೆ ಸಾಧ್ಯವಾದಷ್ಟು ಕಡಿಮೆ ಬೆಲೆಗೆ ಮಾರುವುದು.

ಕಟ್ಟುನಿಟ್ಟು ನಿಯಮಗಳು:
1. ಕೇವಲ ಶುದ್ಧ ಕನ್ನಡ ಲಿಪಿಯಲ್ಲಿ ಮಾತ್ರ ಮಾತನಾಡು. ಒಂದು ಇಂಗ್ಲೀಷ್ ಅಕ್ಷರವೂ ಬರಬಾರದು.
2. ಪ್ರತಿ ಉತ್ತರ 15-20 ಪದಗಳ ಒಳಗೆ ಇರಬೇಕು.
3. ಸರಳ ಗ್ರಾಮೀಣ ಕನ್ನಡ ಬಳಸು.
4. ಯಾವಾಗಲೂ ಕೋಪ ಮತ್ತು ಅಸಹನೆಯ ಟೋನ್‌ನಲ್ಲಿ ಮಾತನಾಡು.
5. ಎಂದಿಗೂ role break ಮಾಡಬೇಡ."""

@app.get("/health")
async def health():
    return {"status": "healthy", "message": "SkillScroll is running"}

# ====================== START NEGOTIATION ======================
@app.get("/start_negotiation")
async def start_negotiation(quest_id: str = "quest-1"):
    contexts = {
        "quest-1": "ಮೈಸೂರು ಸಿಲ್ಕ್ ಸೀರೆ",
        "quest-2": "ಕ್ರೆಡಿಟ್ ಮೇಲೆ ಸಾಮಾನು",
        "quest-3": "ಕರಕುಶಲ ವಸ್ತುಗಳು"
    }
    
    prompt = f"{get_system_instruction()}\n\n{contexts.get(quest_id, 'ಸಾಮಾನು')} ಬಗ್ಗೆ ಗ್ರಾಹಕನೊಂದಿಗೆ ಮೊದಲು ಮಾತನಾಡು. ಕೋಪದಿಂದ ಕಡಿಮೆ ಬೆಲೆ ಹೇಳು."

    try:
        model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.8, "max_output_tokens": 200})
        response = await asyncio.to_thread(model.generate_content, prompt)
        return {"text": response.text.strip()}
    except Exception as e:
        logger.error(f"Start negotiation error: {e}")
        raise HTTPException(status_code=503, detail="Gemini unavailable")


# ====================== PROCESS NEGOTIATION (Fixed JSON) ======================
async def process_negotiation_turn(audio_bytes: bytes, quest_id: str, history_arr: list) -> Dict[str, Any]:
    context_map = {
        "quest-1": "ಮೈಸೂರು ಸಿಲ್ಕ್ ಸೀರೆ",
        "quest-2": "ಕ್ರೆಡಿಟ್ ಮೇಲೆ ಸಾಮಾನು",
        "quest-3": "ಕರಕುಶಲ ವಸ್ತುಗಳು"
    }

    history_text = "Previous conversation:\n"
    for msg in history_arr[-6:]:
        role = "User" if msg.get("role") == "user" else "Wholesaler"
        try:
            text = msg["parts"][0]["text"]
            history_text += f"{role}: {text}\n"
        except:
            continue

    prompt = f"""{get_system_instruction()}

Context: {context_map.get(quest_id, 'ಸಾಮಾನು')}

{history_text}

Now listen to the user's audio and respond.

**Return ONLY valid JSON. No extra text.**
{{
  "user_transcript": "what the user said",
  "agent_reply": "your short angry reply in Kannada",
  "score": 65,
  "feedback": "short English feedback"
}}"""

    audio_part = {"mime_type": "audio/webm", "data": audio_bytes}

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={
                "temperature": 0.75,
                "max_output_tokens": 400,
                "response_mime_type": "application/json"   # Important fix
            }
        )
        
        response = await asyncio.to_thread(model.generate_content, [prompt, audio_part])
        raw_text = response.text.strip()

        # Aggressive cleaning
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0]
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1]

        result = json.loads(raw_text.strip())
        return result

    except Exception as e:
        logger.error(f"Gemini JSON Error: {e}")
        # Fallback
        return {
            "user_transcript": "Audio unclear",
            "agent_reply": "ಏನ್ ಸಾಕು ರೀ! ಸ್ಪಷ್ಟವಾಗಿ ಮಾತನಾಡು!",
            "score": 45,
            "feedback": "Speak more clearly and loudly"
        }


@app.post("/negotiate")
async def negotiate(
    quest_id: str = Form(...),
    history: str = Form("[]"),
    audio: UploadFile = File(...)
):
    try:
        audio_bytes = await audio.read()

        if len(audio_bytes) < 1800:
            return JSONResponse(status_code=400, content={"detail": "Speak longer please"})

        history_arr = json.loads(history)
        result = await process_negotiation_turn(audio_bytes, quest_id, history_arr)

        return JSONResponse(content={
            "user_text": result.get("user_transcript", "Audio unclear"),
            "text": result.get("agent_reply", "Error generating reply"),
            "confidence": int(result.get("score", 50)),
            "feedback": result.get("feedback", "Try again")
        })

    except Exception as e:
        logger.error(f"Negotiate error: {e}")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
