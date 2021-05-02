import gc
import utime
import uos

import ds18x20
import network
import ntptime
import onewire
import ubinascii

import machine

import LS_Y201
import bh1750
import sdcard
import simpleMQTT
import wakeonlan

gc.enable()
gc.collect()

utime.sleep(10)

mqtt_server = 'broker.hivemq.com'
client_id = ubinascii.hexlify(machine.unique_id())
topic_pub = b'q5f8r28s/image'
topic_sub = b'q5f8r28s/i1'

wlan = network.WLAN(network.STA_IF)
wol = wakeonlan.PyWake(
    mac='000AE4C99858', subnetmask='255.255.255.0', my_IPv4='192.168.1.101')

camera = LS_Y201.LS_Y201()
uos.dupterm(None, 1)

try:
    sd = sdcard.SDCard(machine.SPI(1), machine.Pin(15))
    uos.mount(sd, '/sd')
except Exception:
    print("no sd card")

rtc = machine.RTC()
i2c = machine.I2C(scl=machine.Pin(0), sda=machine.Pin(16), freq=100000)
BH = bh1750.BH1750(i2c)

ds_sensor = ds18x20.DS18X20(onewire.OneWire(machine.Pin(4)))

last_message = 0
last_net_check = 0
last_time_sync = 0
last_photo = 0
last_message_check = 0
last_door_check = 0
door_check_interval = 60
message_check_interval = 1
photo_interval = 60
time_sync_interval = 3600
net_check_interval = 2
message_interval = 15
counter = 0
old_data = "0"
close_t = 0
open_t = 0

try:
    ntptime.settime()
except Exception:
    print("time not sync")


def sub_cb(topic, fun_msg):
    print((topic, fun_msg))
    if topic == b'q5f8r28s/i1' and fun_msg == b'1':
        print('ESP received hello message')
        client.publish(b'q5f8r28s/i1', msg=b'0')
        camera.save_picture("test_photo.jpeg")
        client.publish(b'q5f8r28s/image', image='test_photo.jpeg')

    if topic == b'q5f8r28s/i1' and fun_msg == b'2':
        print('ESP received hello message')
        client.publish(b'q5f8r28s/i1', msg=b'0')
        wol.send_packet()


def connect_and_subscribe():
    fun_client = simpleMQTT.MQTTClient(
        client_id, mqtt_server, port=1883, keepalive=60)
    fun_client.set_callback(sub_cb)
    fun_client.connect()
    fun_client.subscribe(topic_sub)
    print('Connected to %s MQTT broker, subscribed to %s topic' %
          (mqtt_server, topic_sub))
    return fun_client


def restart_and_reconnect():
    print('Failed to connect to MQTT broker. Reconnecting...')
    utime.sleep(10)
    machine.reset()


def print_date(acttime=0):
    if acttime == 0:
        acttime = rtc.datetime()

    f_date = "{}_{:02d}_{:02d}".format(acttime[0], acttime[1], acttime[2])
    f_time = "{:02d}:{:02d}:{:02d}".format(acttime[4], acttime[5], acttime[6])
    sec_time = (acttime[4]) * 60 * 60 + acttime[5] * 60 + acttime[6]

    return f_date, f_time, sec_time


def error_log(fun_msg):
    try:
        err_log = open('err_log.txt', 'a')
        fun_act_date, fun_act_time, [] = print_date()
        fun_timestamp = '{} {}'.format(fun_act_date, fun_act_time)
        err_log.write('{} {}\n'.format(fun_timestamp, fun_msg))
        err_log.close()
    except Exception:
        err_log.close()
        print("cannot open error file")


try:
    client = connect_and_subscribe()
except Exception:
    restart_and_reconnect()

