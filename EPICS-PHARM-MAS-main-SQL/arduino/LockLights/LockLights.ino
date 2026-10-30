#include <Adafruit_NeoPixel.h>
#define LED_PIN 4         // The pin to which the Din of the RGB strip is connected
#define NUMPIXELS 91  // Number of pixels in the RGB strip

const int FSR4_pin = A0; // Drawer 4 attached to A0
const int FSR3_pin = A1; // Drawer 3 attached to A1
const int FSR2_pin = A2; // Drawer 2 attached to A2
const int FSR1_pin = A3; // Drawer 1 attached to A3

// lock pins
const int lock1 = 8; 
const int lock2 = 10;
const int lock3 = 6;
const int lock4 = 7;

const int lockPins[4] = { lock1, lock2, lock3, lock4 };
const int fsrPins[4] = { FSR1_pin, FSR2_pin, FSR3_pin, FSR4_pin };

// Locks are HIGH = locked, LOW = unlocked. A released drawer stays unlocked until it has been
// pulled out and pushed closed again, or for OPEN_WAIT_MS if nobody pulls it out. The solenoid
// is powered that whole time, so keep these within the lock's rated on-time to avoid over-heating.
const unsigned long OPEN_WAIT_MS = 10000;    // how long a released drawer waits to be pulled out
const unsigned long OUT_CONFIRM_MS = 200;    // how long the sensor must read the drawer as out before it counts
const unsigned long SENSOR_HOLD_MS = 2000;   // how long to stay unlocked after the sensor last read the drawer as out
const int SENSOR_THRESHOLD = 600;            // pressure sensor readings below this mean the drawer is out

// Commands from the app (each one is echoed back when done):
//   1-4          open mode for that drawer: unlock it, light it green, and watch its sensor.
//                It stays unlocked until it has been pulled out and closed (see above).
//                Other open drawers stay open.
//   7            end open mode for every drawer: lock all and turn all LEDs off.
//   0x20-0x2F    set open mode to exactly the drawers in the low 4 bits (bit 0 = drawer 1).
//                Drawers left out are locked and their LEDs turned off. The app sends this
//                after every change so the LEDs and locks always match the screen.
//   0x30         status: replies with one byte (not an echo). Low 4 bits = drawers in open mode,
//                high 4 bits = locks that are physically unlocked right now.
const int8_t LED_MASK_CMD = 0x20;
const int8_t STATUS_CMD = 0x30;

Adafruit_NeoPixel strip = Adafruit_NeoPixel(NUMPIXELS, LED_PIN, NEO_GRB + NEO_KHZ800);
int firstPixels[5] = { 0, 23, 46, 69, 91 };   // Contains the first pixel number of each box and the last pixel number of the last box + 1

uint8_t openMask = 0;                    // drawers in open mode (bit 0 = drawer 1)
unsigned long unlockUntil[4] = { 0, 0, 0, 0 };  // millis() until which each lock stays unlocked
bool readingOut[4] = { false, false, false, false };  // the sensor currently reads the drawer as out
unsigned long outSince[4] = { 0, 0, 0, 0 };          // millis() when that reading started
bool pulledOut[4] = { false, false, false, false };   // the drawer has been out since it was released

void initPins() {
  for (int d = 0; d < 4; d++) {
    pinMode(lockPins[d], OUTPUT);
    digitalWrite(lockPins[d], HIGH);  // locked
  }
}

void initPixels() {
  // Turn all pixels off
  strip.begin();
  strip.setBrightness(100);
  strip.show();
}

void setup() {
  Serial.begin(9600);  // Initialize serial communication
  initPins(); // init needed pins
  initPixels(); // init pixels for RGB lights
}

void showOpenDrawers() {
  for (int d = 0; d < 4; d++) {
    bool lit = openMask & (1 << d);
    for (int i = firstPixels[d]; i < firstPixels[d + 1]; i++) {
      strip.setPixelColor(i, 0, lit ? 255 : 0, 0);
    }
  }
  strip.show();
}

void holdUnlocked(int d, unsigned long ms) {
  unsigned long until = millis() + ms;
  if ((long)(until - unlockUntil[d]) > 0) {
    unlockUntil[d] = until;
  }
}

// While the drawer is out it stays unlocked; it locks SENSOR_HOLD_MS after it is closed.
// A reading counts only once it has lasted OUT_CONFIRM_MS, so a noisy sensor on a
// closed drawer can't cut the wait short.
void watchSensor(int d) {
  unsigned long now = millis();
  if (analogRead(fsrPins[d]) >= SENSOR_THRESHOLD) {
    readingOut[d] = false;
    return;
  }
  if (!readingOut[d]) {
    readingOut[d] = true;
    outSince[d] = now;
  }
  if (now - outSince[d] < OUT_CONFIRM_MS) {
    return;
  }
  if (!pulledOut[d]) {
    pulledOut[d] = true;
    unlockUntil[d] = now;  // it's open, so stop waiting for it to be pulled out
  }
  holdUnlocked(d, SENSOR_HOLD_MS);
}

// A lock is unlocked only while its drawer is in open mode and its unlock time hasn't run out.
void updateLocks() {
  unsigned long now = millis();
  for (int d = 0; d < 4; d++) {
    bool unlocked = (openMask & (1 << d)) && (long)(unlockUntil[d] - now) > 0;
    digitalWrite(lockPins[d], unlocked ? LOW : HIGH);
  }
}

uint8_t unlockedMask() {
  uint8_t mask = 0;
  for (int d = 0; d < 4; d++) {
    if (digitalRead(lockPins[d]) == LOW) {
      mask |= (1 << d);
    }
  }
  return mask;
}

void handleCommand(int8_t command) {
  if (command == STATUS_CMD) {
    Serial.write(byte(openMask | (unlockedMask() << 4)));
    Serial.flush();
    return;
  }
  if (command >= 1 && command <= 4) {
    int d = command - 1;
    openMask |= (1 << d);
    readingOut[d] = false;
    pulledOut[d] = false;
    holdUnlocked(d, OPEN_WAIT_MS);
  }
  else if (command == 7) {
    openMask = 0;
  }
  else if (command >= LED_MASK_CMD && command < LED_MASK_CMD + 16) {
    openMask = command - LED_MASK_CMD;
  }
  else {
    return;
  }
  updateLocks();
  showOpenDrawers();
  Serial.write(byte(command));
  Serial.flush();  // Make sure response is sent immediately
}

void loop() {
  if (Serial.available() > 0) {
    int8_t command = Serial.read();

    if (command >= '1' && command <= '4' || command == '7')
    {
      command -= '0';
    }

    // Clear any remaining buffered data from the same command burst
    while (Serial.available() > 0) {
      Serial.read();
    }

    handleCommand(command);
  }

  // Every open drawer keeps watching its own sensor: while the drawer reads as out, keep it unlocked.
  for (int d = 0; d < 4; d++) {
    if (openMask & (1 << d)) {
      watchSensor(d);
    } else {
      readingOut[d] = false;
    }
  }
  updateLocks();
}
