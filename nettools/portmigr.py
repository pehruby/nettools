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

switch_ip = {"name":"1.2.3.4", "name2":"2.3.4.5"}

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


# Reads the source file (defined in variable 'file_name' in to a list
def func_lines_from_csv_to_list(source_file):
    if os.path.isfile(source_file) == True and os.stat(source_file).st_size != 0:
        with open(source_file,'r') as file:
            reader = csv.reader(file)
            temp_list = list(reader)
        return temp_list
    else:
        return -1
    file.close


def func_list_to_list_of_dict(source_list):
    '''
    Converts the list in a list of dictionaries with the follwing keys:
    reads the values for the keys sw_old, port_old, sw_new, port_new
    gets the following mandatory keys from the list switch_ip:
    ip_old_sw, ip_new_sw
    gets the following optional keys from the list nxos_switch if the old switch is a Nexus switch:
    vpc_id, sw_pair, ip_pair_sw
    '''
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
# if the old switch is a nexus switch the pair_switch name and ip address and the vpc-id are added to the dictionary
                for switch in nxos_switch:
                    if switch['sw1_name'] == element[0].lower():
                        dict_temp['vpc_id'] = switch['vpc_id']
                        dict_temp['sw_pair'] = switch['sw2_name']
                        dict_temp['ip_pair_sw'] = switch_ip[switch['sw2_name']]
                    elif switch['sw2_name'] == element[0].lower():
                        dict_temp['vpc_id'] = switch['vpc_id']
                        dict_temp['sw_pair'] = switch['sw1_name']
                        dict_temp['ip_pair_sw'] = switch_ip[switch['sw1_name']]
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
            print ('Dictionary des Eintrags'+str(dict_temp))
            new_list.append(dict_temp)

    return new_list

''''
The function return a list of dictionaries
Each dictionary has two keys 'name' as a string which is either the vpc_id(nxos) or the switch name (ios)and 'pc_list' 
which is a list of all interessting port-channelfor the vpc(nxos) or switch(ios)
'''
def func_list_of_port_ch(devices,source_list,typ):
    new_list = []
    for device in devices:
        temp_list = []
        for line in source_list:
            if 'error' in line.keys() and line['error'] != None:
                None
            else:
                if line[typ] == device:
                    if line['port_ch_old'] not in temp_list:
                        new_list.append(line['port_ch_old'])
        temp_dict['name':device,'pc_list':new_list]
        print (temp_dict)
        new_list.append(temp_dict)

    print (new_list)
    return new_list

def func_port_ch_switch(source_list):
    ''''
    The function return a list containing two lists of dictionaries the first list for all IOS switches and the second for all NXOS switches.
    In the ios list is an entry for each switch and all interessting port-channel of the switch
    In the nxos list is an entry for each vpc_id and all interessting port-channel of the vpc
    '''
    list_of_nxos_vpcs = []
    list_of_ios_switches = []
    for element in source_list:
        if 'error' in element.keys() and element['error']!= None:
            None
        else:
            if 'vpc_id' in element.keys():
                if element['vpc_id'] not in list_of_nxos_vpcs:
                    list_of_nxos_vpcs.append(element['vpc_id'])
            else:
                if element['sw_old'] not in list_of_ios_switches:
                    list_of_ios_switches.append(element['sw_old'])
    print (list_of_nxos_vpcs)
    print (list_of_ios_switches)
    list_of_port_channels = func_list_of_port_ch(list_of_nxos_vpcs,source_list,'vpc_id')
    new_list = []
    new_list.append(list_of_port_channels)
    list_of_port_channels = func_list_of_port_ch(list_of_ios_switches,source_list,'sw_old')
    new_list.append(list_of_port_channels)
    print (new_list)

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




    list_from_file = func_lines_from_csv_to_list(file_name)
    list_from_file = func_list_to_list_of_dict(list_from_file)
    list_of_po = func_port_ch_switch(list_from_file)
#    list_to_csv(list_of_dict)
    list_of_dict_new = add_items_to_port_list(list_of_po, username, pswd)
    print (list_of_dict)
    json_output = json.dumps(list_of_dict_new, separators=(',', ':'), indent=4)
    print(json_output)

if __name__ == '__main__':
    main()
    

