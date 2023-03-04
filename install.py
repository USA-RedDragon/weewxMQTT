# installer for the weewxMQTT driver
#
# Based on installer for bootstrap skin
#
# Configured by Bill to install weewxMQTT user driver, 2016.

from weecfg.extension import ExtensionInstaller


def loader():
    return MQTTInstaller()


class MQTTInstaller(ExtensionInstaller):
    def __init__(self):
        super(MQTTInstaller, self).__init__(
            version="0.2",
            name='mqtt',
            description='A weewx driver which subscribes to MQTT topics providing weewx compatible data',
            author="Bill Morrow",
            author_email="morrowwm@gmail.com",
            files=[('bin/user', ['bin/user/mqtt.py'])],
            config={
                'mqtt': {
                    'driver': 'user.mqtt',
                    'host': 'localhost',           # MQTT broker hostname
                    'topic': 'weather',            # topic
                    'poll_interval': 1.0,          # seconds
                    'username': '',                # MQTT broker username
                    'password': '',                # MQTT broker password
                    'timestamp_format': '%Y-%m-%d %H:%M:%S',             # date format
                    'client_id': 'weeWXMQTT',      # MQTT client id
                }
            },
        )
