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

if os.environ.get("GEMINI_API_KEY"):
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    logger.info("✅ Gemini configured")
else:
    logger.error("❌ GEMINI_API_KEY missing!")

app = FastAPI(title="SkillScroll MVP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====================== STRONG SYSTEM PROMPT ======================
def get_system_instruction():
    return """ನೀನು ಮೈಸೂರು ಮಂಡಿಯಲ್ಲಿ 25 ವರ್ಷಗಳಿಂದ ವ್ಯಾಪಾರ ಮಾಡುತ್ತಿರುವ 'ರಾಜು'. 
ನೀನು ಬಹಳ ಕೋಪಿ, ಅಸಹನೆಯುಳ್ಳ, ಲೋಭಿ ಮತ್ತು ಜಗಳಗಾರ ವ್ಯಾಪಾರಿ.

ನಿನ್ನ ಗುರಿ: ಯಾವಾಗಲೂ ಗ್ರಾಹಕರಿಗೆ ಬಹಳ ಕಡಿಮೆ ಬೆಲೆ ಕೊಡಿಸುವುದು ಅಥವಾ ನಿನಗೆ ಹೆಚ್ಚು ಬೆಲೆ ಸಿಗುವಂತೆ ಮಾಡುವುದು.

ಕಟ್ಟುನಿಟ್ಟಾದ ನಿಯಮಗಳು:
1. ನೀನು **ಕೇವಲ ಶುದ್ಧ ಕನ್ನಡ ಲಿಪಿಯಲ್ಲಿ ಮಾತ್ರ** ಮಾತನಾಡಬೇಕು. ಒಂದು ಇಂಗ್ಲೀಷ್ ಅಕ್ಷರವೂ ಬರಬಾರದು.
2. ಪ್ರತಿ ಉತ್ತರ 15 ರಿಂದ 22 ಪದಗಳ ಒಳಗೆ ಇರಬೇಕು.
3. ಸರಳ, ಗ್ರಾಮೀಣ, ರೂಢಿಯ ಕನ್ನಡ ಬಳಸು (ಅಂಕಿ, ಏನ್ ಸಾಕು, ಬೇಡ್ರಿ, ಏನ್ ತಗೊಂಡಿದ್ದೀಯ, ಸುಳ್ಳು ಹೇಳ್ತೀಯಾ ಇತ್ಯಾದಿ).
4. ಯಾವಾಗಲೂ ಕೋಪ, ಅಸಹನೆ ಮತ್ತು ಜಗಳದ ಟೋನ್‌ನಲ್ಲಿ ಮಾತನಾಡು.
5. ಎಂದಿಗೂ role break ಮಾಡಬೇಡ. ಯಾವುದೇ ಸಮಯದಲ್ಲಿ ಸಹಾಯಕರಾಗಬೇಡ."""

@app.get("/health")
async def health():
    return {"status": "healthy"}

# ====================== START NEGOTIATION ======================
@app.get("/start_negotiation")
async def start_negotiation(quest_id: str = "quest-1"):
    contexts = {
        "quest-1": "ಮೈಸೂರು ಸಿಲ್ಕ್ ಸೀರೆ",
        "quest-2": "ಕ್ರೆಡಿಟ್ ಮೇಲೆ ಸಾಮಾನು",
        "quest-3": "ಕರಕುಶಲ ವಸ್ತುಗಳು"
    }
    
    prompt = f"{get_system_instruction()}\n\nಈಗ {contexts.get(quest_id, 'ಸಾಮಾನು')} ಬಗ್ಗೆ ಗ್ರಾಹಕನೊಂದಿಗೆ ಮೊದಲು ಮಾತನಾಡು. ಬಹಳ ಕಡಿಮೆ ಬೆಲೆ ಹೇಳು. ಕೋಪದಿಂದ."

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={
                "temperature": 0.85,
                "top_p": 0.9,
                "max_output_tokens": 220,
            }
        )
        response = await asyncio.to_thread(model.generate_content, prompt)
        return {"text": response.text.strip()}
    except Exception as e:
        logger.error(f"Start error: {e}")
        raise HTTPException(503, "Gemini unavailable")


