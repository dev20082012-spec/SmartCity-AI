import cv2
import time
import requests
import numpy as np
from ultralytics import YOLO

# backend url thingy
API_URL = "http://localhost:8080/api/detections"
CAMERA_ID = "LAPTOP_CAM_1"

# delhi coordinates i guess
LATITUDE = 28.6139
LONGITUDE = 77.2090

# cooldown otherwise backend gets spammed to death lol
ALERT_COOLDOWN = 6
YOLO_CONFIDENCE = 0.6
CROWD_THRESHOLD = 4

print("Loading YOLO model...")
model = YOLO("yolov8n.pt")

print("Opening laptop camera...")
cap = cv2.VideoCapture(0)

# setting webcam resolution hope it doesnt lag
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

last_alert_time = 0

# send alert to spring boot pls work
def send_alert(threat, severity, confidence):
    global last_alert_time
    # skip if sent recently
    if time.time() - last_alert_time < ALERT_COOLDOWN:
        return

    payload = {
        "cameraId": CAMERA_ID,
        "threatType": threat,
        "severity": severity,
        "confidence": float(confidence),
        "latitude": LATITUDE,
        "longitude": LONGITUDE
    }

    try:
        r = requests.post(API_URL, json=payload, timeout=3)
        print(f" ALERT SENT: {threat} | {r.status_code}")
        last_alert_time = time.time()
    except Exception as e:
        # server probably offline again
        print(" Alert failed:", e)

# basic color masking for fire idk works okay
def detect_fire(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    lower_fire = np.array([5, 150, 150])
    upper_fire = np.array([35, 255, 255])

    mask = cv2.inRange(hsv, lower_fire, upper_fire)
    fire_pixels = cv2.countNonZero(mask)

    # if lots of orange red pixels then big fire
    return fire_pixels > 7000

print(" SmartCity AI running (Press Q to quit)")

# main loop dont touch
while True:
    ret, frame = cap.read()
    if not ret:
        print(" Camera not accessible")
        break

    if detect_fire(frame):
        send_alert("FIRE", "CRITICAL", 0.95)
        cv2.putText(frame, " FIRE DETECTED", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

    # run yolo magic here
    results = model(frame, imgsz=320, conf=YOLO_CONFIDENCE, verbose=False)[0]
    annotated = results.plot()

    person_count = 0

    for box in results.boxes:
        cls = int(box.cls[0])
        label = model.names[cls]
        conf = float(box.conf[0])

        if label == "person":
            person_count += 1

        # bag left alone maybe bomb who knows
        if label in ["backpack", "handbag"] and conf > 0.75:
            send_alert("SUSPICIOUS_OBJECT", "HIGH", conf)

    # too many humans in one spot
    if person_count >= CROWD_THRESHOLD:
        send_alert("CROWD_PANIC", "HIGH", 0.90)
        cv2.putText(annotated, "⚠ CROWD DETECTED", (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 165, 255), 3)

    cv2.imshow("SmartCity AI - Live Feed", annotated)

    # press q to stop everything
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("System stopped.")
