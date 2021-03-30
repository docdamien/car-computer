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
    
    


################## config LED ##################
GPIO.setmode(GPIO.BCM)
LED_RED = 17
LED_GREEN = 27
LED_BLUE = 22
GPIO.setup(LED_RED, GPIO.OUT, initial= GPIO.LOW)
GPIO.setup(LED_GREEN, GPIO.OUT, initial= GPIO.LOW)
GPIO.setup(LED_BLUE, GPIO.OUT, initial= GPIO.LOW)



################## config display ##################
device = sh1106(i2c(port=1, address=0x3C), rotate=0)
device.clear()

### setup different fonts
FA_solid = ImageFont.truetype('/home/pi/Desktop/fonts/fa-solid-900.ttf', 12)
FA_solid_small = ImageFont.truetype('/home/pi/Desktop/fonts/fa-solid-900.ttf', 12)
text_large = ImageFont.truetype('/home/pi/Desktop/fonts/digital-7.ttf', 54) #54
text_medium = ImageFont.truetype('/home/pi/Desktop/fonts/digital-7.ttf', 24)
text_small = ImageFont.truetype('/home/pi/Desktop/fonts/digital-7.ttf', 12)
 
### Initialize drawing zone (aka entire screen)
output = Image.new("1", (128,64))
add_to_image = ImageDraw.Draw(output)

### coordinates always: padding-left, padding-top. the first pair of zone is always = start
# speed
speed_zone = [(0,0), (72,48)]
speed_start = (0,0)
# if using small layout
#speed_zone = [(16,24), (36,44)]
#speed_start = (16,24)
#speed_icon_zone = [(0,28), (15,40)]
#speed_icon_start = (0,28)
#add_to_image.text(speed_icon_start, "\uf72e", font=FA_solid, fill="white")

# temp_ext
temp_zone = [(104,44), (128,64)]
temp_start = (104,44)
temp_icon_zone = [(92,48), (128,64)]
temp_icon_start = (92,48)

# temp_int
temp_int_zone = [(104,22), (128,20)]
temp_int_start = (104,22)
temp_int_icon_zone = [(86,26), (128,43)]
temp_int_icon_start = (86,26)

# total_km (icon is gps status icon)
total_km_zone = [(16,44), (80,64)]
total_km_start = (16,44)

# altitude
altitude_zone = [(104,0), (128,21)]
altitude_start = (104,0)
altitude_icon_start = (86,4)

# GPS status
#icon_zone = [(104,0), (128,18)] incl size of FA to 16 and not 12, change above!
#icon_start = (104,2)
icon_zone = [(0,48), (15,64)]
icon_start = (0,48)

# load icons
add_to_image.text(icon_start, "\uf252", font=FA_solid, fill="white")
device.display(output)

# usage
#add_to_image.rectangle(speed_zone, fill="black", outline = "black")
#add_to_image.text(speed_start, "\uf00c", font=FA_solid, fill="white")
#device.display(output)




################## config GPS and GPRS via FONA ##################
SECONDS_BTW_READS = 10
READINGS_PER_UPLOAD = 5
READING_NR = 1
TOTAL_KM = 0
prev_lat = 0
prev_long = 0
TARGET_URL = "https://80overland.com/gps_logger.php"




################## config external thermometer ##################
base_dir = '/sys/bus/w1/devices/28-012032ffbd96'
device_file = base_dir + '/w1_slave'
 
def update_temp_ext():
    add_to_image.text(temp_icon_start, "\uf2c9", font=FA_solid_small, fill="white")
    while True:
        f = open(device_file, 'r')
        lines = f.readlines()
        f.close()
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            temp_c = round(float(temp_string) / 1000.0)
            add_to_image.rectangle(temp_zone, fill="black", outline = "black")
            add_to_image.text(temp_start, str(temp_c), font=text_medium, fill="white")
            device.display(output)
            time.sleep(30)





################## config BMP280 ##################
#bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(busio.I2C(board.SCL, board.SDA), 0x76)
#bmp280.sea_level_pressure = 992
 
def update_temp_int():
    return True
#    add_to_image.text(temp_int_icon_start, "\uf5e4", font=FA_solid_small, fill="white")
#    while True:
#        add_to_image.rectangle(temp_int_zone, fill="black", outline = "black")
#        add_to_image.text(temp_int_start, "%0.f" % bmp280.temperature, font=text_medium, fill="white")
#        device.display(output)
#        time.sleep(30)





