#include <AccelStepper.h>

#define DIR_PIN_X 8
#define STEP_PIN_X 9
#define DIR_PIN_Y 11
#define STEP_PIN_Y 12

#define SCREEN_X_MAX 20000 // # of pixels in UI width
#define SCREEN_Y_MAX 25000 // # of pixels in UI height
// 200 steps per rev
#define MOTOR_X_MAX 20000 // # of total steps for x-motor
#define MOTOR_Y_MAX 25000 // # of total steps for y-motor


AccelStepper stepperX(AccelStepper::DRIVER, STEP_PIN_X, DIR_PIN_X);
AccelStepper stepperY(AccelStepper::DRIVER, STEP_PIN_Y, DIR_PIN_Y); 

String command;
unsigned long previousMillis = 0;

void setup() {
  Serial.begin(9600); // Initialize serial communication
  
  stepperX.setMaxSpeed(2000);
  stepperX.setAcceleration(20000);
  stepperY.setMaxSpeed(2000);
  stepperY.setAcceleration(20000);
}

void loop() {
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= 100) {
    // Construct command
    while (Serial.available() > 0) {
      char currentChar = Serial.read();
      if (currentChar != '\n') {
        command += currentChar;
      }
      else {
        handleCommand(command);
        command = "";
      }
    }
  }
  
  stepperX.run();
  stepperY.run();
}

void handleCommand(String command) {
  Serial.println(command);

  if (command.substring(0, 4) == "move") {
    int delimIdx = command.indexOf(',');

    stepperX.moveTo(map(command.substring(4, delimIdx).toInt(), 0, SCREEN_X_MAX, 0, MOTOR_X_MAX));
    stepperY.moveTo(map(command.substring(delimIdx + 1).toInt(), 0, SCREEN_Y_MAX, 0, MOTOR_Y_MAX));
  }
}
