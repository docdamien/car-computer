from threading import Thread
import smbus
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
    if "$GNGGA" in gpsChars:
        if ",1," not in gpsChars:
            print("Looking for fix... (GGA)")
            return False
        try:
            nmea = pynmea2.parse(gpsChars, check=True)
            print('%.6f'%(nmea.latitude), ",",'%.6f'%(nmea.longitude), ", sats:", nmea.num_sats, ", alt:", nmea.altitude) # GGA
            #alti_display(nmea.altitude)
        except Exception:
            print("NMEA parse error (GGA)")
            pass
    if "$GNRMC" in gpsChars:
        if ",A," not in gpsChars: # 1 for GGA, A for RMC
            print("Looking for fix... (RMC)")
            return False
        try:
            nmea = pynmea2.parse(gpsChars, check=True)
            print('%.6f'%(nmea.latitude), ",",'%.6f'%(nmea.longitude), ",", nmea.spd_over_grnd) # RMC
            #speed_display(nmea.spd_over_grnd)
        except Exception:
            print("NMEA parse error (RMC)")
            pass

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
        time.sleep(1)
        connectBus()

connectBus()

def updateGPS():
    while True:
        readGPS()
            
################## threading and program execution ##################
if __name__ == '__main__':
    gps_thread = Thread(target = updateGPS)
    
    gps_thread.start()