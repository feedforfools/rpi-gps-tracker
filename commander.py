#!/usr/bin/env python3

import time

import support
from serialer import serial_command, write_to_serial

############################################################################
####                   GLOBAL VARIABLES AND CONSTANTS                   ####
############################################################################

LOGGER = False

#########################################################################################################
####                                          Basic AT Functions                                     ####
#########################################################################################################

def check_serial():

    try:
        at_out = serial_command("AT", timeout=1)

    except Exception as e:
        raise e

    else:
        if "ERROR" in at_out:
            return False
        return True


def get_function_state():

    ######################## OUTPUT CFUN #########################################
    # 0     Minimum functionality
    # 1     Full functionality (default)
    # 4     Disable phone both transmit and receive RF circuits 
    # 5     Factory Test Mode 
    # 6     Reset 
    # 7     Offline Mode
    ##############################################################################

    try:
        at_out = serial_command("AT+CFUN?")
        fun_code = int(at_out.split("+CFUN: ")[1])

    except Exception as e:
        raise e

    else:
        if fun_code is 0:
            return "Minimum functionality"
        elif fun_code is 1:
            return "Full functionality"
        elif fun_code is 4:
            return "RF disabled"
        elif fun_code is 5:
            return "Factory test mode"
        elif fun_code is 6:
            return "Reset"
        elif fun_code is 7:
            return "Offline mode"


def set_function_state(code):

    try:
        serial_command("AT+CFUN="+str(code))

    except Exception as e:
        raise e


def reset_modem():

    try:
        serial_command("AT+CFUN=1,1")

    except Exception as e:
        raise e


def get_at_error_config():

    try:
        at_out = serial_command("AT+CMEE?")
        error_code = int(at_out.split("+CMEE: ")[1])

    except Exception as e:
        raise e

    else:
        return error_code


def set_at_error_output(code=2):

    ###################################################################
    #   0. No explanations
    #   1. Code
    #   2. Verbose
    ###################################################################

    try:
        serial_command("AT+CMEE="+str(code))

    except Exception as e:
        raise e


def set_at_netlight(on = False):

    try:
        serial_command("AT+CNETLIGHT="+str(int(on)))

    except Exception as e:
        raise e


def toggle_data_mode():

    try:
        at_out = serial_command("ATO", exit_word="E", timeout=5)
        time.sleep(1.001)

    except Exception as e:
        raise e
    
    else:
        if "CONNECT" in at_out:
            return True
        return False


def toggle_cmd_mode():

    try:
        time.sleep(1.001)
        serial_command("+++", escape_char="", timeout=2)

    except Exception as e:
        raise e
        # try:
        #     time.sleep(1.001)
        #     serial_command("+++", escape_char="", timeout=2)

        # except Exception as e:
        #     config.thread_comm("M1")
        #     raise e            


#########################################################################################################
####                                   SIM7000 CELLULAR FUNCTIONS                                    ####
#########################################################################################################

def get_sim_status():

    ############################### OUTPUT CPIN ##########################################
    # READY         MT is not pending for any password         
    # SIM PIN       MT is waiting SIM PIN to be given        
    # SIM PUK       MT is waiting for SIM PUK to be given 
    # PH_SIM PIN    ME is waiting for phone to SIM card (antitheft) 
    # PH_SIM PUK    ME is waiting for SIM PUK (antitheft) 
    # SIM PIN2      PIN2, e.g. for editing the FDN book possible only 
    #               if preceding Command was acknowledged with +CME ERROR:17
    # SIM PUK2      Possible only if preceding Command was acknowledged with 
    #               error +CME ERROR: 18. 
    ######################################################################################

    try:
        at_out = serial_command("AT+CPIN?")
        pin_status = at_out.split("+CPIN: ")

    except Exception as e:
        raise e

    else:
        if "READY" in pin_status:
            return "Unlocked"
        elif "SIM PIN" in pin_status:
            return "PIN locked"
        elif "SIM PUK" in pin_status:
            return "PUK locked"
        else:
            return "Unknown"


