import os
from dotenv import load_dotenv

load_dotenv()

SESSION_COOKIE_HTTPONLY = False
SESSION_COOKIE_SECURE = True  
SESSION_COOKIE_SAMESITE = 'Lax' 

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecretke291762y")
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://Angelito:Angelito05@cluster0.ifetmab.mongodb.net/")
    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "dgijgaoyp")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "367923394437628")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "Q3Lj95oGK2FXaKUu_dfo-j5cNLI")