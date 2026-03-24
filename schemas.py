# schemas.py
from pydantic import BaseModel
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str     # เพิ่ม
    department: str    # เพิ่ม
    plant: str         # เพิ่ม

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str     # เพิ่ม
    department: str    # เพิ่ม
    plant: str         # เพิ่ม
    role: str
    class Config:
        from_attributes = True

class RoomCreate(BaseModel):
    room_name: str

class RoomResponse(BaseModel):
    id: int
    room_name: str
    is_active: bool
    class Config:
        from_attributes = True

class BookingCreate(BaseModel):
    room_id: int
    purpose: str
    start_time: datetime
    end_time: datetime

class BookingResponse(BaseModel):
    id: int
    room_id: int
    user_id: int
    purpose: str
    start_time: datetime
    end_time: datetime
    status: str
    user: UserResponse  # <--- เคล็ดลับ: สั่งให้ดึงข้อมูล User ออกมาพร้อมกับการจองเลย!
    class Config:
        from_attributes = True