def sim_unlock(pin = False, puk = False):

    try:
        if puk:
            serial_command("AT+CPIN=\""+puk+"\",\""+pin+"\"")
        elif pin:
            serial_command("AT+CPIN=\""+pin+"\"")

    except Exception as e:
        raise e


def clear_sim_lock(pin):

    try:
        serial_command("AT+CLCK=\"SC\",0,\""+pin+"\",1")

    except Exception as e:
        raise e


def get_operator():
    
    ######################## OUTPUT COPS #################################################
    # 0                     No registration
    # 0,0,"operator",x      x -> access tech (see next function)      
    ######################################################################################

    try:
        at_out = serial_command("AT+COPS?")
        cops_list = at_out.split("+COPS: ")[1].split(",")

    except Exception as e:
        raise e

    else:
        if len(cops_list)>2:
            if "SIM-operator" in cops_list[2]:
                cops_list[2] = cops_list[2].replace("SIM-operator","")
            cops_list[2] = cops_list[2].replace(" ","")
            return cops_list[2].replace("\"","")
        return "No registration"


def set_operator_out(code = 1):

    ################################# CODE OUTPUT COPS ###################################
    # Operator code configuration
    # 0     Complete text operator
    # 1     Reduced text operator      
    # 2     Operator code (5 digits)
    # Mode code configuration
    # 0     Automatic mode
    # 1     Manual mode
    # 2     Manual deregister from network
    # >>>>  3     Set only format code on read command
    # 4     Manual/automatic
    ######################################################################################

    try:
        serial_command("AT+COPS=3,"+str(code))

    except Exception as e:
        raise e


def get_access_tech():

    ######################## ACCESS TECH ################################################
    # 0     User-specified GSM access technology
    # 1     GSM compact
    # 3     GSM EGPRS
    # 7     User-specified LTEM1AGB access technology
    # 9     User-specified LTENBS1 access technology
    #####################################################################################

    try:
        at_out = serial_command("AT+COPS?")
        cops_list = at_out.split("+COPS: ")[1].split(",")
        if len(cops_list)>2:
            acc_tech = int(cops_list[3])
        else:
            return False

    except Exception as e:
        raise e

    else:
        if acc_tech is 0:
            return "User GSM"
        elif acc_tech is 1:
            return "GSM compact"
        elif acc_tech is 3:
            return "GSM EGPRS"
        elif acc_tech is 7:
            return "LTE-M1-AGB"
        elif acc_tech is 9:
            return "LTE-NB-S1"


def get_registration_status():

    ######################## OUTPUT CREG ###############################################
    # 0    Not registered, MT is not currently searching a new 
    #      operator to register to
    # 1    Registered, home network 
    # 2    Not  registered,  but  MT  is  currently  searching  
    #      a  new  operator to register to
    # 3    Registration denied
    # 4    Unknown 
    # 5    Registered, roaming 
    ####################################################################################

    try:
        at_out = serial_command("AT+CREG?")
        reg_code = int(at_out.split("+CREG: ")[1].split(",")[1].split(" ")[0])

    except Exception as e:
        raise e

    else:
        if reg_code is 0:
            return "Unregistered"
        elif reg_code is 1:
            return "Registered"
        elif reg_code is 2:
            return "Searching"
        elif reg_code is 3:
            return "Denied"
        elif reg_code is 4:
            return "Unknown"
        elif reg_code is 5:
            return "Roaming"


def get_rssi(dbm = True):

    try:
        at_out = serial_command("AT+CSQ")
        rssi_vote = int(at_out.split("+CSQ: ")[1].split(",")[0])

    except Exception as e:
        raise e

    else:
        if not dbm or rssi_vote > 31:
            return rssi_vote
        return -115 + 2*rssi_vote


def gprs_attach():

    try:
        at_out = serial_command("AT+CGATT=1")

    except Exception as e:
        raise e


