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
import re
import urllib
from urllib import request
import random
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import sh1106
from PIL import ImageFont, Image, ImageDraw
import pymysql
import csv
import json
import hashlib 
import pynmea2
from haversine import haversine, Unit
config = configparser.ConfigParser()
config.read('/home/pi/Desktop/car_computer.ini')

################## start display ##################
device = sh1106(i2c(port=1, address=config['display']['i2c_port']), rotate=0)
device.clear()
pending_redraw = False
output = Image.new("1", (128,64))
add_to_image = ImageDraw.Draw(output)
def setup_font(font_filename, size):
    return ImageFont.truetype(os.path.join(config['general']['folder'],config['general']['folder_fonts'],font_filename), size)
fa_solid = setup_font(config['general']['font_icons'], 12)
fa_solid_largest = setup_font(config['general']['font_icons'], 40)
text_largest = setup_font(config['general']['font_texts'], 58)
text_medium = setup_font(config['general']['font_texts'], 24)
text_small = setup_font(config['general']['font_texts'], 18)
icons = { #to look up the icons on FontAwesome.com, remove quote marks and \u from the search query 
    "save": "\uf56f","cloud": "\uf0c2","error": "\uf00d","check": "\uf058","upload": "\uf382","no_conn": "\uf127","location": "\uf124","question": "\uf128","altitude": "\uf077","distance": "\uf1b9","temperature": "\uf2c9" }
def wipe(zone):
    add_to_image.rectangle(tuple(int(v) for v in re.findall("[0-9]+", config['display'][zone])), fill="black", outline ="black")
def icon(zone,name):
    add_to_image.text(tuple(int(v) for v in re.findall("[0-9]+", config['display'][zone])), icons[name], font=fa_solid, fill="white")
def text(zone,text,fontsize=text_medium):
    add_to_image.text(tuple(int(v) for v in re.findall("[0-9]+", config['display'][zone])), text, font=fontsize, fill="white")

################## upload data from GPS folder via FONA to MySQL ##################
def fix_nulls(s):
    return (line.replace('\0', '') for line in s)
def upload_data():
    sleep(60)
    
    global pending_redraw
    while True:
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
            openPPPD()
            
            if config['db']['mode'] == "db":
                print("mode = db")
                try:
                    db = pymysql.connect(config['db']['db_host'],config['db']['db_user'],config['db']['db_pw'],config['db']['db_name'])
                    cursor = db.cursor()
                    csv_data = csv.reader(fix_nulls(open(oldest_file)))
                    next(csv_data)
                    for row in csv_data:
                        if row:
                            statement = 'INSERT INTO '+config['db']['db_table']+' (gps_time, gps_lat, gps_long, gps_speed) VALUES (%s, %s, %s, %s)'
                            cursor.execute(statement,row)
                    print("Committing to db")
                    db.commit()
                    cursor.close()
                except:
                    print("DB insert error")
                
            if config['db']['mode'] == "server":
                print("mode = server")
                try:
                    csv_data = csv.reader(fix_nulls(open(oldest_file)))
                    next(csv_data)
                    row_nb = 1
                    row_data = {}
                    rows_encoded_nb = 1
                    rows_encoded = {}
                    for row in csv_data:
                        if row:
                            row_data[row_nb] = {'gps_time': int(row[0]), 'gps_lat' : round(float(row[1]), 5), 'gps_long' : round(float(row[2]), 5), 'gps_speed' : round(float(row[3]), 1)}
                            if row_nb % int(config['db']['server_batchsize']) == 0:
                                rows_encoded[rows_encoded_nb] = row_data
                                rows_encoded_nb +=1
                                row_data = {}
                            row_nb +=1
                    rows_encoded[rows_encoded_nb] = row_data
                    row_data = {}
                       
                    for i in rows_encoded : 
                        if rows_encoded[i]:
                            checksum = hashlib.md5(str(rows_encoded[i]).encode())
                            checksum = checksum.hexdigest()
                            
                            req = request.Request(config['db']['server_addr'], method="POST")
                            req.add_header('Content-Type', 'application/json')
                            data = {
                                "hash": checksum,
                                "ID": config['db']['server_ID'],
                                "pw": config['db']['server_pw'],
                                "data": rows_encoded[i]
                            }
                            data = json.dumps(data)
                            data = data.encode()
                            r = request.urlopen(req, data=data)
                            print(r.read())     
                except:
                    print("Server error")

            closePPPD()
            print("Successfully committed to db")
            wipe('GPRS_ZONE')
            icon('GPRS_START',"check")
            pending_redraw = True

            os.rename(current_dir+"/"+oldest_file_name, archive_dir+"/archive_"+oldest_file_name)        
            sleep(60)
            wipe('GPRS_ZONE')
            
        except Exception as e:
            print("Database error:", e)
            wipe('GPRS_ZONE')
            icon('GPRS_START',"no_conn")
            pending_redraw = True
            closePPPD()
            sleep(60)
            wipe('GPRS_ZONE')
            pending_redraw = True
            return
        
        sleep(300)
        
################## config and start GPS ##################
BUS = None
reading_nr = 1
reading_nr_upload = 1
reading_nr_upload_nbrowsinlog = 0
total_km = 0
prev_lat = 0
prev_long = 0

def connectBus():
    global BUS
    BUS = smbus.SMBus(1)

