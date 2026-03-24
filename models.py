# models.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    # --- ข้อมูลที่เพิ่มเข้ามาใหม่ ---
    full_name = Column(String, default="")
    department = Column(String, default="")
    plant = Column(String, default="")
    # ---------------------------
    
    role = Column(String, default="user")

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True, index=True)
    room_name = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    room_id = Column(Integer, ForeignKey("rooms.id"))
    purpose = Column(String, default="")
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    status = Column(String, default="booked")

    user = relationship("User")
    room = relationship("Room")