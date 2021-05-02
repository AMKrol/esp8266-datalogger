import binascii
import usocket


class PyWake(object):
    def __init__(self, mac, subnetmask=None, my_IPv4=None, port=9):
        self.mac = mac
        src_IP_2 = my_IPv4.split('.')

        subnet = subnetmask.split('.')

        broadcastIP = []

        broadcastIP.append(str((255-int(subnet[0])) | int(src_IP_2[0])))
        broadcastIP.append(str((255-int(subnet[1])) | int(src_IP_2[1])))
        broadcastIP.append(str((255-int(subnet[2])) | int(src_IP_2[2])))
        broadcastIP.append(str((255-int(subnet[3])) | int(src_IP_2[3])))

        self.broadcastIPv4 = '.'.join(broadcastIP)
        self.port = port

    def send_packet(self):

        print('sending MP packet for MAC %s' % (self.mac))

        s = usocket.socket(usocket.AF_INET, usocket.SOCK_DGRAM)

        packet = binascii.unhexlify(
            'ffffffffffff') + binascii.unhexlify(self.mac) * 16

        s.sendto(packet, (self.broadcastIPv4, self.port))
