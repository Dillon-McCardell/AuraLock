# File to restart pigpio daemon if necessary

import os
import time
os.system('sudo killall pigpiod')
time.sleep(1)
os.system('sudo pigpiod')
