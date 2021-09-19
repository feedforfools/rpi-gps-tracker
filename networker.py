#!/usr/bin/env python3

import socket, time

from Crypto.Cipher import Salsa20

import config, support
from config import thread_comm
import commander as at

############################################################################
####                   GLOBAL VARIABLES AND CONSTANTS                   ####
############################################################################

LOGGER = None

STOP_HIST_COUNTER = 20     # Counter of consecutive GPS scans without motion

T_GSM_TURN_OFF = 0

GSM_ACTIVATED = False

############################################################################
####                              FUNCTIONS                             ####
############################################################################

# ----------------------------- MAIN METHODS -------------------------------

def init_networker():

    global LOGGER

    LOGGER = support.CustomLogger("net")
    return


def network_monitor(): 
    
    global T_GSM_TURN_OFF

    #LOGGER.debug("Checking connection..")

    update_cellular_info()

    if iface_status("wlan0"):
        if check_internet("wlan0"):
            config.T_LAST_TIME_SYNC = time.time()
            if config.CURRENT_NETWORK_IFACE is not "wlan0":     ##### CHANGE NETWORK INTERFACE USED IN WLAN
                LOGGER.info("[~~~] "+str(config.CURRENT_NETWORK_IFACE)+" ----> wlan0")
                if config.CURRENT_NETWORK_IFACE is "gsm" or GSM_ACTIVATED:
                    T_GSM_TURN_OFF = time.time()
                config.CURRENT_NETWORK_IFACE = "wlan0"
            else:
                if T_GSM_TURN_OFF != 0:
                    if (time.time()-T_GSM_TURN_OFF)>config.TURN_OFF_GSM_TIMER:
                        thread_comm("N2")
                        T_GSM_TURN_OFF = 0
            return
        # else:
        #     LOGGER.warning("> Linked to a WiFi network but not access to internet")
    # else:
    #     LOGGER.warning("> No known WiFi network in range")

    try:
        if "CONNECT OK" in at.connection_status():
            if check_internet("gsm"):
                if config.CURRENT_NETWORK_IFACE is not "gsm":       ##### CHANGE NETWORK INTERFACE USED IN GSM
                    LOGGER.debug("[~~~] "+str(config.CURRENT_NETWORK_IFACE)+" ----> gsm")
                    config.CURRENT_NETWORK_IFACE = "gsm"
                    if T_GSM_TURN_OFF != 0:
                        T_GSM_TURN_OFF = 0
            else:
                LOGGER.warning("> GSM connection is active but ping doesn't work")
            return
    
    except Exception as e:
        LOGGER.exception(e)
        return

    LOGGER.warning("> No internet connections active")
    
    if config.CURRENT_NETWORK_IFACE is not False:
        LOGGER.debug("[~~~] "+str(config.CURRENT_NETWORK_IFACE)+" ----> False")
        config.CURRENT_NETWORK_IFACE = False                        ##### CHANGE NETWORK INTERFACE USED IN FALSE (NO CONNECTION)

    config.thread_comm("N1")

    return


def gsm_network_activation():
    
    global GSM_ACTIVATED

    try:
        status = at.connection_status()
        if status is not "IP INITIAL":
            if status is not "CONNECT OK":
                at.pdp_shut_gprs()
            else:
                LOGGER.debug("> Modem already connected")
                return
        rssi = at.get_rssi()
        reg_status = at.get_registration_status()
        operator = at.get_operator()
        LOGGER.debug("> Modem is "+reg_status+" at "+operator+" ("+str(rssi)+")")
    
    except Exception as e:
        LOGGER.exception(e)
        return False
    
    try:
        if rssi > -105 and (reg_status is "Registered" or reg_status is "Roaming"):
            at.start_connection(config.UP_SERVER_LINK, config.UP_SERVER_UDP_PORT)
        else:
            if reg_status is "Unregistered" and operator is "No registration" and rssi!=99:
                LOGGER.warning(">> Modem needs reset since it's stuck in Unregistered status")
                config.thread_comm("M1con")
                return False
            else:
                LOGGER.warning(">> GSM connection requirements not fulfilled")
                return False

    except ConnectionError as e:
        LOGGER.exception(e)
        config.thread_comm("M1con")
        return False

    except Exception as e:
        LOGGER.exception(e)
        return False

    try:
        at.toggle_cmd_mode()
        LOGGER.info("> Modem connected via GSM")
        GSM_ACTIVATED = True
        return True

    except Exception as e:
        LOGGER.error(">> Toggle CMD mode failed")
        config.thread_comm("M2")
        return False


def gsm_network_deactivation():

    try:
        at.pdp_shut_gprs()
        LOGGER.info("> GSM connection deactivation")
        return True

    except Exception as e:
        LOGGER.exception(e)
        return False


def bearer_network_activation():

    try:
        status = at.bearer_query(1)
        if status:
            if "Bearer" in status:
                at.bearer_close(1)
            else:
                LOGGER.debug("> Modem bearer already open: "+status)
                return True

        # FROM HERE ON THE BEARER CAN BE CREATED SINCE IT'S SURELY NOT ALREADY OPEN
        rssi = at.get_rssi()
        reg_status = at.get_registration_status()
        operator = at.get_operator()
        if rssi > -105 and (reg_status is "Registered" or reg_status is "Roaming"):
            at.bearer_open(1)
        else:
            LOGGER.warning(">> Can't open bearer: "+str(reg_status)+" -> "+str(operator)+" ("+str(rssi)+")")
        
        t_start=time.time()
        status = at.bearer_query(1)
        while status and "Bearer" in status and (time.time()-t_start)<5:
            time.sleep(0.5)
            status = at.bearer_query(1)
        if not status or (time.time()-t_start)>5:
            LOGGER.warning(">> Couldn't open bearer")
            return False

        LOGGER.debug("> Bearer is now open")
        return True

    except Exception as e:
        LOGGER.exception(e)
        return False