# ====================== MAIN NEGOTIATION ======================
async def process_negotiation_turn(audio_bytes: bytes, quest_id: str, history_arr: list) -> Dict[str, Any]:
    context_map = {
        "quest-1": "ಮೈಸೂರು ಸಿಲ್ಕ್ ಸೀರೆಯ ಬೆಲೆ ಕುರಿತು ಜಗಳ ನಡೆಯುತ್ತಿದೆ",
        "quest-2": "ಕ್ರೆಡಿಟ್ ಮೇಲೆ ಸಾಮಾನು ಕೊಡುವುದರ ಬಗ್ಗೆ ಜಗಳ ನಡೆಯುತ್ತಿದೆ",
        "quest-3": "ಕರಕುಶಲ ವಸ್ತುಗಳ ಬೆಲೆ ಕುರಿತು ಜಗಳ ನಡೆಯುತ್ತಿದೆ"
    }

    history_text = ""
    for msg in history_arr[-5:]:   # Last 5 messages
        role = "ಗ್ರಾಹಕ" if msg.get("role") == "user" else "ನಾನು (ರಾಜು)"
        try:
            text = msg["parts"][0]["text"]
            history_text += f"{role}: {text}\n"
        except:
            continue

    prompt = f"""{get_system_instruction()}

ಪ್ರಸ್ತುತ ಸನ್ನಿವೇಶ: {context_map.get(quest_id, '')}

{history_text}

ಈಗ ಗ್ರಾಹಕನ ಆಡಿಯೋ ಕೇಳಿ:
- ಅವರು ಏನು ಹೇಳಿದ್ದಾರೆ ಎಂದು ಸರಿಯಾಗಿ ಅರ್ಥ ಮಾಡಿಕೊ
- ಅದಕ್ಕೆ ಸರಿಯಾದ, ಅರ್ಥವುಳ್ಳ, ಕೋಪದ ಉತ್ತರ ಕೊಡು

Return **only** valid JSON (nothing else):
{{
  "user_transcript": "ಗ್ರಾಹಕ ಹೇಳಿದ್ದು",
  "agent_reply": "ನಿನ್ನ ಉತ್ತರ (ಕನ್ನಡದಲ್ಲಿ)",
  "score": 65,
  "feedback": "ಬೆಲೆ ಇನ್ನೂ ಏರಿಸು ಅಥವಾ ಇನ್ನಷ್ಟು ಜಗಳ ಮಾಡು"
}}"""

    audio_part = {"mime_type": "audio/webm", "data": audio_bytes}

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={
                "temperature": 0.82,
                "top_p": 0.9,
                "max_output_tokens": 450,
            }
        )
        response = await asyncio.to_thread(model.generate_content, [prompt, audio_part])
        
        raw_text = response.text.strip()

        # Clean any markdown
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0]
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1]

        result = json.loads(raw_text.strip())
        return result

    except Exception as e:
        logger.error(f"Gemini processing error: {e}")
        return {
            "user_transcript": "Audio unclear",
            "agent_reply": "ಏನ್ ಸಾಕು ರೀ, ಸ್ಪಷ್ಟವಾಗಿ ಮಾತನಾಡು!",
            "score": 40,
            "feedback": "ಸ್ಪಷ್ಟವಾಗಿ ಮಾತನಾಡಿ"
        }


@app.post("/negotiate")
async def negotiate(
    quest_id: str = Form(...),
    history: str = Form("[]"),
    audio: UploadFile = File(...)
):
    try:
        audio_bytes = await audio.read()

        if len(audio_bytes) < 2000:   # Increased for better transcription
            return JSONResponse(
                status_code=400, 
                content={"detail": "ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಹೆಚ್ಚು ಸಮಯ ಮಾತನಾಡಿ"}
            )

        history_arr = json.loads(history)
        result = await process_negotiation_turn(audio_bytes, quest_id, history_arr)

        return JSONResponse(content={
            "user_text": result.get("user_transcript", "Audio unclear"),
            "text": result.get("agent_reply", "Error"),
            "confidence": int(result.get("score", 50)),
            "feedback": result.get("feedback", "ಬೆಲೆ ಇನ್ನೂ ಏರಿಸು")
        })

    except Exception as e:
        logger.error(f"Negotiate endpoint error: {e}")
        return JSONResponse(status_code=500, content={"detail": "Internal error"})


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
