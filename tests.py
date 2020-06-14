#!/usr/bin/env python

'Take Photo Tests.'

import os
import sys
import unittest
import take_photo
import numpy as np
try:
    import farmware_tools
except ImportError:
    FT_IMPORTED = False
else:
    FT_IMPORTED = True
try:
    from unittest import mock
except ImportError:
    import mock

OUTPUT_FILENAME = 'output.txt'


def read_output_file(output_file):
    'Read test output file.'
    output_file.close()
    with open(OUTPUT_FILENAME, 'r') as output_file:
        output = output_file.read().lower()
    sys.stdout = sys.__stdout__
    print('')
    print(os.environ)
    print('>' * 20)
    print(output)
    print('<' * 20)
    return output


os.environ.clear()
ENVS = [
    'take_photo_logging',
    'camera',
    'IMAGES_DIR',
    'CAMERA_CALIBRATION_total_rotation_angle',
    'FARMBOT_OS_VERSION',
    'FARMWARE_URL',
    'FARMWARE_TOKEN',
]


def re_import():
    try:
        reload(take_photo)
    except NameError:
        import importlib
        importlib.reload(take_photo)


def _prepare_fuser_mock(**kwargs):
    def _fuser_mock(*_args):
        if kwargs.get('missing'):
            try:
                MissingError = FileNotFoundError
            except NameError:
                MissingError = OSError
            raise MissingError
        if kwargs.get('busy'):
            return b' 1 2 3'
        else:
            import subprocess
            raise subprocess.CalledProcessError
    return _fuser_mock


def _prepare_mock_capture(**kwargs):
    def mocked_video_capture(*_args):
        'Used by mock.'
        class MockVideoCapture():
            'Mock cv2.VideoCapture'

            @staticmethod
            def isOpened():
                'is camera open?'
                ret = kwargs.get('isOpened')
                return True if ret is None else ret

            @staticmethod
            def getBackendName():
                'get capture backend'
                if kwargs.get('raise_backend'):
                    raise NameError('mock error')
                return 'mock'

            @staticmethod
            def grab():
                'get frame'
                ret = kwargs.get('grab_return')
                return True if ret is None else ret

            @staticmethod
            def read():
                'get image'
                if kwargs.get('raise_read'):
                    raise NameError('mock error')
                default_return = True, np.zeros([10, 10, 3], np.uint8)
                return kwargs.get('read_return') or default_return

            @staticmethod
            def set(*_args):
                'set parameter'
                return

            @staticmethod
            def release():
                'close camera'
                return

        if kwargs.get('raise_open'):
            raise IOError('mock error')
        return MockVideoCapture()
    return mocked_video_capture


