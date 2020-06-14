#!/usr/bin/env python

'''Take a photo.

Take a photo using a USB or Raspberry Pi camera.
'''

from __future__ import print_function
import os
import sys
from time import time, sleep
import json
import subprocess

# start timer
START_TIME = time()

import requests
import numpy as np

FIRST_IMPORTS_COMPLETE_TIME = time()


def verbose_log(text, time_override=None):
    'Print text with time elapsed since start.'
    now = time_override if time_override is not None else time()
    elapsed = round(now - START_TIME, 4)
    timed_log = '[{:>8}] {}'.format(elapsed, text)
    log_level = os.getenv('take_photo_logging', '').lower()
    if 'quiet' in log_level:
        return
    if 'verbose' not in log_level:
        try:
            print(timed_log, flush=True)
        except TypeError:
            print(timed_log)
        return
    log_content = timed_log if 'timed' in log_level else text
    try:
        log(log_content, 'debug')
    except NameError:
        pass


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
    ft_import_start_msg = 'Importing Farmware Tools...'
    FT_IMPORT_START_TIME = time()
    from farmware_tools import device
except ImportError:
    ft_import_result_msg = 'farmware_tools import error. Using legacy logger.'
    log = legacy_log
else:
    ft_import_result_msg = 'Farmware Tools import complete.'

    def log(message, message_type):
        'Send a log message.'
        device.log('[take-photo] {}'.format(message), message_type)


verbose_log('First imports complete.', FIRST_IMPORTS_COMPLETE_TIME)
verbose_log(ft_import_start_msg, FT_IMPORT_START_TIME)
verbose_log(ft_import_result_msg)

try:
    verbose_log('Importing OpenCV...')
    os.environ['OPENCV_VIDEOIO_DEBUG'] = '1'
    import cv2
except ImportError:
    log('OpenCV import error.', 'error')
    sys.exit(1)
else:
    verbose_log('OpenCV import complete.')


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


def save_image(image):
    'Save an image to file after attempting rotation.'
    filename = image_filename()
    # Try to rotate the image
    try:
        verbose_log('Considering rotation...')
        final_image = rotate(image)
    except:
        verbose_log('Did not rotate image.')
        final_image = image
    else:
        verbose_log('Rotated image.')
        filename = 'rotated_' + filename
    # Save the image to file
    filename_path = upload_path(filename)
    cv2.imwrite(filename_path, final_image)
    verbose_log('Image saved: {}'.format(filename_path))


def _capture_usb_image(camera):
    try:
        return camera.read()
    except Exception as error:
        verbose_log(error)
        log('Image capture error.', 'error')
        return 0, None


def _log_no_image():
    verbose_log('No image.')
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

    # Check for camera
    camera_detected = False
    while camera_port <= max_port_num:
        camera_path = '/dev/video' + str(camera_port)
        if camera_port > 0:  # unexpected port
            verbose_log('Checking for {}...'.format(camera_path))
        if os.path.exists(camera_path):
            verbose_log('Found {}'.format(camera_path))
            camera_detected = True
            break
        else:
            verbose_log('No camera detected at {}.'.format(camera_path))
            camera_port += 1
    if not camera_detected:
        verbose_log('Not at ports 0-{}.'.format(max_port_num))
        log('USB Camera not detected.', 'error')
        return

    # Close process using camera (if open)
    try:
        MissingError = FileNotFoundError
    except NameError:
        MissingError = OSError
    try:
        pids = subprocess.check_output(['fuser', camera_path])
    except MissingError:
        verbose_log('Unable to check if busy.')
    except subprocess.CalledProcessError:
        verbose_log('Camera not busy.')
    else:
        verbose_log('{} busy. Attempting to close...'.format(camera_path))
        for pid in pids.strip().split(b' '):
            subprocess.call(['kill', '-9', pid])

    # Open the camera
    verbose_log('Opening camera...')
    try:
        camera = cv2.VideoCapture(camera_port)
    except Exception as error:
        verbose_log(error)
    try:
        backend = camera.getBackendName()
    except NameError:
        backend = 'not available'
    verbose_log('using backend: ' + backend)
    sleep(0.1)
    try:
        camera_open = camera.isOpened()
    except NameError:
        camera_open = False
    if not camera_open:
        verbose_log('Camera is not open.')
        log('Could not connect to camera.', 'error')
        return
    verbose_log('Camera opened successfully.')

    # Set image size
    verbose_log('Adjusting image with test captures...')
    try:
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, image_width)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, image_height)
    except AttributeError:
        camera.set(cv2.cv.CV_CAP_PROP_FRAME_WIDTH, image_width)
        camera.set(cv2.cv.CV_CAP_PROP_FRAME_HEIGHT, image_height)
    # Capture test frame
    ret, _ = _capture_usb_image(camera)
    if not ret:
        camera.release()
        _log_no_image()
        return
    verbose_log('First test frame captured.')
    # Let camera adjust
    failed_attempts = 0
    for _ in range(discard_frames):
        grab_ret = camera.grab()
        if not grab_ret:
            verbose_log('Could not get frame.')
            failed_attempts += 1
        if failed_attempts >= max_attempts:
            break
        sleep(0.1)

    # Take a photo
    verbose_log('Taking photo...')
    ret, image = _capture_usb_image(camera)

    # Close the camera
    camera.release()

    # Output
    if ret:  # an image has been returned by the camera
        verbose_log('Photo captured.')
        save_image(image)
    else:  # no image has been returned by the camera
        _log_no_image()


def rpi_camera_photo():
    'Take a photo using the Raspberry Pi Camera.'
    try:
        tempfile = upload_path('temporary')
        verbose_log('Taking photo with Raspberry Pi camera...')
        retcode = subprocess.call(
            ['raspistill', '-w', '640', '-h', '480', '-o', tempfile])
        if retcode == 0:
            verbose_log('Image captured.')
            image = cv2.imread(tempfile)
            os.remove(tempfile)
            save_image(image)
        else:
            log('Problem getting image.', 'error')
    except OSError:
        log('Raspberry Pi Camera not detected.', 'error')


def take_photo():
    'Take a photo.'
    CAMERA = os.getenv('camera', 'USB').upper()

    if 'NONE' in CAMERA:
        log('No camera selected. Choose a camera on the device page.', 'error')
    elif 'RPI' in CAMERA:
        rpi_camera_photo()
    else:
        usb_camera_photo()


if __name__ == '__main__':
    take_photo()
