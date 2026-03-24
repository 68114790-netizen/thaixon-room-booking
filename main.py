# main.py
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
import database, models, schemas, auth
from jose import jwt, JWTError
import os

# สร้างตารางในฐานข้อมูล
models.Base.metadata.create_all(bind=database.engine)

# ฟังก์ชันนำเข้าห้องประชุมอัตโนมัติ
def init_gtp_rooms():
    db = database.SessionLocal()
    gtp_rooms = [
        "GTP1-Meetingroom1", "GTP1-Meetingroom2", "GTP1-Meetingroom3",
        "GTP2-Meetingroom1", "GTP2-Meetingroom2", "GTP2-Meetingroom3", "GTP2-Trainingroom",
        "GTP3-Meetingroom1", "GTP3-Meetingroom2", "GTP3-Meetingroom3", "GTP3-Trainingroom"
    ]
    if db.query(models.Room).count() == 0:
        for room_name in gtp_rooms:
            db.add(models.Room(room_name=room_name))
        db.commit()
    db.close()

init_gtp_rooms()

app = FastAPI(title="THAIXON Room Booking API")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        username: str = payload.get("sub")
        if username is None: raise credentials_exception
    except JWTError: raise credentials_exception
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None: raise credentials_exception
    return user

# ================= AUTH API =================
@app.post("/register", response_model=schemas.Token)
def register(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    role = "admin" if db.query(models.User).count() == 0 else "user"
    
    # เพิ่มข้อมูล ชื่อ, แผนก, สาขา ลงในฐานข้อมูลตอนสมัคร
    new_user = models.User(
        username=user.username, 
        hashed_password=auth.get_password_hash(user.password), 
        role=role,
        full_name=user.full_name,
        department=user.department,
        plant=user.plant
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"access_token": auth.create_access_token(data={"sub": new_user.username}), "token_type": "bearer"}

@app.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    return {"access_token": auth.create_access_token(data={"sub": user.username}), "token_type": "bearer"}

@app.get("/users/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user

# ================= ROOMS API =================
@app.get("/rooms", response_model=list[schemas.RoomResponse])
def get_rooms(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Room).all()

@app.post("/rooms", response_model=schemas.RoomResponse)
def create_room(room: schemas.RoomCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin": raise HTTPException(status_code=403, detail="Admin only")
    new_room = models.Room(room_name=room.room_name)
    db.add(new_room)
    db.commit()
    db.refresh(new_room)
    return new_room

@app.put("/rooms/{room_id}/toggle")
def toggle_room_status(room_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin": raise HTTPException(status_code=403, detail="Admin only")
    room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not room: raise HTTPException(status_code=404, detail="Room not found")
    room.is_active = not room.is_active
    db.commit()
    return {"detail": "Status updated"}

@app.delete("/rooms/{room_id}")
def delete_room(room_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin": raise HTTPException(status_code=403, detail="Admin only")
    room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not room: raise HTTPException(status_code=404, detail="Room not found")
    db.delete(room)
    db.commit()
    return {"detail": "Room deleted"}

# ================= BOOKINGS API =================
@app.post("/bookings", response_model=schemas.BookingResponse)
def create_booking(booking: schemas.BookingCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    if booking.end_time <= booking.start_time: 
        raise HTTPException(status_code=400, detail="End time must be after start time")
    
    room = db.query(models.Room).filter(models.Room.id == booking.room_id).first()
    if not room or not room.is_active: 
        raise HTTPException(status_code=400, detail="Room is currently under maintenance")
    
    # ดักการจองซ้อนทับ เฉพาะรายการที่สถานะเป็น booked (ไม่นับรายการที่ยกเลิกไปแล้ว)
    if db.query(models.Booking).filter(
        models.Booking.room_id == booking.room_id, models.Booking.status == "booked",
        or_((models.Booking.start_time <= booking.start_time) & (models.Booking.end_time > booking.start_time),
            (models.Booking.start_time < booking.end_time) & (models.Booking.end_time >= booking.end_time),
            (models.Booking.start_time >= booking.start_time) & (models.Booking.end_time <= booking.end_time))
    ).first(): 
        raise HTTPException(status_code=400, detail="Room is already booked during this time")

    new_booking = models.Booking(
        user_id=current_user.id, room_id=booking.room_id, purpose=booking.purpose, 
        start_time=booking.start_time, end_time=booking.end_time
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    return new_booking

@app.get("/bookings", response_model=list[schemas.BookingResponse])
def get_bookings(db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Booking).all()

@app.delete("/bookings/{booking_id}")
def delete_booking(booking_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(get_current_user)):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking: raise HTTPException(status_code=404, detail="Booking not found")
    if current_user.role != "admin" and booking.user_id != current_user.id: 
        raise HTTPException(status_code=403, detail="Not authorized to cancel this booking")
    
    # เปลี่ยนสถานะเป็นยกเลิก (Soft Delete) เพื่อเก็บประวัติ
    booking.status = "cancelled"
    db.commit()
    return {"detail": "Booking cancelled"}

# ================= FRONTEND & STATIC FILES =================
@app.get("/Thaixon_logo.jpg")
def serve_logo():
    if os.path.exists("Thaixon_logo.jpg"): return FileResponse("Thaixon_logo.jpg")
    return HTMLResponse("Logo not found", status_code=404)

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f: return f.read()
    return "<h1>index.html not found</h1>"