############################################
############################################
##########      Program start       ########
############################################
############################################



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
    add_to_image.rectangle(icon_zone, fill="black", outline = "black")
    add_to_image.text(icon_start, "\uf124", font=FA_solid, fill="white") #location icon
    device.display(output)
        
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
                #print (response)
                #add_to_image.rectangle(icon_zone, fill="black", outline = "black")
                device.display(output)
                return True
            
            # If a fix wasn't found, wait and try again
            if b"+CGNSINF: 1,0," in response:
                sleep(5)
                ser.write(b"AT+CGNSINF\r")
                print ("still looking for fix")
                add_to_image.rectangle(icon_zone, fill="black", outline = "black")
                add_to_image.text(icon_start, "\uf128", font=FA_solid, fill="white") #X
                device.display(output)
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
            altitude = array[5]
            return (lat,lon,time,speed,altitude)

# Start the program by opening the cellular connection and creating a bucket for our data
def update_speed():
    if openPPPD():    
        GPS_DATA = {}
        while True:
            # Close the cellular connection
            if closePPPD():
                print ("closing connection")
                sleep(1)
            # The range is how many data points we'll collect before streaming
            for i in range(READINGS_PER_UPLOAD):
                # Make sure there's a GPS fix
                if checkForFix():
                    # Get lat and long
                    if getCoord():
                        latitude, longitude, time, speed, altitude = getCoord()
                        coord = str(latitude) + "," + str(longitude)
                        #print ("Coordinates:", coord)
                        #print ("Time:", time)
                        print ("Step", i+1, "out of",READINGS_PER_UPLOAD)
                        
                        add_to_image.rectangle(speed_zone, fill="black", outline = "black")
                        add_to_image.text(speed_start, str(round(float(speed))), font=text_large, fill="white")
                        add_to_image.rectangle(altitude_zone, fill="black", outline = "black")
                        add_to_image.text(altitude_icon_start, "\uf6fc", font=FA_solid, fill="white")
                        add_to_image.text(altitude_start, str(round(float(altitude))), font=text_medium, fill="white")
                        
                        global READING_NR
                        global TOTAL_KM
                        
                        dist = 0
                        if READING_NR != 1:
                            dist = haversine(((float(prev_lat)), (float(prev_long))), ((float(latitude)), (float(longitude))))
                            TOTAL_KM = TOTAL_KM+dist
                            print("Total KM:", TOTAL_KM)
                            add_to_image.rectangle(total_km_zone, fill="black", outline = "black")
                            add_to_image.text(total_km_start, "%0.1f" % TOTAL_KM, font=text_medium, fill="white")
                        
                        prev_lat = latitude
                        prev_long = longitude
                        
                        GPS_DATA[i] = {'lat': latitude, 'long' : longitude, 'time' : time, 'speed' : speed, 'altitude' : altitude}
                        READING_NR +=1
                        device.display(output)
                        
                        sleep(SECONDS_BTW_READS)
                        
                # Turn the cellular connection on every READINGS_PER_UPLOAD reads
                if i == (READINGS_PER_UPLOAD-1):
                    print ("opening connection")
                    add_to_image.rectangle(icon_zone, fill="black", outline = "black")
                    add_to_image.text(icon_start, "\uf7c0", font=FA_solid, fill="white") #sat dish
                    device.display(output)

                    if openPPPD():
                        print ("streaming")                    
                        add_to_image.rectangle(icon_zone, fill="black", outline = "black")
                        add_to_image.text(icon_start, "\uf382", font=FA_solid, fill="white") #upload
                        device.display(output)
                        
                        url_values = urllib.parse.urlencode(GPS_DATA)
                        #print(url_values)

                        full_url = TARGET_URL + '?' + url_values
                        with urllib.request.urlopen(full_url) as response:
                            print(response)
                           
                        print ("streaming complete")
                        GPS_DATA = {}  
                        add_to_image.rectangle(icon_zone, fill="black", outline = "black")
                        add_to_image.text(icon_start, "\uf00c", font=FA_solid, fill="white") #check
                        device.display(output)


if __name__ == '__main__':
    temp_ext_thread = Thread(target = update_temp_ext)
    temp_int_thread = Thread(target = update_temp_int)
    speed_thread = Thread(target = update_speed)
    
    temp_ext_thread.start()
    temp_int_thread.start()
    speed_thread.start()
    
    speed_thread.join()