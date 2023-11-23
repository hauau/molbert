import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import SQLALCHEMY_DATABASE_URL, DEBUG_SQL

engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=DEBUG_SQL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
