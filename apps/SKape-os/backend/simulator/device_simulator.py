import math
import os
import random
import time
from datetime import datetime

import requests


# ============================================================
# SKape Device Simulator
# ============================================================

BACKEND_URL = os.getenv(
    "SKAPE_BACKEND_URL",
    "http://127.0.0.1:8000",
)

# ------------------------------------------------------------
# Device identity
# ------------------------------------------------------------

DEVICE_ID = os.getenv(
    "SKAPE_DEVICE_ID",
    "SKAPE-TEST-002",
)

# Database primary-key ID of the device
DEVICE_DB_ID = int(
    os.getenv(
        "SKAPE_DEVICE_DB_ID",
        "5",
    )
)

# ------------------------------------------------------------
# Intervals
# ------------------------------------------------------------

HEARTBEAT_INTERVAL = 10
TELEMETRY_INTERVAL = 5


# ============================================================
# DEVICE CREDENTIALS
# ============================================================

DEVICE_SECRET = os.getenv(
    "SKAPE_DEVICE_SECRET",
    "",
)


# ============================================================
# VALIDATE CONFIGURATION
# ============================================================

def validate_configuration():
    print("=" * 65)
    print("SKape Device Simulator")
    print("=" * 65)
    print(f"Backend:            {BACKEND_URL}")
    print(f"Device:             {DEVICE_ID}")
    print(f"Database Device ID: {DEVICE_DB_ID}")
    print(f"Heartbeat:          {HEARTBEAT_INTERVAL} seconds")
    print(f"Telemetry:          {TELEMETRY_INTERVAL} seconds")
    print("=" * 65)
    print()

    if not DEVICE_SECRET:
        print("ERROR: Device credentials are not configured.")
        print()
        print("Set the device secret in PowerShell:")
        print('$env:SKAPE_DEVICE_SECRET="your-device-secret"')
        print()
        print("Do NOT paste the secret into source code.")
        print()
        return False

    return True


# ============================================================
# DEVICE HEADERS
# ============================================================

def device_headers():
    return {
        "X-Device-ID": DEVICE_ID,
        "X-Device-Secret": DEVICE_SECRET,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ============================================================
# HEARTBEAT
# ============================================================

def send_heartbeat():
    url = (
        f"{BACKEND_URL}"
        f"/api/v1/devices/heartbeat"
    )

    try:
        response = requests.post(
            url,
            headers=device_headers(),
            timeout=5,
        )

        if response.status_code == 200:
            data = response.json()

            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"HEARTBEAT OK | "
                f"Device: {data.get('device_id')} | "
                f"Status: {data.get('status')} | "
                f"Last seen: {data.get('last_seen_at')}"
            )

            return True

        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] "
            f"HEARTBEAT FAILED | "
            f"HTTP {response.status_code} | "
            f"{response.text}"
        )

        return False

    except requests.exceptions.RequestException as error:
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] "
            f"HEARTBEAT ERROR | {error}"
        )

        return False


# ============================================================
# TELEMETRY GENERATOR
# ============================================================

def generate_telemetry(tick: int):
    """
    Generate realistic changing sensor values.

    Sine waves prevent abrupt changes while small random
    variations make the simulated readings more realistic.
    """

    temperature = (
        26.0
        + 2.0 * math.sin(tick / 8)
        + random.uniform(-0.25, 0.25)
    )

    sensor_1 = (
        50.0
        + 15.0 * math.sin(tick / 5)
        + random.uniform(-1.5, 1.5)
    )

    sensor_2 = (
        7.0
        + 0.8 * math.sin(tick / 7)
        + random.uniform(-0.08, 0.08)
    )

    sensor_3 = (
        100.0
        + 20.0 * math.sin(tick / 10)
        + random.uniform(-2.0, 2.0)
    )

    return {
        "temperature": round(temperature, 2),
        "sensor_1": round(sensor_1, 2),
        "sensor_2": round(sensor_2, 2),
        "sensor_3": round(sensor_3, 2),
    }


# ============================================================
# SEND TELEMETRY
# ============================================================

def send_telemetry(tick: int):
    url = (
        f"{BACKEND_URL}"
        f"/api/v1/devices/"
        f"{DEVICE_DB_ID}/telemetry"
    )

    payload = generate_telemetry(tick)

    try:
        response = requests.post(
            url,
            headers=device_headers(),
            json=payload,
            timeout=5,
        )

        if response.status_code == 200:
            data = response.json()

            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"TELEMETRY OK | "
                f"Temp: {data.get('temperature')} °C | "
                f"S1: {data.get('sensor_1')} | "
                f"S2: {data.get('sensor_2')} | "
                f"S3: {data.get('sensor_3')}"
            )

            return True

        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] "
            f"TELEMETRY FAILED | "
            f"HTTP {response.status_code} | "
            f"{response.text}"
        )

        return False

    except requests.exceptions.RequestException as error:
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] "
            f"TELEMETRY ERROR | {error}"
        )

        return False


# ============================================================
# MAIN
# ============================================================

def main():

    if not validate_configuration():
        return

    print("Device authentication configured.")
    print("Using X-Device-ID + X-Device-Secret.")
    print()

    print("Starting device simulation...")
    print("Press CTRL+C to stop.")
    print()

    tick = 0

    # Send immediately on startup
    last_heartbeat = time.time() - HEARTBEAT_INTERVAL
    last_telemetry = time.time() - TELEMETRY_INTERVAL

    try:

        while True:

            now = time.time()

            # ------------------------------------------------
            # HEARTBEAT
            # ------------------------------------------------

            if (
                now - last_heartbeat
                >= HEARTBEAT_INTERVAL
            ):
                send_heartbeat()
                last_heartbeat = now

            # ------------------------------------------------
            # TELEMETRY
            # ------------------------------------------------

            if (
                now - last_telemetry
                >= TELEMETRY_INTERVAL
            ):
                send_telemetry(tick)

                last_telemetry = now
                tick += 1

            time.sleep(0.25)

    except KeyboardInterrupt:

        print()
        print("Stopping SKape Device Simulator...")
        print("Simulator stopped.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()