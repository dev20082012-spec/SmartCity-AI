import cv2
import time
import requests
import numpy as np
import threading
import argparse
import webbrowser
from datetime import datetime
from ultralytics import YOLO
import uvicorn
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

# Configuration Defaults
API_URL = "http://localhost:8080/api/detections"
CAMERA_ID = "LAPTOP_CAM_1"
LATITUDE = 28.6139
LONGITUDE = 77.2090

ALERT_COOLDOWN = 6  # seconds
YOLO_CONFIDENCE = 0.6
CROWD_THRESHOLD = 4
PORT = 5000

# Global shared state
state = {
    "fps": 0.0,
    "person_count": 0,
    "crowd_detected": False,
    "fire_detected": False,
    "suspicious_objects": 0,
    "recent_alerts": [],
    "last_alert_time": 0,
    "alert_cooldown": ALERT_COOLDOWN,
    "yolo_confidence": YOLO_CONFIDENCE,
    "crowd_threshold": CROWD_THRESHOLD,
    "camera_active": False,
    "camera_source": "Webcam 0",
    "is_fallback": False,
    "backend_online": False,
    "total_alerts_sent": 0
}

latest_frame_jpeg = None
frame_lock = threading.Lock()
running = True

# Initialize YOLO model
print("Loading YOLO model (yolov8n.pt)...")
model = YOLO("yolov8n.pt")


def send_alert_async(threat: str, severity: str, confidence: float):
    """Dispatches alert in a background thread to prevent frame drops."""
    def _worker():
        global state
        now = time.time()
        if now - state["last_alert_time"] < state["alert_cooldown"]:
            return

        state["last_alert_time"] = now
        payload = {
            "cameraId": CAMERA_ID,
            "threatType": threat,
            "severity": severity,
            "confidence": round(float(confidence), 2),
            "latitude": LATITUDE,
            "longitude": LONGITUDE
        }

        alert_record = {
            "id": len(state["recent_alerts"]) + 1,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "threat": threat,
            "severity": severity,
            "confidence": round(float(confidence), 2),
            "status": "SENT"
        }

        try:
            r = requests.post(API_URL, json=payload, timeout=2)
            state["backend_online"] = True
            state["total_alerts_sent"] += 1
            alert_record["status"] = f"HTTP {r.status_code}"
            print(f" [ALERT SENT] {threat} ({severity}) -> {API_URL} [{r.status_code}]")
        except Exception as e:
            state["backend_online"] = False
            alert_record["status"] = "Spring Boot Offline (Logged Locally)"
            print(f" [ALERT LOCAL ONLY] {threat} ({severity}) - Backend unreachable: {e}")

        # Keep last 25 alerts in memory for web UI
        state["recent_alerts"].insert(0, alert_record)
        if len(state["recent_alerts"]) > 25:
            state["recent_alerts"].pop()

    threading.Thread(target=_worker, daemon=True).start()


