import machine
import micropython
import network
import esp
esp.osdebug(None)
import gc
gc.collect()

ssid = 'DLINK'
password = 'Hydrologia1!'

station = network.WLAN(network.STA_IF)

station.active(True)
station.connect(ssid, password)

while station.isconnected() == False:
  pass
