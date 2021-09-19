#!/usr/bin/env python3

from logging.handlers import QueueListener
import time, math
from time import sleep
import pickle
from queue import LifoQueue

import blendler, config, networker, support
import commander as at


############################################################################
####                   GLOBAL VARIABLES AND CONSTANTS                   ####
############################################################################

COUNTER = 0

LOGGER = None

PACKET_LIFO_QUEUE = LifoQueue()                           # In this queue are stored the packets ready to be sent in LiFo criteria

LAST_GPS_SCAN = ["-", "-", "-", "-", "-", "-", "-", "-", "-"]   # Last GPS scan for reliability purposes (not resetting GPS)
GPS_FAIL = 0                                                    # Consecutive GPS fails counter

OMEGA = math.pi/60
TZERO = 0                                          

############################################################################
####                              FUNCTIONS                             ####
############################################################################

def init_packager():

    global LOGGER

    LOGGER = support.CustomLogger("pac")
    packet_queue_load()

    return


############################# GPS AND PACKETS ##############################

def packet_producer():

    global LAST_GPS_SCAN, OMEGA, TZERO, GPS_FAIL

    #LOGGER.debug("Getting GPS coordinates..")
    try:
        gps_scan = at.gps_get_location()
    except Exception as e:
        LOGGER.exception(e)
        gps_scan = False
      
    if gps_scan:
        
        if gps_scan[0]==1:      # GPS is active
            if gps_scan[1]==1:  # GPS fix is done

                already_failed = False

                for i, field in enumerate(gps_scan):
                    if not field:
                        LOGGER.warning(">> Error on GPS scan: "+str(gps_scan))
                        if "-" not in LAST_GPS_SCAN[i]:
                            gps_scan[i] = LAST_GPS_SCAN[i]
                        if not already_failed:
                            already_failed = True
                            GPS_FAIL += 1
                            if GPS_FAIL >= 5:
                                config.thread_comm("M1gps")
                                GPS_FAIL = 0

                try:
                    networker.flow_controller("gps", float(gps_scan[6]))

                except Exception as e:
                    LOGGER.warning(">> Error on GPS scan after flow controller: "+str(gps_scan))
                    GPS_FAIL += 1
                    if GPS_FAIL >= 5:
                        config.thread_comm("M1gps")
                        GPS_FAIL = 0
                    return False
                
                if not already_failed:
                    GPS_FAIL = 0
                LAST_GPS_SCAN = gps_scan

                return build_packet(gps_scan)
                
            else:
                # NO FIX -> last position is sent even when there's no GPS signal (to send ble variations anyway)
                # 
                # TODO: predict next possible position via current GPS position, speed and course
                LOGGER.warning("> No fix")
                networker.flow_controller("nofix")

                if "-" not in LAST_GPS_SCAN:
                    LAST_GPS_SCAN[2] = support.get_utc_timestamp()
                    config.LAST_ERROR += "|no-fix|"
                    return build_packet(LAST_GPS_SCAN)
                
                return False
        else:
            # GPS NOT ACTIVE
            LOGGER.warning(">> GPS is not active")
            config.thread_comm("M3")
            return False
    else:
        LOGGER.error(">> GPS scan failed")
        GPS_FAIL += 1
        if GPS_FAIL >= 5:
            config.thread_comm("M1gps")
            GPS_FAIL = 0
        return False


def packet_handler(packet):

    if not networker.send_udp_packet(packet, config.CURRENT_NETWORK_IFACE):
        config.thread_comm("N0")
        PACKET_LIFO_QUEUE.put(packet)


def queue_exhauster():

    data = False
    LOGGER.debug("> Emptying the packets queue..")
    try:
        if config.CURRENT_NETWORK_IFACE is "gsm":
            at.toggle_data_mode()
        data = True
        while not PACKET_LIFO_QUEUE.empty() and not config.start_producer.is_set() and not config.connection_check.is_set():
            current_packet = PACKET_LIFO_QUEUE.get()
            PACKET_LIFO_QUEUE.task_done()

            if not networker.send_udp_packet(current_packet, config.CURRENT_NETWORK_IFACE, True):
                PACKET_LIFO_QUEUE.put(current_packet)
                config.connection_check.set()
                break
            sleep(0.1)
        else:
            if config.CURRENT_NETWORK_IFACE is "gsm":
                try:
                    at.toggle_cmd_mode()

                except Exception as e:
                    LOGGER.error(">> Toggle CMD mode failed")
                    config.thread_comm("M2")

            if PACKET_LIFO_QUEUE.empty():
                LOGGER.debug("> Packets queue is empty")
            else:
                LOGGER.debug("> Emptying queue stopped")
    
    except Exception as e:
        LOGGER.exception(e)
        if data:
            try:
                at.toggle_cmd_mode()
            except Exception as e:
                LOGGER.error(">> Toggle CMD mode failed")
                config.thread_comm("M2")
                return False


def packet_lifo_queue_empty():
    return PACKET_LIFO_QUEUE.empty()


def packet_queue_load():
    
    global PACKET_LIFO_QUEUE

    try:
        with open(config.BAK_PATH+"pakq.bak","rb") as queue_save_file:
            queue_list = pickle.load(queue_save_file)
            for element in queue_list:
                PACKET_LIFO_QUEUE.put(element)
            support.bash_cmd("rm pakq.bak")
            LOGGER.info("> Loaded "+ str(len(queue_list)) +" packets from queue backup file")
    except FileNotFoundError:
        LOGGER.info("> No QUEUE backup file found")
    except Exception as e:
        LOGGER.exception(e)
    return


def packet_queue_dump():

    try:
        if not PACKET_LIFO_QUEUE.empty():
            with open(config.BAK_PATH+"pakq.bak","wb") as queue_save_file:
                pickle.dump(list(PACKET_LIFO_QUEUE.queue), queue_save_file)
            LOGGER.info("> Saved "+ str(len(PACKET_LIFO_QUEUE.queue)) +" packets to file")
            return True
        LOGGER.info("> Queue is empty")
        return True
    except Exception as e:
        LOGGER.exception(e)
        LOGGER.error(">> Error on queue backup: "+str(e))
        return False

            
############################ PACKAGER SUPPORT ##############################

def build_packet(coords):

    global COUNTER

    COUNTER += 1

    if COUNTER>99999:
        COUNTER = 0
    
    count = 0

    packet = ""

    packet += coords[3]                                                     + ";"
    packet += coords[4]                                                     + ";"
    packet += coords[5]                                                     + ";"
    packet += str(coords[6])                                                + ";"
    packet += coords[7]                                                     + ";"
    if config.CURRENT_RSSI:
        packet += str(config.CURRENT_RSSI)
    packet +=                                                                 ";"
    packet += coords[2]                                                     + ";"
    packet += config.DEVICE_ID                                              + ";"
    packet += config.VERSION                                                + ";"
    
    for ble in blendler.BLE_LIST:
        if ble.vis is 1:
            print_ble = ""
            if count is not 0:
                print_ble = ","
            print_ble += ble.mac.replace(":","") + str(ble.rssi)
            packet += print_ble
            count += 1

    packet +=                                                                 ";"
    if config.CURRENT_NETWORK_IFACE is "gsm":
        packet += str(config.CURRENT_OPERATOR)                              + ";"
    else:
        packet += str(config.CURRENT_NETWORK_IFACE)                         + ";"
    packet += str(config.PRODUCE_PACKET_TIMER)                              + ";"
    packet += str(COUNTER)                                                  + ";"
    packet += str(config.LAST_ERROR)                

    config.LAST_ERROR = ""

    return packet

#---------------------------------------------------------------------------
