#!/usr/bin/env python
'''Take a photo.

Take a photo using a USB or Raspberry Pi camera.
'''

import os
import sys
from time import time, sleep
import json
import subprocess
import requests
import numpy as np

try:
    from farmware_tools.env import Env
except ImportError:
    IMAGES_DIR = os.getenv('IMAGES_DIR')
else:
    IMAGES_DIR = Env().images_dir


def _farmware_api_url():
    major_version = int(os.getenv('FARMBOT_OS_VERSION', '0.0.0')[0])
    base_url = os.environ['FARMWARE_URL']
    return base_url + 'api/v1/' if major_version > 5 else base_url


def legacy_log(message, message_type):
    'Send a message to the log.'
    try:
        os.environ['FARMWARE_URL']
    except KeyError:
        print(message)
    else:
        log_message = '[take-photo] ' + str(message)
        headers = {
            'Authorization': 'bearer {}'.format(os.environ['FARMWARE_TOKEN']),
            'content-type': 'application/json'}
        payload = json.dumps(
            {'kind': 'send_message',
             'args': {'message': log_message, 'message_type': message_type}})
        requests.post(_farmware_api_url() + 'celery_script',
                      data=payload, headers=headers)


try:
    from farmware_tools import device
except ImportError:
    log = legacy_log
else:
    def log(message, message_type):
        'Send a log message.'
        device.log('[take-photo] {}'.format(message), message_type)


try:
    import cv2
except ImportError:
    log('OpenCV import error.', 'error')
    sys.exit(1)


def rotate(image):
    'Rotate image if calibration data exists.'
    angle = float(os.environ['CAMERA_CALIBRATION_total_rotation_angle'])
    sign = -1 if angle < 0 else 1
    turns, remainder = -int(angle / 90.), abs(angle) % 90  # 165 --> -1, 75
    if remainder > 45: turns -= 1 * sign  # 75 --> -1 more turn (-2 turns total)
    angle += 90 * turns                   #        -15 degrees
    image = np.rot90(image, k=turns)
    height, width, _ = image.shape
    matrix = cv2.getRotationMatrix2D((int(width / 2), int(height / 2)), angle, 1)
    return cv2.warpAffine(image, matrix, (width, height))


def image_filename():
    'Prepare filename with timestamp.'
    epoch = int(time())
    filename = '{timestamp}.jpg'.format(timestamp=epoch)
    return filename


def upload_path(filename):
    'Filename with path for uploading an image.'
    images_dir = IMAGES_DIR or '/tmp/images'
    if not os.path.isdir(images_dir):
        log('{} directory does not exist.'.format(images_dir), 'error')
    path = images_dir + os.sep + filename
    return path


def save_image(image, start_time=None):
    'Save an image to file after attempting rotation.'
    filename = image_filename()
    # Try to rotate the image
    try:
        final_image = rotate(image)
    except:
        final_image = image
    else:
        filename = 'rotated_' + filename
    # Save the image to file
    filename_path = upload_path(filename)
    cv2.imwrite(filename_path, final_image)
    print_with_time('Image saved: {}'.format(filename_path), start_time)


def print_with_time(text, start_time=None):
    'Print text with time elapsed.'
    if start_time is None:
        print(text)
    else:
        elapsed = round(time() - start_time, 4)
        print('[{:>8}] {}'.format(elapsed, text))


def _capture_usb_image(camera, start_time):
    try:
        return camera.read()
    except Exception as error:
        print_with_time(error, start_time)
        log('Image capture error.', 'error')
        return 0, None


def _log_no_image(start_time):
    print_with_time('No image.', start_time)
    log('Problem getting image.', 'error')


def usb_camera_photo():
    'Take a photo using a USB camera.'
    # Settings
    camera_port = 0      # default USB camera port
    max_port_num = 1     # highest port to try if not detected on port
    discard_frames = 10  # number of frames to discard for auto-adjust
    max_attempts = 5     # number of failed discard frames before quit
    image_width = 640    # pixels
    image_height = 480   # pixels

    subprocess.call(['rmmod', 'uvcvideo'])
    subprocess.call(['modprobe', 'uvcvideo', 'quirks=128', 'nodrop=1', 'timeout=6000'])

    # Start timer
    start = time()

    # Check for camera
    camera_detected = False
    while camera_port <= max_port_num:
        camera_path = '/dev/video' + str(camera_port)
        if camera_port > 0:  # unexpected port
            print_with_time('Checking for {}...'.format(camera_path), start)
        if os.path.exists(camera_path):
            print_with_time('Found {}'.format(camera_path), start)
            camera_detected = True
            break
        else:
            print_with_time(
                'No camera detected at {}.'.format(camera_path), start)
            camera_port += 1
    if not camera_detected:
        print_with_time('Not at ports 0-{}.'.format(max_port_num), start)
        log('USB Camera not detected.', 'error')
        return

    # Close process using camera (if open)
    try:
        pid = subprocess.check_output(['fuser', camera_path])
    except subprocess.CalledProcessError:
        pass
    else:
        print_with_time(
            '{} in use. Attempting to close...'.format(camera_path), start)
        subprocess.call(['kill', '-9', pid])

    # Open the camera
    try:
        camera = cv2.VideoCapture(camera_port)
    except Exception as error:
        print_with_time(error, start)
    sleep(0.1)
    if not camera.isOpened():
        print_with_time('Camera is not open.', start)
        log('Could not connect to camera.', 'error')
        return
    print_with_time('Camera opened successfully.', start)

    # Set image size
    print_with_time('Adjusting image with test captures...', start)
    try:
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, image_width)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, image_height)
    except AttributeError:
        camera.set(cv2.cv.CV_CAP_PROP_FRAME_WIDTH, image_width)
        camera.set(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT, image_height)
    # Capture test frame
    ret, _ = _capture_usb_image(camera, start)
    if not ret:
        camera.release()
        _log_no_image(start)
        return
    # Let camera adjust
    failed_attempts = 0
    for _ in range(discard_frames):
        grab_ret = camera.grab()
        if not grab_ret:
            print_with_time('Could not get frame.', start)
            failed_attempts += 1
        if failed_attempts >= max_attempts:
            break
        sleep(0.1)

    # Take a photo
    print_with_time('Taking photo...', start)
    ret, image = _capture_usb_image(camera, start)

    # Close the camera
    camera.release()

    # Output
    if ret:  # an image has been returned by the camera
        save_image(image, start)
    else:  # no image has been returned by the camera
        _log_no_image(start)


def rpi_camera_photo():
    'Take a photo using the Raspberry Pi Camera.'
    try:
        tempfile = upload_path('temporary')
        retcode = subprocess.call(
            ['raspistill', '-w', '640', '-h', '480', '-o', tempfile])
        if retcode == 0:
            image = cv2.imread(tempfile)
            os.remove(tempfile)
            save_image(image)
        else:
            log('Problem getting image.', 'error')
    except OSError:
        log('Raspberry Pi Camera not detected.', 'error')


if __name__ == '__main__':
    CAMERA = os.getenv('camera', 'USB').upper()

    if 'NONE' in CAMERA:
        log('No camera selected. Choose a camera on the device page.', 'error')
    elif 'RPI' in CAMERA:
        rpi_camera_photo()
    else:
        usb_camera_photo()
