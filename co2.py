#!/usr/bin/env python2

import sys, fcntl, time, os

from Adafruit_IO import Client
from pushover import Client as PushoverClient

AIO_USER = os.getenv('AIO_USER')
AIO_KEY = os.getenv('AIO_USER')

PUSHOVER_CLIENT = os.getenv('PUSHOVER_CLIENT')
PUSHOVER_TOKEN = os.getenv('PUSHOVER_TOKEN')

aio = Client(AIO_USER, AIO_KEY)
pushover = PushoverClient(PUSHOVER_CLIENT, api_token=PUSHOVER_TOKEN)

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

if __name__ == "__main__":
    # Key retrieved from /dev/random, guaranteed to be random ;)
    key = [0xc4, 0xc6, 0xc0, 0x92, 0x40, 0x23, 0xdc, 0x96]

    fp = open(sys.argv[1], "a+b",  0)

    HIDIOCSFEATURE_9 = 0xC0094806
    set_report = "\x00" + "".join(chr(e) for e in key)
    fcntl.ioctl(fp, HIDIOCSFEATURE_9, set_report)

    too_high = False
    already_sent = False
    while True:
        values = {}

        while (0x50 not in values or 0x42 not in values):
            data = list(ord(e) for e in fp.read(8))
            decrypted = decrypt(key, data)
            if decrypted[4] != 0x0d or (sum(decrypted[:3]) & 0xff) != decrypted[3]:
                print hd(data), " => ", hd(decrypted),  "Checksum error"
            else:
                op = decrypted[0]
                val = decrypted[1] << 8 | decrypted[2]

                values[op] = val

                # Output all data, mark just received value with asterisk
                #print ", ".join( "%s%02X: %04X %5i" % ([" ", "*"][op==k], k, v, v) for (k, v) in sorted(values.items())), "  ",
                ## From http://co2meters.com/Documentation/AppNotes/AN146-RAD-0401-serial-communication.pdf
                if 0x50 in values:
                    print "CO2: %4i" % values[0x50],
                if 0x42 in values:
                    print "T: %2.2f" % (values[0x42]/16.0-273.15),
                if 0x44 in values:
                    print "RH: %2.2f" % (values[0x44]/100.0),
                print

        aio.send('co2-ppm', values[0x50])
        aio.send('temperature-in-c', values[0x42]/16.0-273.15)

        if values[0x50] > 1000 and not too_high:
            too_high = True
            if not already_sent:
                pushover.send_message("Stoss your luft! co2 ppm is {}".format(values[0x50]))
                already_sent = True
        elif values[0x50] < 600 and too_high:
            too_high = False
            already_sent = False
            pushover.send_message("Luft has been stossed! co2 ppm is {}".format(values[0x50]))

        time.sleep(60)
