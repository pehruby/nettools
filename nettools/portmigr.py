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

file_name = "developtests/Ports1.csv"
file_name_sip = "developtests/switch_ip.csv"
file_name_nxos = "developtests/nxos.csv"


output_file = "developtests/Output.csv"

switch_ip = []
nxos_switch = []

def func_convert_list(source_list):
    '''
    The function creates a list of list in which the inner list has always to entries.
    '''
    new_dict = {}
    for element in source_list:
        new_dict.update({element[0]: element[1]})

    return new_dict


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
    switch_port_dict = {}       # dictionary where key is switch IP and value is dictionary of interface switchport parameters 
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
                if 'vpc_id' in item:    # test if it is NX-OS
                    switch_port_dict[ip_of_switch] = cscofunc.get_cli_sh_int_switchport_dict_nxos(net_connect)
                    pc_summ = cscofunc.get_cli_sh_etherchannel_summary_nxos(net_connect)
                else:
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
        if 'vpc_id' in item:    # test if it is NX-OS
            pcnr = get_nxos_pc_port_number(item['port_old'], pc_summ)
            if pcnr != '0':
                item['port_ch_old'] = pcnr
            else:
                item['error'].append('port_ch_old number not found')
        else:       # IOS
            po_name = switch_port_dict[ip_of_switch][iface]['bundle_member'] # portchannel name (with Po in name)
            pcnr = po_name.replace('Po','')
            item['port_ch_old'] = pcnr


    return portlist         # return list

def get_nxos_pc_port_number(iface, pc_list):
    '''
    Returns portchannel number which is iface member of
    '''
    for item in pc_list:
        if iface in item['int_list']:            # is interface member of port-channel pcnum? 
            return item['pc_number']        # return port-channel number
    return '0'            # otherwise return 0

def func_lines_from_csv_to_list(source_file):
# Reads the source file (defined in variable 'file_name' in to a list
    if os.path.isfile(source_file) == True and os.stat(source_file).st_size != 0:
        with open(source_file,'r') as file:
            reader = csv.reader(file)
            temp_list = list(reader)
        return temp_list
    else:
        return -1
    file.close

def func_new_list_from_list(source_list):
    '''
    The function creates a list of dictionaries from a list.
    The Keys in each dictionary are 'sw1_name','sw2_name' and 'vpc_id'
    '''
    new_list = []
    for element in source_list:
        temp_dict = {'sw1_name': element[0], 'sw2_name': element[1], 'vpc_id': int(element[2])}
        #        print (temp_dict)
        new_list.append(temp_dict)
        #    print (new_list)

    return new_list

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
            dict_temp["sw_old"] = element[0].lower()
# Conversion of switchname to IP address
            if dict_temp["sw_old"].startswith('de'):
                dict_temp["ip_old_sw"] = switch_ip[dict_temp["sw_old"]]
# if the old switch is a nexus switch the pair_switch name and ip address and the vpc-id are added to the dictionary
                for switch in nxos_switch:
                    if switch['sw1_name'] == dict_temp["sw_old"]:
                        dict_temp['vpc_id'] = switch['vpc_id']
                        dict_temp['sw_pair'] = switch['sw2_name']
                        dict_temp['ip_pair_sw'] = switch_ip[switch['sw2_name']]
                    elif switch['sw2_name'] == dict_temp["sw_old"]:
                        dict_temp['vpc_id'] = switch['vpc_id']
                        dict_temp['sw_pair'] = switch['sw1_name']
                        dict_temp['ip_pair_sw'] = switch_ip[switch['sw1_name']]
            else:
                if dict_temp["error"] != None:
                    dict_temp["error"].append(element[0] + ' is not a valid switchname')
                else:
                    dict_temp["error"] = [element[0] + ' is not a valid switchname']
            dict_temp["port_old"] = element[1]
            dict_temp["sw_new"] = element[2].lower()
# Conversion of switchname to IP address including some input validation
            if dict_temp["sw_new"].startswith('de'):
#                print ("starts with de")
                if dict_temp["sw_new"].endswith('-1') or dict_temp["sw_new"].endswith('-2'):
#                    print ("ends with -1 or -2")
                    dict_temp["ip_new_sw"] = switch_ip[dict_temp["sw_new"]]
                else:
#                    print ("does not end with -1 or -2")
                    dict_temp["ip_new_sw"] = switch_ip[dict_temp["sw_new"]+'-1']
            else:
                if dict_temp["error"] != None:
                    dict_temp["error"].append(element[2]+' is not a valid switchname')
                else:
                    dict_temp["error"] = [element[2]+' is not a valid switchname']
            dict_temp["port_new"] = element[3]