def debug_gps():
    sleep(1)
    time = datetime.datetime.now()
    gga1 = pynmea2.GGA('GN', 'GGA', (time.strftime("%H%M%S"), '5231.059', 'N', '01324.946', 'E', '1', '04', '2.6', '69.00', 'M', '-33.9', 'M', '', '0000'))
    gga2 = pynmea2.GGA('GN', 'GGA', (time.strftime("%H%M%S"), '5231.058', 'N', '01324.946', 'E', '0', '04', '2.6', '73.00', 'M', '-33.9', 'M', '', '0000'))
    gga3 = pynmea2.GGA('GN', 'GGA', (time.strftime("%H%M%S"), '5231.057', 'N', '01324.946', 'E', '1', '04', '2.6', '73.00', 'M', '-33.9', 'M', '', '0000'))
    rmc1 = pynmea2.RMC('GN', 'RMC', (time.strftime("%H%M%S"), 'A',  '5231.056', 'N', '01324.946', 'E', '0', '26.2', time.strftime("%d%m%y"), 'A'))
    rmc2 = pynmea2.RMC('GN', 'RMC', (time.strftime("%H%M%S"), 'A',  '5231.060', 'N', '01324.946', 'E', '2', '324.2', time.strftime("%d%m%y"), 'A'))
    nmea = [gga1,rmc1,gga2,gga3,rmc2]
    return str(random.choice(nmea))

def parseResponse(gpsLine):
    global pending_redraw
    gpsChars = ''.join(chr(c) for c in gpsLine)
    
    ##### uncomment only for testing when the GPS chip has no reception #####
    #gpsChars = debug_gps()
    #print(gpsChars)
    
    if "GGA" in gpsChars:
        if ",1," not in gpsChars:
            print("GGA?")
            wipe('ALL')
            wipe('STATUS_ZONE')
            wipe('STATUS_ICON_ZONE')
            icon('STATUS_ICON_START', "location")
            pending_redraw = True
            sleep(1)
            return False
        try:
            nmea = pynmea2.parse(gpsChars, check=True)
            
            #we have a location, wipe
            wipe('STATUS_ICON_ZONE')
            
            ## update altitude
            icon('ALTI_ICON_START', "altitude")
            wipe('ALTI_ZONE')
            text('ALTI_START', str('%.0f'%(nmea.altitude)))
            
            ## update total distance
            global reading_nr
            global total_km
            global prev_lat
            global prev_long
            dist = 0
            if reading_nr != 1:
                dist = haversine(((float(prev_lat)), (float(prev_long))), ((float(nmea.latitude)), (float(nmea.longitude))))
                total_km = total_km+dist
                icon('DIST_ICON_START', "distance")
                wipe('DIST_ZONE')
                if total_km < 100:
                    text('DIST_START', "%0.1f" % total_km)
                if total_km >= 100:
                    text('DIST_START', "%0.f" % total_km)
            prev_lat = nmea.latitude
            prev_long = nmea.longitude
            
            pending_redraw = True
            reading_nr +=1
            
        except Exception as e:
            print("GGA parse error:", e)
            wipe('STATUS_ICON_ZONE')
            icon('STATUS_ICON_START', "question")
            pending_redraw = True
            pass
        
    if "RMC" in gpsChars:
        if ",A," not in gpsChars: # 1 for GGA, A for RMC
            print("RMC?")
            wipe('ALL')
            wipe('STATUS_ZONE')
            wipe('STATUS_ICON_ZONE')
            icon('STATUS_ICON_START', "location")
            pending_redraw = True
            sleep(1)
            return False
        try:
            nmea = pynmea2.parse(gpsChars, check=True)
            
            #we have a location, wipe
            wipe('STATUS_ICON_ZONE')
            
            #update heading info
            wipe('STATUS_ZONE')
            dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
            ix = round(nmea.true_course / (360. / len(dirs)))
            text('STATUS_START_TEXT', dirs[ix % len(dirs)])
            
            ## update speed
            wipe('SPEED_ZONE')
            text('SPEED_START', str('%.0f'%(nmea.spd_over_grnd*1.852)), fontsize=text_largest)
            
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
                #print("Added to log. Total in Log from this session is", reading_nr_upload_nbrowsinlog)
                #wipe('STATUS_ZONE')
                #icon('STATUS_START',"save")
                wipe('STATUS_ICON_ZONE')
                icon('STATUS_ICON_START', "save")


            reading_nr_upload +=1
            pending_redraw = True
            
        except Exception as e:
            print("RMC parse error:", e)
            wipe('STATUS_ICON_ZONE')
            icon('STATUS_ICON_START', "question")
            pending_redraw = True
            pass

def readGPS():
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
        time.sleep(0.2)
        connectBus()

connectBus()
def updateGPS():
    while True:
        readGPS()

################## config external thermometer ##################
def update_temp_ext(temp_signature='t=', update_interval=config['temp_ext']['update_interval']):
    global pending_redraw
    try:
        icon('TEMP_ICON_START', "temperature")
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
                wipe('TEMP_ZONE')
                text('TEMP_START', str(temp_c))
                pending_redraw = True
                time.sleep(int(update_interval))
    except Exception as e:
        print("Temperature error:", e)
        icon('TEMP_ICON_START', "temperature")
        wipe('TEMP_ZONE')
        icon('TEMP_START', "error")
        pending_redraw = True
        time.sleep(int(update_interval))
        pass
            

################## update display ##################
def update_display():
    sleep(0.5)
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
    wipe('GPRS_ZONE')
    icon('GPRS_START', "cloud")
    global pending_redraw
    pending_redraw = True
    sleep(20)
    try:
        urllib.request.urlopen(config['db']['ping'])
        print("Connection is on")
        wipe('GPRS_ZONE')
        icon('GPRS_START', "upload")
        pending_redraw = True
        return True
    except:
        print("Connection error")
        wipe('GPRS_ZONE')
        icon('GPRS_START', "no_conn")
        pending_redraw = True
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