import os
from os import system
from time import sleep
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import sh1106
from PIL import ImageFont

# config display
device = sh1106(i2c(port=1, address=0x3C), rotate=0)
device.clear()

FA_solid = ImageFont.truetype('/home/pi/Desktop/fonts/fa-solid-900.ttf', 16)
FA_regular = ImageFont.truetype('/home/pi/Desktop/fonts/fa-regular-400.ttf', 16)

device.clear()
with canvas(device) as draw:
    draw.text((0, 0), text="\uf382", font=FA_solid, fill="white")
    draw.text((112, 2), text="\uf124", font=FA_solid, fill="white")
sleep(10)
device.clear()