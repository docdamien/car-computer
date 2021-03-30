from os import system
import serial
import subprocess
import urllib
import urllib.request
import urllib.parse
import array
import requests
from time import sleep

# config GPS and GPRS via FONA
SECONDS_BTW_READS = 10
GPS_DATA = {}
TARGET_URL = "https://80overland.com/gps_logger.php"

# Start PPPD
def openPPPD():
    print("Opening PPPD")
    # Check if PPPD is already running by looking at syslog output
    output1 = subprocess.check_output("cat /var/log/syslog | grep pppd | tail -1", shell=True)
    if b"secondary DNS address" not in output1 and b"locked" not in output1:
        while True:
            # Start the "fona" process
            subprocess.call("sudo pon fona", shell=True)
            sleep(2)
            output2 = subprocess.check_output("cat /var/log/syslog | grep pppd | tail -1", shell=True)
            if b"script failed" not in output2:
                break
    # Make sure the connection is working
    while True:
        output2 = subprocess.check_output("cat /var/log/syslog | grep pppd | tail -1", shell=True)
        output3 = subprocess.check_output("cat /var/log/syslog | grep pppd | tail -3", shell=True)
        if b"secondary DNS address" in output2 or b"secondary DNS address" in output3:
            return True
            print("PPPD opened successfully")

# Stop PPPD
def closePPPD():
    print("turning off cell connection")
    # Stop the "fona" process
    subprocess.call("sudo poff fona", shell=True)
    # Make sure connection was actually terminated
    while True:
        output = subprocess.check_output("cat /var/log/syslog | grep pppd | tail -1", shell=True)
        if b"Exit" in output:
            return True

# Check for a GPS fix
def checkForFix():
    print ("checking for fix")
    # Start the serial connection
    ser=serial.Serial('/dev/serial0', 115200, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=1)
    # Turn on the GPS
    ser.write(b"AT+CGNSPWR=1\r")
    ser.write(b"AT+CGNSPWR?\r")
    while True:
        response = ser.readline()
        if b" 1" in response:
            break
    # Ask for the navigation info parsed from NMEA sentences
    ser.write(b"AT+CGNSINF\r")
    while True:
            response = ser.readline()
            # Check if a fix was found
            if b"+CGNSINF: 1,1," in response:
                print ("fix found")
                print (response)
                return True
            # If a fix wasn't found, wait and try again
            if b"+CGNSINF: 1,0," in response:
                sleep(5)
                ser.write(b"AT+CGNSINF\r")
                print ("still looking for fix")
            else:
                ser.write(b"AT+CGNSINF\r")

# Read the GPS data for Latitude and Longitude
def getCoord():
    # Start the serial connection
    ser=serial.Serial('/dev/serial0', 115200, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=1)
    ser.write(b"AT+CGNSINF\r")
    while True:
        response = ser.readline()
        if b"+CGNSINF: 1," in response:
            # Split the reading by commas and return the parts referencing lat and long
            array = response.split(b",")
            lat = array[3]
            lon = array[4]
            time = array[2]
            speed = array[6]
            return (lat,lon,time,speed)

# Start the program by opening the cellular connection and creating a bucket for our data
if openPPPD():    
    while True:
        # Close the cellular connection
        if closePPPD():
            print ("closing connection")
            sleep(1)
        # The range is how many data points we'll collect before streaming
        for i in range(10):
            # Make sure there's a GPS fix
            if checkForFix():
                # Get lat and long
                if getCoord():
                    latitude, longitude, time, speed = getCoord()
                    coord = str(latitude) + "," + str(longitude)
                    print ("Coordinates:", coord)
                    print ("Time:", time)
                    print ("Step", i, "out of 10")
                    GPS_DATA[i] = {'lat': latitude, 'long' : longitude, 'time' : time, 'speed' : speed}
                    sleep(SECONDS_BTW_READS)
            # Turn the cellular connection on every 10 reads
            if i == 9:
                print ("opening connection")

                if openPPPD():
                    print ("streaming")
                    
                    url_values = urllib.parse.urlencode(GPS_DATA)
                    #print(url_values)

                    full_url = TARGET_URL + '?' + url_values
                    with urllib.request.urlopen(full_url) as response:
                        print(response)
                       
                    print ("streaming complete")
                    GPS_DATA = {}