def detect_fire(frame):
    """Detects fire color signatures in HSV color space."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_fire = np.array([5, 150, 150])
    upper_fire = np.array([35, 255, 255])
    mask = cv2.inRange(hsv, lower_fire, upper_fire)
    fire_pixels = cv2.countNonZero(mask)
    return fire_pixels > 7000


def create_simulation_frame(counter: int):
    """Creates a high-tech synthetic frame if physical camera is inaccessible."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Gradient backdrop
    for y in range(480):
        frame[y, :] = (int(15 + y * 0.05), int(20 + y * 0.06), int(30 + y * 0.07))

    # Grid overlay
    for x in range(0, 640, 40):
        cv2.line(frame, (x, 0), (x, 480), (35, 45, 55), 1)
    for y in range(0, 480, 40):
        cv2.line(frame, (0, y), (640, y), (35, 45, 55), 1)

    # Simulated targets moving
    x_pos = int(280 + 140 * np.sin(counter * 0.04))
    y_pos = int(220 + 70 * np.cos(counter * 0.04))
    
    cv2.rectangle(frame, (x_pos - 40, y_pos - 70), (x_pos + 40, y_pos + 70), (0, 255, 128), 2)
    cv2.putText(frame, "SIMULATED PERSON 0.89", (x_pos - 40, y_pos - 78),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 128), 1)

    cv2.putText(frame, "NO HARDWARE WEBCAM DETECTED - SIMULATION MODE ACTIVE", (30, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 2)
    cv2.putText(frame, f"TARGET RADAR: ({x_pos}, {y_pos})", (30, 70),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1)
    return frame


def video_processing_loop(show_gui: bool = False):
    """Background worker thread capturing frames, running YOLO and fire detection."""
    global latest_frame_jpeg, running, state
    
    print("Opening camera feed (index 0)...")
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    camera_opened = cap.isOpened()
    if camera_opened:
        ret, test_frame = cap.read()
        if not ret or test_frame is None:
            camera_opened = False
            cap.release()

    state["camera_active"] = camera_opened
    state["is_fallback"] = not camera_opened

    if camera_opened:
        print(" Camera 0 connected successfully.")
    else:
        print(" Camera 0 not available or access denied. Running in High-Fidelity Simulation Stream mode.")

    fps_timer = time.time()
    frame_count = 0
    sim_counter = 0

    while running:
        if camera_opened:
            ret, frame = cap.read()
            if not ret or frame is None:
                frame = create_simulation_frame(sim_counter)
                sim_counter += 1
        else:
            frame = create_simulation_frame(sim_counter)
            sim_counter += 1

        # Fire Detection
        fire_active = detect_fire(frame)
        state["fire_detected"] = fire_active
        if fire_active:
            send_alert_async("FIRE", "CRITICAL", 0.95)
            cv2.rectangle(frame, (10, 10), (630, 470), (0, 0, 255), 4)
            cv2.putText(frame, " CRITICAL: FIRE DETECTED ", (30, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 255), 3)

        # YOLO Inference
        conf_thresh = state["yolo_confidence"]
        results = model(frame, imgsz=320, conf=conf_thresh, verbose=False)[0]
        annotated = results.plot()

        person_count = 0
        suspicious_count = 0

        for box in results.boxes:
            cls = int(box.cls[0])
            label = model.names[cls]
            conf = float(box.conf[0])

            if label == "person":
                person_count += 1

            if label in ["backpack", "handbag"] and conf > 0.75:
                suspicious_count += 1
                send_alert_async("SUSPICIOUS_OBJECT", "HIGH", conf)

        state["person_count"] = person_count
        state["suspicious_objects"] = suspicious_count

        # Crowd Panic Detection
        crowd_thresh = state["crowd_threshold"]
        is_crowd = person_count >= crowd_thresh
        state["crowd_detected"] = is_crowd
        if is_crowd:
            send_alert_async("CROWD_PANIC", "HIGH", 0.90)
            cv2.putText(annotated, f" ALERT: CROWD PANIC ({person_count} PERSONS)", (30, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 165, 255), 3)

        # HUD Overlay on frame
        cv2.putText(annotated, f"FPS: {state['fps']:.1f} | CAM: {CAMERA_ID}", (15, 465),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 200), 2)
        cv2.putText(annotated, f"PERSONS: {person_count} | FIRE: {'YES' if fire_active else 'NO'}", (15, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        # Calculate FPS
        frame_count += 1
        now = time.time()
        elapsed = now - fps_timer
        if elapsed >= 1.0:
            state["fps"] = round(frame_count / elapsed, 1)
            frame_count = 0
            fps_timer = now

        # Encode JPEG for web streaming
        ret_enc, jpeg_bytes = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ret_enc:
            with frame_lock:
                latest_frame_jpeg = jpeg_bytes.tobytes()

        # Optional Desktop Window if --gui is passed
        if show_gui:
            cv2.imshow("SmartCity AI - Live Feed", annotated)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                running = False
                break

        # Brief sleep to pace capture loop if running synthetic feed
        if not camera_opened:
            time.sleep(0.04)

    if camera_opened:
        cap.release()
    if show_gui:
        cv2.destroyAllWindows()
    print("Video processing thread stopped.")


# FastAPI Application Setup
app = FastAPI(title="SmartCity AI Live Feed", version="2.0")


def generate_frames():
    """Generator yielding MJPEG multipart stream for <img> tag."""
    while running:
        with frame_lock:
            frame_data = latest_frame_jpeg

        if frame_data is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
        time.sleep(0.033)  # ~30 FPS max streaming


@app.get("/video_feed")
def video_feed():
    """Endpoint serving real-time video stream."""
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/stats")
def get_stats():
    """Real-time detection statistics and active telemetry."""
    return JSONResponse(state)


class ConfigUpdate(BaseModel):
    yolo_confidence: float | None = None
    crowd_threshold: int | None = None
    alert_cooldown: float | None = None


@app.post("/api/config")
def update_config(cfg: ConfigUpdate):
    """Dynamically adjust detection thresholds."""
    if cfg.yolo_confidence is not None:
        state["yolo_confidence"] = max(0.1, min(1.0, cfg.yolo_confidence))
    if cfg.crowd_threshold is not None:
        state["crowd_threshold"] = max(1, min(50, cfg.crowd_threshold))
    if cfg.alert_cooldown is not None:
        state["alert_cooldown"] = max(1.0, min(60.0, cfg.alert_cooldown))
    return JSONResponse({"status": "updated", "config": {
        "yolo_confidence": state["yolo_confidence"],
        "crowd_threshold": state["crowd_threshold"],
        "alert_cooldown": state["alert_cooldown"]
    }})


class TestAlertRequest(BaseModel):
    threat: str
    severity: str
    confidence: float = 0.95


@app.post("/api/trigger_test_alert")
def trigger_test_alert(req: TestAlertRequest):
    """Manually dispatch a test incident to Spring Boot & UI."""
    send_alert_async(req.threat, req.severity, req.confidence)
    return JSONResponse({"message": f"Test alert '{req.threat}' queued successfully."})


HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SmartCity AI - Live Detection Command Center</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #07090e;
            --bg-card: rgba(15, 23, 42, 0.75);
            --bg-card-border: rgba(255, 255, 255, 0.08);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-cyan: #06b6d4;
            --accent-emerald: #10b981;
            --accent-amber: #f59e0b;
            --accent-rose: #ef4444;
            --glow-rose: 0 0 25px rgba(239, 68, 68, 0.35);
            --glow-cyan: 0 0 25px rgba(6, 182, 212, 0.3);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
            background: var(--bg-base);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
            background-image: 
                radial-gradient(circle at 15% 15%, rgba(6, 182, 212, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 85% 85%, rgba(239, 68, 68, 0.06) 0%, transparent 40%);
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 28px;
            background: rgba(10, 15, 29, 0.85);
            backdrop-filter: blur(14px);
            border-bottom: 1px solid var(--bg-card-border);
            position: sticky;
            top: 0;
            z-index: 50;
        }

        .brand-badge {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .pulse-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--accent-emerald);
            box-shadow: 0 0 10px var(--accent-emerald);
            animation: pulse 1.8s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.8; }
            50% { transform: scale(1.3); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.8; }
        }

        .brand-title {
            font-size: 19px;
            font-weight: 700;
            letter-spacing: -0.3px;
            background: linear-gradient(135deg, #ffffff 40%, var(--accent-cyan));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .status-pill {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            font-weight: 600;
            padding: 6px 14px;
            border-radius: 9999px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--bg-card-border);
        }

        .btn-link {
            text-decoration: none;
            color: #ffffff;
            background: linear-gradient(135deg, #0284c7, #0369a1);
            font-size: 12px;
            font-weight: 600;
            padding: 7px 16px;
            border-radius: 8px;
            transition: all 0.2s;
            border: none;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .btn-link:hover {
            transform: translateY(-1px);
            box-shadow: var(--glow-cyan);
        }

        .dashboard-container {
            display: grid;
            grid-template-columns: 1fr 380px;
            gap: 22px;
            padding: 24px 28px;
            max-width: 1680px;
            margin: 0 auto;
        }

        @media (max-width: 1100px) {
            .dashboard-container {
                grid-template-columns: 1fr;
            }
        }

        .video-card {
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--bg-card-border);
            border-radius: 16px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.4);
        }

        .video-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 14px 20px;
            border-bottom: 1px solid var(--bg-card-border);
            background: rgba(15, 23, 42, 0.5);
        }

        .video-wrapper {
            position: relative;
            background: #000;
            aspect-ratio: 4 / 3;
            max-height: 580px;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }

        .video-stream {
            width: 100%;
            height: 100%;
            object-fit: contain;
        }

        .live-tag {
            position: absolute;
            top: 16px;
            left: 16px;
            display: flex;
            align-items: center;
            gap: 7px;
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(8px);
            color: #ff3344;
            padding: 5px 12px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
            border: 1px solid rgba(255, 51, 68, 0.3);
        }

        .live-tag .dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #ff3344;
            animation: pulse 1s infinite;
        }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 14px;
            padding: 18px 20px;
            background: rgba(10, 15, 29, 0.4);
            border-top: 1px solid var(--bg-card-border);
        }

        @media (max-width: 768px) {
            .metrics-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        .metric-item {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--bg-card-border);
            border-radius: 10px;
            padding: 12px 14px;
        }

        .metric-title {
            font-size: 11px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }

        .metric-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 22px;
            font-weight: 700;
            display: flex;
            align-items: baseline;
            gap: 6px;
        }

        .metric-status {
            font-size: 12px;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 4px;
        }

        .status-safe { background: rgba(16, 185, 129, 0.15); color: #10b981; }
        .status-danger { background: rgba(239, 68, 68, 0.2); color: #ef4444; animation: pulse 1s infinite; }
        .status-warn { background: rgba(245, 158, 11, 0.2); color: #f59e0b; }

        .sidebar {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        .panel-card {
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--bg-card-border);
            border-radius: 16px;
            padding: 18px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
        }

        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
            font-size: 14px;
            font-weight: 700;
        }

        .control-group {
            margin-bottom: 14px;
        }

        .control-label {
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }

        .slider {
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
            outline: none;
            -webkit-appearance: none;
        }

        .slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: var(--accent-cyan);
            cursor: pointer;
            box-shadow: 0 0 10px var(--accent-cyan);
        }

        .btn-test {
            width: 100%;
            padding: 9px 12px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            border: 1px solid rgba(255, 255, 255, 0.1);
            background: rgba(255, 255, 255, 0.05);
            color: #fff;
            cursor: pointer;
            transition: all 0.15s;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }

        .btn-test:hover {
            background: rgba(255, 255, 255, 0.12);
        }

        .btn-fire { border-color: rgba(239, 68, 68, 0.4); color: #fca5a5; }
        .btn-fire:hover { background: rgba(239, 68, 68, 0.2); }

        .btn-crowd { border-color: rgba(245, 158, 11, 0.4); color: #fde68a; }
        .btn-crowd:hover { background: rgba(245, 158, 11, 0.2); }

        .alerts-feed {
            max-height: 270px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .alerts-feed::-webkit-scrollbar {
            width: 5px;
        }
        .alerts-feed::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }

        .alert-item {
            background: rgba(255, 255, 255, 0.03);
            border-left: 3px solid #64748b;
            padding: 9px 12px;
            border-radius: 6px;
            font-size: 12px;
            display: flex;
            flex-direction: column;
            gap: 3px;
        }

        .alert-item.CRITICAL { border-left-color: var(--accent-rose); background: rgba(239, 68, 68, 0.08); }
        .alert-item.HIGH { border-left-color: var(--accent-amber); background: rgba(245, 158, 11, 0.08); }

        .alert-top {
            display: flex;
            justify-content: space-between;
            font-weight: 600;
        }

        .alert-time {
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            color: var(--text-secondary);
        }

        .alert-status {
            font-size: 10px;
            color: #94a3b8;
        }

        .empty-placeholder {
            text-align: center;
            color: var(--text-secondary);
            font-size: 12px;
            padding: 24px 0;
        }
    </style>
</head>
<body>

    <header>
        <div class="brand-badge">
            <div class="pulse-dot"></div>
            <div>
                <div class="brand-title">SmartCity AI • Vision Stream</div>
                <div style="font-size: 11px; color: var(--text-secondary);">Autonomous Threat & Surveillance Engine</div>
            </div>
        </div>

        <div class="header-actions">
            <div class="status-pill">
                <span id="backendStatusDot" style="width: 8px; height: 8px; border-radius: 50%; background: #64748b;"></span>
                <span id="backendStatusText">Backend Checking...</span>
            </div>
            <a href="http://localhost:8080" target="_blank" class="btn-link">
                <span>🗺️ Incident Map</span>
            </a>
        </div>
    </header>

    <main class="dashboard-container">
        <!-- Main Video Card -->
        <div class="video-card">
            <div class="video-header">
                <div style="font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 8px;">
                    <span>📹</span>
                    <span id="camSourceTitle">LAPTOP_CAM_1 • Primary Detection Feed</span>
                </div>
                <div style="font-size: 12px; font-family: 'JetBrains Mono', monospace; color: var(--accent-cyan);" id="fpsDisplay">
                    -- FPS
                </div>
            </div>

            <div class="video-wrapper">
                <div class="live-tag">
                    <span class="dot"></span>
                    <span>LIVE AI RECOGNITION</span>
                </div>
                <img id="streamImg" src="/video_feed" class="video-stream" alt="AI Live Stream" />
            </div>

            <div class="metrics-grid">
                <div class="metric-item">
                    <div class="metric-title">👥 Detected Persons</div>
                    <div class="metric-value">
                        <span id="personCount">0</span>
                        <span id="crowdBadge" class="metric-status status-safe">NORMAL</span>
                    </div>
                </div>

                <div class="metric-item">
                    <div class="metric-title">🔥 Thermal / Fire</div>
                    <div class="metric-value">
                        <span id="fireBadge" class="metric-status status-safe">CLEAR</span>
                    </div>
                </div>

                <div class="metric-item">
                    <div class="metric-title">🎒 Suspicious Bags</div>
                    <div class="metric-value">
                        <span id="suspiciousCount">0</span>
                    </div>
                </div>

                <div class="metric-item">
                    <div class="metric-title">📡 Alerts Dispatched</div>
                    <div class="metric-value">
                        <span id="totalAlerts">0</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Sidebar Controls & Logs -->
        <div class="sidebar">
            <!-- Controls Card -->
            <div class="panel-card">
                <div class="panel-header">
                    <span>⚙️ Detection Thresholds</span>
                </div>

                <div class="control-group">
                    <div class="control-label">
                        <span>YOLO Confidence</span>
                        <span id="confVal">60%</span>
                    </div>
                    <input type="range" min="20" max="95" value="60" class="slider" id="confSlider" oninput="updateConfidence(this.value)">
                </div>

                <div class="control-group">
                    <div class="control-label">
                        <span>Crowd Panic Threshold</span>
                        <span id="crowdVal">4 Persons</span>
                    </div>
                    <input type="range" min="2" max="15" value="4" class="slider" id="crowdSlider" oninput="updateCrowdThresh(this.value)">
                </div>

                <div style="margin-top: 16px;">
                    <div class="control-label" style="margin-bottom: 8px;">
                        <span>Simulate Manual Trigger</span>
                    </div>
                    <button class="btn-test btn-fire" onclick="triggerAlert('FIRE', 'CRITICAL', 0.98)">
                        🔥 Test Fire Alert
                    </button>
                    <button class="btn-test btn-crowd" onclick="triggerAlert('CROWD_PANIC', 'HIGH', 0.90)">
                        ⚠️ Test Crowd Panic Alert
                    </button>
                    <button class="btn-test" onclick="triggerAlert('SUSPICIOUS_OBJECT', 'HIGH', 0.85)">
                        🎒 Test Unattended Luggage
                    </button>
                </div>
            </div>

            <!-- Live Alert Feed -->
            <div class="panel-card" style="flex: 1;">
                <div class="panel-header">
                    <span>🚨 Live Alert Log</span>
                    <span style="font-size: 11px; font-weight: normal; color: var(--text-secondary);">Real-time</span>
                </div>
                <div class="alerts-feed" id="alertsList">
                    <div class="empty-placeholder">No alerts triggered yet</div>
                </div>
            </div>
        </div>
    </main>

    <script>
        async function fetchStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();

                document.getElementById('fpsDisplay').innerText = data.fps + ' FPS';
                document.getElementById('personCount').innerText = data.person_count;
                document.getElementById('suspiciousCount').innerText = data.suspicious_objects;
                document.getElementById('totalAlerts').innerText = data.total_alerts_sent;

                // Crowd Status
                const crowdBadge = document.getElementById('crowdBadge');
                if (data.crowd_detected) {
                    crowdBadge.innerText = 'CROWD ALERT';
                    crowdBadge.className = 'metric-status status-danger';
                } else {
                    crowdBadge.innerText = 'NORMAL';
                    crowdBadge.className = 'metric-status status-safe';
                }

                // Fire Status
                const fireBadge = document.getElementById('fireBadge');
                if (data.fire_detected) {
                    fireBadge.innerText = '🔥 FIRE DETECTED';
                    fireBadge.className = 'metric-status status-danger';
                } else {
                    fireBadge.innerText = 'CLEAR';
                    fireBadge.className = 'metric-status status-safe';
                }

                // Backend Status
                const dot = document.getElementById('backendStatusDot');
                const text = document.getElementById('backendStatusText');
                if (data.backend_online) {
                    dot.style.background = '#10b981';
                    text.innerText = 'Spring Boot (8080) Online';
                } else {
                    dot.style.background = '#f59e0b';
                    text.innerText = 'Spring Boot Offline (Local Cache)';
                }

                // Render Alerts
                const container = document.getElementById('alertsList');
                if (data.recent_alerts && data.recent_alerts.length > 0) {
                    container.innerHTML = data.recent_alerts.map(a => `
                        <div class="alert-item ${a.severity}">
                            <div class="alert-top">
                                <span>${a.threat}</span>
                                <span class="alert-time">${a.timestamp}</span>
                            </div>
                            <div class="alert-status">Conf: ${(a.confidence * 100).toFixed(0)}% • ${a.status}</div>
                        </div>
                    `).join('');
                }
            } catch (e) {
                console.error("Stats poll failed", e);
            }
        }

        async function updateConfidence(val) {
            document.getElementById('confVal').innerText = val + '%';
            await fetch('/api/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({yolo_confidence: val / 100.0})
            });
        }

        async function updateCrowdThresh(val) {
            document.getElementById('crowdVal').innerText = val + ' Persons';
            await fetch('/api/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({crowd_threshold: parseInt(val)})
            });
        }

        async function triggerAlert(threat, severity, confidence) {
            try {
                await fetch('/api/trigger_test_alert', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({threat, severity, confidence})
                });
                fetchStats();
            } catch (err) {
                alert("Failed to send test alert: " + err);
            }
        }

        // Poll stats every second
        setInterval(fetchStats, 1000);
        fetchStats();
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    """Serves the SmartCity AI Web Dashboard."""
    return HTMLResponse(content=HTML_DASHBOARD)