def gprs_status():

    try:
        at_out = serial_command("AT+CGATT?")
        gprs = int(at_out.split("+CGATT: ")[1].split("\n")[0])

    except Exception as e:
        raise e
    
    else:
        if gprs is 0:
            return False
        return True


def gprs_detach():

    try:
        at_out = serial_command("AT+CGATT=0")

    except Exception as e:
        raise e

#########################################################################################################
####                                 SIM7000 TCP/UDP NET FUNCTIONS                                   ####
#########################################################################################################

    ############### PDP CONTEXT STATES ###############
    #                                                #
    #   0:  IP INITIAL                               #
    #   1:  IP START                                 #
    #   2:  IP CONFIG                                #
    #   3:  IP GPRSACT                               #          
    #   4:  IP STATUS                                #
    #   5:  TCP/UDP CONNECTING - SERVER LISTENING    #
    #   6:  CONNECT OK                               #
    #   7:  TCP/UDP CLOSING                          #
    #   8:  TCP/UDP CLOSED                           #
    #   9:  PDP DEACT                                #
    #                                                #
    ##################################################

def pdp_set_network(apn):

    #############################
    #   Start:  IP INITIAL      #
    #   End:    IP START        #
    #############################

    try:
        at_out = serial_command("AT+CSTT=\""+apn+"\"")

    except Exception as e:
        raise e
    

def pdp_get_network_configuration():

    try:
        at_out = serial_command("AT+CSTT?")
        apn = at_out.split("\"")[1]

    except Exception as e:
        raise e

    else:
        return apn


def pdp_gprs_call():

    #############################
    #   Start:  IP START        #
    #   Mid:    IP CONFIG       #
    #   End:    IP GPRSACT      #
    #############################

    try:
        at_out = serial_command("AT+CIICR")

    except Exception as e:
        raise e


def pdp_get_ip():

    #########################################################################
    #   Start:  IP GPRSACT, TPC/UDP CONNECTING, SERVER LISTENING,           #
    #           IP STATUS, CONNECT OK, TCP/UDP CLOSING, TCP/UDP CLOSED      #
    #   End:    IP STATUS                                                   #
    #########################################################################

    try:
        at_out = serial_command("AT+CIFSR", exit_word=".",  timeout=10)

    except Exception as e:
        raise e

    else:
        return at_out


def pdp_shut_gprs():

    #############################
    #   Start:  Every state     #
    #   End:    IP INITIAL      #
    #############################

    try:
        at_out = serial_command("AT+CIPSHUT")

    except Exception as e:
        raise e


def start_connection(url, port, protocol="UDP"):

    ###############################################################
    #   Start:  IP INITIAL (if APN is configured), IP STATUS      #
    #   Mid:    All middle ones                                   #
    #   End:    CONNECT OK                                        #
    ###############################################################

    try:
        at_out = serial_command("AT+CIPSTART=\""+protocol+"\",\""+str(url)+"\",\""+str(port)+"\"", exit_word="CONNECT", timeout=160)
        
    except Exception as e:
        raise e
    
    if "FAIL" in at_out:
        raise ConnectionError("CONNECT FAIL while activating GSM connection")


def connection_status():
    
    ##################################
    #   OK                           #
    #                                #      
    #   STATE: <state>               #
    ##################################

    try:
        at_out = serial_command("AT+CIPSTATUS", exit_word="STATE", timeout=1)
        state = at_out.split(": ")[1]

    except Exception as e:
        raise e

    else:
        return state  


def stop_connection():

    ###############################################################
    #   Start:  TCP/UDP CONNECTING, CONNECT OK                    #
    #   Mid:    TCP/UDP CLOSING                                   #
    #   End:    TCP/UDP CLOSED                                    #
    ###############################################################

    try:
        at_out = serial_command("AT+CIPCLOSE")

    except Exception as e:
        raise e


