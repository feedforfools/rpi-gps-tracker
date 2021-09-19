#!/usr/bin/env python3

import time, gpiozero

import serialer as ser
import config, support
import commander as at

#########################################################################################################
####                                     GLOBAL VARS AND CONSTS                                      ####
#########################################################################################################

LOGGER = None

PWRKEY = None

#########################################################################################################
####                                            FUNCTIONS                                            ####
#########################################################################################################

#########################################################################################################
####                                           Main methods                                          ####
#########################################################################################################

def init_modemdler():

    global LOGGER, PWRKEY

    LOGGER = support.CustomLogger("mod")
    PWRKEY = gpiozero.OutputDevice(config.GPIO_PWR_PIN, active_high = True)
    modem_pwr_on()


def init_comms_layer():

    at.set_at_netlight()
    at.set_at_error_output(2)
    at.set_operator_out()
    at.gps_enable()
    if config.SIM_APN and (config.SIM_APN != at.pdp_get_network_configuration() or config.SIM_APN not in at.bearer_get_config(1)):
        at.pdp_shut_gprs()
        at.set_transparent_mode()
        at.pdp_set_network(config.SIM_APN)
        at.pdp_shut_gprs()
        at.bearer_set_config(1, "APN", config.SIM_APN)
    return


def modem_stuck_recovery():

    LOGGER.debug("> Modem data mode recovery")

    try:
        at.check_serial()
    
    except Exception as e:
        # PROBABLY IN DATA MODE
        time.sleep(0.5)
        try:
            at.toggle_cmd_mode()

        except Exception as e:
            LOGGER.error(" >> First time recovery failed.. Last time")
            time.sleep(1)
            try:
                at.toggle_cmd_mode()
            
            except Exception as e:
                LOGGER.error(" >> Recovery failed")
                config.thread_comm("M1")
                return
        
        try:
            at.check_serial()
        
        except Exception as e:
            LOGGER.error(" >> Recovery failed")
            config.thread_comm("M1")
            return
    
    LOGGER.debug("> Recover complete")
    return


def get_gps_time():

    try:
        gps_scan = at.gps_get_location()
        if gps_scan[0]==1:      # GPS is active
            if gps_scan[1]==1:  # GPS fix is done
                return gps_scan[2]
        return False
        
    except Exception as e:
        LOGGER.exception(e)
        return False


#########################################################################################################
####                                          Modem HW Functions                                     ####
#########################################################################################################

        ################ NOTES ON GPIO PWR RESET #############################################
        #   PWR pin on modem (SIM7000) is active LOW (it changes state when is               #
        #   pulled down to GND): 0 = LOW = 3.3v, 1 = HIGH = 0v.                              #
        #   For some reason, when a change of state from 3.3v to 0 is needed, it'll          #
        #   not respond at the first change of state: I need to change to 0V (1) two         #
        #   times in order to power off.                                                     #
        ######################################################################################

def modem_pwr_toggle():

    try:
        # Need to be always on 0: bring up to 1 for 1 second and then bring back to 0
        if PWRKEY.value:
            PWRKEY.off()
        PWRKEY.on()     # UP = 1
        time.sleep(1.1)       # WAIT >1 SECOND (otherwise power down won't work)
        PWRKEY.off()     # DOWN = 0
        # Now the modem will change power state

    except gpiozero.GPIOZeroError as e:
        raise e


def modem_pwr_on():

    LOGGER.debug("> Booting up modem..")
    on = False
    while not on:
        try:
            ser.init_serial_object(config.MODEM_UART_SERIAL_PATH)
            time.sleep(0.5)
            at.check_serial()
        except Exception as e:
            try:
                modem_pwr_toggle()
                time.sleep(8)
            except Exception as e:
                raise e
        else:
            LOGGER.debug("> Modem is ON")
            on = True
    return


def modem_pwr_off():

    LOGGER.debug("> Shutting down modem..")
    off = False
    while not off:
        try:
            at.check_serial()
        except Exception as e:
            off = True
        else:
            try:
                modem_pwr_toggle()
                time.sleep(6)
            except Exception as e:
                raise e
    else:
        LOGGER.debug("> Modem is OFF")
    return


def modem_pwr_reset():

    try:
        modem_pwr_off()
        modem_pwr_on()

    except Exception as e:
        raise e
    
    else:
        LOGGER.debug("> Reset complete")
    
#---------------------------------------------------------------------------


