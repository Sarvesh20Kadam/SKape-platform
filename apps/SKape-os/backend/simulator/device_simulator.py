import time
from datetime import datetime

import requests


# ============================================================
# SKape Device Simulator
# ============================================================

BACKEND_URL = "http://127.0.0.1:8000"

DEVICE_ID = "STM32A"

HEARTBEAT_INTERVAL = 10


def send_heartbeat():
    url = f"{BACKEND_URL}/api/v1/devices/heartbeat"

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

        else:
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"HEARTBEAT FAILED | "
                f"HTTP {response.status_code} | "
                f"{response.text}"
            )

    except requests.exceptions.RequestException as error:
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] "
            f"CONNECTION ERROR | {error}"
        )


def main():
    print("=" * 60)
    print("SKape Device Simulator")
    print("=" * 60)
    print(f"Backend: {BACKEND_URL}")
    print(f"Device:  {DEVICE_ID}")
    print(f"Interval: {HEARTBEAT_INTERVAL} seconds")
    print("=" * 60)
    print()
    print("Starting heartbeat...")
    print("Press CTRL+C to stop.")
    print()

    while True:
        send_heartbeat()
        time.sleep(HEARTBEAT_INTERVAL)


if __name__ == "__main__":
    main()