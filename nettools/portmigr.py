import csv
import os

import sys
import getpass
import getopt
import re
import json
from time import sleep
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException
from paramiko.ssh_exception import SSHException

import cscofunc

file_name = "developtests/Ports.csv"
# switch_ip = {"de-aah-ant-saa":"10.232.10.53","de-aah-ant-sab":"10.232.10.54","de-aah-ant-sac":"10.232.10.57","de-aah-ant-sad":"10.232.10.58","de-aah-ant-sag":"10.232.10.35","de-aah-ant-sah":"10.232.10.36","de-aah-ant-sai":"10.232.10.37","de-aah-ant-saj":"10.232.10.38","de-aah-ant-sak":"10.232.10.43","de-aah-ant-sal":"10.232.10.44","de-aah-ant-sam":"10.232.10.47","de-aah-ant-san":"10.232.10.48","de-aah-ant-sao":"10.232.10.6","de-aah-ant-sap":"10.232.10.18","de-aah-ant-sat":"10.232.10.7","de-aah-ant-sau":"10.232.10.11","de-aah-ant-saw":"10.232.10.12","de-aah-ant-say":"10.232.10.13","de-aah-ant-sbc":"10.232.10.39","de-aah-ant-sbd":"10.232.10.40","de-aah-ant-sbe":"10.232.10.41","de-aah-ant-sbf":"10.232.10.42","de-aah-ant-sbg":"10.232.10.45","de-aah-ant-sbh":"10.232.10.46","de-aah-ant-sbi":"10.232.10.49","de-aah-ant-sbj":"10.232.10.50","de-aah-ant-sbk":"10.232.10.9","de-aah-ant-sbl":"10.232.10.20","de-aah-ant-sbn":"10.232.10.51","de-aah-ant-sbp":"10.232.10.52","de-aah-ant-sbs":"10.232.10.16","de-aah-ant-sbx":"10.232.10.62","de-aah-ant-sbz":"10.232.10.63","de-aah-ant-sca":"10.232.10.17","de-aah-ant-dc-s031-1":"10.178.156.7","de-aah-ant-dc-s031-2":"10.178.156.8","de-aah-ant-dc-s032-1":"10.178.156.9","de-aah-ant-dc-s032-2":"10.178.156.10","de-aah-ant-dc-s033-1":"10.178.156.11","de-aah-ant-dc-s033-2":"10.178.156.12","de-aah-ant-dc-s034-1":"10.178.156.15","de-aah-ant-dc-s034-2":"10.178.156.16","de-aah-ant-dc-s035-1":"10.178.156.13","de-aah-ant-dc-s035-2":"10.178.156.14","de-aah-ant-dc-s038-1":"10.178.156.19","de-aah-ant-dc-s038-2":"10.178.156.20","de-aah-ant-dc-s039-1":"10.178.156.49","de-aah-ant-dc-s039-2":"10.178.156.59","de-aah-ant-dc-s048-1":"10.178.156.95","de-aah-ant-dc-s048-2":"10.178.156.96","de-aah-ant-dc-s050-1":"10.178.156.103","de-aah-ant-dc-s050-2":"10.178.156.104","de-aah-ant-dc-s054-1":"10.178.156.97","de-aah-ant-dc-s054-2":"10.178.156.98","de-aah-ant-dc-s056-1":"10.178.156.99","de-aah-ant-dc-s056-2":"10.178.156.100"}
switch_ip = {"de-c6506_hra_vss":"10.106.0.169", "de-aah-ant-saa":"10.232.10.53","de-aah-ant-sab":"10.232.10.54","de-aah-ant-sac":"10.232.10.57","de-aah-ant-sad":"10.232.10.58","de-aah-ant-sag":"10.232.10.35","de-aah-ant-sah":"10.232.10.36","de-aah-ant-sai":"10.232.10.37","de-aah-ant-saj":"10.232.10.38","de-aah-ant-sak":"10.232.10.43","de-aah-ant-sal":"10.232.10.44","de-aah-ant-sam":"10.232.10.47","de-aah-ant-san":"10.232.10.48","de-aah-ant-sao":"10.232.10.6","de-aah-ant-sap":"10.232.10.18","de-aah-ant-sat":"10.232.10.7","de-aah-ant-sau":"10.232.10.11","de-aah-ant-saw":"10.232.10.12","de-aah-ant-say":"10.232.10.13","de-aah-ant-sbc":"10.232.10.39","de-aah-ant-sbd":"10.232.10.40","de-aah-ant-sbe":"10.232.10.41","de-aah-ant-sbf":"10.232.10.42","de-aah-ant-sbg":"10.232.10.45","de-aah-ant-sbh":"10.232.10.46","de-aah-ant-sbi":"10.232.10.49","de-aah-ant-sbj":"10.232.10.50","de-aah-ant-sbk":"10.232.10.9","de-aah-ant-sbl":"10.232.10.20","de-aah-ant-sbn":"10.232.10.51","de-aah-ant-sbp":"10.232.10.52","de-aah-ant-sbs":"10.232.10.16","de-aah-ant-sbx":"10.232.10.62","de-aah-ant-sbz":"10.232.10.63","de-aah-ant-sca":"10.232.10.17","de-aah-ant-dc-s031-1":"10.178.156.7","de-aah-ant-dc-s031-2":"10.178.156.8","de-aah-ant-dc-s032-1":"10.178.156.9","de-aah-ant-dc-s032-2":"10.178.156.10","de-aah-ant-dc-s033-1":"10.178.156.11","de-aah-ant-dc-s033-2":"10.178.156.12","de-aah-ant-dc-s034-1":"10.178.156.15","de-aah-ant-dc-s034-2":"10.178.156.16","de-aah-ant-dc-s035-1":"10.178.156.13","de-aah-ant-dc-s035-2":"10.178.156.14","de-aah-ant-dc-s038-1":"10.178.156.19","de-aah-ant-dc-s038-2":"10.178.156.20","de-aah-ant-dc-s039-1":"10.178.156.49","de-aah-ant-dc-s039-2":"10.178.156.59","de-aah-ant-dc-s048-1":"10.178.156.95","de-aah-ant-dc-s048-2":"10.178.156.96","de-aah-ant-dc-s050-1":"10.178.156.103","de-aah-ant-dc-s050-2":"10.178.156.104","de-aah-ant-dc-s054-1":"10.178.156.97","de-aah-ant-dc-s054-2":"10.178.156.98","de-aah-ant-dc-s056-1":"10.178.156.99","de-aah-ant-dc-s056-2":"10.178.156.100"}

