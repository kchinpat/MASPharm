#include <Adafruit_NeoPixel.h>
#include "HardwareConfig.h"

constexpr bool validLockPin(int pin) {
  // Pins 0 and 1 are reserved for the serial protocol on Uno/Nano.
  return pin >= 2 && pin <= 13 && pin < NUM_DIGITAL_PINS;
}
constexpr bool validProfile() {
  return HARDWARE_PROFILE_VERIFIED == 1 &&
    validLockPin(LOCK_PINS[0]) && validLockPin(LOCK_PINS[1]) &&
    validLockPin(LOCK_PINS[2]) && validLockPin(LOCK_PINS[3]) &&
    LOCK_PINS[0] != LOCK_PINS[1] && LOCK_PINS[0] != LOCK_PINS[2] &&
    LOCK_PINS[0] != LOCK_PINS[3] && LOCK_PINS[1] != LOCK_PINS[2] &&
    LOCK_PINS[1] != LOCK_PINS[3] && LOCK_PINS[2] != LOCK_PINS[3] &&
    (RELEASE_LEVEL == LOW || RELEASE_LEVEL == HIGH) &&
    RELEASE_PULSE_MS > 0 && RELEASE_PULSE_MS < 0x80000000UL &&
    RELEASE_REST_MS > 0 && RELEASE_REST_MS < 0x80000000UL &&
    (!LIGHTS_ENABLED || (validLockPin(LED_DATA_PIN) &&
      LED_DATA_PIN != LOCK_PINS[0] && LED_DATA_PIN != LOCK_PINS[1] &&
      LED_DATA_PIN != LOCK_PINS[2] && LED_DATA_PIN != LOCK_PINS[3] &&
      LED_COUNT > 0 && PIXEL_START[0] == 0 && PIXEL_START[4] == LED_COUNT &&
      PIXEL_START[0] < PIXEL_START[1] && PIXEL_START[1] < PIXEL_START[2] &&
      PIXEL_START[2] < PIXEL_START[3] && PIXEL_START[3] < PIXEL_START[4] &&
      LIGHT_TIMEOUT_MS > 0 && LIGHT_TIMEOUT_MS < 0x80000000UL));
}
static_assert(HARDWARE_COMMISSIONED == 0 || HARDWARE_COMMISSIONED == 1,
              "HARDWARE_COMMISSIONED must be 0 or 1");
static_assert(!HARDWARE_COMMISSIONED || validProfile(),
              "Configure and verify HardwareConfig.h before enabling outputs");

Adafruit_NeoPixel strip;
int8_t released = -1;
unsigned long releaseStarted = 0;
unsigned long releasedAt[4] = {0, 0, 0, 0};
bool resting[4] = {false, false, false, false};
bool lightsActive = false;
unsigned long lightsStarted = 0;

void deactivate(uint8_t index) {
  if (released == index) {
    digitalWrite(LOCK_PINS[index], RELEASE_LEVEL == HIGH ? LOW : HIGH);
    released = -1;
    releasedAt[index] = millis();
    resting[index] = true;
  }
}
void clearLights() {
  if (LIGHTS_ENABLED) {
    strip.clear();
    strip.show();
  }
  lightsActive = false;
}
void setLight(uint8_t index, bool on) {
  if (!LIGHTS_ENABLED || index >= 4) return;
  for (unsigned int pixel = PIXEL_START[index]; pixel < PIXEL_START[index + 1]; ++pixel)
    strip.setPixelColor(pixel, 0, on ? 255 : 0, 0);
  strip.show();
  if (on) {
    lightsActive = true;
    lightsStarted = millis();
  }
}
void lockAll() {
  if (released >= 0) deactivate(released);
  clearLights();
}
void serviceTimers() {
  const unsigned long now = millis();
  for (uint8_t i = 0; i < 4; ++i)
    if (resting[i] && (unsigned long)(now - releasedAt[i]) >= RELEASE_REST_MS)
      resting[i] = false;
  if (released >= 0 && (unsigned long)(now - releaseStarted) >= RELEASE_PULSE_MS)
    deactivate(released);
  if (lightsActive && (unsigned long)(now - lightsStarted) >= LIGHT_TIMEOUT_MS)
    clearLights();
}
bool selectCompartment(uint8_t index) {
  // Repeated commands cannot extend an active pulse or bypass coil rest.
  if (released >= 0 || resting[index]) return false;
  clearLights();
  setLight(index, true);
  releaseStarted = millis();
  released = index;
  digitalWrite(LOCK_PINS[index], RELEASE_LEVEL);
  return true;
}
void handleCommand(uint8_t cmd) {
  if (cmd == 0) {
    Serial.println(HARDWARE_COMMISSIONED ? F("MAS/1 READY") : F("MAS/1 DISABLED"));
    return;
  }
  if (cmd > 23 || cmd == 9) {
    Serial.println(F("MAS/1 ERR UNKNOWN"));
    return;
  }
  if (!HARDWARE_COMMISSIONED) {
    Serial.println(F("MAS/1 ERR DISABLED"));
    return;
  }
  if ((cmd >= 1 && cmd <= 4) || (cmd >= 20 && cmd <= 23)) {
    if (!selectCompartment(cmd <= 4 ? cmd - 1 : cmd - 20)) {
      Serial.println(F("MAS/1 ERR BUSY"));
      return;
    }
  }
  else if (cmd >= 5 && cmd <= 8) {
    deactivate(cmd - 5);
    setLight(cmd - 5, false);
  }
  else if (cmd == 10 || cmd == 19) lockAll();
  else if (cmd >= 11 && cmd <= 18) {
    if (!LIGHTS_ENABLED) {
      Serial.println(F("MAS/1 ERR UNSUPPORTED"));
      return;
    }
    setLight(cmd <= 14 ? cmd - 11 : cmd - 15, cmd <= 14);
  }
  Serial.print(F("MAS/1 ACK "));
  Serial.println(cmd);
}
void setup() {
  // Configure inactive levels before opening serial. Disabled builds leave
  // actuator and LED pins undriven, even with an incomplete profile.
  if (HARDWARE_COMMISSIONED) {
    for (uint8_t i = 0; i < 4; ++i) {
      digitalWrite(LOCK_PINS[i], RELEASE_LEVEL == HIGH ? LOW : HIGH);
      pinMode(LOCK_PINS[i], OUTPUT);
    }
    if (LIGHTS_ENABLED) {
      strip.updateType(NEO_GRB + NEO_KHZ800);
      strip.updateLength(LED_COUNT);
      strip.setPin(LED_DATA_PIN);
      strip.begin();
      strip.setBrightness(100);
      clearLights();
    }
  }
  Serial.begin(9600);
}
void loop() {
  // Timers run on every pass, including while a command stream is arriving.
  if (HARDWARE_COMMISSIONED) serviceTimers();
  if (Serial.available() > 0) handleCommand((uint8_t)Serial.read());
}