def bearer_network_deactivation():

    try:
        status = at.bearer_query(1)
        if status:
            at.bearer_close(1)
            LOGGER.debug("> Bearer now closed")
        else:
            LOGGER.debug("> Bearer already closed")
        return True

    except Exception as e:
        LOGGER.exception(e)
        return False


def http_get(url, timeout, binary):

    try:
        try:
            at.http_term()
        except Exception as e:
            pass
        at.http_init()

        at.http_set_config("CID", 1)
        at.http_set_config("URL", url)

        code, size = at.http_action(0, timeout)
        if code!=200:
            LOGGER.warning(">> GET Request failed: "+str(code))
            return False

        out = at.http_read(size, binary)
        at.http_term()
        return out

    except Exception as e:
        LOGGER.exception(e)
        return False

# --------------------------- NETWORK STATUS UTILITIES ------------------------------

def send_udp_packet(message, interface, loop = False):

    if interface:
        salsa_cipher = Salsa20.new(key=config.SALSA_KEY) 
        enc_msg = salsa_cipher.nonce + salsa_cipher.encrypt(bytes(message, encoding='utf-8'))

        if interface is "gsm":
            try:
                if loop:
                    at.send_packet(enc_msg)
                else:
                    if not at.toggle_data_mode():
                        LOGGER.warning("UDP Packet Send Failed: no active connection")
                        return False
                    at.send_packet(enc_msg)

            except Exception as e:
                LOGGER.error("UDP Packet Send Failed: "+str(e))
                LOGGER.exception(e)
                return False
            
            try:
                if not loop:
                    at.toggle_cmd_mode()
            
            except Exception as e:
                LOGGER.error(">> Toggle CMD mode failed")
                config.thread_comm("M2")
                return False

        else:
            try:
                opened_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                opened_socket.settimeout(3)
                opened_socket.setsockopt(socket.SOL_SOCKET, 25, str(interface + '\0').encode('utf-8'))
                if not check_internet(interface):
                    LOGGER.warning("> No internet connection with wlan0 interface")
                    return False
                opened_socket.sendto(enc_msg, (config.UP_SERVER_LINK, config.UP_SERVER_UDP_PORT))

            except socket.timeout:
                LOGGER.warning("> UDP Packet Send Failed: timeout reached!")
                return False

            except socket.gaierror:
                LOGGER.warning("> UDP Packet Send Failed: network error!")
                return False

            except OSError:
                LOGGER.warning("> UDP Packet Send Failed: other error!")
                return False

        LOGGER.info(support.debug_print_packet(message))
        return True
    return False


def flow_controller(caller, speed = False):

    global STOP_HIST_COUNTER

    if caller is "gps":
        # TODO: make a function for adapting the send frequency to vehicle speed
        if speed < 3:
            STOP_HIST_COUNTER += 1
        else: 
            STOP_HIST_COUNTER = 0

        if STOP_HIST_COUNTER is 0 and not config.NOW_MOVING:
            config.PRODUCE_PACKET_TIMER = 5
            config.NOW_MOVING = True
            config.LONG_TIME_NO_MOVE = False
        elif STOP_HIST_COUNTER > 30:
            if config.PRODUCE_PACKET_TIMER < 60:
                config.PRODUCE_PACKET_TIMER = 60
            config.LONG_TIME_NO_MOVE = True
        elif STOP_HIST_COUNTER > 15:
            if config.PRODUCE_PACKET_TIMER < 60:
                config.PRODUCE_PACKET_TIMER = 60
        elif STOP_HIST_COUNTER > 11:
            config.PRODUCE_PACKET_TIMER = 30
        elif STOP_HIST_COUNTER > 5:
            config.PRODUCE_PACKET_TIMER = 10
            config.NOW_MOVING = False

        if config.PRODUCE_PACKET_TIMER is 20:
            config.PRODUCE_PACKET_TIMER = 5
        config.TIME_TO_NEXT_SEND = config.PRODUCE_PACKET_TIMER  
    
    elif caller is "nofix":
        # TODO: make a function for adapting the send frequency to elapsed time
        if config.PRODUCE_PACKET_TIMER > 20:
            config.PRODUCE_PACKET_TIMER = 20
        config.TIME_TO_NEXT_SEND = config.PRODUCE_PACKET_TIMER
    
    elif caller is "disabled":
        # TODO: make a function for adapring the send frequency to elapsed time
        config.PRODUCE_PACKET_TIMER = 5
        config.TIME_TO_NEXT_SEND = config.PRODUCE_PACKET_TIMER


def iface_status(iface):

    if iface in support.bash_cmd("ifconfig -s", timeout=0.1):
        return True
    return False


def check_internet(iface):

    # if iface is False:
    #     return False
    try:
        if iface is "wlan0":
            output = support.bash_cmd("fping --quiet --alive --iface "+ iface +" --retry=2 1.1.1.1", 2, True)
            if output is not "" and "Error Timeout" not in output:
                return True
            output = support.bash_cmd("fping --quiet --alive --iface "+ iface +" --retry=2 8.8.8.8", 2, True)
            if output is not "" and "Error Timeout" not in output:
                return True
            return False
        
        if iface is "gsm":
            if at.pdp_ping("1.1.1.1"):
                return True
            if at.pdp_ping("8.8.8.8"):
                return True
            return False
    
    except Exception as e:
        LOGGER.exception(e)
        return False


def update_cellular_info():
    
    try:
        config.CURRENT_OPERATOR = at.get_operator()
        config.CURRENT_RSSI = at.get_rssi(False)
    except Exception as e:
        LOGGER.exception(e)