while True:
    if (utime.time() - last_message_check) > message_check_interval:
        try:
            client.check_msg()
        except Exception:
            print("no new message")

        try:
            client.ping()
        except Exception:
            client.close_socket()
            try:
                print("trying connect....")
                client = connect_and_subscribe()
            except Exception:
                print("reconnect failed")
                error_log("reconnect failed")
        last_message_check = utime.time()

    if (utime.time() - last_time_sync) > time_sync_interval:
        try:
            ntptime.settime()
            print("time synced")
            last_time_sync = utime.time()
        except Exception:
            print("time sync failed")
            error_log("time sync failed")

    if (utime.time() - last_net_check) > net_check_interval:
        try:
            if not wlan.isconnected():
                print('connecting to network...')
                wlan.connect('DLINK', 'Hydrologia1!')

                start = utime.ticks_ms()
                while not wlan.isconnected():
                    if utime.ticks_diff(utime.ticks_ms(), start) > 5000:
                        continue
                print('network config:', wlan.ifconfig())
                last_net_check = utime.time()
        except Exception:
            print(" no network")
            error_log(" no network")

    if (utime.time() - last_message) > message_interval:
        try:
            ds_sensor.convert_temp()
            utime.sleep(1)
            temp_out = "{:3.1f}".format(
                ds_sensor.read_temp(b'(\x9f\xf2\x84\x05\x00\x00L'))
            # "{:3.1f}".format(ds_sensor.read_temp(b'(\xff\xce\x01i\x18\x03\x14'))
            temp_in = temp_out
        except Exception:
            print("DS sensor fail")
            error_log("DS sensor fail")
            temp_in = 0
            temp_out = 0

        try:
            lum = "{:3.2f}".format(BH.luminance(bh1750.BH1750.ONCE_HIRES_2))
        except Exception:
            print("BH1750 error")
            error_log("BH1750 sensor fail")
            lum = 0

        act_date, act_time, act_sec = print_date()
        timestamp = '{} {}'.format(act_date, act_time)

        print(timestamp)
        print('Temperature inside: {} C'.format(temp_in))
        print('Luminance: {} lux'.format(lum))
        print('Temperature outside: {} C'.format(temp_out))
        try:
            client.publish(b"q5f8r28s/o1", str(temp_in), retain=False)
            utime.sleep(0.05)
            client.publish(b"q5f8r28s/o3", str(lum), retain=False)
            utime.sleep(0.05)
            client.publish(b"q5f8r28s/o4", str(temp_out), retain=False)
            utime.sleep(0.05)
            client.publish(b"q5f8r28s/time", timestamp, retain=False)
        except Exception:
            pass

        try:
            datalog = open('/sd/data_{}.txt'.format(act_date), 'a')
        except Exception:
            print("Datalog.txt not found")
            error_log("Data file not found")
            try:
                sd = sdcard.SDCard(machine.SPI(1), machine.Pin(15))
                uos.mount(sd, '/sd')
            except Exception:
                print(" no sd card")
                error_log("no SD card")
        else:
            datalog.write('{} {},{},{},{}'.format(
                act_date, act_time, temp_in, temp_out, lum))
            datalog.write('\n')
            datalog.close()

        try:
            msg = b'Hello #%d' % counter
            client.publish(b'q5f8r28s/test', msg)
            last_message = utime.time()
            counter += 1
        except Exception:
            pass

    act_date, act_time, act_sec = print_date()

    if old_data != act_date:
        data_file = []
        try:
            date_file = open("daty.csv", 'r')
            line = []

            while True:
                line = date_file.readline()

                if not line:
                    break

                if line[:5] == act_date[5:10]:
                    break

            date_file.close()

            close_time = (2020, 1, 1, 1, int(line[12:14]), int(line[15:17]), 0)
            open_time = (2020, 1, 1, 1, int(line[6:8]), int(line[9:11]), 0)

            close_d, close_t, close_sec = print_date(close_time)
            open_d, open_t, open_sec = print_date(open_time)

            old_data = act_date

        except Exception:
            date_file.close()
            print("date.csv not opened")
            error_log("date.csv not opened")

    if (utime.time() - last_door_check) > door_check_interval:
        try:
            act_date, act_time, act_sec = print_date()
            status_print = ""
            if act_sec <= open_sec or act_sec >= close_sec:
                status_print = "closed"
            else:
                status_print = "open"
            print("door status: ", status_print)
            last_door_check = utime.time()

        except Exception:
            print("door operation failed")
            error_log("door operation failed")

    if (utime.time() - last_photo) > photo_interval:
        print("take photo")

        last_photo = utime.time()
