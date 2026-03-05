import os
from dotenv import load_dotenv

load_dotenv()

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True  
SESSION_COOKIE_SAMESITE = 'Lax' 

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    MONGODB_URI = os.getenv("MONGODB_URI")
    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")