#            print ('Dictionary des Eintrags'+str(dict_temp))
            new_list.append(dict_temp)

    return new_list



def func_list_of_port_ch(devices,source_list,typ):
    '''
    The function return a list of dictionaries
    Each dictionary has two keys 'name' as a string which is either the vpc_id(nxos) or the switch name (ios)and 'pc_list' 
    which is a list of all interessting port-channelfor the vpc(nxos) or switch(ios)
    '''
#    print (devices)
    new_list = []
    for device in devices:
        temp_list = []
        for line in source_list:
            if line['error'] != None:
                None
            else:
                if typ in line.keys():
                    if line[typ] == device:
                        if 'port_ch_old' in line.keys():
                            if line['port_ch_old'] not in temp_list:
                                temp_list.append(line['port_ch_old'])
                        else:
#                            print('no port-channel')
                            None
        if typ is 'vpc_id':
            temp_dict = {'vpc_id':device,'pc_list':temp_list}
        else:
            temp_dict = {'name':device,'pc_list':temp_list}
#        print (temp_dict)
        new_list.append(temp_dict)

#    print (new_list)
    return new_list



def func_port_ch_switch(source_list):
    '''
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
#    print (list_of_nxos_vpcs)
#    print (list_of_ios_switches)
    list_of_port_channels = func_list_of_port_ch(list_of_nxos_vpcs,source_list,'vpc_id')
    new_list = []
    new_list.append(list_of_port_channels)
    list_of_port_channels = func_list_of_port_ch(list_of_ios_switches,source_list,'sw_old')
    new_list.append(list_of_port_channels)
#    print (new_list)

    return new_list

def func_port_ch_switch2(source_list):
    '''
    (Petr) func_port_ch_switch2 creates just one list, I hope this is acceptable ...

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
#    print (list_of_nxos_vpcs)
#    print (list_of_ios_switches)
    # list_of_port_channels = func_list_of_port_ch(list_of_nxos_vpcs,source_list,'vpc_id')
    # new_list = []
    # new_list.append(list_of_port_channels)
    # list_of_port_channels = func_list_of_port_ch(list_of_ios_switches,source_list,'sw_old')
    # new_list.append(list_of_port_channels)
#    print (new_list)
    new_list = []
    list_of_port_channels = func_list_of_port_ch(list_of_nxos_vpcs,source_list,'vpc_id')
    for item in list_of_port_channels:
        new_list.append(item)
    list_of_port_channels = func_list_of_port_ch(list_of_ios_switches,source_list,'sw_old')
    for item in list_of_port_channels:
        new_list.append(item)


    return new_list

def func_list_to_file(source_list):
    '''
    The function creates a output file in csv format which contains the values for all keys in the variable key for each dictionary from the list of dictionaries 'source_list'
    '''
    keys = ('sw_old','port_old','ip_old_sw','port_ch_old','sw_new','port_new','ip_new_sw','port_ch_new','error','warning')
    target_file = open(output_file, 'w')
    target_file.write('sw_old;port_old;ip_old_sw;port_ch_old;sw_new;port_new;ip_new_sw;port_ch_new;error;warning\n')
    for line in source_list:
        for key in keys:
            if key in line.keys():
                target_file.write(str(line[key])+';')
            else:
                target_file.write(';')
        target_file.write ('\n')
    target_file.close()

def convert_pc_list_to_dict(pc_list):
    '''
    Converts list of portchannels into dictionary
    key is PC name (i.e Po33)
    value is list of interfaces
    '''
    new_dict = {}
    for item in pc_list:
        new_dict['Po'+item['pc_number']] = item['int_list']
    return new_dict