class TakePhotoTest(unittest.TestCase):
    'Test Take Photo.'

    def setUp(self):
        for env in ENVS:
            try:
                del os.environ[env]
            except KeyError:
                pass
        os.environ['IMAGES_DIR'] = '/tmp'
        self.outfile = open(OUTPUT_FILENAME, 'w')
        sys.stdout = self.outfile

    def test_default(self):
        'Test default Take Photo.'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertGreater(output.count('[ '), 3)
        self.assertLess(output.count('send_message'), 3)
        self.assertFalse('rotated' in output)

    def test_quiet(self):
        'Test quiet log level.'
        os.environ['take_photo_logging'] = 'quiet'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertFalse('[ ' in output)

    def test_verbose(self):
        'Test verbose log level.'
        os.environ['take_photo_logging'] = 'verbose'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertFalse('[ ' in output)
        if FT_IMPORTED:
            self.assertGreater(output.count('send_message'), 3)

    def test_timed_verbose(self):
        'Test timed verbose log level.'
        os.environ['take_photo_logging'] = 'verbose_timed'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertTrue('[ ' in output)
        if FT_IMPORTED:
            self.assertGreater(output.count('send_message'), 3)

    @unittest.skipIf(FT_IMPORTED, '')
    @mock.patch('requests.post', mock.Mock())
    def test_verbose_legacy(self):
        'Test verbose log level with legacy log.'
        os.environ['take_photo_logging'] = 'verbose'
        os.environ['FARMWARE_URL'] = 'url'
        os.environ['FARMWARE_TOKEN'] = 'token'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertFalse('[ ' in output)

    @mock.patch('os.path.exists', mock.Mock())
    @mock.patch('cv2.VideoCapture', _prepare_mock_capture())
    def test_capture_success(self):
        'Test image capture.'
        del os.environ['IMAGES_DIR']
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertTrue('saved' in output)
        self.assertTrue('directory does not exist' in output)

    @mock.patch('os.path.exists', mock.Mock())
    @mock.patch('cv2.VideoCapture', _prepare_mock_capture(raise_open=True))
    def test_camera_open_error(self):
        'Test error on camera open.'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertTrue('mock error' in output)
        self.assertTrue('could not connect' in output)

    @mock.patch('os.path.exists', mock.Mock())
    @mock.patch('cv2.VideoCapture', _prepare_mock_capture(raise_backend=True))
    def test_camera_get_backend_error(self):
        'Test error on get backend.'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertTrue('not available' in output)

    @mock.patch('os.path.exists', mock.Mock())
    @mock.patch('cv2.VideoCapture', _prepare_mock_capture(raise_read=True))
    def test_camera_read_error(self):
        'Test error on camera read.'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertTrue('mock error' in output)
        self.assertTrue('image capture error' in output)

    @mock.patch('os.path.exists', mock.Mock())
    @mock.patch('subprocess.check_output',
                mock.Mock(side_effect=_prepare_fuser_mock(missing=True)))
    @mock.patch('cv2.VideoCapture', _prepare_mock_capture())
    def test_camera_no_busy_check(self):
        'Test unable to check if camera is busy.'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertTrue('unable to check' in output)

    @mock.patch('os.path.exists', mock.Mock())
    @mock.patch('subprocess.check_output',
                mock.Mock(side_effect=_prepare_fuser_mock(busy=True)))
    @mock.patch('cv2.VideoCapture', _prepare_mock_capture())
    def test_camera_busy(self):
        'Test camera busy.'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertTrue('attempting to close' in output)

    @mock.patch('os.path.exists', mock.Mock())
    @mock.patch('cv2.VideoCapture', _prepare_mock_capture(isOpened=False))
    def test_camera_not_open(self):
        'Test camera not open.'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertTrue('could not connect' in output)

    @mock.patch('os.path.exists', mock.Mock())
    @mock.patch('cv2.VideoCapture',
                _prepare_mock_capture(read_return=(False, None)))
    def test_no_image(self):
        'Test no image.'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertTrue('no image' in output)

    @mock.patch('os.path.exists', mock.Mock())
    @mock.patch('cv2.VideoCapture', _prepare_mock_capture(grab_return=False))
    def test_no_grab_image(self):
        'Test no grab return.'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertTrue('could not get frame' in output)

    @mock.patch('os.path.exists', mock.Mock())
    @mock.patch('os.path.isdir', mock.Mock())
    @mock.patch('cv2.VideoCapture', _prepare_mock_capture())
    def test_rotated(self):
        'Test image rotation.'
        os.environ['CAMERA_CALIBRATION_total_rotation_angle'] = '45'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertTrue('rotated' in output)
        self.assertFalse('directory does not exist' in output)

    def test_none_camera(self):
        'Test none camera selection.'
        os.environ['camera'] = 'none'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertTrue('no camera selected' in output)
        self.assertFalse('USB' in output)

    def test_rpi_camera(self):
        'Test rpi camera selection.'
        os.environ['camera'] = 'rpi'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertTrue('raspberry pi' in output)
        self.assertFalse('USB' in output)

    @mock.patch('cv2.imread', mock.Mock(side_effect=lambda _:
                                        np.zeros([10, 10, 3], np.uint8)))
    @mock.patch('os.remove', mock.Mock())
    @mock.patch('subprocess.call', mock.Mock(side_effect=lambda _: 0))
    def test_rpi_camera_capture(self):
        'Test rpi camera capture success.'
        os.environ['camera'] = 'rpi'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertTrue('raspberry pi' in output)
        self.assertTrue('image captured' in output)

    @mock.patch('subprocess.call', mock.Mock(side_effect=lambda _: 1))
    def test_rpi_camera_capture_failure(self):
        'Test rpi camera capture failure.'
        os.environ['camera'] = 'rpi'
        re_import()
        take_photo.take_photo()
        output = read_output_file(self.outfile)
        self.assertTrue('raspberry pi' in output)
        self.assertTrue('problem' in output)

    def tearDown(self):
        self.outfile.close()
        sys.stdout = sys.__stdout__
        os.remove(OUTPUT_FILENAME)