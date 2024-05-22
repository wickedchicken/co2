#!/usr/bin/env python3

import sys, fcntl, time, os
import tomllib
import netrc
import argparse
import datetime
import glob
import traceback

from pathlib import Path

from peewee import *
from playhouse.mysql_ext import MariaDBConnectorDatabase

from digitemp.master import UART_Adapter
from digitemp.device import TemperatureSensor

import requests

CONFIG_FILE = Path(Path(__file__).parent, 'co2.toml')

def get_config_data():
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)

def get_db_connection_data(config_data):
    netrc_host = f"{config_data['database']['hostname']}:{config_data['database']['port']}"
    parsed_netrc = netrc.netrc()
    login, _, password = parsed_netrc.authenticators(netrc_host)
    return login, password

db_proxy = DatabaseProxy() # Create a proxy for our db.

class BaseModel(Model):
    class Meta:
        database = db_proxy

class LogEntry(BaseModel):
    measurement_type = CharField(index=True, default='sensor_recording')
    room_name = CharField(index=True)
    recorded = DateTimeField(default=lambda: datetime.datetime.now(datetime.timezone.utc), index=True)
    temperature_c = FloatField(null=True)
    co2_ppm = FloatField(null=True)


def meteoblue_request(meteoblue_key, lat, lon):
    url = f"https://my.meteoblue.com/packages/current?apikey={meteoblue_key}&lat={lat}&lon={lon}&tz=UTC&format=json"
    data = requests.get(url).json()
    outdoor_temperature_c = data['data_current']['temperature']
    recorded = datetime.datetime.fromisoformat(data['data_current']['time']).replace(tzinfo=datetime.timezone.utc)

    try:
        meteoblue_entry = LogEntry.create(
            measurement_type='meteoblue',
            temperature_c=outdoor_temperature_c,
            recorded=recorded,
            room_name='balcony',
        )
        meteoblue_entry.save()
        print('Logged meteoblue entry {}'.format(meteoblue_entry), flush=True)
    except requests.RequestException:
        print('Error with meteoblue request:', flush=True)
        traceback.print_exc()
    except KeyError:
        print('Error accessing meteoblue data', flush=True)
        traceback.print_exc()

def contact_sensor_request(device_path):
    sensor = TemperatureSensor(UART_Adapter(str(device_path)))
    temperature_c = sensor.get_temperature()
    usbtemp_entry = LogEntry.create(
        measurement_type='usbtemp',
        temperature_c=temperature_c,
        room_name='living room wall',
    )
    usbtemp_entry.save()
    print('Logged usbtemp entry {}'.format(usbtemp_entry), flush=True)

def decrypt(key,  data):
    cstate = [0x48,  0x74,  0x65,  0x6D,  0x70,  0x39,  0x39,  0x65]
    shuffle = [2, 4, 0, 7, 1, 6, 5, 3]

    phase1 = [0] * 8
    for i, o in enumerate(shuffle):
        phase1[o] = data[i]

    phase2 = [0] * 8
    for i in range(8):
        phase2[i] = phase1[i] ^ key[i]

    phase3 = [0] * 8
    for i in range(8):
        phase3[i] = ( (phase2[i] >> 3) | (phase2[ (i-1+8)%8 ] << 5) ) & 0xff

    ctmp = [0] * 8
    for i in range(8):
        ctmp[i] = ( (cstate[i] >> 4) | (cstate[i]<<4) ) & 0xff

    out = [0] * 8
    for i in range(8):
        out[i] = (0x100 + phase3[i] - ctmp[i]) & 0xff

    return out

def hd(d):
    return " ".join("%02X" % e for e in d)

def inner_loop(args, config_data):
    # Key retrieved from /dev/random, guaranteed to be random ;)
    key = [0xc4, 0xc6, 0xc0, 0x92, 0x40, 0x23, 0xdc, 0x96]

    fp = open(args.device_path, "a+b",  0)
    
    HIDIOCSFEATURE_9 = 0xC0094806
    set_report = [0x00] + key
    set_report = bytearray(set_report)
    fcntl.ioctl(fp, HIDIOCSFEATURE_9, set_report)

    meteoblue_start = time.time()

    while True:
        values = {}

        while (0x50 not in values or 0x42 not in values):
            data = list(fp.read(8))

            decrypted = None
            if data[4] == 0x0d and (sum(data[:3]) & 0xff) == data[3]:
                decrypted = data
            else:
                decrypted = decrypt(key, data)

            if decrypted[4] != 0x0d or (sum(decrypted[:3]) & 0xff) != decrypted[3]:
                print(hd(data), " => ", hd(decrypted),  "Checksum error", flush=True)
            else:
                op = decrypted[0]
                val = decrypted[1] << 8 | decrypted[2]

                values[op] = val

                # Output all data, mark just received value with asterisk
                #print ", ".join( "%s%02X: %04X %5i" % ([" ", "*"][op==k], k, v, v) for (k, v) in sorted(values.items())), "  ",
                ## From http://co2meters.com/Documentation/AppNotes/AN146-RAD-0401-serial-communication.pdf
                if 0x50 in values:
                    print("CO2: %4i" % values[0x50], end=' ', flush=True)
                if 0x42 in values:
                    print("T: %2.2f" % (values[0x42]/16.0-273.15), end=' ', flush=True)
                if 0x44 in values:
                    print("RH: %2.2f" % (values[0x44]/100.0), end=' ', flush=True)
                print()

        entry = LogEntry.create(
            measurement_type='sensor_recording',
            room_name=args.room_name, temperature_c=values[0x42]/16.0-273.15, co2_ppm=values[0x50])
        entry.save()
        print('Logged entry {}'.format(entry), flush=True)

        contact_sensor_request(args.usbtemp_device_path)

        if (time.time() - meteoblue_start) > config_data['meteoblue']['freq']:
            meteoblue_request(config_data['meteoblue']['api_key'], config_data['meteoblue']['lat'],
                config_data['meteoblue']['lon'])
            meteoblue_start = time.time()

        time.sleep(60)

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--device-path",
        help="path to the device to read from, such as /dev/co2mini0",
        type=Path,
        default=Path(glob.glob("/dev/co2mini*")[0]),
    )
    parser.add_argument(
        "--usbtemp-device-path",
        help="path to the device to read from, such as /dev/usbtemp0",
        type=Path,
        default=Path(glob.glob("/dev/usbtemp*")[0]),
    )
    parser.add_argument(
        "--create-tables",
        help="create the SQL tables needed for data collection",
        action='store_true'
    )
    parser.add_argument(
        "--room-name",
        help="location the sample was taken in",
        default="living room",
    )
    return parser.parse_args()


if __name__ == "__main__":
    config_data = get_config_data()
    db_login, db_password = get_db_connection_data(config_data)

    args = get_args()

    db = MariaDBConnectorDatabase(
        config_data['database']['name'],
        host=config_data['database']['hostname'],
        port=int(config_data['database']['port']),
        user=db_login,
        password=db_password,
    )
    db_proxy.initialize(db)
    db.connect()
    try:
        if args.create_tables:
            db.create_tables([LogEntry])
        inner_loop(args, config_data)
    finally:
        db.close()



