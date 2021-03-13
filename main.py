import time, os, ntptime, onewire, ds18x20, ubinascii, network, gc
from machine import Pin, I2C, RTC, SPI
import LS_Y201, sdcard, simpleMQTT, bh1750
gc.enable()
gc.collect()

time.sleep(10)

mqtt_server = 'broker.hivemq.com'
client_id = ubinascii.hexlify(machine.unique_id())
topic_pub = b'q5f8r28s/image'
topic_sub = b'q5f8r28s/i1'

wlan = network.WLAN(network.STA_IF)

camera = LS_Y201.LS_Y201()
uos.dupterm(None,1)

try:
    sd = sdcard.SDCard(SPI(1), Pin(15))
    os.mount(sd, '/sd')
except:
    print("no sd card")

rtc = RTC()
i2c = I2C(scl=Pin(0), sda=Pin(16), freq=100000)
BH = bh1750.BH1750(i2c)

ds_sensor = ds18x20.DS18X20(onewire.OneWire(Pin(4)))

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
except:
    print("time not sync")

def sub_cb(topic, msg):
    print((topic, msg))
    if topic == b'q5f8r28s/i1' and msg == b'1':
        print('ESP received hello message')
        client.publish(b'q5f8r28s/i1', msg=b'0')
        camera.save_picture("test_photo.jpeg")
        client.publish(b'q5f8r28s/image', image='test_photo.jpeg')

def connect_and_subscribe():
    global client_id, mqtt_server, topic_sub
    client = simpleMQTT.MQTTClient(client_id, mqtt_server, port=1883, keepalive=60)
    client.set_callback(sub_cb)
    client.connect()
    client.subscribe(topic_sub)
    print('Connected to %s MQTT broker, subscribed to %s topic' % (mqtt_server, topic_sub))
    return client

def restart_and_reconnect():
    print('Failed to connect to MQTT broker. Reconnecting...')
    time.sleep(10)
    machine.reset()

def print_act_date():
    acttime = rtc.datetime()

    f_date = "{}_{:02d}_{:02d}".format(acttime[0], acttime[1], acttime[2])
    f_time = "{:02d}:{:02d}:{:02d}".format(acttime[4], acttime[5], acttime[6])
    sec_time = (acttime[4])*60*60 + acttime[5]*60 + acttime[6]

    return f_date, f_time, sec_time

def print_date(acttime):

    f_date = "{}_{:02d}_{:02d}".format(acttime[0], acttime[1], acttime[2])
    f_time = "{:02d}:{:02d}:{:02d}".format(acttime[4], acttime[5], acttime[6])
    sec_time = (acttime[4])*60*60 + acttime[5]*60 + acttime[6]

    return f_date, f_time, sec_time

try:
    client = connect_and_subscribe()
except:
    restart_and_reconnect()

while True:
    if(time.time() - last_message_check) > message_check_interval:
        try:
            client.check_msg()
        except:
            print("no new message")

        try:
            client.ping()
        except:
            client.close_socket()
            try:
                print("trying connect....")
                client = connect_and_subscribe()
            except:
                print("reconnect failed")
        last_message_check = time.time()

    if(time.time() - last_time_sync) > time_sync_interval:
        try:
            ntptime.settime()
            print("time synced")
            last_time_sync = time.time()
        except:
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
        except:
            print(" no network")

    if (time.time() - last_message) > message_interval:
        try:
            ds_sensor.convert_temp()
            time.sleep(1)
            temp_out = "{:3.1f}".format(ds_sensor.read_temp(b'(\x9f\xf2\x84\x05\x00\x00L'))
            temp_in = temp_out #"{:3.1f}".format(ds_sensor.read_temp(b'(\xff\xce\x01i\x18\x03\x14'))
        except:
            print("DS sensor fail")
            temp_in = 0
            temp_out = 0

        try:
            lum = "{:3.2f}".format(BH.luminance(bh1750.BH1750.ONCE_HIRES_2))
        except:
            print("BH1750 error")
            lum = 0

        act_date, act_time, act_sec= print_act_date()
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
        except:
            pass
        
        try:
            datalog = open('/sd/data_{}.txt'.format(act_date), 'a')
        except:
            print("Datalog.txt not found")
            try:
                sd = sdcard.SDCard(SPI(1), Pin(15))
                os.mount(sd, '/sd')
            except:
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
        except OSError as e:
            pass


    if(time.time() - last_photo) > photo_interval:
           print("take photo")

           last_photo = time.time()
