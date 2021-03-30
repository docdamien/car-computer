## System stuff
import os
from threading import Thread
import glob
import serial
import board
import subprocess
import smbus
import time
from time import sleep
import datetime
import configparser
import urllib
from urllib import request
## Display stuff
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import sh1106
from PIL import ImageFont, Image, ImageDraw
## GPS
import pymysql
import csv
import pynmea2
from haversine import haversine, Unit
## read config file
config = configparser.ConfigParser()
config.read('/home/pi/Desktop/car_computer.ini')

### start display ###
device = sh1106(i2c(port=1, address=config['display']['i2c_port']), rotate=0)
device.clear()
pending_redraw = False

### setup different fonts
def setup_font(font_filename, size):
    return ImageFont.truetype(os.path.join(config['general']['folder'],config['general']['folder_fonts'],font_filename), size)
fa_solid = setup_font('fa-solid-900.ttf', 12)
fa_solid_largest = setup_font('fa-solid-900.ttf', 40)
text_largest = setup_font('digital-7.ttf', 58)
text_medium = setup_font('digital-7.ttf', 24)
text_small = setup_font('digital-7.ttf', 18)
 
### Initialize drawing zone (aka entire screen)
output = Image.new("1", (128,64))
add_to_image = ImageDraw.Draw(output)

### coordinates always: padding-left, padding-top. the first pair of zone is mostly = start (except to offset small icons)
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
speed_zone = [(66,0), (128,45)]
speed_start = (66,0)
# GPRS status
gprs_zone = [(114,46), (128,64)]
gprs_start = (114,50)
# GPS status, incl. GPS startup icon
status_icon_zone = [(70,50), (88,64)]
status_icon_start = (70,50)
status_zone = [(86,46), (113,64)]
status_start_text = (86,46)
status_start = (86,50)


################## upload data from GPS folder via FONA to MySQL ##################
def fix_nulls(s):
    return (line.replace('\0', '') for line in s)
def upload_data():
    while True:
        sleep(5)
        current_dir = os.path.join(config['general']['folder'],config['general']['folder_data'])
        archive_dir = os.path.join(config['general']['folder'],config['general']['folder_data_archive'])
        path, dirs, files = next(os.walk(current_dir))
        file_count = len(files)
        if file_count < 2:
            print("Not enough GPS.csv files found so it's probably in use now or doesn't exist")
            return
        list_of_files = glob.glob(current_dir+"/*.csv")
        oldest_file = min(list_of_files, key=os.path.getctime)
        oldest_file_name = os.path.basename(oldest_file)
        
        try:
            add_to_image.rectangle(gprs_zone, fill="black", outline = "black")
            add_to_image.text(gprs_start, "\uf0c2", font=fa_solid, fill="white")
            global pending_redraw
            pending_redraw = True
            openPPPD()
            print("Opening remote db: done")
            
            db = pymysql.connect(config['db']['host'],config['db']['user'],config['db']['pw'],config['db']['name'])
            cursor = db.cursor()
            csv_data = csv.reader(fix_nulls(open(oldest_file)))
            next(csv_data)
            for row in csv_data:
                if row:
                    statement = 'INSERT INTO '+config['db']['table']+' (gps_time, gps_lat, gps_long, gps_speed) VALUES (%s, %s, %s, %s)'
                    cursor.execute(statement,row)
            print("Committing to db")
            db.commit()
            cursor.close()
            closePPPD()
            print("Successfully committed to db")
            add_to_image.rectangle(gprs_zone, fill="black", outline = "black")
            add_to_image.text(gprs_start, "\uf058", font=fa_solid, fill="white")
            pending_redraw = True

            os.rename(current_dir+"/"+oldest_file_name, archive_dir+"/archive_"+oldest_file_name)        
            sleep(60)
            add_to_image.rectangle(gprs_zone, fill="black", outline = "black")
            
        except Exception as e:
            print("Database error:", e)        
            sleep(60)
            add_to_image.rectangle(gprs_zone, fill="black", outline = "black")
            return
        
        sleep(300)
        
