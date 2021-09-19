#!/usr/bin/env python3

import subprocess, os, urllib3, logging, re, math
import datetime, time
from logging.handlers import TimedRotatingFileHandler
import traceback

import config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

############################################################################
####                   GLOBAL VARIABLES AND CONSTANTS                   ####
############################################################################

LOGGER = False

############################################################################
####                               CLASSES                              ####
############################################################################

class CustomLogger():
    def __init__(self, name):
        self.name = name

    def general(self, level, message):
        config.CUSTOM_LOG_QUEUE.put([self.name, level, message])

    def info(self, message):
        self.general(0, message)

    def debug(self, message):
        self.general(1, message)

    def warning(self, message):
        self.general(2, message)

    def error(self, message):
        self.general(3, message)

    def exception(self, exc: Exception):
        self.general(3, ''.join(traceback.format_tb(exc.__traceback__))+" "+str(exc))

    def critical(self, message):
        self.general(4, message)
    
############################################################################
####                              FUNCTIONS                             ####
############################################################################

# ----------------------------- MODEM/OS APIs ------------------------------

def bash_cmd(cmd, timeout=5, ignore_exit_status=False, background=False):
    
    try:     
        if background:
            cmd_list = cmd.split(" ")
            subprocess.Popen(cmd_list)
            return True
        else:
            return subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True, timeout=timeout).decode()
    
    except subprocess.CalledProcessError as proc_e:
        if ignore_exit_status:
            return proc_e.output.decode()
        return "Error CalledProcess: " + proc_e.output.decode()

    except subprocess.TimeoutExpired as time_e:
        return "Error Timeout: " + time_e.output.decode()
    
    except Exception as gen_e:
        return "Error system command: " + gen_e


def reboot_system():
    return bash_cmd("sudo reboot now")


def restart_process():
    os.system("python3 "+config.REL_PATH+"supervisor.py")
    os._exit(0)
    return 

def set_local_time_from_gps(gps_timestamp):
    
    try:
        output = bash_cmd("date -s \""+str(datetime.datetime.fromtimestamp(int(float(gps_timestamp))))+"\"")
        set_os_timezone()
    
    except Exception as e:
        LOGGER.exception(e)
        LOGGER.error(">> Error on setting system datetime from GPS")


def set_os_timezone():
    try:
        output = bash_cmd("timedatectl set-timezone Europe/Rome")
        return "Set timezone correctly!"
    except:
        return "Error in setting timezone!"


# --------------------------------- VARIOUS DEBUG UTILITIES --------------------------------

def logger_publisher_thread():

    if LOGGER:
        while True:
            try:
                if not config.CUSTOM_LOG_QUEUE.empty():

                    log_line = config.CUSTOM_LOG_QUEUE.get()

                    if log_line[1] is 0:
                        LOGGER.info(log_line[0]+"  "+log_line[2])
                    elif log_line[1] is 1:
                        LOGGER.debug(log_line[0]+"  "+log_line[2])
                    elif log_line[1] is 2:
                        LOGGER.warning(log_line[0]+"  "+log_line[2])
                    elif log_line[1] is 3:
                        LOGGER.error(log_line[0]+"  "+log_line[2])
                    elif log_line[1] is 4:
                        LOGGER.critical(log_line[0]+"  "+log_line[2])
            except Exception as e:
                LOGGER.error("ini  Error in logger: "+str(e))

            time.sleep(0.1)


def setup_logger(device_id, create_file=True, path = config.LOG_PATH, level = logging.DEBUG):

    global LOGGER

    # create logger object
    LOGGER = logging.getLogger(device_id)
    LOGGER.setLevel(level)

    # create formatter to add to the handlers
    formatter = logging.Formatter('%(asctime)s %(levelname).3s %(message)s','%H:%M:%S')

    # create the console handler and add to the logger 
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(formatter)
    LOGGER.addHandler(ch)

    # create the file handler and add to the logger
    if create_file:
        fh = TimedRotatingFileHandler(path+device_id+".log", when="midnight", interval=1, backupCount=31)
        fh.setLevel(level)
        fh.setFormatter(formatter)
        LOGGER.addHandler(fh)
    
    LOGGER.info("ini  ######################################################")
    LOGGER.info("ini  #              GPS Tracker" + device_id)
    LOGGER.info("ini  ######################################################")

    return


def escape_ansi(line):
    ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', line)


def calc_str_time(diff):
    str_time = ""
    calc_time = int(math.floor(diff/60))
    if calc_time!=0:
        str_time += str(calc_time) + "m"
    str_time += str(round(diff%60,2)) + "s"
    return str_time


def get_utc_timestamp():
    return str(int(datetime.datetime.now().timestamp()))


def iso_to_timestamp(isodate):
    return int(datetime.datetime.timestamp(datetime.datetime.fromisoformat(isodate.replace("Z", "+00:00"))))


def gps_date_to_timestamp(gps_datetime):
    return (datetime.datetime(int(gps_datetime[0:4]),
                              int(gps_datetime[4:6]),
                              int(gps_datetime[6:8]),
                              int(gps_datetime[8:10]),
                              int(gps_datetime[10:12]),
                              int(gps_datetime[12:14])) - datetime.datetime(1970,1,1)).total_seconds()


def debug_print_packet(packet, show_date = True, show_gps = True, show_ble = False):

    packet_list = packet.split(";")
    output = packet_list[12] + "_"
    if show_date:
        output += datetime.datetime.utcfromtimestamp(int(float(packet_list[6]))).strftime('%H:%M:%S')
    output += " | BLE: "+ str(packet_list[9].count("-"))
    if show_gps:
        output += " | "+packet_list[0]+" "+packet_list[1]+" "+packet_list[3]
    
    ## TODO: add BLE data to output

    return output


def speed_custom_sin_generator(omega, tzero):

    return max(int(100*math.sin(omega*(time.time()-tzero))),0)
