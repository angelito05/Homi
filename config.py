import os
from dotenv import load_dotenv

load_dotenv()

SESSION_COOKIE_HTTPONLY = True  # Evita que JavaScript acceda a la cookie (protección XSS)
SESSION_COOKIE_SECURE = False    # Solo envía cookies sobre HTTPS (requiere certificado SSL)
SESSION_COOKIE_SAMESITE = 'Lax' # Protección adicional contra CSRF

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecretke291762y")
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://Angelito:Angelito05@cluster0.ifetmab.mongodb.net/")
    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "dgijgaoyp")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "367923394437628")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "Q3Lj95oGK2FXaKUu_dfo-j5cNLI")