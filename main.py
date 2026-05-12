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

# Import Firebase
from firebase_config import db

# ====================== Logging Setup ======================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("Python version:", sys.version)
print("Current directory:", os.getcwd())
print("Files in root:", os.listdir("."))

# ====================== Load Environment ======================
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
logger.info("Gemini API configured")

app = FastAPI(title="SkillScroll MVP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====================== Health Check ======================
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "firebase": "connected" if db is not None else "disabled",
        "gemini": "configured"
    }

# ====================== Start Negotiation ======================
@app.get("/start_negotiation")
async def start_negotiation(quest_id: str = "quest-1"):
    system_instruction = (
        "ROLE: You are an aggressive, impatient Mandi wholesaler from Mysore, Karnataka. "
        "Your only goal is to lowball the user and force a bad deal.\n"
        "CRITICAL RULE 1: You MUST write your response EXCLUSIVELY in the native Kannada script (ಕನ್ನಡ ಲಿಪಿ). "
        "Do NOT use a single English letter.\n"
        "CRITICAL RULE 2: Keep replies under 20 words. Use simple, rural vocabulary.\n"
        "CRITICAL RULE 3: Never break character. Act angry."
    )
    
    context = "a product"
    if quest_id == "quest-1":
        context = "Mysore silk"
    elif quest_id == "quest-2":
        context = "goods on credit"
    elif quest_id == "quest-3":
        context = "handicrafts"
        
    prompt = f"{system_instruction}\n\nGive your initial lowball offer for {context} to start the negotiation:"
    
    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 300,
            }
        )
        response = await asyncio.to_thread(model.generate_content, prompt)
        return {"text": response.text.strip()}
    
    except Exception as e:
        logger.error(f"Error in /start_negotiation: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=503, detail="Gemini is temporarily unavailable")


# ====================== Process Negotiation Turn ======================
async def process_negotiation_turn(audio_bytes: bytes, quest_id: str, history_arr: list) -> Dict[str, Any]:
    system_instruction = (
        "ROLE: You are an aggressive, impatient Mandi wholesaler from Mysore, Karnataka. "
        "Your only goal is to lowball the user and force a bad deal.\n"
        "CRITICAL RULE 1: You MUST write your 'user_transcript' and 'agent_reply' EXCLUSIVELY in the native Kannada script (ಕನ್ನಡ ಲಿಪಿ). "
        "Do NOT use a single English letter for the spoken dialogue.\n"
        "CRITICAL RULE 2: Keep replies under 20 words. Use simple, rural vocabulary.\n"
        "CRITICAL RULE 3: Never break character.\n\n"
        "CRITICAL RULE 4: Return valid JSON with keys: 'user_transcript', 'agent_reply', 'score', 'feedback'"
    )
    
    context = ""
    if quest_id == "quest-1":
        context = "Context: You are lowballing silk by 30-40%. User wants fair price."
    elif quest_id == "quest-2":
        context = "Context: You are a buyer demanding goods on credit. User wants advance."
    elif quest_id == "quest-3":
        context = "Context: You are negotiating for handicrafts."

    history_text = "Previous Conversation History:\n"
    for msg in history_arr:
        role = "User" if msg.get("role") == "user" else "Wholesaler"
        try:
            text_content = msg["parts"][0]["text"]
            history_text += f"{role}: {text_content}\n"
        except (KeyError, IndexError, TypeError):
            continue

    prompt = f"{system_instruction}\n{context}\n\n{history_text}\nNow, process the attached audio for the User's latest turn."
    
    audio_part = {
        "mime_type": "audio/webm",
        "data": audio_bytes
    }

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 500,
            }
        )
        
        response = await asyncio.to_thread(model.generate_content, [prompt, audio_part])
        
        raw_text = response.text.strip()
        
        # Clean markdown if Gemini adds it
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        result = json.loads(raw_text.strip())
        return result
        
    except json.JSONDecodeError:
        logger.error(f"JSON parsing failed. Raw: {response.text if 'response' in locals() else 'None'}")
        raise HTTPException(status_code=503, detail="Gemini returned invalid JSON.")
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=503, detail="Gemini is temporarily unavailable")


# ====================== Negotiate Endpoint ======================
@app.post("/negotiate")
async def negotiate(
    quest_id: str = Form(...),
    history: str = Form("[]"),
    audio: UploadFile = File(...)
):
    try:
        audio_bytes = await audio.read()
        
        if not audio_bytes or len(audio_bytes) < 500:
            raise HTTPException(status_code=400, detail="Empty or invalid audio file.")
        if len(audio_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Audio file too large (max 10MB)")

        history_arr = json.loads(history)
        
        gemini_result = await process_negotiation_turn(audio_bytes, quest_id, history_arr)
        
        return JSONResponse(content={
            "user_text": gemini_result.get("user_transcript", "Audio unclear"),
            "text": gemini_result.get("agent_reply", "Error generating reply"),
            "confidence": gemini_result.get("score", 50),
            "feedback": gemini_result.get("feedback", "Keep pushing for a better price.")
        })
        
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    except Exception as e:
        logger.error(f"Unexpected error in /negotiate: {e}")
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})


# ====================== Mount Frontend ======================
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
