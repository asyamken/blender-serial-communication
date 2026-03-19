#include <Arduino.h>
#include <dht_nonblocking.h> 

#define DHT_SENSOR_TYPE DHT_TYPE_11

static const int sensorPin = GPIO_NUM_0;
static const int DHT_SENSOR_PIN = GPIO_NUM_2;

DHT_nonblocking dht_sensor( DHT_SENSOR_PIN, DHT_SENSOR_TYPE );
String command;
unsigned long last_time_ms;
float latest_humidity;


// put function declarations here:
int getBrightness();
bool wait_ms(unsigned long ms);

void setup() {
  command = "";
  Serial.begin(115200);
  pinMode(sensorPin, OUTPUT);
  last_time_ms = millis();
}

void loop() {
    float humidity;
    float temperature;
    int brightness;

    if(wait_ms(50)){
        if(dht_sensor.measure(&temperature, &humidity)){
            latest_humidity = humidity;
        }
    }

    if(Serial.available() > 0){
        command = Serial.readStringUntil('\n');
        if (command == "Get All"){
            brightness = 4095-getBrightness();
            Serial.print(brightness);
            Serial.print(",");
            Serial.print(latest_humidity);
    }
    }
}

int getBrightness(){
    int sensorValue = analogRead(sensorPin);
    return sensorValue;
}

bool wait_ms(unsigned long ms){
    if (millis() - last_time_ms < ms) 
        return true;
    last_time_ms = millis();
    return false;
}

