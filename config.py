import os
from dotenv import load_dotenv

load_dotenv()

SESSION_COOKIE_HTTPONLY = True  # Evita que JavaScript acceda a la cookie (protección XSS)
SESSION_COOKIE_SECURE = False    # Solo envía cookies sobre HTTPS (requiere certificado SSL)
SESSION_COOKIE_SAMESITE = 'Lax' # Protección adicional contra CSRF

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecretke291762y")
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://Angelito:Angelito05@cluster0.ifetmab.mongodb.net/")