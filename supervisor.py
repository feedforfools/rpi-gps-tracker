#!/usr/bin/env python3

import threading, time

import blendler, config, modemdler, networker, packager, support, updater
from modemdler import init_modemdler
from networker import init_networker
from updater import init_updater
from packager import init_packager
from blendler import init_blendler
from config import EXIT_STATUSES, thread_comm

############################################################################
####                            EXIT STATUSES                           ####
############################################################################

########################### MODEM/NETWORK ERRORS ###########################
#   
#   W0 -> reboot system
#   W1 -> restart process without rebooting
#
#   M0 -> modem critical error: general error
#   M1 -> reset modem hardware
#   M2 -> modem not responsive: stuck on data mode
#   M3 -> init modem software
#
#   N0 -> network critical error: force network connection check
#   N1 -> network critical error: start GSM connection
#   N2 -> network optimization msg: turn down GSM connection
#
#   U0 -> error in firmware update
#   U1 -> update firmware
#   U2 -> update SIM config
#
############################################################################

############################################################################
####                   GLOBAL VARIABLES AND CONSTANTS                   ####
############################################################################

LOGGER = None
LAST_ERROR_CODE_FOR_CRASH = ""
COUNTER_M1_FOR_CRASH = 0

############################ Threads Definition ############################

log_publisher = threading.Thread(target=support.logger_publisher_thread)
ble_scanner = threading.Thread(target=blendler.ble_thread)
queue_sender = threading.Thread(target=packager.queue_exhauster)

############################################################################
####                              FUNCTIONS                             ####
############################################################################

def init_system():

    global LOGGER

    support.set_os_timezone()
    config.DEVICE_ID = support.bash_cmd("hostname").split()[0]
    support.setup_logger(config.DEVICE_ID)
    log_publisher.start()
    LOGGER = support.CustomLogger("sup")

    init_networker()
    init_updater()
    init_packager()
    init_blendler()

    try:
        init_modemdler()

    except Exception as e:
        LOGGER.critical(">> System initiation failed: "+str(e))
        LOGGER.exception(e)
        thread_comm("M1")
        return
    
    LOGGER.info("> System initiated")

    try:
        modemdler.init_comms_layer()
    
    except Exception as e:
        LOGGER.critical(">> Modem initiation failed: "+str(e))
        LOGGER.exception(e)
        thread_comm("M3")
        return
    
    LOGGER.info("> Modem initiated")

    return


def error_handler():

    global LAST_ERROR_CODE_FOR_CRASH, COUNTER_M1_FOR_CRASH

    queue_tuple = EXIT_STATUSES.get()
    error_code = queue_tuple[1]
    
    EXIT_STATUSES.task_done()
    LOGGER.warning("> New exit status: "+error_code)

    if "M" in error_code:
        if "1" in error_code:
            # Reset modem and try reinitialization
            try:
                modemdler.modem_pwr_reset()
                thread_comm("M3")
            except Exception as e:
                LOGGER.critical(">> Modem reset failed")
                LOGGER.exception(e)
                thread_comm("M1")
                return

        elif "2" in error_code:
            # Modem stuck in data mode
            modemdler.modem_stuck_recovery()

        elif "3" in error_code:
            # Initialize modem software
            try:
                modemdler.init_comms_layer()
            except Exception as e:
                LOGGER.critical(">> Modem initialization failed")
                LOGGER.exception(e)
                thread_comm("M1")
                return
            LOGGER.info("> Modem initiated")
                
    elif "N" in error_code:
        if "0" in error_code:
            config.connection_check.set()
        elif "1" in error_code:
            config.start_gsm_network.set()
        elif "2" in error_code:
            config.stop_gsm_network.set()

    elif "U" in error_code:
        if "0" in error_code:
            LOGGER.error(">> Error in update")
        elif "1" in error_code:
            config.start_firmware_updater.set()
        elif "2" in error_code:
            config.start_config_downloader.set()
            
    elif "W" in error_code:
        config.stop_ble_scanner.set()
        if ble_scanner.is_alive():
            ble_scanner.join()
        if queue_sender.is_alive():
            queue_sender.join()
        packager.packet_queue_dump()
        blendler.ble_lists_dump()
        if "0" in error_code:
            support.reboot_system()
        elif "1" in error_code:
            support.restart_process()
    
    LAST_ERROR_CODE_FOR_CRASH = error_code


