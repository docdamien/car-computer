from time import sleep
import board
import busio
import adafruit_bmp280

bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(busio.I2C(board.SCL, board.SDA), 0x76)
 
# change this to match the location's pressure (hPa) at sea level
bmp280.sea_level_pressure = 992
 
while True:
    print("\nTemperature: %0.1f C" % bmp280.temperature)
    print("Pressure: %0.1f hPa" % bmp280.pressure)
    print("Altitude = %0.2f meters" % bmp280.altitude)
    time.sleep(2)
    #device.clear()