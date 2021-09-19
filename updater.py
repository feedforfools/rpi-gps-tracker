#!/usr/bin/env python3

import requests, json, zipfile
from os import path
from configparser import ConfigParser

from Crypto.Cipher import Salsa20

import config, networker, support

############################################################################
####                   GLOBAL VARIABLES AND CONSTANTS                   ####
############################################################################

LOGGER = None

LAST_SSID = ""
LAST_PWD = ""

############################################################################
####                              FUNCTIONS                             ####
############################################################################

# ----------------------------- MAIN METHODS -------------------------------

def init_updater():

    global LOGGER

    LOGGER = support.CustomLogger("upd")
    load_sim_config()
    
    return

# ------------------------------- CONFIG DOWNLOADER ---------------------------------

def load_sim_config():

    try:
        file_config_parser = ConfigParser()
        if path.exists(config.CFG_PATH+"sim_config.ini"):
            config_file = open(config.CFG_PATH+"sim_config.ini", "r")            
            file_config_parser.read(config.CFG_PATH+"sim_config.ini")
            config.SIM_APN = file_config_parser.get('main', 'apn')
            config.SIM_PIN = file_config_parser.get('main', 'pin')
            config.CONFIG_LAST_UPDATE = int(file_config_parser.get('main', 'last'))
            LOGGER.info("> sim_config.ini found: "+config.SIM_APN+" "+config.SIM_PIN)
            config_file.close()
            config.MODEM_CONFIG_CHANGED = True
        else:
            LOGGER.debug("> No sim_config.ini found")

    except Exception as e:
        LOGGER.error(">> Can't load sim configuration: "+str(e))
        LOGGER.exception(e)


def write_sim_config():

    try:
        file_config_parser = ConfigParser()
        support.bash_cmd("rm "+config.CFG_PATH+"sim_config.ini")
        file_config_parser.read(config.CFG_PATH+"sim_config.ini")
        file_config_parser.add_section('main')
        file_config_parser.set('main', 'apn', config.SIM_APN)
        file_config_parser.set('main', 'pin', config.SIM_PIN)
        file_config_parser.set('main', 'last', str(config.CONFIG_LAST_UPDATE))
        with open(config.CFG_PATH+"sim_config.ini", "w") as config_file:
            file_config_parser.write(config_file)
        LOGGER.info("> New sim_config.ini written successfully")
        return True
    except Exception as e:
        LOGGER.error(">> Something went wrong: "+str(e))
        LOGGER.exception(e)
        return False


def get_data_from_server(interface, url, timeout = 15, binary = False):

    if interface is not "wlan0":
        if not networker.bearer_network_activation():
            return False
        get_out = networker.http_get(url, timeout, binary) 
        networker.bearer_network_deactivation()
    else:
        try:
            out = requests.get("https://" + url, timeout=timeout, verify=False)
            if binary:
                get_out = out.content
            else:
                get_out = out.text
        except Exception as e:
            LOGGER.error(">> Server request error: "+str(e))
            return False        
    return get_out


def get_remote_update_info(interface):
    
    get_out = get_data_from_server(interface, config.DOWN_SERVER_LINK + config.DEVICE_ID)

    if get_out:
        out_list = get_out.split(";")
        if out_list[0]:
            if int(out_list[0])>config.CONFIG_LAST_UPDATE:
                config.thread_comm("U2")
        else:
            LOGGER.warning("> No SIM config data for this device")
        if out_list[1]:
            try:
                if config.REMOTE_VERSION != out_list[1]:
                    if config.version_cmp(config.VERSION, out_list[1]):
                        config.REMOTE_VERSION = out_list[1]
                        if not path.isfile(config.BAK_PATH+config.REMOTE_VERSION+".zip"):
                            config.DOWNLOAD_FW = True
                        else:
                            LOGGER.info("> New FW version "+str(out_list[1])+" already downloaded")
                            config.DOWNLOAD_FW = False
                        config.thread_comm("U1")
                    else:
                        LOGGER.info("> Current FW version "+config.VERSION+" is updated (s.v: "+str(out_list[1])+")")
            except Exception as e:
                LOGGER.error(">> FW update not supported: "+str(out_list[1]))
                return False
        else:
            LOGGER.warning("> No FW update for this device")  
    else:
        LOGGER.error(">> No data downloaded")
        return False