#+CIPPING: 2,"0.0.0.0",60000,255 
def pdp_ping(server, retry=2, size=1, timeout=30, ttl=64):
    
    ###############################################################
    #   retry       = [1, 100]                                    #
    #   size        = [1, 1024]                                   #
    #   timeout     = [1, 600] -> [100ms, 60s]                    #
    #   ttl         = [1, 255]                                    #
    ###############################################################

    try:
        at_out = serial_command("AT+CIPPING="+server+","+str(retry)+","+str(size)+","+str(timeout)+","+str(ttl))

    except Exception as e:
        raise e

    else:
        if "60000,255" in at_out:
            return False
        return True


def set_transparent_mode(active=True):
    
    try:
        at_out = serial_command("AT+CIPMODE="+str(int(active)))

    except Exception as e:
        raise e


def set_packet_format(hex=True):

    try:
        at_out = serial_command("AT+CIPSENDHEX="+str(int(hex)))

    except Exception as e:
        raise e


def send_packet(message, transparent = True, length = False): # message needs to be coherent to the packet format set before

    try:
        if transparent:
            write_to_serial(message, "")
        else:
            if length:
                serial_command("AT+CIPSEND="+str(length), ">")
                serial_command(message, escape_char="", exit_word="</>")
            else:
                serial_command("AT+CIPSEND=", ">")
                at_out = serial_command(message, escape_char=chr(26))

    except Exception as e:
        raise e  

#########################################################################################################
####                                  SIM7000 BEARER NET FUNCTIONS                                   ####
#########################################################################################################

    ######################## AT+SAPBR CMD TYPE #####################################
    # 0    Close bearer
    # 1    Open bearer 
    # 2    Query bearer
    # 3    Set bearer parameters
    # 4    Get bearer parameters 
    ################################################################################

def bearer_close(cid):

    try:
        serial_command("AT+SAPBR=0,"+str(cid), timeout=2)

    except Exception as e:
        raise e


def bearer_open(cid):

    try:
        serial_command("AT+SAPBR=1,"+str(cid))

    except Exception as e:
        raise e


def bearer_query(cid):

    # +SAPBR: CID,CODE,IP-ADDR
    ######################## QUERY STATUS CODE (second number) #######################
    # 0    Bearer is connecting
    # 1    Bearer is connected
    # 2    Bearer is closing
    # 3    Bearer is closed
    ##################################################################################

    try:
        at_out = serial_command("AT+SAPBR=2,"+str(cid), timeout=2)
        code = int(at_out.split(",")[1])
        ip = at_out.split(",")[2].split("\"")[1]

    except Exception as e:
        raise e

    else:
        if code is 0:
            return "Bearer connecting"
        if code is 1:
            return ip # Bearer connected
        if code is 2:
            return "Bearer closing"
        if code is 3:
            return False        


def bearer_set_config(cid, tag, value):

    ### tag ########################## AT+SAPBR SET CMDS ##################################
    # CONTYPE       Type of Internet connection -> [CSD, GPRS]
    # APN           Connection APN
    # USER          Connection Username
    # PWD           Connection Password
    # PHONENUM      Phone number for CSD call 
    # RATE          CSD connection rate -> [0 (2400), 1 (4800), 2 (9600), 3 (14400)]
    #######################################################################################

    try:
        serial_command("AT+SAPBR=3,"+str(cid)+",\""+tag+"\",\""+value+"\"", timeout=2)

    except Exception as e:
        raise e


def bearer_get_config(cid):

    try:
        at_out = serial_command("AT+SAPBR=4,"+str(cid), timeout=2)

    except Exception as e:
        raise e 

    else:
        return at_out
        
#########################################################################################################
####                                    SIM7000 HTTP NET FUNCTIONS                                   ####
#########################################################################################################

def http_init():

    try:
        serial_command("AT+HTTPINIT")

    except Exception as e:
        raise e


def http_term():

    try:
        serial_command("AT+HTTPTERM")

    except Exception as e:
        raise e


def http_set_config(tag, value):

    ################################## AT+SAPBR SET CMDS ###########################################
    # CID           Connection bearer ID
    # URL           HTTP client URL
    # TIMEOUT       Request timeout, default is 120, minimum is 30
    ################################################################################################

    try:
        if tag is "URL":
            serial_command("AT+HTTPPARA=\""+tag+"\",\""+str(value)+"\"")
        else:
            serial_command("AT+HTTPPARA=\""+tag+"\","+str(value))

    except Exception as e:
        raise e


