import time
from machine import UART
import os

class LS_Y201():
    _CMD_RESET = b'V\x00&\x00'
    _RESP_RESET = b'v\x00&\x00'
    _CMD_TAKE_PICTURE = b'V\x006\x01\x00'
    _CMD_IMAGE_SIZE = b'V\x004\x01\x00'
    _CND_GETJPEGBODY = bytearray(b'V\x002\x0c\x00\n\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
    _CMD_COMPRESS_RATIO = bytearray(b'V\x001\x05\x01\x01\x12\x04\x00')

    _CMD_IMAGE_640_480_temp = b'V\x00T\x01\x00'
    _CMD_IMAGE_320_240_temp = b'V\x00T\x01\x11'
    _CMD_IMAGE_160_120_temp = b'V\x00T\x01\x22'

    _RESP_IMAGE_SIZE_CHANGE = b'v\x00T\x00\x00'
    _RESP_RESET = b'v\x00&\x00'
    _RESP_TAKE_PICTURE = b'v\x006\x00\x00'
    _RESP_IMAGE_SIZE = b'v\x004\x00\x04\x00\x00'
    _RESP_GETJPEGBODY = b'v\x002\x00\x00'
    _RESP_PARAM_ACCEPT = b'v\x001\x00\x00'

    def __init__(self):
        self.bus = UART(0, 38400, rxbuf=69)

    def reset(self):
        resp = self.rec_resp_on_cmd(self._CMD_RESET, 4)
        if resp == self._RESP_RESET:
            time.sleep(1)
            return 1
        else:
            return 0

    def take_picture(self):
        resp = self.rec_resp_on_cmd(self._CMD_TAKE_PICTURE, 5)
        if resp == self._RESP_TAKE_PICTURE:
            return 1
        else:
            return 0

    def take_image_size(self):
        resp = self.rec_resp_on_cmd(self._CMD_IMAGE_SIZE, 9)
        resp_cmd = resp[0:7]
        resp_size = resp[7:]
        image_size = 0
        for byte in resp_size:
            image_size = (image_size << 8) | byte

        if resp_cmd == self._RESP_IMAGE_SIZE:
            return image_size
        else:
            return 0

    def send_com(self, cmd):
        self.bus.read()
        self.bus.write(cmd)

    def rec_resp_on_cmd(self, cmd, read_size):
        self.bus.read()
        self.bus.write(cmd)
        time.sleep(0.1)
        return self.bus.read(read_size)

    def rec_resp(self, resp_size):
        return self.bus.read(resp_size)

    def readbuffer_save(self, path):
        size_total = self.take_image_size()
        print('Photo size {} bytes'.format(size_total))
        addr = 0
        k = 64
        x = 10
        self._CND_GETJPEGBODY[12] = (k >> 8) & 0xff
        self._CND_GETJPEGBODY[13] = (k >> 0) & 0xff
        self._CND_GETJPEGBODY[14] = (x >> 9) & 0xff
        self._CND_GETJPEGBODY[15] = (x >> 0) & 0xff
        jpegfile = open(path, 'a')

        while addr <= size_total - k:
            self._CND_GETJPEGBODY[8] = (addr >> 8) & 0xff
            self._CND_GETJPEGBODY[9] = (addr >> 0) & 0xff

            self.send_com(self._CND_GETJPEGBODY)
            time.sleep(0.05)
            resp = UART(0).read()
            header = resp[:5]
            if  header == self._RESP_GETJPEGBODY:
                jpegfile.write(resp[5:5+k])
                addr = addr + k

        if size_total != addr:
            k = size_total - addr
            self._CND_GETJPEGBODY[8] = (addr >> 8) & 0xff
            self._CND_GETJPEGBODY[9] = (addr >> 0) & 0xff
            self._CND_GETJPEGBODY[12] = (k >> 8) & 0xff
            self._CND_GETJPEGBODY[13] = (k >> 0) & 0xff
            self.send_com(self._CND_GETJPEGBODY)
            time.sleep(0.05)
            resp = UART(0).read()
            header = resp[:5]
            if  header == self._RESP_GETJPEGBODY:
                jpegfile.write(resp[5:5+k])
        jpegfile.close()

    def compression_ratio(self, comp_ratio):
        if 0 <= comp_ratio <= 255:
            self._CMD_COMPRESS_RATIO[8] = comp_ratio & 0xFF
            resp = self.rec_resp_on_cmd(self._CMD_COMPRESS_RATIO, 5)
            if resp == self._RESP_PARAM_ACCEPT:
                return 1
            else:
                return 0
        else:
            return 0

    def image_size_temp(self, size):
        if size == 'L':
            resp = self.rec_resp_on_cmd(self._CMD_IMAGE_640_480_temp, 5)
            if resp == self._RESP_IMAGE_SIZE_CHANGE:
                return 1
            else:
                return 0
        elif size == 'M':
            resp = self.rec_resp_on_cmd(self._CMD_IMAGE_320_240_temp, 5)
            if resp == self._RESP_IMAGE_SIZE_CHANGE:
                return 1
            else:
                return 0
        elif size == 'S':
            resp = self.rec_resp_on_cmd(self._CMD_IMAGE_160_120_temp, 5)
            if resp == self._RESP_IMAGE_SIZE_CHANGE:
                return 1
            else:
                return 0

    def save_picture(self, path):
        self.reset()
        time.sleep(1)
        try:
            os.remove(path)
        except:
            print("No file to remove")
        self.take_picture()
        self.readbuffer_save(path)

    def set_mqtt_image(self):
        self.reset()
        time.sleep(1)
        self.image_size('M')
        slef.compression_ratio(36)

