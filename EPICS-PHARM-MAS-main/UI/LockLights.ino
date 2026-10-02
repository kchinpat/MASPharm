#include <Adafruit_NeoPixel.h>
#include <avr/wdt.h>
#define PIN 4         // The pin to which the Din of the RGB strip is connected
#define NUMPIXELS 91  // Number of pixels in the RGB strip

// lock pints
const int lockPin = 5;  // Full drawer
const int lock1 = 10; 
const int lock2 = 8;
const int lock3 = 7;
const int lock4 = 6;

Adafruit_NeoPixel strip = Adafruit_NeoPixel(NUMPIXELS, PIN, NEO_GRB + NEO_KHZ800);
int firstPixels[5] = { 0, 23, 46, 69, 91 };   // Contains the first pixel number of each box and the last pixel number of the last box + 1
int rgbValues[6] = { 255, 0, 0, 0, 255, 0 };  //Contains the rgb values for two colors (red and green)

unsigned long timeCommand = 0; // Track time when previous command was processed
unsigned long timeLock = 0; // Track time when lock was unlocked
int8_t command;
bool locked = true;


void initPins() {
  // Lock pins
  pinMode(lockPin, OUTPUT);
  pinMode(lock1, OUTPUT);
  pinMode(lock2, OUTPUT);
  pinMode(lock3, OUTPUT);
  pinMode(lock4, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);

  // Turn locks on
  digitalWrite(lockPin, HIGH);
  digitalWrite(lock1, HIGH);
  digitalWrite(lock2, HIGH);
  digitalWrite(lock3, HIGH);
  digitalWrite(lock4, HIGH);
  digitalWrite(LED_BUILTIN, LOW);
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

void toggleRGB(int cmd) {
  // turn off all RGB's
  if (cmd == 5) {
    for (int i = firstPixels[0]; i < firstPixels[4]; i++) {
      strip.setPixelColor(i, 0, 255, 0);
    }
  }
  else {
    for (int i = 0; i < NUMPIXELS; i++) { strip.setPixelColor(i, 0, 0, 0); } 
    // turn on RGB for specific drawer
    if (cmd) { 
      for (int i = firstPixels[cmd - 1]; i < firstPixels[cmd]; i++) { 
        strip.setPixelColor(i, 0, 255, 0); 
      } 
    }
  }
  strip.show();
}

void lockCompartments() {
    digitalWrite(lock1, HIGH);
    digitalWrite(lock2, HIGH);
    digitalWrite(lock3, HIGH);
    digitalWrite(lock4, HIGH); 
}
void unlockCompartment(int pin) {
    // turn on correct pin
    if (pin) {
      digitalWrite(pin, LOW);
    }
}
/* Handle Command */
void handleCommand(int8_t command) {
    // which drawer to unlock
    if (command == 1) { 
      lockCompartments();
      unlockCompartment(lock1); 
    }
    else if (command == 2) { 
      lockCompartments();
      unlockCompartment(lock2); 
    }
    else if (command == 3) { 
      lockCompartments();
      unlockCompartment(lock3); 
    }
    else if (command == 4) { 
      lockCompartments();
      unlockCompartment(lock4); 
    }

    // if (command > 0 && command <= 5) { 
    //   digitalWrite(lockPin, LOW);
    // }
    if (command == 5) {
      unlockCompartment(lock1);
      unlockCompartment(lock2);
      unlockCompartment(lock3);
      unlockCompartment(lock4);
      toggleRGB(5);
    }
    toggleRGB(command); // captures commands 1-5

    if (command == 7) {
      digitalWrite(lockPin, HIGH);
      lockCompartments();
      toggleRGB(0);
    }
}

void loop() {
  // Check for and process new command every 100 ms
  while (Serial.available() > 0) {
    // digitalWrite(9, HIGH);
    command = Serial.read();
    Serial.println(command);
    if (command >= '1' && command <= '4') {
      command -= '0';
    }
    else if (command == '7') {
      command -= '0';
    }

    handleCommand(command); // handle the command

  }
}