def task_coordinator(t_now, t_last_connection_check, t_last_update_check, t_last_packet_produced):

    # SECTIONS TO SET THE TIME-BASED TRIGGERS TO LAUNCH THE CORRESPONDING THREAD
    if (t_now-config.T_LAST_TIME_SYNC) > config.TIME_SYNC_TIMER and config.CURRENT_NETWORK_IFACE is not "wlan0":
        config.gps_local_time_sync.set()

    # Set the trigger for the network monitor
    if (t_now-t_last_connection_check) > config.CONNECTION_CHECK_TIMER:
        config.connection_check.set()

    # Set the start trigger for the configuration downloader
    if config.LONG_TIME_NO_MOVE and (t_now-t_last_update_check) > config.UPDATE_CHECK_TIMER:
        config.start_update_check.set()
        
    # Set the trigger for the producer 
    if (t_now-t_last_packet_produced) > config.TIME_TO_NEXT_SEND:
        config.start_producer.set()

    # Set the start and stop trigger for the ble scanner
    if not config.NOW_MOVING:
        config.stop_ble_scanner.clear()
        config.start_ble_scanner.set()
        if not packager.packet_lifo_queue_empty():
            if config.TIME_TO_NEXT_SEND==60:
                config.start_exhauster.set()
    else:
        config.stop_ble_scanner.set()           


def task_starter(t_now, t_last_connection_check, t_last_update_check, t_last_packet_produced):

    global ble_scanner, queue_sender
    # SECTIONS TO START THE TASKS BASED ON EACH TRIGGER

    # Start the ble scanner
    if config.start_ble_scanner.is_set():
        if not ble_scanner.is_alive():
            ble_scanner = threading.Thread(target=blendler.ble_thread)
            ble_scanner.start()
        config.start_ble_scanner.clear()
    
    # Set time from GPS
    if config.gps_local_time_sync.is_set():
        if not queue_sender.is_alive():
            gps_timestamp = modemdler.get_gps_time()
            #LOGGER.debug("> "+str(float(gps_timestamp)))
            if gps_timestamp:
                LOGGER.info("> Syncing local time to satellites")
                support.set_local_time_from_gps(gps_timestamp)
                config.T_LAST_TIME_SYNC = t_now
                config.gps_local_time_sync.clear()

    # Start the gsm network
    if config.start_gsm_network.is_set():
        if not queue_sender.is_alive():
            if networker.gsm_network_activation():
                config.start_gsm_network.clear()
            else:
                LOGGER.error(">> Couldn't activate GSM connection")
            config.connection_check.set()

    # Stop the gsm network
    if config.stop_gsm_network.is_set():
        if not queue_sender.is_alive():
            if not networker.gsm_network_deactivation():
                LOGGER.error(">> Couldn't disconnect GSM connection")
            config.stop_gsm_network.clear()     

    # Start the network monitor
    if config.connection_check.is_set():
        if not queue_sender.is_alive():
            networker.network_monitor()
            t_last_connection_check = t_now
            config.connection_check.clear()

    # Start the update controller (for sim config and firmware)
    if config.start_update_check.is_set():
        if not queue_sender.is_alive():
            updater.get_remote_update_info(config.CURRENT_NETWORK_IFACE)
            t_last_update_check = t_now
            config.start_update_check.clear()

    # Start the config downloader
    if config.start_config_downloader.is_set():
        if not queue_sender.is_alive():
            updater.get_remote_sim_config(config.CURRENT_NETWORK_IFACE)
            config.start_config_downloader.clear()
    # Start the firmware downloader
    if config.start_firmware_updater.is_set():
        if not queue_sender.is_alive():
            updater.download_and_update_firmware(config.CURRENT_NETWORK_IFACE)
            config.start_firmware_updater.clear()

    # Start the producer
    if config.start_producer.is_set():
        if not queue_sender.is_alive():
            packet = packager.packet_producer()

            # if packet:
            #     packager.packet_handler(packet)
            
            t_last_packet_produced = t_now
            config.start_producer.clear()

    # Start the queue exhauster
    if config.start_exhauster.is_set():
        if not queue_sender.is_alive():
            queue_sender = threading.Thread(target=packager.queue_exhauster)
            queue_sender.start()
        config.start_exhauster.clear()

    return t_last_connection_check, t_last_update_check, t_last_packet_produced


############################################################################
####                                MAIN                                ####
############################################################################

def main_supervisor():

    init_system()

    t_last_packet_produced = time.time()-config.PRODUCE_PACKET_TIMER+5
    t_last_update_check = time.time()-config.UPDATE_CHECK_TIMER+5
    config.T_LAST_TIME_SYNC = time.time()-config.TIME_SYNC_TIMER+1
    t_last_connection_check = 0

    while True:

        if not EXIT_STATUSES.empty():
            error_handler()        
        else:
            t_now = time.time() # to uniform the threads temporal signal to each loop cycle. But maybe is better to launch them asynchronously

            task_coordinator(t_now, t_last_connection_check, t_last_update_check, t_last_packet_produced) 
            t_last_connection_check, t_last_update_check, t_last_packet_produced = task_starter(t_now, t_last_connection_check, t_last_update_check, t_last_packet_produced)

        time.sleep(0.5)
    
    return 0

#---------------------------------------------------------------------------