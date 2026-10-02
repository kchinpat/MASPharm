#include "Arduino.h"
#include <cassert>
unsigned long fakeNow = 0;
unsigned long clockStep = 0;
int pins[20] = {};
int writes = 0;
FakeSerial Serial;
#include "LockLights.ino"

void command(uint8_t value) {
  Serial.output.clear();
  Serial.input.push_back(value);
  loop();
}
void reset() {
  released = -1;
  for (int i = 0; i < 4; ++i) resting[i] = false;
  fakeNow = 0;
  clockStep = 0;
  setup();
}
int main() {
  reset();
  command(0);
#if !HARDWARE_COMMISSIONED
  assert(Serial.output == "MAS/1 DISABLED\n");
  for (int cmd = 1; cmd < 256; ++cmd) command(static_cast<uint8_t>(cmd));
  assert(writes == 0);
#else
  assert(Serial.output == "MAS/1 READY\n");
  for (int i = 0; i < 4; ++i) assert(pins[LOCK_PINS[i]] != RELEASE_LEVEL);
  command(20);
  assert(Serial.output == "MAS/1 ACK 20\n");
  assert(pins[LOCK_PINS[0]] == RELEASE_LEVEL);
  fakeNow = RELEASE_PULSE_MS - 1;
  command(20);
  assert(Serial.output == "MAS/1 ERR BUSY\n");
  command(21);
  assert(Serial.output == "MAS/1 ERR BUSY\n");
  fakeNow = RELEASE_PULSE_MS;
  command(0);  // Serial traffic must not prevent the pulse ending.
  assert(pins[LOCK_PINS[0]] != RELEASE_LEVEL);
  command(20);
  assert(Serial.output == "MAS/1 ERR BUSY\n");
  fakeNow += RELEASE_REST_MS;
  command(20);
  assert(Serial.output == "MAS/1 ACK 20\n");
  command(19); // Explicit lock terminates a pulse and starts rest.
  assert(released == -1);
  assert(pins[LOCK_PINS[0]] != RELEASE_LEVEL);
  command(20);
  assert(Serial.output == "MAS/1 ERR BUSY\n");
  command(21); // Rest is per drawer.
  assert(pins[LOCK_PINS[1]] == RELEASE_LEVEL);
  command(5); // Locking a different drawer cannot end this pulse.
  assert(released == 1);
  command(6);
  assert(released == -1);
  int before = writes;
  command(255);
  assert(Serial.output == "MAS/1 ERR UNKNOWN\n" && writes == before);
  command(9);
  assert(Serial.output == "MAS/1 ERR UNKNOWN\n" && writes == before);

  reset();
  command(20);
  fakeNow = RELEASE_PULSE_MS;
  clockStep = 1; // Clock ticks between timer snapshot and deactivation.
  loop();
  assert(resting[0]);
  clockStep = 0;
  command(20);
  assert(Serial.output == "MAS/1 ERR BUSY\n");

  reset();
  fakeNow = ~0UL - RELEASE_PULSE_MS / 2;
  command(23);
  fakeNow += RELEASE_PULSE_MS; // Unsigned timer wrap.
  loop();
  assert(released == -1 && resting[3]);
  fakeNow += RELEASE_REST_MS;
  command(23);
  assert(Serial.output == "MAS/1 ACK 23\n");
  command(19);
  command(11);
  assert(Serial.output == (LIGHTS_ENABLED ? "MAS/1 ACK 11\n" : "MAS/1 ERR UNSUPPORTED\n"));
  fakeNow += LIGHT_TIMEOUT_MS;
  loop();
  assert(!lightsActive);
#endif
}
