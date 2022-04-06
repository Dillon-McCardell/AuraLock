# AuraLock Facial Recognition Door Lock Project
# Dillon McCardell


#Imports for ADC
import busio
#from cv2 import namedWindow
import digitalio
import board
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_servokit import ServoKit
import RPi.GPIO as GPIO
from adafruit_mcp3xxx.analog_in import AnalogIn
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
cs = digitalio.DigitalInOut(board.D13)
mcp = MCP.MCP3008(spi, cs)
kit = ServoKit(channels=16)
channel = AnalogIn(mcp, MCP.P0)

# Imports for Facial Recognition
import face_recognition
import picamera
import numpy as np
import os

# Import for deadbolt file
import deadbolt

#dictionary to store facial recognition images
images_dict = {}
encodings_dict = {}
#List to store the values from the encoding_dict
global encodings_list
encodings_list = []
# Variable to halt image capture
global imageHalt 
imageHalt = False
# Variable to halt doorSense_thread
global lockHalt
lockHalt = False
# Variable to allow anyone to unlock home when 'DelayedUnlock' is true
global delayedUnlock 
delayedUnlock = False

# Get a reference to the Raspberry Pi camera.
camera = picamera.PiCamera()
camera.resolution = (320, 240)
output = np.empty((240, 320, 3), dtype=np.uint8)

#Imports for Firebase
import time
import pyrebase

#import for threading
from threading import *

#imports for Firebase Admin SDK (not working)
import firebase_admin
from firebase_admin import credentials
cred = credentials.Certificate("/home/pi/Documents/AuraLock/ServiceAccountCredentials.json")
firebase_admin.initialize_app(cred)

# Imports for GPIO (doorSensor and LED)
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
doorSensor = 16
led = 19
GPIO.setup(doorSensor,GPIO.IN)
GPIO.setup(led,GPIO.OUT)
# Set LED to OFF to start
GPIO.output(led,False)


