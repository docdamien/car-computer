import os
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

def openPPPD():
    print("Opening PPPD")
    
    subprocess.call("sudo pon fona", shell=True)
    print("FONA on")
    
    sleep(30)
    try:
        urllib.request.urlopen('http://google.com')
        print("Connection is on")
        return True
    except:
        print("No connection")
        return False

# Stop PPPD
def closePPPD():
    print("turning off PPPD")
    subprocess.call("sudo poff fona", shell=True)
    print("turned off")
    return True

openPPPD()
sleep(5)
closePPPD()