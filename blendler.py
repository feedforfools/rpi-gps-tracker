#!/usr/bin/env python3

import threading, time
import pickle

from bluepy.btle import ScanEntry
from bluepy.btle import Scanner

import config, support

############################################################################
####                   GLOBAL VARIABLES AND CONSTANTS                   ####
############################################################################

LOGGER = None

BLE_SCANNER = None

BLE_SCAN_DURATION = 1
BLE_LIST_MAX_LENGHT = 40
BLE_RSSI_FILTER = -80

BLE_LIST = []
BLE_CHANGE_STATE = []

BLE_CHANGES_LIST = []                                           # This list stores the changes to be inserted in the packets with
                                                                # a differential logic: therefore right now is not used.
                                                                # This list will be shared between two threads: the BLE 
                                                                # scanning routine and the packet forming routine.
ble_lock = threading.Lock()                                     # So it will need a Lock to handle concurrency.
                                                                # However maybe it's possible to use a Queue to append the BLE
                                                                # changed, since it handles automatically the concurrency.

############################################################################
####                               CLASSES                              ####
############################################################################

class BleDevice():
    def __init__(self, mac, tm, name, rssi):
        self.mac = mac
        self.tm = tm
        self.name = name
        self.rssi = rssi
        self.hist = 0b0000000001
        self.vis = -1

    def __hash__(self):
        return hash(self.mac)

    def __eq__(self, other):
        if not isinstance(other, type(self)) and not isinstance(other, str) and not isinstance(other, ScanEntry): return NotImplemented
        if isinstance(other, str):
            return self.mac == other
        elif isinstance(other, ScanEntry):
            return self.mac == other.addr
        return self.mac == other.mac
    
    def update_status(self, found = 0, rssi = 0):
        self.hist = 0b01111111111 & (self.hist << 1)
        if found == 1 or found is True:
            self.hist |= 0b1
            self.rssi = rssi
        if int(self.hist) == 0 and self.vis != -1:
            self.vis = -1
            return self.vis 
        if int(self.hist & 0b0000000111) == 7 and self.vis != 1:
            self.vis = 1
            return self.vis
        return 0
    
    def print_status(self, wrssi = True, whist = False, wvis = False):
        output = self.mac + " " + self.name
        if wrssi:
            output += " ("+str(self.rssi)+")"
        if wvis:
            if self.vis:
                output += " | VISIBLE"
            else:
                output += " | INVISIBLE"
        if whist:
            output += " > "+bin(self.hist)

        return output

############################################################################
####                              FUNCTIONS                             ####
############################################################################

def init_blendler():

    global LOGGER, BLE_SCANNER

    LOGGER = support.CustomLogger("ble")
    BLE_SCANNER = Scanner()
    ble_lists_load()

    return


def ble_lists_dump():

    try:
        if BLE_LIST:
            with open(config.BAK_PATH+"blel.bak","wb") as list_save_file:
                pickle.dump(BLE_LIST, list_save_file)
        if BLE_CHANGES_LIST:
            with open(config.BAK_PATH+"blechl.bak","wb") as list_save_file:
                pickle.dump(BLE_CHANGES_LIST, list_save_file)
        if BLE_CHANGE_STATE:
            with open(config.BAK_PATH+"blechs.bak","wb") as list_save_file:
                pickle.dump(BLE_CHANGE_STATE, list_save_file)
        LOGGER.info("> Saved BLE lists to file")
        return True
    except Exception as e:
        LOGGER.error(">> Error on BLE lists backup: "+str(e))
        return False


def ble_lists_load():

    global BLE_LIST, BLE_CHANGES_LIST, BLE_CHANGE_STATE

    try:
        with open(config.BAK_PATH+"blel.bak","rb") as list_save_file:
            BLE_LIST = pickle.load(list_save_file)
            support.bash_cmd("rm blel.bak")
        LOGGER.info("> Load BLE list from backup file")
    except FileNotFoundError:
        LOGGER.info("> No BLE list backup file found")
        BLE_LIST = []
    except Exception as e:
        LOGGER.error(">> BLE list load error: "+str(e))
        BLE_LIST = []


    try:
        with open(config.BAK_PATH+"blechl.bak","rb") as list_save_file:
            BLE_CHANGES_LIST = pickle.load(list_save_file)
            support.bash_cmd("rm blechl.bak")
        LOGGER.info("> Load BLE CHANGES list from backup file")
    except FileNotFoundError:
        LOGGER.info("> No BLE CHANGES list backup file found")
        BLE_CHANGES_LIST = []
    except Exception as e:
        LOGGER.error(">> BLE CHANGES list load error: "+str(e))
        BLE_CHANGES_LIST = []


    try:
        with open(config.BAK_PATH+"blechs.bak","rb") as list_save_file:
            BLE_CHANGE_STATE = pickle.load(list_save_file)
            support.bash_cmd("rm blechs.bak")
        LOGGER.info("> Load BLE CHANGE STATE list from backup file")
    except FileNotFoundError:
        LOGGER.info("> No BLE CHANGE STATE list backup file found")
        BLE_CHANGE_STATE = []
    except Exception as e:
        LOGGER.error(">> BLE CHANGE STATE list load error: "+str(e))
        BLE_CHANGE_STATE = []

    return

