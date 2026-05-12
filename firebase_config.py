import os
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

def initialize_firebase():
    # Only initialize if not already initialized
    if not firebase_admin._apps:
        project_id = os.environ.get("FIREBASE_PROJECT_ID")
        private_key = os.environ.get("FIREBASE_PRIVATE_KEY")
        client_email = os.environ.get("FIREBASE_CLIENT_EMAIL")

        if project_id and private_key and client_email:
            # Clean the private key
            private_key = private_key.replace("\\n", "\n").strip()
            
            cred_dict = {
                "type": "service_account",
                "project_id": project_id,
                "private_key": private_key,
                "client_email": client_email,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            try:
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                logger.info("✅ Firebase initialized successfully with service account")
                return firestore.client()
            except Exception as e:
                logger.error(f"❌ Firebase initialization failed: {e}")
                return None
                
        elif os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            try:
                firebase_admin.initialize_app()
                logger.info("✅ Firebase initialized with Application Default Credentials")
                return firestore.client()
            except Exception as e:
                logger.error(f"❌ Firebase init with default credentials failed: {e}")
                return None
        else:
            logger.warning("⚠️ Firebase credentials not found. Running without Firebase.")
            return None
    
    # If already initialized
    try:
        return firestore.client()
    except Exception as e:
        logger.error(f"❌ Could not get Firestore client: {e}")
        return None


# Initialize DB
db = initialize_firebase()