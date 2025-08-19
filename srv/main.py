from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio, time

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

# stare in-memory
stations = {}  # id -> dict(status, power, energy, online)
clients_ws = {}  # id -> set(websockets)
rfid_whitelist = {"04A1B2C3D4": "Camera 203", "DEADBEEF01": "Admin"}

class LoginReq(BaseModel):
    email: str
    password: str

class CommandReq(BaseModel):
    action: str  # "start"|"stop"
    limit_kW: float | None = None

class RFIDReq(BaseModel):
    uid: str

@app.get("/health")
def health():
    return {"ok": True, "ts": time.time()}

@app.post("/login")
def login(body: LoginReq):
    # simplu pentru MVP
    if body.email and body.password:
        return {"token": "demo-token", "role": "admin"}
    return {"error": "invalid"}

@app.get("/station/{sid}/status")
def status(sid: str):
    st = stations.get(sid, {"online": True, "power": 0.0, "energy": 0.0, "status": "idle"})
    stations[sid] = st
    return st

@app.post("/station/{sid}/command")
def command(sid: str, body: CommandReq):
    st = stations.setdefault(sid, {"online": True, "power": 0.0, "energy": 0.0, "status": "idle"})
    if body.action == "start":
        st["status"] = "charging"
        if body.limit_kW: st["limit_kW"] = body.limit_kW
    elif body.action == "stop":
        st["status"] = "stopped"
        st["power"] = 0.0
    return {"ok": True, "status": st}

@app.post("/rfid/check")
def rfid_check(body: RFIDReq):
    label = rfid_whitelist.get(body.uid.upper())
    return {"allowed": bool(label), "label": label or ""}

@app.websocket("/ws/station/{sid}")
async def ws_station(websocket: WebSocket, sid: str):
    await websocket.accept()
    clients_ws.setdefault(sid, set()).add(websocket)
    try:
        while True:
            # trimite stare la fiecare 1s (mock)
            st = stations.setdefault(sid, {"online": True, "power": 0.0, "energy": 0.0, "status": "idle"})
            if st.get("status") == "charging":
                st["power"] = st.get("limit_kW", 7.0)
                st["energy"] = st.get("energy", 0.0) + st["power"] / 3600.0
            await websocket.send_json({"sid": sid, **st})
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    finally:
        clients_ws[sid].discard(websocket)