def func_create_dict_with_pc_ports(big_list, dev_pc_list, username, password):
    '''
    Creates list of dictionaries. Each dictionary contains following keys:
    sw_old - name of the swich
    port_ch_old - name of portchannel (ie. Po33)
    ports - list of ports in port_ch_old
    sw_old2 - (NXOS only)
    ports2 - (NXOS only)
    '''
    list_of_dict = []
    for item in dev_pc_list:
        if 'name' in item.keys():      # it is IOS device
            device_ip = switch_ip[item['name']] #get IP of item
            net_connect = cli_open_session(device_ip, username, password)   # connect to device
            list_of_device_pc = cscofunc.get_cli_sh_etherchannel_summary(net_connect)
            dict_of_device_pc = convert_pc_list_to_dict(list_of_device_pc)
            for pc in item['pc_list']:
                new_dict = {}
                new_dict['sw_old'] = item['name']
                new_dict['port_ch_old'] = pc
                new_dict['ports'] = dict_of_device_pc['Po'+pc]
                list_of_dict.append(new_dict)
            net_connect.disconnect()
        if 'vpc_id' in item.keys():       # NXOS device
            (sw_old1, sw_old2) = get_switchnames_for_vpcid(item['vpc_id'])
            device_ip = switch_ip[sw_old1] #get IP of first device
            net_connect = cli_open_session(device_ip, username, password)   # connect to device
            list_of_device_pc = cscofunc.get_cli_sh_etherchannel_summary_nxos(net_connect)
            dict_of_device_pc = convert_pc_list_to_dict(list_of_device_pc)
            for pc in item['pc_list']:  # hopefuly just one entry ...
                new_dict = {}
                new_dict['sw_old'] = sw_old1
                new_dict['port_ch_old'] = pc        
                new_dict['ports'] = dict_of_device_pc['Po'+pc]
            net_connect.disconnect() 
            device_ip = switch_ip[sw_old2] #get IP of second device
            net_connect = cli_open_session(device_ip, username, password)   # connect to device
            list_of_device_pc = cscofunc.get_cli_sh_etherchannel_summary_nxos(net_connect)
            dict_of_device_pc = convert_pc_list_to_dict(list_of_device_pc)
            for pc in item['pc_list']:  # hopefuly just one entry ...
                new_dict['sw_old2'] = sw_old2
                new_dict['port_ch_old'] = pc
                new_dict['ports2'] = dict_of_device_pc['Po'+pc]
            list_of_dict.append(new_dict)
            net_connect.disconnect()
    return list_of_dict

def get_switchnames_for_vpcid(vpcid):
    '''
    Get davices which has vpcid configured
    '''
    for item in nxos_switch:
        if item['vpc_id'] == vpcid:
            return (item['sw1_name'], item['sw2_name'])   # Return names of two switches
    return ('','')          # Error, devices were not found

def func_list_to_file(source_list):
    '''
    The function creates a output file in csv format which contains the values for all keys in the variable key for each dictionary from the list of dictionaries 'source_list'
    '''
    keys = ('sw_old','port_old','ip_old_sw','port_ch_old','sw_new','port_new','ip_new_sw','port_ch_new','error','warning')
    target_file = open(output_file, 'w')
    target_file.write('sw_old;port_old;ip_old_sw;port_ch_old;sw_new;port_new;ip_new_sw;port_ch_new;error;warning\n')
    for line in source_list:
        for key in keys:
            if key in line.keys():
                target_file.write(str(line[key])+';')
            else:
                target_file.write(';')
        target_file.write ('\n')
    target_file.close()


def func_change_mapped_vlans(list_from_file):
    '''
    This function changes vlans in the the keys 'vlans' and 'native_vlan' in the globalvariable list_from_file if they are in the list of dictionaries that contains all vlan_mappings
    If a change is done there will be an entry in vlans_trans and in warning 
    '''
    mapping_list = [{'old_vlan': 400, 'new_vlan': 500}, {'old_vlan': 405, 'new_vlan': 505}]

    for element in list_from_file:
        if element['error'] == None:
            index = 0
            for vlan in element['vlan_list']:
                for item in mapping_list:
                    if vlan == item['old_vlan']:
                        element['vlan_list'][index] = item['new_vlan']
                        if element['warning'] == None:
                            element['warning'] == [str(vlan) + ' is a mapped vlan']
                        else:
                            element['error'].append(str(vlan) + ' is a mapped vlan')
                        if 'vlans_trans' in element.keys():
                            element['vlans_trans'].append(item)
                        else:
                            element['vlans_trans'] = [item]
                index += 1
            if element['sw_mode'] == 'trunk':
                for item in mapping_list:
                    if element['native_vlan'] == item['old_vlan']:
                        if element['warning'] == None:
                            element['warning'] = ['The native VLAN is a mapped vlan']
                        else:
                            element['error'].append('The native VLAN is a mapped vlan')
#                        print('Change ' + str(element['native_vlan']) + ' against ' + str(item['new_vlan']))
                        element['native_vlan'] = item['new_vlan']
    return list_from_file

def get_vlan_list_of_switch(device_ip, username, password):
    '''
    Returns list of VLans configured on switch 'device_ip'
    '''
    vlan_list = []
    net_connect = cli_open_session(device_ip, username, password)   # connect to device
    vlan_dict = cscofunc.get_cli_sh_vlan(net_connect)
    for item in vlan_dict:          # go through all vlan entries
        vlan_list.append(item['number'])    # add vlan number to target list
    net_connect.disconnect()
    return vlan_list


