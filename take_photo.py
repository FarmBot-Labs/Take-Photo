#!/usr/bin/env python
'''Take a photo.

Take a photo using a USB camera for use as a FarmBot Farmware.
'''

import os.path
from time import time, sleep
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
for i in range(discard_frames):
    camera.grab()

# Take a photo
ret, image = camera.read()

# Close the camera
camera.release()

# Prepare filename with timestamp
epoch = int(time())
filename = '/tmp/images/{timestamp}.jpg'.format(timestamp=epoch)

# Output
if ret:  # an image has been returned by the camera
    # Save the image to file
    cv2.imwrite(filename, image)
    print("Image saved: {}".format(filename))
else:  # no image has been returned by the camera
    print("Problem getting image.")
