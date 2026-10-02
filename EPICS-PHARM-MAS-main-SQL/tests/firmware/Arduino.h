#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include <sstream>
#define LOW 0
#define HIGH 1
#define OUTPUT 1
#define NUM_DIGITAL_PINS 20
#define F(value) value
extern unsigned long fakeNow;
extern unsigned long clockStep;
extern int pins[20];
extern int writes;
inline unsigned long millis() { auto result = fakeNow; fakeNow += clockStep; return result; }
inline void digitalWrite(int pin, int value) { pins[pin] = value; ++writes; }
inline void pinMode(int, int) {}
struct FakeSerial {
  std::string output;
  std::vector<uint8_t> input;
  void begin(int) {}
  int available() { return static_cast<int>(input.size()); }
  int read() { int value = input.front(); input.erase(input.begin()); return value; }
  template<class T> void print(T value) { std::ostringstream s; s << value; output += s.str(); }
  template<class T> void println(T value) { print(value); output += '\n'; }
  void println(uint8_t value) { println(static_cast<int>(value)); }
};
extern FakeSerial Serial;
