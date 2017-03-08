#!/usr/bin/env python
'''Take a photo.

Take a photo using a USB or Raspberry Pi camera.
'''

import os.path
from time import time, sleep


def image_filename():
    'Prepare filename with timestamp.'
    epoch = int(time())
    filename = '/tmp/images/{timestamp}.jpg'.format(timestamp=epoch)
    return filename

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
        cv2.imwrite(image_filename(), image)
        print("Image saved: {}".format(image_filename()))
    else:  # no image has been returned by the camera
        print("Problem getting image.")

def rpi_camera_photo():
    'Take a photo using the Raspberry Pi Camera.'
    from subprocess import call
    try:
        retcode = call(["raspistill", "-md", "4", "-o", image_filename()])
        if retcode == 0:
            print("Image saved: {}".format(image_filename()))
        else:
            print("Problem getting image.")
    except OSError:
        print("Raspberry Pi Camera not detected.")

if __name__ == '__main__':
    try:
        CAMERA = os.environ['camera']
    except (KeyError, ValueError):
        CAMERA = 'USB'  # default camera

    if CAMERA == 'USB':
        usb_camera_photo()
    elif CAMERA == 'RPI':
        rpi_camera_photo()