def http_action(action, timeout):

    ############################### HTTP ACTION CODE ###########################################
    # 0    GET
    # 1    POST
    # 2    HEAD
    # 3    DELETE
    ############################################################################################

    try:
        at_out = serial_command("AT+HTTPACTION="+str(action), exit_word=":", timeout=timeout)
        result = at_out.split("+HTTPACTION: ")[1]
        code = int(result.split(",")[1]) 
        size = int(result.split(",")[2])

    except Exception as e:
        raise e
    
    else:
        return code, size


def http_read(size, binary = False):

    try:
        at_out = serial_command("AT+HTTPREAD", binary=binary, size=size)
        if not binary:
            get_read = at_out.split(" ")[2]

    except Exception as e:
        raise e

    else:
        if not binary:
            return get_read
        return at_out

#########################################################################################################
####                                    SIM7000 GNSS/GPS FUNCTIONS                                   ####
#########################################################################################################

def gps_enable():

    try:
        serial_command("AT+CGNSPWR=1")

    except Exception as e:
        raise e


def gps_disable():

    try:
        serial_command("AT+CGNSPWR=0")

    except Exception as e:
        raise e


def gps_get_location():

    try:
        at_out = serial_command("AT+CGNSINF")
        gps_scan = cgnsinf_parser(at_out.split("+CGNSINF: ")[1])
        
    except Exception as e:
        raise e

    else:
        return gps_scan
        
############################################# CGNSINF STRING LEGENDA ################################################
#
#  +CGNSINF: run_status,fix_status,utc,latitude,longitude,altitude,speed,course,fix_mode,?,hdop,pdop,vdop,?,
#            gps_sat_in_view,gnss_used_sat,glonass_used_sat,?,c/n0_max,hpa,vpa
#
#   1- run_status:          0 > GPS disabled
#                           1 > GPS enabled
#   2- fix_status:          0 > No fix 
#                           1 > Fix done
#   3- utc:                 yyyyMMddhhmmss.sss
#   4- latitude:            ±dd.dddddd
#   5- longitude:           ±ddd.dddddd
#   6- altitude:            [m]
#   7- speed:               0-999.99 [km/h]
#   8- course:              0-360.00 [°]
#   9- fix_mode:            ?
#   10- ?:                  reserved
#   11- hdop:               0-99.9 [Horizontal Dilution of Precision]
#   12- pdop:               0-99.9 [Position Dilution of Precision]
#   13- vdop:               0-99.9 [Vertical Dilution of Precision]
#   14- ?:                  reserved
#   15- gps_sat_in_view:    0-99
#   16- gnss_used_sat:      0-99
#   17- glonass_used_sat:   0-99
#   18- ?:                  reserved
#   19- c/n0_max:           0-55 [dBHz]
#   20- hpa:                0-9999.9 [m]     
#   21- vpa:                0-9999.9 [m]
#
####################################################################################################################

def cgnsinf_parser(cgnsinf):

    scan_fields = cgnsinf.split(",")
    output = []
    output.append(int(scan_fields[0]))          # run_status
    if output[0]==1:
        output.append(int(scan_fields[1]))      # fix_status
        if output[1]==1:
            output.append(str(support.gps_date_to_timestamp(scan_fields[2])))  # utc
            output.append(str(scan_fields[3]))  # latitude
            output.append(str(scan_fields[4]))  # longitude
            output.append(str(scan_fields[5]))  # altitude
            output.append(str(scan_fields[6]))  # speed
            output.append(str(scan_fields[7]))  # course
            output.append(str(scan_fields[8]))  # fix_mode

    ############################################# OUTPUT FORMAT ####################################################
    #   run_status, fix_status, utc, latitude, longitude, altitude, speed, course, fix_mode                        # 
    ################################################################################################################

    return output