def func_vlans_in_fabricpath(list_from_file, username, pswd):
    '''
    This function checks if all vlans from the variabl list_from_file are in a variable vlan_list
    If not the function will fill the key error
    '''
    for element in list_from_file:
        if element['error'] == None:
            vlan_list = get_vlan_list_of_switch(element['ip_old_sw'], username, pswd) # HERE MUST BE NEW SWITCH, JUST TEST
            for vlan in element['vlan_list']:
                if vlan not in vlan_list:
                    if element['error'] == None:
                        element['error'] == [str(vlan)+' is not on the new switch']
                    else:
                        element['error'].append(str(vlan)+' is not on the new switch')
            if element['sw_mode'] == 'trunk':
                if element['native_vlan'] not in vlan_list:
                    if element['error'] == None:
                        element['error'] == [str(element['native_vlan']) + ' is not on the new switch']
                    else:
                        element['error'].append(str(element['native_vlan']) + ' is not on the new switch')

    return list_from_file

def func_ports_in_list(sw_name,port_list,list_from_file):
    '''
    the function checks if all the ports in the port_list of the switch with the name sw_name are in the input file
    :param sw_name: 
    :param port_list: 
    :return: 
    '''
    all_in = True
    for port in port_list:
        found = False
#        print ('new port '+str(port))
        for element in list_from_file:
            if element['sw_old'] == sw_name and element['port_old'] == port:
#                print ('Port found')
                found = True
        if found == False:
            all_in = False

    return all_in

def func_po_ch_all_in(source_list,list_from_file):
    '''
    This function checks with the help of a sub function (func_ports_in_list) if all ports belonging to a port-channel are in the input file
    :param source_list: 
    :return: 
    '''
    for item in source_list:
        all_in = func_ports_in_list(item['sw_old'],item['ports'],list_from_file)
        if 'sw_old2' in item.keys():
            all_in2 = func_ports_in_list(item['sw_old2'],item['ports2'],list_from_file)
            all_in = all_in and all_in2
        item['all_in'] = all_in

    return source_list

def func_find_ports_of_pc(sw_name,port_list,list_from_file):
    '''
    The function searches in the global variable list_from_file for all ports from the portlist on a switch and writes a warning massage in 
    :param sw_name: 
    :param port_list: 
    :return: 
    '''

    for port in port_list:
        for element in list_from_file:
            if element['sw_old'] == sw_name and element['port_old'] == port:
                if element['error'] == None:
                    element['error'] = ['not all ports of port-channel in list']
                else:
                    element['error'].append('not all ports of port-channel in list')

    return list_from_file

def func_write_po_error(source_list,list_from_file):
    '''
    The function searches for incomplete port-channels and if it finds one forwards the information of the switchname(s) and the associated port_list to the function func_find_ports_of_pc
    :param source_list: 
    :return: 
    '''
    for item in source_list:
        if item['all_in'] == False:
            list_from_file = func_find_ports_of_pc(item['sw_old'], item['ports'],list_from_file)
            if 'ports2' in item.keys():
                list_from_file = func_find_ports_of_pc(item['sw_old2'], item['ports2'],list_from_file)

    return list_from_file

def main():

    username = ''
    pswd = ''
    global switch_ip
    global nxos_switch

    usage_str = '''
    Usage: portmigr.py [OPTIONS]
    -h,     --help                      display help
    -u,     --username                  username
    -p,     --password                  password, optional
    '''
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



    list_from_file = func_lines_from_csv_to_list(file_name_sip)
    switch_ip = func_convert_list(list_from_file)
#    print(switch_ip)
    list_from_file = func_lines_from_csv_to_list(file_name_nxos)
    nxos_switch = func_new_list_from_list(list_from_file)
#    print(nxos_switch)
    list_from_file = func_lines_from_csv_to_list(file_name)
    list_from_file = func_list_to_list_of_dict(list_from_file)
    list_from_file = add_items_to_port_list(list_from_file, username, pswd)
    list_of_po = func_port_ch_switch2(list_from_file)
    list_of_po_ports = func_create_dict_with_pc_ports(list_from_file, list_of_po, username, pswd)
    list_of_po_ports = func_po_ch_all_in(list_of_po_ports,list_from_file)
    list_from_file = func_write_po_error(list_of_po_ports,list_from_file)
    list_from_file = func_change_mapped_vlans(list_from_file)
    list_from_file = func_vlans_in_fabricpath(list_from_file, username, pswd)
    func_list_to_file(list_from_file)


   
#    list_to_csv(list_of_dict)
#    list_of_dict_new = add_items_to_port_list(list_of_po, username, pswd)
    #print (list_of_dict_new)
    #json_output = json.dumps(list_of_dict_new, separators=(',', ':'), indent=4)
    #print(json_output)

if __name__ == '__main__':
    main()
    

