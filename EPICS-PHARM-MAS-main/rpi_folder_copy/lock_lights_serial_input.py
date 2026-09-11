from serial import Serial, SerialException, PARITY_NONE, STOPBITS_ONE, EIGHTBITS
import serial.serialutil
import time
import threading
import glob
from enum import Enum

# class Data(Enum):
#     DRAWER_1 = 1
#     DRAWER_2 = 2
#     DRAWER_3 = 3
#     DRAWER_4 = 4
#     UNLOCK = 5
#     RGB_1 = 6
#     RGB_2 = 7
#     RGB_3 = 8
#     RGB_4 = 9
class Data(Enum):
    UNLOCK_CABINET_1 = 1
    UNLOCK_CABINET_2 = 2
    UNLOCK_CABINET_3 = 3
    UNLOCK_CABINET_4 = 4
    LOCK_CABINET_1 = 5
    LOCK_CABINET_2 = 6
    LOCK_CABINET_3 = 7
    LOCK_CABINET_4 = 8
    UNLOCK_DRAWER = 9
    LOCK_DRAWER = 10
    RGB_1_ON = 11
    RGB_2_ON = 12
    RGB_3_ON = 13
    RGB_4_ON = 14
    RGB_1_OFF = 15
    RGB_2_OFF = 16
    RGB_3_OFF = 17
    RGB_4_OFF = 18
# wait 2 seconds for the connection
def setup_uart() -> Serial:
    ## set up UART connection
    try:
        uart = Serial(port='/dev/serial0',
                      baudrate=9600,
                      parity=PARITY_NONE,
                      stopbits=STOPBITS_ONE,
                      bytesize=EIGHTBITS,
                      timeout=1)
        return uart
    except SerialException as e:
        print(f"Error opening UART: {e}")
        return None

def send_byte(uart_connection, byte_value) -> None:
    """Send a single byte to Arduino"""
    if uart_connection and uart_connection.is_open:
        try:
            # Send single byte (0-255)
            uart_connection.write(bytes([byte_value]))
            print(f"Sent byte: {byte_value} (0x{byte_value:02X})")
        except Exception as e:
            print(f"Failed to send command: {e}")
            return
    else:
        print(f"Failed to send command - no uart connection: {byte_value}")








'''




old code

'''

" unlock"
def emUnlock(uart) -> None:
    send_byte(uart, 5)



" turn on lights"
def rgbOn(boxNum, uart) -> None:
    rgb = 5
    rgb += boxNum
    send_byte(uart, rgb)

# Moving this function here to avoid circular import
def open_drawer(drawer, uart):
    print(f"Opening drawer {drawer}")

    # DELAYS ARE NEEDED
    # The Arduino is programmed to check for a new command every 0.1 seconds, so commands (serial write) must be sent at least 0.1 seconds apart
    # This does also delay/freezes the UI however
    rgbOn(drawer, uart)
    time.sleep(0.12)
    emUnlock(uart)
    time.sleep(0.12)

    return