def get_remote_sim_config(interface):

    # Get GSM configuration from server
    LOGGER.info("> Update SIM config from server")

    get_out = get_data_from_server(interface, config.CONFIG_DOWN_SERVER_LINK + config.DEVICE_ID, binary=True)

    if get_out:
        salsa_cipher = Salsa20.new(key=config.SALSA_KEY, nonce=get_out[:8])
        config_json = salsa_cipher.decrypt(get_out[8:]).decode("utf-8")
        config_json_data = json.loads(config_json)["data"]

        if config_json_data:
            config_dict = json.loads(json.dumps(config_json_data))[0]
            last_update = support.iso_to_timestamp(config_dict["updated"])

            config.SIM_APN = config_dict["apn"]
            config.SIM_PIN = config_dict["pin"]
            config.CONFIG_LAST_UPDATE = last_update
            wifiSSID = config_dict["ssid"]
            wifiPWD = config_dict["password"]

            config.MODEM_CONFIG_CHANGED = True

            if wifiSSID and wifiPWD:
                if LAST_SSID == wifiSSID and LAST_PWD == wifiPWD:
                    LOGGER.info("> Wifi connection downloaded already configured")
                else:
                    edit_wpa_conf(wifiSSID, wifiPWD)

            if write_sim_config():
                return True
            return False
        else:
            LOGGER.error(">> Download error: no config data")
    else:
        LOGGER.error(">> No data downloaded")
        config.thread_comm("N3")
        return False


def edit_wpa_conf(ssid, pwd):

    global LAST_SSID, LAST_PWD

    wpa_list = support.bash_cmd("wpa_cli list_networks")

    if ssid in wpa_list:
        for line in wpa_list.splitlines():
            if ssid in line:
                ssid_id = line[0]
        out_delete_wpa_ssid = support.bash_cmd("wpa_cli remove_network "+ssid_id)
        if "OK" in out_delete_wpa_ssid:
            out_save_wpa_ssid = support.bash_cmd("wpa_cli save_config")
            if "OK" in out_save_wpa_ssid:
                LOGGER.debug("> New configuration for "+ssid+": delete OK")
            else:
                LOGGER.debug(">> Something went wrong in the delete")
        else:
            LOGGER.debug(">> Something went wrong in the delete")

    wpa_list = support.bash_cmd("wpa_cli list_networks")
    if ssid not in wpa_list:
        LOGGER.debug("> Adding a new WiFi")
        output = support.bash_cmd("sh -c \"wpa_passphrase \'"+str(ssid)+"\' \'"+str(pwd)+"\' >> /etc/wpa_supplicant/wpa_supplicant.conf\"") 
        if not "Error" in output:
            support.bash_cmd("wpa_cli reconfigure")
            LOGGER.info("> Added custom WiFi configuration")
        else:
            LOGGER.error(output)
        LAST_SSID = ssid
        LAST_PWD = pwd


def download_and_update_firmware(interface):

    if get_firmware_update(interface):
        if backup_current_firmware():
            if update_firmware():
                return True
    config.thread_comm("U0")
    config.REMOTE_VERSION = ""
    return False


def get_firmware_update(interface):

    if config.DOWNLOAD_FW:
        # get firmware update from server
        LOGGER.info("> Download firmware update from server")

        get_out = get_data_from_server(interface, config.FIRM_DOWN_SERVER_LINK + config.DEVICE_ID, 60, True)
        if get_out:
            try:
                with open(config.BAK_PATH+config.REMOTE_VERSION+".zip", "wb") as file:
                    file.write(get_out)
            except Exception as e:
                LOGGER.error(">> ZIP saving error")
                LOGGER.exception(e)
                return False
        else:
            LOGGER.error(">> No data downloaded")
            return False
    return True


def backup_current_firmware():

    LOGGER.info("> Backing up current fw version")
    current_fw_bu_folder = config.BAK_PATH+config.VERSION

    if "Error" in support.bash_cmd("mkdir "+current_fw_bu_folder):
        LOGGER.warning("> Backup folder "+current_fw_bu_folder+" already existing")
        return True
    if "Error" in support.bash_cmd("cp "+config.REL_PATH+"*.py "+current_fw_bu_folder):
        LOGGER.error(">> Backup failed")
        return False
    return True


def update_firmware():

    LOGGER.info("> Updating firmware version to "+config.REMOTE_VERSION)
    if "Error" in support.bash_cmd("rm "+config.REL_PATH+"*.py"):
        LOGGER.error(">> Update failed: couldn't delete current version")
        return False
    try:
        with zipfile.ZipFile(config.BAK_PATH+config.REMOTE_VERSION+".zip", 'r') as zip_ref:
            zip_ref.extractall(config.REL_PATH)
    except Exception as e:
        LOGGER.error(">> Update failed: couldn't extract update zip")
        LOGGER.exception(e)
        LOGGER.error(str(e))
        LOGGER.debug("> Recover from backup")
        support.bash_cmd("cp "+config.BAK_PATH+config.VERSION+"/*.py "+config.REL_PATH)
        return False
    else:
        support.bash_cmd("chmod 666 "+config.REL_PATH+"*.py")
        support.bash_cmd("rm "+config.BAK_PATH+config.REMOTE_VERSION+".zip")
    LOGGER.info("> Update successful: restarting process to new version")
    config.thread_comm("W1")
    return True

#------------------------------------------------------------------------------------