################## config and start GPS ##################
BUS = None
gpsReadInterval = 1
reading_nr = 1
reading_nr_upload = 1
reading_nr_upload_nbrowsinlog = 0
total_km = 0
prev_lat = 0
prev_long = 0

def connectBus():
    global BUS
    BUS = smbus.SMBus(1)

def parseResponse(gpsLine):
    local_pending_redraw = False
    global pending_redraw
    gpsChars = ''.join(chr(c) for c in gpsLine)
    # debug only
    #gpsChars = "$GNGGA,161229.487,3723.2475,N,12158.3416,W,1,07,1.0,9.0,M,,,,0000*06"
    #gpsChars = "$GNRMC,210230.00,A,3855.4487,N,09446.0071,W,8.088,076.2,130420,,A*7E"
    
    if "GGA" in gpsChars:
        if ",1," not in gpsChars:
            print("GGA?")
            add_to_image.rectangle(status_icon_zone, fill="black", outline = "black")
            add_to_image.rectangle(status_zone, fill="black", outline = "black")
            add_to_image.text(status_icon_start, "\uf124", font=fa_solid, fill="white")
            add_to_image.text(status_start, "\uf128", font=fa_solid, fill="white")
            pending_redraw = True
            sleep(1)
            return False
        try:
            nmea = pynmea2.parse(gpsChars, check=True)
            if "0.0" in str(nmea.latitude) or "0.0" in str(nmea.longitude):
                return False
            
            ## update altitude
            add_to_image.text(alti_icon_start, "\uf077", font=fa_solid, fill="white")
            add_to_image.rectangle(alti_zone, fill="black", outline = "black")
            add_to_image.text(alti_start, str('%.0f'%(nmea.altitude)), font=text_medium, fill="white")
            
            ## update total distance
            global reading_nr
            global total_km
            global prev_lat
            global prev_long
            dist = 0
            if reading_nr != 1:
                dist = haversine(((float(prev_lat)), (float(prev_long))), ((float(nmea.latitude)), (float(nmea.longitude))))
                total_km = total_km+dist
                add_to_image.text(dist_icon_start, "\uf1b9", font=fa_solid, fill="white")
                add_to_image.rectangle(dist_zone, fill="black", outline = "black")
                add_to_image.text(dist_start, "%0.1f" % total_km, font=text_medium, fill="white")
            prev_lat = nmea.latitude
            prev_long = nmea.longitude
            
            local_pending_redraw = True
            reading_nr +=1
            
        except Exception as e:
            print("GGA parse error:", e)
            add_to_image.rectangle(status_zone, fill="black", outline = "black")
            local_pending_redraw = True
            pass
        
    if "RMC" in gpsChars:
        if ",A," not in gpsChars: # 1 for GGA, A for RMC
            print("RMC?")
            add_to_image.rectangle(status_icon_zone, fill="black", outline = "black")
            add_to_image.rectangle(status_zone, fill="black", outline = "black")
            add_to_image.text(status_icon_start, "\uf124", font=fa_solid, fill="white")
            add_to_image.text(status_start, "\uf128", font=fa_solid, fill="white")
            pending_redraw = True
            sleep(1)
            return False
        try:
            nmea = pynmea2.parse(gpsChars, check=True)
            if "0.0" in str(nmea.latitude) or "0.0" in str(nmea.longitude):
                return False

            add_to_image.rectangle(status_zone, fill="black", outline = "black")
            
            ## update speed
            add_to_image.rectangle(speed_zone, fill="black", outline = "black")
            add_to_image.text(speed_start, str('%.0f'%(nmea.spd_over_grnd*1.852)), font=text_largest, fill="white")
            local_pending_redraw = True
            
            ## log every log_frequency nth GPS coordinate in CSV file
            global reading_nr_upload
            global reading_nr_upload_nbrowsinlog
            if reading_nr_upload % int(config['gps']['log_frequency']) == 0:
                t = datetime.datetime.combine(nmea.datestamp, nmea.timestamp).strftime("%s")
                d = datetime.datetime.combine(nmea.datestamp, nmea.timestamp).strftime("%Y%m%d%H")
                filename = os.path.join(config['general']['folder'],config['general']['folder_data'],'gps_' + d + '.csv')
                with open(filename, 'a', newline='') as csvfile:
                    gps_writer = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
                    gps_writer.writerow([t, nmea.latitude, nmea.longitude, nmea.spd_over_grnd*1.852])
                reading_nr_upload_nbrowsinlog +=1
                print("Added to log. Total in Log from this session is", reading_nr_upload_nbrowsinlog)
                add_to_image.rectangle(status_icon_zone, fill="black", outline = "black")
                add_to_image.rectangle(status_zone, fill="black", outline = "black")
                add_to_image.text(status_icon_start, "\uf124", font=fa_solid, fill="white")
                add_to_image.text(status_start, "\uf56f", font=fa_solid, fill="white")
            reading_nr_upload +=1
            
        except Exception as e:
            print("RMC parse error:", e)
            add_to_image.rectangle(status_zone, fill="black", outline = "black")
            local_pending_redraw = True
            pass
    
    if local_pending_redraw == True:
        pending_redraw = True

