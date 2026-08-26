import math
import os
import random
import time
from datetime import datetime

import requests


# ============================================================
# SKape Device Simulator
# ============================================================

BACKEND_URL = "http://127.0.0.1:8000"

DEVICE_ID = "STM32A"
DEVICE_DB_ID = 2

HEARTBEAT_INTERVAL = 10
TELEMETRY_INTERVAL = 5

# ------------------------------------------------------------
# Credentials
#
# Set these as environment variables before running:
#
# $env:SKAPE_EMAIL="your-email@example.com"
# $env:SKAPE_PASSWORD="your-password"
# ------------------------------------------------------------

EMAIL = os.getenv("SKAPE_EMAIL", "")
PASSWORD = os.getenv("SKAPE_PASSWORD", "")


# ============================================================
# AUTHENTICATION
# ============================================================

access_token = None


def login():
    global access_token

    if not EMAIL or not PASSWORD:
        print()
        print("ERROR: Simulator credentials are not configured.")
        print()
        print('Set them in PowerShell:')
        print('$env:SKAPE_EMAIL="your-email@example.com"')
        print('$env:SKAPE_PASSWORD="your-password"')
        print()
        return False

    url = f"{BACKEND_URL}/api/v1/users/login"

    try:
        response = requests.post(
            url,
            data={
                "username": EMAIL,
                "password": PASSWORD,
            },
            timeout=5,
        )

        if response.status_code != 200:
            print(
                f"[AUTH FAILED] "
                f"HTTP {response.status_code} | "
                f"{response.text}"
            )
            return False

        data = response.json()

        access_token = data.get("access_token")

        if not access_token:
            print("[AUTH FAILED] No access token returned.")
            return False

        print("[AUTH] Login successful")

        return True

    except requests.exceptions.RequestException as error:
        print(f"[AUTH ERROR] {error}")
        return False


# ============================================================
# HEADERS
# ============================================================


def authenticated_headers():
    return {
        "Authorization": f"Bearer {access_token}",
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

    params = {
        "device_id": DEVICE_ID,
    }

    try:
        response = requests.post(
            url,
            params=params,
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

    The sine waves prevent the values from jumping randomly
    while small random noise makes them look more realistic.
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
    global access_token

    url = (
        f"{BACKEND_URL}"
        f"/api/v1/devices/"
        f"{DEVICE_DB_ID}/telemetry"
    )

    payload = generate_telemetry(tick)

    try:
        response = requests.post(
            url,
            headers=authenticated_headers(),
            json=payload,
            timeout=5,
        )

        # ----------------------------------------------------
        # Token expired / invalid
        # ----------------------------------------------------

        if response.status_code == 401:
            print(
                "[TELEMETRY] Authentication expired. "
                "Logging in again..."
            )

            if login():
                response = requests.post(
                    url,
                    headers=authenticated_headers(),
                    json=payload,
                    timeout=5,
                )
            else:
                return False

        # ----------------------------------------------------
        # Success
        # ----------------------------------------------------

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

    print("=" * 65)
    print("SKape Device Simulator")
    print("=" * 65)
    print(f"Backend:           {BACKEND_URL}")
    print(f"Device:            {DEVICE_ID}")
    print(f"Database Device ID:{DEVICE_DB_ID}")
    print(f"Heartbeat:         {HEARTBEAT_INTERVAL} seconds")
    print(f"Telemetry:         {TELEMETRY_INTERVAL} seconds")
    print("=" * 65)
    print()

    # --------------------------------------------------------
    # Login
    # --------------------------------------------------------

    print("Authenticating with SKape OS...")

    if not login():
        return

    print()
    print("Starting device simulation...")
    print("Press CTRL+C to stop.")
    print()

    tick = 0

    last_heartbeat = 0
    last_telemetry = 0

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


if __name__ == "__main__":
    main()