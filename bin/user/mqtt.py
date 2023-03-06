#!/usr/bin/python
#
# weewx driver that reads data from MQTT subscription for Python 3 and Weewx 4.x
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.
#
# See http://www.gnu.org/licenses/

#
# The units must be weewx.US:
#   degree_F, inHg, inch, inch_per_hour, mile_per_hour
#
# To use this driver, put this file in the weewx user directory, then make
# the following changes to weewx.conf:
#
# [Station]
#     station_type = mqtt
# [mqtt]
#     host = localhost           # MQTT broker hostname
#     topic = weather/+          # topic
#     driver = user.mqtt
#
# If the variables in the file have names different from those in weewx, then
# create a mapping such as this:
#
# [mqtt]
#     ...
#     [[label_map]]
#         temp = outTemp
#         humi = outHumidity
#         in_temp = inTemp
#         in_humid = inHumidity

from __future__ import with_statement
import syslog
import time
import datetime
import json
import queue
import paho.mqtt.client as mqtt
import weewx.drivers

DRIVER_VERSION = "0.2"


def logmsg(dst, msg):
    syslog.syslog(dst, 'mqtt: %s' % msg)


def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)


def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)


def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)


def _get_as_float(d, s):
    v = None
    if s in d:
        try:
            v = float(d[s])
        except ValueError as e:
            logerr("cannot read value for '%s': %s" % (s, e))
    return v


def loader(config_dict, engine):
    return MQTTDriver(**config_dict['mqtt'])


class MQTTDriver(weewx.drivers.AbstractDevice):
    """weewx driver that reads data from a file"""

    def __init__(self, **stn_dict):
        # where to find the data file
        self.host = stn_dict.get('host', 'localhost')
        self.topic = stn_dict.get('topic', 'weather')
        self.username = stn_dict.get('username', '')
        self.password = stn_dict.get('password', '')
        self.client_id = stn_dict.get('client', 'weeWXMQTT')
        self.username = stn_dict.get('username', '')
        self.password = stn_dict.get('password', '')
        self.timestamp_format = stn_dict.get('timestamp_format', '%Y-%m-%d %H:%M:%S')

        # how often to poll the weather data file, seconds
        self.poll_interval = float(stn_dict.get('poll_interval', 1.0))

        # mapping from variable names to weewx names
        self.label_map = stn_dict.get('label_map', {})

        loginf("MQTT host is %s" % self.host)
        loginf("MQTT topic is %s" % self.topic)
        loginf("MQTT client is %s" % self.client_id)
        loginf("MQTT username is %s" % self.username)
        loginf("polling interval is %s" % self.poll_interval)
        loginf('label map is %s' % self.label_map)

        self.payload = queue.Queue()
        self.connected = False

        self.client = mqtt.Client(client_id=self.client_id)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # TODO - need some reconnect on disconnect logic
        # self.client.on_disconnect = self.on_disconnect

        self.client.username_pw_set(self.username, self.password)
        self.client.connect(self.host, 1883, 60)
        self.client.loop_start()

    # The callback for when the client rEceives a CONNACK response from the server.
    def on_connect(self, client, userdata, flags, rc):
        loginf("Connected on mqtt server with result code "+str(rc))
        if rc == 0:
            self.connected = True
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        self.client.subscribe(self.topic)

    # The callback for when a PUBLISH message is received from the MQTT server.
    def on_message(self, client, userdata, msg):
        msg.payload = msg.payload.decode('UTF-8')
        self.payload.put(msg.payload, block=True, timeout=None)

        logdbg("Added to queue of %d message %s" % (self.payload.qsize(), msg.payload))

    def closePort(self):
        self.client.disconnect()
        self.client.loop_stop()

    def genLoopPackets(self):
        while True:
            # read whatever values we can get from the MQTT broker
            logdbg("Queue of %d entries" % self.payload.qsize())
            logdbg("Waiting for non-empty queue")
            while not self.payload.empty():
                try:
                    msg = self.payload.get(block=True, timeout=self.poll_interval)
                except queue.Empty:
                    logdbg("Queue is empty")
                    continue
                logdbg("Working on queue of size %d with payload : %s" % (self.payload.qsize(), msg))
                try:
                    data = json.loads(msg)
                except ValueError as e:
                    logerr("cannot read value for '%s': %s" % (msg, e))
                    continue

                data["usUnits"] = weewx.METRICWX

                # Now iterate over each key in the `label_map` dictionary.
                # If the key is in the data, then rename it to the value.
                for label in self.label_map.keys():
                    # dateTime is a special case handled later
                    if label == "dateTime":
                        continue
                    if self.label_map[label] in data:
                        data[label] = data.pop(self.label_map[label])

                if "dateTime" in self.label_map:
                    data["dateTime"] = time.mktime(
                        datetime.datetime.strptime(
                            data[self.label_map["dateTime"]],
                            self.timestamp_format
                        )
                        .timetuple()
                    )
                elif "dateTime" not in data:
                    data["dateTime"] = time.mktime(
                        datetime.datetime.now(tz=datetime.timezone.utc).timetuple()
                    )

                yield data

                continue

            time.sleep(self.poll_interval)

        self.client.disconnect()
        self.client.loop_stop()

    @property
    def hardware_name(self):
        return "mqtt"
