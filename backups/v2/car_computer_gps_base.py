from os import system
from threading import Thread
import glob
import serial
import subprocess
import urllib
import urllib.request
import urllib.parse
import array
import requests
from time import sleep
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import sh1106
from PIL import ImageFont, Image, ImageDraw
import time
import board
import busio
import adafruit_bmp280
import subprocess
import RPi.GPIO as GPIO
from haversine import haversine, Unit
import csv
import pandas
import sqlalchemy
import datetime
import pathlib
import json
import smbus
import logging
import pynmea2


################## config GPRS via FONA ##################
target_url = "https://80overland.com/gps_logger.php"



################## config display ##################
device = sh1106(i2c(port=1, address=0x3c), rotate=0)
device.clear()
global pending_redraw
pending_redraw = False

### setup different fonts
FA_solid = ImageFont.truetype('/home/pi/Desktop/fonts/fa-solid-900.ttf', 12)
FA_solid_largest = ImageFont.truetype('/home/pi/Desktop/fonts/fa-solid-900.ttf', 40)
text_largest = ImageFont.truetype('/home/pi/Desktop/fonts/digital-7.ttf', 58)
text_medium = ImageFont.truetype('/home/pi/Desktop/fonts/digital-7.ttf', 24)
text_small = ImageFont.truetype('/home/pi/Desktop/fonts/digital-7.ttf', 12)
 
### Initialize drawing zone (aka entire screen)
output = Image.new("1", (128,64))
add_to_image = ImageDraw.Draw(output)

### coordinates always: padding-left, padding-top. the first pair of zone is always = start

# temp_ext
temp_zone = [(14,44), (36,64)]
temp_start = (14,44)
temp_icon_zone = [(0,48), (15,64)]
temp_icon_start = (3,48)

# alti
alti_zone = [(14,22), (69,40)]
alti_start = (14,22)
alti_icon_zone = [(0,24), (15,40)]
alti_icon_start = (0,26)

# distance
dist_zone = [(14,0), (69,21)]
dist_start = (14,0)
dist_icon_zone = [(0,4), (15,21)]
dist_icon_start = (0,4)

# speed
speed_zone = [(70,0), (128,48)]
speed_start = (70,0)

# GPS status, incl. GPS startup icon
#status_icon_zone = [(118,49), (80,64)]
#status_icon_start = (118,49)
#status_zone = [(74,50), (128,64)]
#status_start = (74,50)
status_icon_zone = [(118,49), (80,64)]
status_icon_start = (118,49)
status_zone = [(74,50), (128,64)]
status_start = (74,50)

# usage
#add_to_image.rectangle(speed_zone, fill="black", outline = "black")
#add_to_image.text(speed_start, "\uf00c", font=FA_solid, fill="white")
#device.display(output)




################## config and start GPS ##################
BUS = None
address = 0x42
gpsReadInterval = 1
reading_nr = 1
total_km = 0
prev_lat = 0
prev_long = 0
# http://ava.upuaut.net/?p=768

def connectBus():
    global BUS
    BUS = smbus.SMBus(1)