output_file = "developtests/Output.csv"


def int_number_to_name(sh_int_des_output, number):
    '''
    Transforms interface number to valid name, i.e 1/3/4 to Te1/3/4 by parsing output of 'sh interface description'
    '''

    intstr = re.search(r"\n([A-Za-z]+" + re.escape(number) + r")\s", sh_int_des_output)
    if intstr:
        fullname = cscofunc.conv_int_to_interface_name(intstr.group(1)) # Gi -> GigabitEthernet ,..
        return fullname
    return "Error"
def cli_open_session(ip, username, pswd):
    '''
    Open SSH session to IP address
    If session is not established, nothing is returned. Function which called this function must check it !!
    '''
    try:
        net_connect = ConnectHandler(device_type='cisco_ios', ip=ip, username=username, password=pswd)
    except NetMikoTimeoutException:
        print("- unable to connect to the device, timeout")
        return
        # sys.exit(2)
    except (EOFError, SSHException):
        print("- unable to connect to the device, error")
        return
        # sys.exit(2)

    return net_connect

def add_items_to_port_list(portlist, username, pswd):
    '''
    Reads needed items from target switch (ssh connection) and add it to dictionary
    Input:
        portlist - list of dictionaries
        username, pswd - credentials for ssh login
    Output:
        potrlist - list of dictionaries with new kews added to the dictionary
    '''
    switch_port_dict = {}       # dictionary where key is switch IP and value is dictionary of interface porameters of switches
    sh_int_desc_dict = {}       # dictionary where key is IP of the switch and value is 'sh interface desc'
    for item in portlist:       # process all items in list
        if item['error'] != None:
            continue                # if there is already error in this item don't process it
        ip_of_switch = item['ip_old_sw']    # ip of switch we are going to collect informations from
        print("\nProcessing device:", ip_of_switch)

        if ip_of_switch not in sh_int_desc_dict.keys(): # do we have alredy needed entry for this switch<
            net_connect = cli_open_session(ip_of_switch, username, pswd)    # connect to switch
            if not net_connect:         # unable to connect
                if item['error'] == None:
                    item['error'] = []
                item['error'].append("Unable to connect")       # add error enrty into list
                continue        # process next item
            cli_param = "sh interface description"
            sh_int_desc_dict[ip_of_switch] = net_connect.send_command(cli_param)       
            if ip_of_switch not in switch_port_dict.keys():
                switch_port_dict[ip_of_switch] = cscofunc.get_cli_sh_int_switchport_dict(net_connect)
            net_connect.disconnect()        # disconnect from the switch
        full_int_name = int_number_to_name(sh_int_desc_dict[ip_of_switch], item['port_old'])    # 1/3/4 -> GigabitEthernet1/3/4
        if full_int_name == 'Error':
            if item['error'] == None:
                item['error'] = []
            item['error'].append("Unable to transform interface name")       # add error enrty into list    
            continue        # process next item
        item['port_old'] = full_int_name
        if ip_of_switch not in switch_port_dict.keys():
            switch_port_dict[ip_of_switch] = cscofunc.get_cli_sh_int_switchport_dict(net_connect)
        iface = item['port_old']
        item['sw_mode'] = switch_port_dict[ip_of_switch][iface]['oper_mode']            # add new entries for switch which is being processeed
        item['vlan_list'] = switch_port_dict[ip_of_switch][iface]['trunk_vlans']
        item['native_vlan'] = switch_port_dict[ip_of_switch][iface]['trunk_native_mode_vlan']
        item['port_ch_old'] = switch_port_dict[ip_of_switch][iface]['bundle_member']


    return portlist         # return list


