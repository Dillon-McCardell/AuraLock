# Helper file for AuraLock 
# Consolidates code to extend and retract deadbolt

import time
import os
import pigpio
import busio
import read_PWM
import board
import digitalio
from adafruit_servokit import ServoKit
from adafruit_mcp3xxx.analog_in import AnalogIn
import adafruit_mcp3xxx.mcp3008 as MCP
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
cs = digitalio.DigitalInOut(board.D13)
mcp = MCP.MCP3008(spi, cs)
channel = AnalogIn(mcp, MCP.P0)


kit = ServoKit(channels=16)

PWM_GPIO = 20
RUN_TIME = 60.0
SAMPLE_TIME = 2.0

pi = pigpio.pi()

p = read_PWM.reader(pi, PWM_GPIO)
global pw
pw = 0

# Extending the deadbolt is more complicated, as the gear must not
# be in contact with the deadbolt once fully extended
def extend():
  while True:
    while(channel.value < 36000):
      kit.continuous_servo[0].throttle = -0.1
    time.sleep(0.05)
    if(channel.value >= 36000):
      break
    else:
      pass
  kit.continuous_servo[0].throttle = 0.1
  while True:
    pw = p.pulse_width()
    print(pw)
    if pw is 0:
      os.system('sudo killall pigpiod')
      os.system('sudo pigpiod')
      print('pigpiod restarted')
    # Retract the deadbolt only slighlty until the pulse width of the servo
    # indicates the gear is not in contact with the deadbolt. These values
    # have been aquired through manual testing.
    if pw in range(80,300) or pw in range(610,870): 
      print('break at',pw)
      break
    time.sleep(0.05)
    if channel.value > 36000: break
  kit.continuous_servo[0].throttle = 0

# Retract simple retracts the deadbolt until resistance is met
def retract():
  while True:
    while(channel.value < 36000):
      kit.continuous_servo[0].throttle = 0.15
    time.sleep(0.05)
    if(channel.value >= 36000):
      break
    else:
      pass
  kit.continuous_servo[0].throttle = 0

# Range 415 > pw > 175
# Range 945 > pw > 700