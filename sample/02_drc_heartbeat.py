import time

from pydjimqtt import (
    MQTTClient,
    ServiceCaller,
    request_control_auth,
    enter_drc_mode,
    exit_drc_mode,
    start_heartbeat,
    stop_heartbeat,
)


MQTT_CONFIG = {
    "host": "127.0.0.1",
    "port": 1883,
    "username": "admin",
    "password": "password",
}
GATEWAY_SN = "YOUR_GATEWAY_SN"


def main() -> None:
    mqtt = MQTTClient(gateway_sn=GATEWAY_SN, mqtt_config=MQTT_CONFIG)
    mqtt.connect()
    caller = ServiceCaller(mqtt)

    heartbeat_thread = None
    try:
        request_control_auth(caller, user_id="pilot", user_callsign="callsign")
        input("Confirm control on RC, then press Enter to enter DRC...")

        mqtt_broker = {
            "address": f"{MQTT_CONFIG['host']}:{MQTT_CONFIG['port']}",
            "client_id": f"drc-{GATEWAY_SN}",
            "username": MQTT_CONFIG["username"],
            "password": MQTT_CONFIG["password"],
            "expire_time": int(time.time()) + 3600,
            "enable_tls": False,
        }

        enter_drc_mode(
            caller, mqtt_broker=mqtt_broker, osd_frequency=100, hsi_frequency=10
        )
        heartbeat_thread = start_heartbeat(mqtt, interval=0.2)

        print("DRC active. Press Ctrl+C to exit.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        if heartbeat_thread:
            stop_heartbeat(heartbeat_thread)
        try:
            exit_drc_mode(caller)
        finally:
            mqtt.disconnect()


if __name__ == "__main__":
    main()