def lines_from_csv_to_list(source_file):
    if os.path.isfile(source_file) == True and os.stat(source_file).st_size != 0:
        with open(source_file,'r') as file:
            reader = csv.reader(file)
            temp_list = list(reader)
        return temp_list
    else:
        return -1
    file.close

def list_to_list_of_dict(source_list):
    new_list = []
    for element in source_list:
        dict_temp = {"error":None,"warning":None}
# Ignore Header of csv. file
        if element[0].lower().startswith('swi'):
            None
# Ignore empty lines
        elif element[0] == '':
            None
        else:
            dict_temp["sw_old"] = element[0]
# Conversion of switchname to IP address
            if element[0].lower().startswith('de'):
                dict_temp["ip_old_sw"] = switch_ip[element[0].lower()]
            else:
                if dict_temp["error"] != None:
                    dict_temp["error"].append(element[0] + ' is not a valid switchname')
                else:
                    dict_temp["error"] = [element[0] + ' is not a valid switchname']
            dict_temp["port_old"] = element[1]
            dict_temp["sw_new"] = element [2]
# Conversion of switchname to IP address including some input validation
            if element[2].lower().startswith('de'):
#                print ("starts with de")
                if element[2].lower().endswith('-1') or element[2].lower().endswith('-2'):
#                    print ("ends with -1 or -2")
                    dict_temp["ip_new_sw"] = switch_ip[element[2].lower()]
                else:
#                    print ("does not end with -1 or -2")
                    dict_temp["ip_new_sw"] = switch_ip[element[2].lower()+'-1']
            else:
                if dict_temp["error"] != None:
                    dict_temp["error"].append(element[2]+' is not a valid switchname')
                else:
                    dict_temp["error"] = [element[2]+' is not a valid switchname']
            dict_temp["port_new"] = element[3]
#            print (dict_temp)
            new_list.append(dict_temp)

    return new_list

'''
def list_to_csv(source_list):
    target_file = open(output_file, 'w')
    output = source_list[0].keys()
    output_line = ""
        for value in output:
            output_line += value+','
        target_file.write(output+'\n')
    for line in source_list:
        target_file.write(str(list(line.values()))+'\n')
    target_file.close()
'''

def main():

    username = ''
    pswd = ''
    
    argv = sys.argv[1:]

    try:
        opts, args = getopt.getopt(argv, "hp:u:", [ "help" "password=", "username="])
    except getopt.GetoptError:
        print(usage_str)
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print(usage_str)
            sys.exit()

        elif opt in ("-u", "--username"):
            username = arg
        elif opt in ("-p", "--password"):
            pswd = arg


    # sanity checks
    if not username:
        print("Username is not specified")
        sys.exit(2)


    if pswd == '':
        pswd = getpass.getpass('Password:')



    list_from_file = lines_from_csv_to_list(file_name)
    list_of_dict = list_to_list_of_dict(list_from_file)
#    list_to_csv(list_of_dict)
    list_of_dict_new = add_items_to_port_list(list_of_dict, username, pswd)
    print (list_of_dict)
    json_output = json.dumps(list_of_dict_new, separators=(',', ':'), indent=4)
    print(json_output)

if __name__ == '__main__':
    main()
    

