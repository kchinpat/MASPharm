import serial
import time

ser = serial.Serial(port='COM3', baudrate=9600, timeout=1)
time.sleep(1)

def sendCommand(command):
    #ser = serial.Serial(port='COM3', baudrate=9600, timeout=1)
    #time.sleep(1)

    ser.write((command + '\n').encode())

    #time.sleep(0.1)
    #ser.close()

def reverse():
    sendCommand("reverse")

def setSpeed(speed):
    command = "set" + str(speed)
    sendCommand(command)
