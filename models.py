from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")  # "admin" or "user"
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    media = relationship("Media", back_populates="uploader", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")

class Church(Base):
    __tablename__ = "churches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    address = Column(String, nullable=True)
    map_link = Column(String, nullable=True)
    contact = Column(String, nullable=True)
    timings = Column(String, nullable=True)
    about = Column(Text, nullable=True)
    cover_image = Column(String, nullable=True)  # Path to image
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    media = relationship("Media", back_populates="church", cascade="all, delete-orphan")

class FounderProfile(Base):
    __tablename__ = "founder_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="కొనగంటి ప్రకాష్బాబు గారు")
    about = Column(Text, nullable=True)
    birth_date = Column(String, nullable=True)
    death_date = Column(String, nullable=True)
    highlights = Column(Text, nullable=True)  # Bullet points or key milestones
    photo = Column(String, nullable=True)

class PastorProfile(Base):
    __tablename__ = "pastor_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    role = Column(String, default="Pastor")
    about = Column(Text, nullable=True)
    message = Column(Text, nullable=True)  # Pastor's message to the congregation
    photo = Column(String, nullable=True)

class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(Integer, ForeignKey("churches.id"), nullable=False)
    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # "image" or "video"
    status = Column(String, default="pending")  # "approved", "pending", "rejected"
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    church = relationship("Church", back_populates="media")
    uploader = relationship("User", back_populates="media")

class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    youtube_link = Column(String, nullable=True)
    hero_title = Column(String, default="Welcome to Calvary Gospel Prayer Fellowship")
    hero_subtitle = Column(String, default="Experience the blessings and grace of our Lord Jesus Christ")
    contact_phone = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)  # e.g., "created_church", "uploaded_media"
    target_type = Column(String, nullable=False)  # e.g., "church", "media"
    target_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="audit_logs")
