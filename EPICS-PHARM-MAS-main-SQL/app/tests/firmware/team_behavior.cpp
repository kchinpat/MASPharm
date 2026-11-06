#include "Arduino.h"
#include <cassert>
unsigned long fakeNow = 0;
unsigned long clockStep = 0;
int pins[20] = {};
int analogValues[20] = {};
int writes = 0;
FakeSerial Serial;
#include "LockLights.ino"

const int CLOSED = 900;  // pressure reading of a drawer pushed in
const int OUT = 100;     // pressure reading of a drawer pulled out

void command(uint8_t value) {
  Serial.output.clear();
  Serial.input.push_back(value);
  loop();
}
void run(unsigned long ms) {
  for (unsigned long t = 0; t < ms; t += 10) {
    fakeNow += 10;
    loop();
  }
}
bool unlocked(int d) { return pins[lockPins[d]] == LOW; }
void reset(unsigned long now = 0) {
  openMask = 0;
  for (int d = 0; d < 4; ++d) {
    unlockUntil[d] = 0;
    readingOut[d] = false;
    outSince[d] = 0;
    pulledOut[d] = false;
    analogValues[fsrPins[d]] = CLOSED;
  }
  fakeNow = now;
  clockStep = 0;
  setup();
}
void release(int drawer) {
  command(0x20);  // what the app sends first: secure the others
  command(drawer);
  assert(Serial.output == std::string(1, static_cast<char>(drawer)));
}

int main() {
  // Every drawer uses its own lock and sensor; drawer 1 is D8 and A3.
  assert(lockPins[0] == 8 && fsrPins[0] == A3);
  for (int d = 0; d < 4; ++d) {
    reset();
    for (int e = 0; e < 4; ++e) assert(!unlocked(e));
    release(d + 1);
    for (int e = 0; e < 4; ++e) assert(unlocked(e) == (e == d));
    analogValues[fsrPins[d]] = OUT;
    run(OPEN_WAIT_MS * 3);  // out far longer than the wait: still unlocked
    assert(unlocked(d));
    analogValues[fsrPins[d]] = CLOSED;
    run(SENSOR_HOLD_MS - 20);
    assert(unlocked(d));
    run(40);  // locks once it has been closed
    assert(!unlocked(d));
  }

  // Nobody pulls it out: unlocked for the whole wait, then locked.
  reset();
  release(1);
  run(OPEN_WAIT_MS - 20);
  assert(unlocked(0));
  run(40);
  assert(!unlocked(0));

  // Pulled out late in the wait: stays unlocked past the wait until it is closed.
  reset();
  release(1);
  run(OPEN_WAIT_MS - 500);
  analogValues[A3] = OUT;
  run(5000);
  assert(unlocked(0));
  analogValues[A3] = CLOSED;
  run(SENSOR_HOLD_MS + 20);
  assert(!unlocked(0));

  // Closed early: locks then, without waiting out the rest of the wait.
  reset();
  release(1);
  analogValues[A3] = OUT;
  run(1000);
  analogValues[A3] = CLOSED;
  run(SENSOR_HOLD_MS + 20);
  assert(!unlocked(0) && fakeNow < OPEN_WAIT_MS);

  // A brief noisy reading on a closed drawer doesn't cut the wait short.
  reset();
  release(1);
  analogValues[A3] = OUT;
  run(OUT_CONFIRM_MS / 2);
  analogValues[A3] = CLOSED;
  run(SENSOR_HOLD_MS + 500);
  assert(unlocked(0));

  // The app's lock command locks at once, even with the drawer out, and ends open mode.
  reset();
  release(1);
  analogValues[A3] = OUT;
  run(1000);
  command(7);
  assert(Serial.output == std::string(1, '\x07'));
  assert(!unlocked(0));
  run(1000);
  assert(!unlocked(0));

  // Status: low bits open mode, high bits released locks.
  reset();
  release(2);
  command(0x30);
  assert(Serial.output.size() == 1 && static_cast<uint8_t>(Serial.output[0]) == 0x22);

  // millis() wrapping during the wait.
  reset(~0UL - OPEN_WAIT_MS / 2);
  release(1);
  run(OPEN_WAIT_MS - 20);
  assert(unlocked(0));
  run(40);
  assert(!unlocked(0));
  return 0;
}