try:     
    #On startup unlock the door, then wait to see if the door is closed, and then lock it
    print('Unlocking Door')
    deadbolt.retract()
    # Wait for the door to be closed
    print('Waiting for the Door to be Closed')
    while True:
        if GPIO.input(doorSensor):
            time.sleep(2)
            print('Door Closed')
            deadbolt.extend()
            print('Door Locked')
            for x in range(10):
                GPIO.output(led, True)
                time.sleep(0.05)
                GPIO.output(led,False)
                time.sleep(0.05)
            break


    config = {
    "apiKey": "u223vhdszRvM9UwdykvSWcR9XkuSe9JHiwq5g98i",
    "authDomain": "project-auralock.firebaseapp.com",
    "databaseURL": "https://project-auralock-default-rtdb.firebaseio.com",
    "storageBucket": "project-auralock.appspot.com"
    }

    firebase = pyrebase.initialize_app(config)
    db = firebase.database()
    storage = firebase.storage()

    #Initialize Database to false (no data needs to be retrieved)
    db.child("AuraLock Data").child("Unlock").set('False')
    db.child("AuraLock Data").child("addFace").set('False')

    #Define a the Unlock Thread which listens for the 'Unlock' key in Firebase to change to a value of 'True'
    def unlock_thread():
        while True:
            get_data = db.child("AuraLock Data").child("Unlock").get()
            if(get_data.val() == 'True'):
                print('Remote Unlock')
                global lockHalt
                lockHalt = True
                GPIO.output(led,True)
                db.child("AuraLock Data").child("Unlock").set('False')
                deadbolt.retract()
                time.sleep(5)
                while True:
                    if GPIO.input(doorSensor):
                        deadbolt.extend()
                        lockHalt = False
                        break
                GPIO.output(led,False)
            time.sleep(1)

    def addFace_thread():
        while True:
            get_data = db.child("AuraLock Data").child("addFace").get()
            if(get_data.val() == 'True'):
                global imageHalt
                imageHalt = True
                db.child("AuraLock Data").child("addFace").set('False')
                db.child("AuraLock Data").child("Adding Face").set('working')
                data = db.child("AuraLock Data").child("name").get()
                name = data.val()
                print('Adding Face of %s...'% name)
                storage.child("AuraLock Data").child('Images to RPi').child("%s.jpg"%name).download("/home/pi/Documents/AuraLock/Images to RPi/%s.jpg"%name)
                print('Image Downloaded, Loading Image')
                images_dict[name] = face_recognition.load_image_file("/home/pi/Documents/AuraLock/Images to RPi/%s.jpg"%name)
                print('Encoding Image')
                encodings_dict[name+"_encoding"] = face_recognition.face_encodings(images_dict[name])[0]
                values = encodings_dict.values()
                values_list = list(values)
                global encodings_list
                encodings_list.extend(values_list)
                print('success')
                db.child("AuraLock Data").child("Adding Face").set('complete')
                imageHalt = False
                for x in range(10):
                    GPIO.output(led, True)
                    time.sleep(0.05)
                    GPIO.output(led,False)
                    time.sleep(0.05)
            time.sleep(1)

    def facial_recognition_thread():
        while True:
            while not imageHalt:
                # print("Capturing image.")
                # Grab a single frame of video from the RPi camera as a numpy array
                camera.capture(output, format="rgb")
                # Find all the faces and face encodings in the current frame of video
                face_locations = face_recognition.face_locations(output)
                # print("Found {} faces in image.".format(len(face_locations)))
                face_encodings = face_recognition.face_encodings(output, face_locations)
                # Declare global variable lockHalt which halts other threads that would conflict with this one
                global lockHalt
                # Loop over each face found in the frame to see if it's someone we know.
                for face_encoding in face_encodings:
                    if delayedUnlock:
                        GPIO.output(led,True)
                        lockHalt = True
                        deadbolt.retract()
                        time.sleep(5)
                        #Wait for door to close
                        while True:
                            if GPIO.input(doorSensor):
                                time.sleep(2)
                                # Lock Door
                                print('Door Closed, Locking Door')
                                deadbolt.extend()
                                lockHalt = False
                                break
                        GPIO.output(led,False)
                    else:
                        # See if the face is a match for the known face(s)
                        match = face_recognition.compare_faces(encodings_list, face_encoding)
                        name = "Unknown Person"
                        keys = images_dict.keys()
                        keys_list = list(keys)
                        for i in range(len(keys_list)):
                            if match[(len(match)-len(keys_list))+i]:
                                name = keys_list[i]
                                #print(keys_list)
                                lockHalt = True
                                if GPIO.input(doorSensor):
                                    GPIO.output(led,True)
                                    # Take an image of who unlocked the door and upload it to Firebase
                                    camera.capture('/home/pi/Documents/AuraLock/Images to App/%s.jpg'%name)
                                    storage.child("AuraLock Data").child('Images to App').child('%s'%name).put('/home/pi/Documents/AuraLock/Images to App/%s.jpg'%name)
                                    # Notify App that a new unlock has been made
                                    db.child("AuraLock Data").child("newUnlock").set('True')
                                    db.child("AuraLock Data").child("newUnlockName").set('%s'%name)
                                    # Remove the image of who unlocked the door from the RPi
                                    os.remove('/home/pi/Documents/AuraLock/Images to App/%s.jpg'%name)
                                    # Unlock Door
                                    print('%s is Unlocking Door'%name)
                                    deadbolt.retract()
                                    time.sleep(5)
                                    #Wait for door to close
                                    while True:
                                        if GPIO.input(doorSensor):
                                            time.sleep(2)
                                            # Lock Door
                                            print('Door Closed, Locking Door')
                                            deadbolt.extend()
                                            lockHalt = False
                                            break
                                    GPIO.output(led,False)
                        print('%s\'s Face Detected'%name)

    def doorSense_thread():
        while True:
            while not lockHalt:
                if not GPIO.input(doorSensor):
                    GPIO.output(led,True)
                    while True:
                        if GPIO.input(doorSensor):
                            time.sleep(1.5)
                            deadbolt.extend()
                            GPIO.output(led,False)
                            break
                        else:
                            pass
            time.sleep(1)

    # Gives functionality to allow user to unlock the door for a set amount of time.
    # When true, the door will open to any face detected, not just authorized ones.
    # The delay time is pulled from Firebase, and remaining time is updated in Firebase every minute
    def delayed_unlock_thread():
        while True:
            # Pull value from firebase
            get_data = db.child("AuraLock Data").child("DelayedUnlock").child("DelayUnlock").get()
            # If the mobile app user has triggered a delayed unlock:
            if (get_data.val() == 'True'):
                global delayedUnlock
                # Notify facial_recognition_thread to unlock to any face
                delayedUnlock = True
                # Reset Firebase variable
                db.child("AuraLock Data").child("DelayedUnlock").child("DelayUnlock").set("False")
                # Get time delay value
                get_data = db.child("AuraLock Data").child("DelayedUnlock").child("delayTime").get()
                # Cast to int, removing decimals
                delayTime = int(get_data.val())
                # Debugging print
                print('Delayed Unlock Enabled for %s minutes'%delayTime)
                timeRemaining = delayTime
                for i in range(delayTime+1):
                    print('Time Remaining: %s minute(s)'%timeRemaining)
                    db.child("AuraLock Data").child("DelayedUnlock").child("timeRemaining").set(timeRemaining)
                    # Update time remaining every minute
                    time.sleep(60)
                    timeRemaining = timeRemaining - 1
                delayedUnlock = False
            time.sleep(2)

                

    #Create the thread
    T1 = Thread(target=unlock_thread)
    T2 = Thread(target=addFace_thread)
    T3 = Thread(target=facial_recognition_thread)
    T4 = Thread(target=doorSense_thread)
    T5 = Thread(target=delayed_unlock_thread)
    #Start the thread
    T1.start()
    T2.start()
    T3.start()
    T4.start()
    T5.start()



except KeyboardInterrupt:
    camera.close()
    os.system("echo -->Camera Closed")


