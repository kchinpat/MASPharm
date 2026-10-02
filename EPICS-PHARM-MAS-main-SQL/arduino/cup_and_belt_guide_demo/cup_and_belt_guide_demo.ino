#include <AccelStepper.h>

#define DIR_PIN_X 4
#define STEP_PIN_X 3
#define DIR_PIN_Y 11
#define STEP_PIN_Y 6

#define EN_PIN_X 5
#define EN_PIN_Y 10

#define RIGHT_SWITCH_PIN 13
#define CUP_SWITCH_PIN 8

AccelStepper stepperX(AccelStepper::DRIVER, STEP_PIN_X, DIR_PIN_X);
AccelStepper stepperY(AccelStepper::DRIVER, STEP_PIN_Y, DIR_PIN_Y); 

String command;
unsigned long previousMillis = 0;

void cup_home(void);
void cup_open(void);
void belt_home(void);
void belt_open(void);
void load_1(void);

void setup() {
  pinMode(EN_PIN_X, OUTPUT);
  pinMode(EN_PIN_Y, OUTPUT);
  digitalWrite(EN_PIN_X, HIGH);
  digitalWrite(EN_PIN_Y, HIGH);
  pinMode(RIGHT_SWITCH_PIN, INPUT);
  pinMode(CUP_SWITCH_PIN, INPUT);


  Serial.begin(9600); // Initialize serial communication
  
  stepperX.setMaxSpeed(750);
  stepperX.setAcceleration(1000);
  stepperY.setMaxSpeed(200);
  stepperY.setAcceleration(100);
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
}

void handleCommand(String command) {
  Serial.println(command);
  Serial.println(command.toInt());

  if (command.toInt() == 0) {
    cup_home();
  }
  else if (command.toInt() == 1) {
    cup_open();
  }
  else if (command.toInt() == 2) {
    belt_home();
  }
  else if (command.toInt() == 3) {
    belt_open();
  }
  else if (command.toInt() == 4) {
    load_1();
  }
}

void cup_home()
{
  digitalWrite(EN_PIN_X, LOW);
  stepperX.moveTo(-4000);
  Serial.println(("Cup moving home"));

  while(stepperX.currentPosition() != stepperX.targetPosition())
  {
    if (digitalRead(CUP_SWITCH_PIN) == HIGH)
    {
      if (!(stepperX.distanceToGo() > 0))
      {
        stepperX.stop();
        stepperX.setCurrentPosition(0);
        Serial.println("Cup switch hit. Setting position to 0");
        break;
      }
      
    }
    stepperX.run();
  }
  digitalWrite(EN_PIN_X, HIGH);
}

void cup_open()
{
  digitalWrite(EN_PIN_X, LOW);
  stepperX.moveTo(3800);
  Serial.println(("Cup opening"));
  while(stepperX.currentPosition() != stepperX.targetPosition())
  {
    stepperX.run();
  }
  digitalWrite(EN_PIN_X, HIGH);
}

void belt_home()
{
  digitalWrite(EN_PIN_Y, LOW);
  stepperY.moveTo(4000);
  Serial.println(("Belt moving home"));

  while(stepperY.currentPosition() != stepperY.targetPosition())
  {
    if (digitalRead(RIGHT_SWITCH_PIN) == HIGH)
    {
      if(digitalRead(RIGHT_SWITCH_PIN) == HIGH)
      {
        if (!(stepperY.distanceToGo() < 0))
        {
          stepperY.stop();
          stepperY.setCurrentPosition(1000);
          Serial.println("Right switch hit. Setting position to 1000");
          break;
        }
      }
      
      
    }
    stepperY.run();
  }
  digitalWrite(EN_PIN_Y, HIGH);
}

void belt_open()
{
  digitalWrite(EN_PIN_Y, LOW);
  stepperY.moveTo(0);
  Serial.println(("Belt opening"));
  while(stepperY.currentPosition() > stepperY.targetPosition())
  {
    stepperY.run();
  }
  stepperY.stop();
  digitalWrite(EN_PIN_Y, HIGH);
}

void load_1()
{
  cup_home();
  belt_home();
  belt_open();
  cup_open();
  cup_home();
  belt_home();
}
