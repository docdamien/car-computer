# Needed modules will be imported
import RPi.GPIO as GPIO
import time
   
GPIO.setmode(GPIO.BCM)
   
# The output pins will be declared, which are connected with the LEDs.
LED_RED = 17
LED_GREEN = 27
LED_BLUE = 22
 
GPIO.setup(LED_RED, GPIO.OUT, initial= GPIO.LOW)
GPIO.setup(LED_GREEN, GPIO.OUT, initial= GPIO.LOW)
GPIO.setup(LED_BLUE, GPIO.OUT, initial= GPIO.LOW)

  

   
# Scavenging work after the end of the program
GPIO.cleanup()

def LED_on(duration, color):
    if "red" in color:
        GPIO.output(LED_RED,GPIO.HIGH) #LED will be switched ON
        GPIO.output(LED_GREEN,GPIO.LOW) #LED will be switched OFF
        GPIO.output(LED_BLUE,GPIO.LOW) #LED will be switched OFF
        time.sleep(duration)
        GPIO.cleanup()
        
LED_on(1,"red")