############################ BLE SCAN FUNCTIONS #############################

def ble_thread():

    LOGGER.info("> Starting the BLE scanner")
    while not config.stop_ble_scanner.is_set():
        ble_scanner()
        if ble_state_monitor():
            # # Lock BLE_CHANGES_LIST
            # with blendler.ble_lock:
            #     for index, ble_state in enumerate(blendler.BLE_CHANGE_STATE):
            #         if ble_state == 1 and blendler.BLE_LIST[index].tm:
            #             # In order to not send a packet with a (+) and (-) for the same BLE (not sure it can happen)
            #             # an algorithm that uses the sum in time of the BLE_CHANGE_STATE to create the list just before 
            #             # the creation of the packet could solve this problem: NOTICE THAT this mod may clash with 
            #             # the call of clean_ble_list method since it may drop elements from the state vector 
            #             # between two variations, and since we need to sum them they need to have the same dimension
                        
            #             blendler.BLE_CHANGES_LIST.append("(+) "+blendler.BLE_LIST[index].print_status())
            #         elif ble_state == -1 and blendler.BLE_LIST[index].tm:
            #             blendler.BLE_CHANGES_LIST.append("(-) "+blendler.BLE_LIST[index].print_status())
            # # Unlock BLE_CHANGES_LIST
            config.start_producer.set()
        time.sleep(0.5)
    else:
        LOGGER.warning("> Shutting down the BLE scanner")
        config.stop_ble_scanner.clear()


def ble_scanner():

    global BLE_SCANNER
    try:
        unfilt_devices = BLE_SCANNER.scan(BLE_SCAN_DURATION)
        ble_process(unfilt_devices)
    except Exception as e:
        support.bash_cmd("hciconfig hci0 down && hciconfig hci0 up")
        raise Exception(e)

    
def ble_process(devices):
    
    # the code below on avg is executed in 5ms
    global BLE_LIST
    global BLE_CHANGE_STATE

    # filter scanned devices by rssi (not under BLE_RSSI_FILTER)
    # IN DEBUG SCAN FOR ALL BLE DEVICES -> IN RELEASE FILTER FOR "key-in-name" IN BLE NAME
    filt_devices = [dev for dev in devices if dev.rssi > BLE_RSSI_FILTER]

    for index, ble_dev in enumerate(BLE_LIST):  # update the already once scanned ble
        scan_dev = next((x for x in filt_devices if x==ble_dev), None)
        if scan_dev is None:                    # ble_dev not present in this scan
            BLE_CHANGE_STATE[index] = ble_dev.update_status() 
        else:                                   # ble_dev is present in this scan
            BLE_CHANGE_STATE[index] = ble_dev.update_status(1, scan_dev.rssi) 
            filt_devices.remove(scan_dev) # remove the already processed device from devices (leaving with list of never found devices)

    for dev in filt_devices: # create a new ble object for each remaining scanned device (since they're new)
        name = dev.getValueText(9)
        if name is not None:
            if "key-in-name" in name:
                ble_dev = BleDevice(dev.addr, True, name, dev.rssi)
                BLE_LIST.append(ble_dev)
                BLE_CHANGE_STATE.append(0)
            # else:
            #     ble_dev = BleDevice(dev.addr, False, name, dev.rssi)
            #     BLE_LIST.append(ble_dev)
            #     BLE_CHANGE_STATE.append(0)

    # remove from ble list all the not found device for long time if the list is growing long
    if len(BLE_CHANGE_STATE) > BLE_LIST_MAX_LENGHT:
        clean_ble_lists()


def ble_state_monitor():
    
    if(sum(map(abs, BLE_CHANGE_STATE))!=0):
        ble_changes_visualizer()
        return True
    return False


def clean_ble_lists():

    global BLE_LIST
    global BLE_CHANGE_STATE

    for index, ble_dev in enumerate(BLE_LIST):
        if int(ble_dev.hist) == 0:
            BLE_LIST.pop(index)
            BLE_CHANGE_STATE.pop(index)

########################### OTHER BLE FUNCTIONS ############################

def ble_visualizer(all_ble=False):

    for ble_dev in BLE_LIST:
        if ble_dev.vis == 1:
            if ble_dev.tm or all_ble:
                print(ble_dev.print_status())
                

def ble_changes_visualizer(all_ble=False):

    print("+++++++ BT CHANGES +++++++")
    for index, ble_state in enumerate(BLE_CHANGE_STATE):
        if BLE_LIST[index].tm or all_ble:
            if ble_state == 1:
                print("(+) "+BLE_LIST[index].print_status())
            elif ble_state == -1:
                print("(-) "+BLE_LIST[index].print_status())

############################################################################
####                                MAIN                                ####
############################################################################

def main_blendler():

    global BLE_SCANNER

    BLE_SCANNER = Scanner()
    # for test purposes only
    t_start = time.time()

    while True:
        ble_scanner()
        if ble_state_monitor():
            ble_changes_visualizer(True)
        if time.time()-t_start>10:
            ble_visualizer(True)
            t_start = time.time()

    return 0

#---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        main_blendler()
    except Exception as e:
        print("main crashed. Error: %s", e)