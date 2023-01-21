import os

from sqlalchemy.ext.declarative import declarative_base

SQLALCHEMY_DATABASE_URL = os.getenv("DB_URI") or "sqlite+aiosqlite:///"

Base = declarative_base()
