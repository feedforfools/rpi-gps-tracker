#!/usr/bin/env python3

import queue, threading
from packaging import version

############################################################################
####                   GLOBAL VARIABLES AND CONSTANTS                   ####
############################################################################

VERSION = "1.3.0"
REMOTE_VERSION = ""
DOWNLOAD_FW = False

DEVICE_ID = ""

LOG_PATH = "/home/pi/log/"
CFG_PATH = "/home/pi/cfg/"
REL_PATH = "/home/pi/rel/"
BAK_PATH = "/home/pi/rel/bak/"
MODEM_UART_SERIAL_PATH = "/dev/serial0"
MODEM_SERIAL_OBJECT = False

LOG_ON_FILE = True
CUSTOM_LOG_QUEUE = queue.Queue()

GPIO_PWR_PIN = 4

CURRENT_NETWORK_IFACE = False
IFACE_LOCK = threading.Lock()
CURRENT_OPERATOR = False
CURRENT_RSSI = False

SIM_APN = ""
SIM_PIN = ""
SIM_PUK = ""
CONFIG_LAST_UPDATE = 0
MODEM_CONFIG_CHANGED = True

PRODUCE_PACKET_TIMER = 20
TIME_TO_NEXT_SEND = PRODUCE_PACKET_TIMER
CONNECTION_CHECK_TIMER = 25
TURN_OFF_GSM_TIMER = 30
NOW_MOVING = False
LONG_TIME_NO_MOVE = False
UPDATE_CHECK_TIMER = 60*15
TIME_SYNC_TIMER = 60*60*2
T_LAST_TIME_SYNC = 0

UP_SERVER_LINK = ""
UP_SERVER_UDP_PORT = 0

DOWN_SERVER_LINK = ""
CONFIG_DOWN_SERVER_LINK = ""
FIRM_DOWN_SERVER_LINK = ""

EXIT_STATUSES = queue.PriorityQueue()

LAST_ERROR = ""

start_ble_scanner = threading.Event()
stop_ble_scanner = threading.Event()

start_producer = threading.Event()
start_exhauster = threading.Event()
stop_exhauster = threading.Event()

start_gsm_network = threading.Event()
stop_gsm_network = threading.Event()

connection_check = threading.Event()
gps_local_time_sync = threading.Event()

start_update_check = threading.Event()
start_config_downloader = threading.Event()
start_firmware_updater = threading.Event()

SALSA_KEY = b""

############################################################################
####                              FUNCTIONS                             ####
############################################################################

def thread_comm(exit_code):
    
    priority = 0
    if "U" in exit_code:
        priority = 10
    elif "N" in exit_code:
        priority = 5
    elif exit_code is "M3":
        priority = 4
    elif exit_code is "M2":
        priority = 3
    elif exit_code is "M1":
        priority = 2
    elif exit_code is "W0" or exit_code is "W1":
        priority = 1

    if not EXIT_STATUSES.empty():
        queue_tuple = EXIT_STATUSES.get()
        top_priority = queue_tuple[0]
        top_code = queue_tuple[1]
        if top_priority >= 5:
            EXIT_STATUSES.put((top_priority,top_code))
        else:
            if priority >= top_priority:
                EXIT_STATUSES.put((top_priority,top_code))
            else:
                EXIT_STATUSES.put((priority,exit_code)) 
    else:
        EXIT_STATUSES.put((priority,exit_code))


def version_cmp(this_version, other_version):
    
    if "b" in other_version and this_version != other_version:
        return True
    if "b" in this_version and this_version != other_version:
        return True
    if version.parse(this_version) < version.parse(other_version):
        return True
    return False