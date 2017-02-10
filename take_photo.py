'''Take a photo.

Take a photo using a USB camera for use as a FarmBot Farmware.
'''

from time import time, sleep
import cv2

# Settings
camera_port = 0      # default USB camera port
discard_frames = 20  # number of frames to discard for auto-adjust

# Open the camera
camera = cv2.VideoCapture(camera_port)
sleep(0.1)

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
    print "Image saved: {}".format(filename)
else:  # no image has been returned by the camera
    print "No camera detected."
