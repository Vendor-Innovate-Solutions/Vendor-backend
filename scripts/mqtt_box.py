import paho.mqtt.client as mqtt
import json

MQTT_BROKER = "mqtt.eclipseprojects.io"
MQTT_PORT = 1883
MQTT_TOPIC = "manufacturing/anomalies"

# MQTT Callback when a message is received
def on_message(client, userdata, msg):
    print(f"[📩] Message received on topic {msg.topic}")
    try:
        payload = json.loads(msg.payload.decode())
        print(f"[✅] Parsed Payload: {payload}")

        # Example: process the received data
        if payload['confidence'] >= 0.7:
            print(f"[🚨] High Confidence Defect Detected - Confidence: {payload['confidence']}")
            # Here, you could update a database, alert UI, or take action
        else:
            print("[ℹ] Confidence below threshold, no action taken.")
    except Exception as e:
        print(f"[❌] Error processing message: {e}")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[✅] Connected to MQTT Broker!")
        client.subscribe(MQTT_TOPIC)
        print(f"[📡] Subscribed to topic: {MQTT_TOPIC}")
    else:
        print(f"[❌] Failed to connect, return code {rc}")

# Setup MQTT Client
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_forever()