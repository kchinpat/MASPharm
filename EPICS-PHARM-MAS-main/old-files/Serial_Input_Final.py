import serial
import time

# ser = serial.Serial(port='COM3', baudrate=9600, timeout=1)
# time.sleep(1)

def sendCommand(command):
    ser = serial.Serial(port='COM3', baudrate=9600, timeout=1)
    time.sleep(1)

    ser.write((command + '\n').encode())

    time.sleep(0.1)
    ser.close()

def emUnlock():
    sendCommand("unlock")

def rgbOn(boxNum):
    command = "on " + str(boxNum) + " 1"
    sendCommand(command)

def rgbOff(boxNum):
    sendCommand("off " + str(boxNum))