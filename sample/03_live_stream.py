import time

from pydjimqtt import MQTTClient, ServiceCaller, request_control_auth, start_live, stop_live, set_live_quality


MQTT_CONFIG = {
    "host": "127.0.0.1",
    "port": 1883,
    "username": "admin",
    "password": "password",
}
GATEWAY_SN = "YOUR_GATEWAY_SN"
RTMP_URL = "rtmp://127.0.0.1/live/test"


def main() -> None:
    mqtt = MQTTClient(gateway_sn=GATEWAY_SN, mqtt_config=MQTT_CONFIG)
    mqtt.connect()
    caller = ServiceCaller(mqtt)

    try:
        request_control_auth(caller, user_id="pilot", user_callsign="callsign")
        input("Confirm control on RC, then press Enter to start live...")

        video_id = start_live(caller, mqtt, RTMP_URL,
                              video_index="normal-0", video_quality=3)
        if not video_id:
            return

        set_live_quality(caller, video_id, video_quality=3)
        print("Live stream running for 10 seconds...")
        time.sleep(10)
        stop_live(caller, video_id)
    finally:
        mqtt.disconnect()


if __name__ == "__main__":
    main()
