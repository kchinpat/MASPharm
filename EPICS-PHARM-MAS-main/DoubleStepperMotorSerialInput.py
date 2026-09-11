import serial
import time

ser = serial.Serial(port='COM3', baudrate=9600, timeout=1)
time.sleep(1)

def sendCommand(command):
    ser.write((command + '\n').encode())

# def reverse(motor):
#     command = str(motor) + "reverse"
#     sendCommand(command)

# def setSpeed(motor, speed):
#     command = str(motor) + "set" + str(speed)
#     sendCommand(command)

def move(x, y):
    command = "move" + str(x) + "," + str(y)
    sendCommand(command)