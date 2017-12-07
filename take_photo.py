#!/usr/bin/env python
'''Take a photo.

Take a photo using a USB or Raspberry Pi camera.
'''

import os
from time import time, sleep
from shutil import move
import json
import requests


def api_url():
    major_version = int(os.getenv('FARMBOT_OS_VERSION', '0.0.0')[0])
    base_url = os.environ['FARMWARE_URL']
    return base_url + 'api/v1/' if major_version > 5 else base_url

def log(message, message_type):
    'Send a message to the log.'
    try:
        os.environ['FARMWARE_URL']
    except KeyError:
        print(message)
    else:
        log_message = '[take-photo] ' + str(message)
        headers = {
            'Authorization': 'bearer {}'.format(os.environ['FARMWARE_TOKEN']),
            'content-type': "application/json"}
        payload = json.dumps(
            {"kind": "send_message",
             "args": {"message": log_message, "message_type": message_type}})
        requests.post(api_url() + 'celery_script',
                      data=payload, headers=headers)

def image_filename():
    'Prepare filename with timestamp.'
    epoch = int(time())
    filename = '{timestamp}.jpg'.format(timestamp=epoch)
    return filename

def tmp_path(filename):
    'Filename with path for uploading an image.'
    path = '/tmp/' + filename
    return path

def upload_path(filename):
    'Filename with path for uploading an image.'
    path = os.environ['IMAGES_DIR'] + os.sep + filename
    return path

def usb_camera_photo():
    'Take a photo using a USB camera.'
    import cv2
    # Settings
    camera_port = 0      # default USB camera port
    # image_width = 1600   # pixels
    # image_height = 1200  # pixels
    discard_frames = 20  # number of frames to discard for auto-adjust

    # Check for camera
    if not os.path.exists('/dev/video' + str(camera_port)):
        print("No camera detected at video{}.".format(camera_port))
        camera_port += 1
        print("Trying video{}...".format(camera_port))
        if not os.path.exists('/dev/video' + str(camera_port)):
            print("No camera detected at video{}.".format(camera_port))
            log("USB Camera not detected.", "error")

    # Open the camera
    camera = cv2.VideoCapture(camera_port)
    sleep(0.1)

    # try:
    #     camera.set(cv2.CAP_PROP_FRAME_WIDTH, image_width)
    #     camera.set(cv2.CAP_PROP_FRAME_HEIGHT, image_height)
    # except AttributeError:
    #     camera.set(cv2.cv.CV_CAP_PROP_FRAME_WIDTH, image_width)
    #     camera.set(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT, image_height)

    # Let camera adjust
    for _ in range(discard_frames):
        camera.grab()

    # Take a photo
    ret, image = camera.read()

    # Close the camera
    camera.release()

    # Output
    if ret:  # an image has been returned by the camera
        # Save the image to file
        filename = image_filename()
        cv2.imwrite(upload_path(filename), image)
        print("Image saved: {}".format(upload_path(filename)))
    else:  # no image has been returned by the camera
        log("Problem getting image.", "error")

def rpi_camera_photo():
    'Take a photo using the Raspberry Pi Camera.'
    from subprocess import call
    try:
        filename = image_filename()
        retcode = call(
            ["raspistill", "-o", tmp_path(filename)])
        move(tmp_path(filename), upload_path(filename))
        if retcode == 0:
            print("Image saved: {}".format(upload_path(filename)))
        else:
            log("Problem getting image.", "error")
    except OSError:
        log("Raspberry Pi Camera not detected.", "error")

if __name__ == '__main__':
    try:
        CAMERA = os.environ['camera']
    except (KeyError, ValueError):
        CAMERA = 'USB'  # default camera

    if 'RPI' in CAMERA:
        rpi_camera_photo()
    else:
        usb_camera_photo()
