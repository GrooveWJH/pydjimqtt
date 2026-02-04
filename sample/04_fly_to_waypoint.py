import time

from pydjimqtt import (
    MQTTClient,
    ServiceCaller,
    request_control_auth,
    fly_to_waypoint,
    monitor_flyto_progress,
)


MQTT_CONFIG = {
    "host": "127.0.0.1",
    "port": 1883,
    "username": "admin",
    "password": "password",
}
GATEWAY_SN = "YOUR_GATEWAY_SN"

# Replace with a safe target point.
WAYPOINT = {
    "lat": 39.0427514,
    "lon": 117.7238255,
    "height": 50.0,
}


def main() -> None:
    mqtt = MQTTClient(gateway_sn=GATEWAY_SN, mqtt_config=MQTT_CONFIG)
    mqtt.connect()
    caller = ServiceCaller(mqtt)

    try:
        request_control_auth(caller, user_id="pilot", user_callsign="callsign")
        input("Confirm control on RC, then press Enter to fly...")

        fly_to_waypoint(
            caller,
            lat=WAYPOINT["lat"],
            lon=WAYPOINT["lon"],
            height=WAYPOINT["height"],
            max_speed=8,
        )

        while True:
            status, _progress = monitor_flyto_progress(
                mqtt, callsign="drone", show_progress=True
            )
            if status in {"wayline_ok", "wayline_failed", "wayline_cancel"}:
                print(f"Fly-to finished with status: {status}")
                break
            time.sleep(0.5)
    finally:
        mqtt.disconnect()


if __name__ == "__main__":
    main()