def readGPS(gpsReadInterval=1):
    c = None
    response = []
    try:
        while True: # Newline, or bad char.
            global BUS
            c = BUS.read_byte(int(config['gps']['i2c_port'], 16))
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

################## config external thermometer ##################
def update_temp_ext(temp_signature='t=', update_interval=config['temp_ext']['update_interval']):
    add_to_image.text(temp_icon_start, "\uf2c9", font=fa_solid, fill="white")
    base_dir = config['temp_ext']['w1_folder']
    device_folder = glob.glob(base_dir + '28*')[0]
    device_file = device_folder + '/w1_slave'
    while True:
        f = open(device_file, 'r')
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
            time.sleep(int(update_interval))
            

################## update display ##################
def update_display():
    sleep(2)
    while True:
        global pending_redraw
        if pending_redraw:
            device.display(output)
            pending_redraw = False
        time.sleep(0.2)
            

################## start cellular connection ##################          
def openPPPD():
    subprocess.call("sudo pon fona", shell=True)
    print("FONA on")
    add_to_image.rectangle(gprs_zone, fill="black", outline = "black")
    add_to_image.text(gprs_start, "\uf0c2", font=fa_solid, fill="white")
    global pending_redraw
    pending_redraw = True
    
    sleep(20)
    try:
        add_to_image.rectangle(gprs_zone, fill="black", outline = "black")
        add_to_image.text(gprs_start, "\uf0c2", font=fa_solid, fill="white")
        pending_redraw = True
        urllib.request.urlopen(config['db']['ping'])
        print("Connection is on")
        add_to_image.rectangle(gprs_zone, fill="black", outline = "black")
        add_to_image.text(gprs_start, "\uf382", font=fa_solid, fill="white")
        pending_redraw = True
        return True
    except:
        print("No connection")
        add_to_image.rectangle(gprs_zone, fill="black", outline = "black")
        add_to_image.text(gprs_start, "\uf127", font=fa_solid, fill="white")
        pending_redraw = True
        sleep(5)
        return False

# Stop PPPD
def closePPPD():
    print("turning off PPPD")
    subprocess.call("sudo poff fona", shell=True)
    print("turned off")
    return True
            
################## threading and program execution ##################
if __name__ == '__main__':
    temp_ext_thread = Thread(target = update_temp_ext)
    display_thread = Thread(target=update_display)
    gps_thread = Thread(target = updateGPS)
    data_thread = Thread(target = upload_data)
    
    display_thread.start() 
    gps_thread.start()
    data_thread.start()
    temp_ext_thread.start()
    
    display_thread.join()