def parseResponse(gpsLine):
    gpsChars = ''.join(chr(c) for c in gpsLine)
    local_pending_redraw = False
    
    if "$GNGGA" in gpsChars:
        if ",1," not in gpsChars:
            print("Looking for fix... (GGA)")
            add_to_image.rectangle(status_icon_zone, fill="black", outline = "black")
            add_to_image.rectangle(status_zone, fill="black", outline = "black")
            add_to_image.text(status_icon_start, "\uf252", font=FA_solid, fill="white")
            add_to_image.text(status_start, "GPS...", fill="white")
            return False
        try:
            nmea = pynmea2.parse(gpsChars, check=True)
            print('%.6f'%(nmea.latitude), ",",'%.6f'%(nmea.longitude), ", sats:", nmea.num_sats, ", alt:", nmea.altitude) # GGA
            
            ## update altitude
            add_to_image.text(alti_icon_start, "\uf077", font=FA_solid, fill="white")
            add_to_image.rectangle(alti_zone, fill="black", outline = "black")
            add_to_image.text(alti_start, str('%.0f'%(nmea.altitude)), font=text_medium, fill="white")
            
            ## fix found, show nb satelites
            add_to_image.rectangle(status_icon_zone, fill="black", outline = "black")
            add_to_image.rectangle(status_zone, fill="black", outline = "black")
            text_sats = "Sats.:" + nmea.num_sats
            add_to_image.text(status_start, text_sats, fill="white")
            
            ## update total distance
            global reading_nr
            global total_km
            global prev_lat
            global prev_long
            dist = 0
            if reading_nr != 1:
                dist = haversine(((float(prev_lat)), (float(prev_long))), ((float(nmea.latitude)), (float(nmea.longitude))))
                total_km = total_km+dist
                print("Total KM:", total_km)
                add_to_image.text(dist_icon_start, "\uf1b9", font=FA_solid, fill="white")
                add_to_image.rectangle(dist_zone, fill="black", outline = "black")
                add_to_image.text(dist_start, "%0.1f" % total_km, font=text_medium, fill="white")
            prev_lat = nmea.latitude
            prev_long = nmea.longitude
            reading_nr +=1
            
            ## log every 10th GPS coordinate in CSV file
            if reading_nr % 10 == 0:
                filename = 'data/gps/gps_' + datetime.datetime.now().strftime("%Y%m%d") + '.csv'
                with open(filename, 'a', newline='') as csvfile:
                    gps_writer = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
                    gps_writer.writerow([nmea.timestamp, nmea.latitude, nmea.longitude, nmea.altitude])
            
            local_pending_redraw = True
            
        except Exception as e:
            print("NMEA parse error (GGA)")
            print(e)
            pass
        
    if "$GNRMC" in gpsChars:
        if ",A," not in gpsChars: # 1 for GGA, A for RMC
            print("Looking for fix... (RMC)")
            return False
        try:
            nmea = pynmea2.parse(gpsChars, check=True)
            print("Speed: ", nmea.spd_over_grnd) # RMC
            ## update speed
            add_to_image.rectangle(speed_zone, fill="black", outline = "black")
            add_to_image.text(speed_start, str('%.0f'%(nmea.spd_over_grnd)), font=text_largest, fill="white")
            local_pending_redraw = True
        except Exception as e:
            print("NMEA parse error (RMC)")
            print(e)
            pass
        
    if local_pending_redraw == True:
        global pending_redraw
        pending_redraw = True

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
def updateGPS(gpsReadInterval=1):
    while True:
        readGPS()
        #sleep(gpsReadInterval)





################## config external thermometer ##################
def update_temp_ext(temp_signature='t=', update_interval=60):
    add_to_image.text(temp_icon_start, "\uf2c9", font=FA_solid, fill="white")
    while True:
        f = open('/sys/bus/w1/devices/28-012032ffbd96/w1_slave', 'r')
        lines = f.readlines()
        f.close()
        equals_pos = lines[1].find(temp_signature)
        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            temp_c = round(float(temp_string) / 1000.0)
            add_to_image.rectangle(temp_zone, fill="black", outline = "black")
            add_to_image.text(temp_start, str(temp_c), font=text_medium, fill="white")
            global pending_redraw
            pending_redraw = True
            
            filename = 'data/temp_ext/tempext_' + datetime.datetime.now().strftime("%Y%m%d") + '.csv'
            with open(filename, 'a', newline='') as csvfile:
                temp_ext_writer = csv.writer(csvfile, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)
                temp_ext_writer.writerow([str(temp_c)])
            
            time.sleep(update_interval)
            
            
            
    

################## update display ##################
def update_display():
    while True:
        # there is a potential race condition here, not critical
        global pending_redraw
        if pending_redraw:
            pending_redraw = False
            device.display(output)
        time.sleep(0.5)
            
            

################## start cellular connection ##################          
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
    print("turning off PPPD")
    # Stop the "fona" process
    subprocess.call("sudo poff fona", shell=True)
    # Make sure connection was actually terminated
    while True:
        output = subprocess.check_output("cat /var/log/syslog | grep pppd | tail -1", shell=True)
        if b"Exit" in output:
            return True


            
            
            
            
            
            
            
            
################## threading and program execution ##################
if __name__ == '__main__':
    temp_ext_thread = Thread(target = update_temp_ext)
    display_thread = Thread(target=update_display)
    gps_thread = Thread(target = updateGPS)
    
    temp_ext_thread.start()
    display_thread.start() 
    gps_thread.start()
    
    display_thread.join()