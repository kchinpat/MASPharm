#pragma once
#include "Arduino.h"
#define NEO_GRB 0
#define NEO_KHZ800 0
class Adafruit_NeoPixel {
public:
  void clear() {}
  void show() {}
  void setPixelColor(unsigned int, int, int, int) {}
  void updateType(int) {}
  void updateLength(unsigned int) {}
  void setPin(int) {}
  void begin() {}
  void setBrightness(int) {}
};
