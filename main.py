import gc
import time
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

gc.enable()
gc.collect()

time.sleep(10)

mqtt_server = 'broker.hivemq.com'
client_id = ubinascii.hexlify(machine.unique_id())
topic_pub = b'q5f8r28s/image'
topic_sub = b'q5f8r28s/i1'

wlan = network.WLAN(network.STA_IF)

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
message_check_interval = 1
photo_interval = 60
time_sync_interval = 3600
net_check_interval = 2
message_interval = 15
counter = 0

try:
    ntptime.settime()
except Exception:
    print("time not sync")


def sub_cb(topic, fun_msg):
    print((topic, fun_msg))
    if topic == b'q5f8r28s/i1' and fun_msg == b'1':
        print('ESP received hello message')
        client.publish(b'q5f8r28s/i1', fun_msg=b'0')
        camera.save_picture("test_photo.jpeg")
        client.publish(b'q5f8r28s/image', image='test_photo.jpeg')


def connect_and_subscribe():
    fun_client = simpleMQTT.MQTTClient(client_id, mqtt_server, port=1883, keepalive=60)
    fun_client.set_callback(sub_cb)
    fun_client.connect()
    fun_client.subscribe(topic_sub)
    print('Connected to %s MQTT broker, subscribed to %s topic' % (mqtt_server, topic_sub))
    return fun_client


def restart_and_reconnect():
    print('Failed to connect to MQTT broker. Reconnecting...')
    time.sleep(10)
    machine.reset()


def print_act_date():
    acttime = rtc.datetime()

    f_date = "{}_{:02d}_{:02d}".format(acttime[0], acttime[1], acttime[2])
    f_time = "{:02d}:{:02d}:{:02d}".format(acttime[4], acttime[5], acttime[6])
    sec_time = (acttime[4]) * 60 * 60 + acttime[5] * 60 + acttime[6]

    return f_date, f_time, sec_time


def print_date(acttime):
    f_date = "{}_{:02d}_{:02d}".format(acttime[0], acttime[1], acttime[2])
    f_time = "{:02d}:{:02d}:{:02d}".format(acttime[4], acttime[5], acttime[6])
    sec_time = (acttime[4]) * 60 * 60 + acttime[5] * 60 + acttime[6]

    return f_date, f_time, sec_time


def error_log(fun_msg):
    try:
        err_log = open('err_log.txt', 'a')
        fun_act_date, fun_act_time, [] = print_act_date()
        fun_timestamp = '{} {}'.format(fun_act_date, fun_act_time)
        err_log.write('{} {}\n'.format(fun_timestamp, fun_msg))
    except Exception:
        print("cannot open error file")


try:
    client = connect_and_subscribe()
except Exception:
    restart_and_reconnect()

while True:
    if (time.time() - last_message_check) > message_check_interval:
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
        last_message_check = time.time()

    if (time.time() - last_time_sync) > time_sync_interval:
        try:
            ntptime.settime()
            print("time synced")
            last_time_sync = time.time()
        except Exception:
            print("time sync failed")

    if (time.time() - last_net_check) > net_check_interval:
        try:
            if not wlan.isconnected():
                print('connecting to network...')
                wlan.connect('DLINK', 'Hydrologia1!')

                start = time.ticks_ms()
                while not wlan.isconnected():
                    if time.ticks_diff(time.ticks_ms(), start) > 5000:
                        continue
                print('network config:', wlan.ifconfig())
                last_net_check = time.time()
        except Exception:
            print(" no network")

    if (time.time() - last_message) > message_interval:
        try:
            ds_sensor.convert_temp()
            time.sleep(1)
            temp_out = "{:3.1f}".format(ds_sensor.read_temp(b'(\x9f\xf2\x84\x05\x00\x00L'))
            temp_in = temp_out  # "{:3.1f}".format(ds_sensor.read_temp(b'(\xff\xce\x01i\x18\x03\x14'))
        except Exception:
            print("DS sensor fail")
            temp_in = 0
            temp_out = 0

        try:
            lum = "{:3.2f}".format(BH.luminance(bh1750.BH1750.ONCE_HIRES_2))
        except Exception:
            print("BH1750 error")
            lum = 0

        act_date, act_time, act_sec = print_act_date()
        timestamp = '{} {}'.format(act_date, act_time)

        print(timestamp)
        print('Temperature inside: {} C'.format(temp_in))
        print('Luminance: {} lux'.format(lum))
        print('Temperature outside: {} C'.format(temp_out))
        try:
            client.publish(b"q5f8r28s/o1", str(temp_in), retain=False)
            time.sleep(0.05)
            client.publish(b"q5f8r28s/o3", str(lum), retain=False)
            time.sleep(0.05)
            client.publish(b"q5f8r28s/o4", str(temp_out), retain=False)
            time.sleep(0.05)
            client.publish(b"q5f8r28s/time", timestamp, retain=False)
        except Exception:
            pass

        try:
            datalog = open('/sd/data_{}.txt'.format(act_date), 'a')
        except Exception:
            print("Datalog.txt not found")
            try:
                sd = sdcard.SDCard(machine.SPI(1), machine.Pin(15))
                uos.mount(sd, '/sd')
            except Exception:
                print(" no sd card")
        else:
            datalog.write('{} {},{},{},{}'.format(act_date, act_time, temp_in, temp_out, lum))
            datalog.write('\n')
            datalog.close()

        try:
            msg = b'Hello #%d' % counter
            client.publish(b'q5f8r28s/test', msg)
            last_message = time.time()
            counter += 1
        except Exception:
            pass

        try:
            date_file = open('daty.csv', 'r')
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

            act_date, act_time, act_sec = print_act_date()

            status_print = ""
            if act_sec <= open_sec or act_sec >= close_sec:
                status_print = "closed"
            else:
                status_print = "open"

            print("door status: ", status_print)

        except Exception:
            print("door error")

    if (time.time() - last_photo) > photo_interval:
        print("take photo")

        last_photo = time.time()
