import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecretke291762y")
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://Angelito:Angelito05@cluster0.ifetmab.mongodb.net/")