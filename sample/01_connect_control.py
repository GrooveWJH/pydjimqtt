from pydjimqtt import MQTTClient, ServiceCaller, request_control_auth, release_control_auth


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

    try:
        request_control_auth(caller, user_id="pilot", user_callsign="callsign")
        input("Confirm control on RC, then press Enter to release...")
        release_control_auth(caller)
    finally:
        mqtt.disconnect()


if __name__ == "__main__":
    main()
