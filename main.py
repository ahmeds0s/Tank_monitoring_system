import requests
import asyncio
from requests.auth import HTTPBasicAuth
from fastapi import (
    FastAPI,
    Request,
    Form,
    Depends,
    Response,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from auth import authenticate_user, create_access_token, decode_token
from datetime import timedelta
from db import init_db, insert_sensor_data
from fastapi.templating import Jinja2Templates
import sqlite3


@asynccontextmanager
async def lifespan(app: FastAPI):
    global dashboard_open
    print("starting collecting data offline")
    task = asyncio.create_task(collecting_data())
    yield

    print("app shutting down")
    await task


app = FastAPI(lifespan=lifespan)
dashboard_open = False


@app.on_event("startup")
def startup():
    init_db()


async def collecting_data():
    while True:
        if not dashboard_open:
            get_data_from_ard(1)
            print("collecting data.......")
            await asyncio.sleep(0.5)
            get_data_from_ard(2)
            await asyncio.sleep(1)
        await asyncio.sleep(1)


templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


####          database ###


@app.get("/api/history")
async def get_history(limit: int = 10, sensor_id: int = 1):
    with sqlite3.connect("sensor_data.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT sensor_id, tank_level, system_status, timestamp
            FROM sensor_data
            WHERE sensor_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (sensor_id, limit),
        )
        rows = cursor.fetchall()
        print(sensor_id, rows, "\n")
        return JSONResponse(
            content=[
                {
                    "sensor_id": r[0],
                    "tank_level": r[1],
                    "system_status": r[2],
                    "timestamp": r[3],
                }
                for r in rows
            ]
        )


templates = Jinja2Templates(directory="templates")


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    return templates.TemplateResponse("history.html", {"request": request})


@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if not authenticate_user(username, password):
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid credentials"}
        )

    token = create_access_token(
        data={"sub": username}, expires_delta=timedelta(minutes=30)
    )
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(key="access_token", value=token, httponly=True)
    return response


### favicon ######################
# Serve static files (icons, manifest, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")


# Optional: Direct mappings for root-level icon URLs
@app.get("/apple-touch-icon.png")
async def apple_icon():
    print("send apple icon")
    return FileResponse("static/apple-touch-icon.png")


@app.get("/favicon-32x32.png")
async def favicon_32():
    return FileResponse("static/favicon-32x32.png")


@app.get("/favicon-16x16.png")
async def favicon_16():
    return FileResponse("static/favicon-16x16.png")


@app.get("/site.webmanifest")
async def manifest():
    return FileResponse("static/site.webmanifest")


@app.get("/favicon.ico")
async def favicon():
    return FileResponse("static/favicon.ico")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    global dashboard_open
    dashboard_open = True
    token = request.cookies.get("access_token")
    if not token or not decode_token(token):
        return RedirectResponse(url="/")
    data = get_data_from_ard(1)

    """  json += "\"Sensor ID\":\"" + String("1") + "\",";
  json += "\"Timestamp\":\"" + String("20:25") + "\",";
  json += "\"Tank level\":" + String(get_sensor_data()) + ",";
  json += "\"Status\":\"" + String("OK") + "\"";
  json += "}";
"""

    data = {
        "title": "System Dashboard",
        "stats": {
            "tank_level": data["Tank level"],
            "update_time": str(timedelta(seconds=int(data["Timestamp"]) / 1000)),
            "system_status": data["Status"],
        },
    }
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "data": data}
    )


@app.get("/api/data")
async def get_data(sensor_id: int):
    # Simulate changing values
    data = get_data_from_ard(sensor_id)
    data = {
        "title": "System Dashboard",
        "stats": {
            "tank_level": data["Tank level"],
            "update_time": str(timedelta(seconds=int(data["Timestamp"]) / 1000)),
            "system_status": data["Status"],
        },
    }
    return data


# using websocket instead of fetch update
@app.websocket("/ws/data/{sensor_id}")
async def websocket_endpoint(websocket: WebSocket, sensor_id: int):
    await websocket.accept()
    try:
        while True:
            data = get_data_from_ard(sensor_id)

            payload = {
                "sensor_id": sensor_id,
                "tank_level": data["Tank level"],
                "update_time": str(timedelta(seconds=int(data["Timestamp"]) / 1000)),
                "system_status": data["Status"],
                "Timestamp": data.get("Timestamp"),  # Optional
            }

            await websocket.send_json(payload)
            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        print(f"Client disconnected from sensor {sensor_id}")
        global dashboard_open
        dashboard_open = False


# IP of the Arduino
arduino_ip = "192.168.2.177"
port = 80

# Auth credentials from Arduino sketch
username = "user"
password = "secret"

# The path used in the Arduino sketch (can be customized as needed)
url = f"http://{arduino_ip}:{port}/api/sensors/"


# Send PUT request
def get_data_from_ard(sensor_id: int):
    try:
        response = requests.post(
            url + str(sensor_id), auth=HTTPBasicAuth(username, password)
        )

        print("Status Code:", response.status_code)
        print("Response Text:")
        data = response.json()
        print(data)

    except requests.exceptions.RequestException as e:
        print("Error communicating with Arduino:")
        print(e)
        data = {
            "Sensor ID": "1",
            "Timestamp": "0",
            "Tank level": -1,
            "Status": "inaccessable",
        }
        return data

    insert_sensor_data(data["Sensor ID"], data["Tank level"], data["Status"])

    return data
