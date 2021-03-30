from threading import Thread
import smbus
import time
import pynmea2

BUS = None
address = 0x42
gpsReadInterval = 1
# http://ava.upuaut.net/?p=768

def connectBus():
    global BUS
    BUS = smbus.SMBus(1)

def parseResponse(gpsLine):
    gpsChars = ''.join(chr(c) for c in gpsLine)
    print(gpsChars)

def readGPS(gpsReadInterval=1):
    c = None
    response = []
    try:
        while True: # Newline, or bad char.
            global BUS
            c = BUS.read_byte(address)
            if c == 255:
                return False
            elif c == 10:
                break
            else:
                response.append(c)
        parseResponse(response)
    except IOError:
        time.sleep(0.5)
        connectBus()

connectBus()

def updateGPS():
    while True:
        readGPS()
            
################## threading and program execution ##################
if __name__ == '__main__':
    gps_thread = Thread(target = updateGPS)
    
    gps_thread.start()