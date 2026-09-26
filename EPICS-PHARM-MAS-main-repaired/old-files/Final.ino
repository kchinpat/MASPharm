#include <Adafruit_NeoPixel.h>
#define PIN            6  // The pin to which the Din of the RGB strip is connected
#define NUMPIXELS      91 // Number of pixels in the RGB strip

String command;
bool commandCompleted = false;

const int lockPin = 5;
bool locked = true;
unsigned long previousMillis = 0;

Adafruit_NeoPixel strip = Adafruit_NeoPixel(NUMPIXELS, PIN, NEO_GRB + NEO_KHZ800);
int firstPixels[5] = {0, 23, 46, 69, 91}; // Contains the first pixel number of each box and the last pixel number of the last box + 1
int rgbValues[6] = {255, 0, 0, 0, 255, 0}; //Contains the rgb values for two colors (red and green)


void setup() {
  Serial.begin(9600); // Initialize serial communication
  strip.begin();
  delay(100);
  strip.show(); // Initialize all pixels to 'off'
  pinMode(lockPin, OUTPUT);
  digitalWrite(lockPin, LOW); // Lock em lock
}

void loop() {
  command = "";

  // Construct command
  while (Serial.available() > 0) {
    char currentChar = Serial.read();
    if (currentChar != '\n') {
      command += currentChar;
    }
  }

  if (command.length() > 0) {
    Serial.println(command);
  }

  unsigned long currentMillis = millis(); // Get current time
  // Lock em lock if 500 ms passed since it was unlocked
  if (!locked) {
    if (currentMillis - previousMillis >= 1000) {
      digitalWrite(lockPin, LOW);
      locked = true;
    }
  }
  // Unlock em lock
  if (command == "unlock") {
    digitalWrite(lockPin, HIGH);
    locked = false;
  }
  // Turn on rgb strip in specified box
  else if (command.substring(0, 2) == "on") {
    int boxNum = command.charAt(3) - '0';
    int rgbIndex = (command.charAt(5) - '0') * 3;
    turnOnPixels(firstPixels[boxNum - 1], firstPixels[boxNum], rgbValues[rgbIndex], rgbValues[rgbIndex + 1], rgbValues[rgbIndex + 2]);
  }
  else if (command.substring(0, 3) == "off") {
    int boxNum = command.charAt(4) - '0';
    turnOffPixels(firstPixels[boxNum - 1], firstPixels[boxNum]);
  }

  delay(100);
}

// Turns on pixels from firstPixel to lastPixel
void turnOnPixels(int firstPixel, int lastPixel, int r, int g, int b) {
  strip.setBrightness(100);
  for (int i = firstPixel; i < lastPixel; i++) {
    strip.setPixelColor(i, r, g, b);
  }
  strip.show();
}

// Turns off pixels from firstPixel to lastPixel inclusive
void turnOffPixels(int firstPixel, int lastPixel) {
  for (int i = firstPixel; i < lastPixel; i++) {
    strip.setPixelColor(i, 0, 0, 0);
  }
  strip.show();
}