def open_browser_delayed(url: str, delay: float = 1.2):
    """Opens browser automatically after server boots."""
    def _open():
        time.sleep(delay)
        print(f"\n🚀 Opening web interface at {url}")
        webbrowser.open(url)
    threading.Thread(target=_open, daemon=True).start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SmartCity AI Live Feed & Detection")
    parser.add_argument("--gui", action="store_true", help="Also display local OpenCV cv2.imshow window")
    parser.add_argument("--port", type=int, default=PORT, help=f"Web server port (default {PORT})")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch web browser")
    args = parser.parse_args()

    # Start video processing loop in background thread
    t_video = threading.Thread(target=video_processing_loop, args=(args.gui,), daemon=True)
    t_video.start()

    # Launch browser automatically
    web_url = f"http://localhost:{args.port}"
    if not args.no_browser:
        open_browser_delayed(web_url)

    print(f"\n=======================================================")
    print(f" 🏙️  SmartCity AI Web Streaming Server Started")
    print(f" 🌐  Dashboard URL : {web_url}")
    print(f" 📹  Video Stream  : {web_url}/video_feed")
    print(f" 📡  Alert API     : {API_URL}")
    print(f"=======================================================\n")

    try:
        uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")
    except KeyboardInterrupt:
        print("\nShutting down SmartCity AI...")
    finally:
        running = False
