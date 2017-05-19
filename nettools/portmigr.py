import csv
import os

import sys
import getpass
import getopt
import re
import yaml
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException
from paramiko.ssh_exception import SSHException

import cscofunc

#file_name = "developtests/Ports.csv"
#file_name_sip = "developtests/switch_ip.csv"
#file_name_nxos = "developtests/nxos.csv"
#file_name_old_new = 'developtests/sw_old_new.csv'


#output_file = "developtests/Output.csv"

switch_ip = []
nxos_switch = []

def func_convert_list(source_list):
    '''
    The function creates a list of list in which the inner list has always to entries.
    :param source_list: 
    :return: 
    Version: 1.0
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

def func_add_items_to_port_list(portlist, username, pswd):
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
                item['noerror'] = False
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
            item['noerror'] = False
            continue        # process next item
        item['port_old'] = full_int_name
        if ip_of_switch not in switch_port_dict.keys():
            switch_port_dict[ip_of_switch] = cscofunc.get_cli_sh_int_switchport_dict(net_connect)
        iface = item['port_old']
        item['sw_mode'] = switch_port_dict[ip_of_switch][iface]['oper_mode']            # add new entries for switch which is being processeed
        if item['sw_mode'] == 'down':
            if item['error'] == None:
                item['error'] = []
            item['error'].append("Port down")       # add error enrty into list
            item['noerror'] = False
            continue        # process next item
        if item['sw_mode'] == 'access' or item['sw_mode'] == 'static access': # port is access, add access vlan into vlan list
            item['vlan_list'] = []
            item['vlan_list'].append(switch_port_dict[ip_of_switch][iface]['access_mode_vlan'])
        else:       # port is trunk, add trunk vlan list
            item['vlan_list'] = switch_port_dict[ip_of_switch][iface]['trunk_vlans']
        item['native_vlan'] = switch_port_dict[ip_of_switch][iface]['trunk_native_mode_vlan']
        if 'vpc_id' in item:    # test if it is NX-OS
            pcnr = get_nxos_pc_port_number(item['port_old'], pc_summ)
            if pcnr != '0':
                item['port_ch_old'] = pcnr
            else:
                item['error'].append('port_ch_old number not found')
                item['noerror'] = False
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
    '''
    Reads the source file (defined in variable 'file_name' in to a list
    :param source_file: 
    :return:
    Version: 1.0
    '''
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
    :param source_list: 
    :return: 
    Version: 1.0
    '''
    
    new_list = []
    for element in source_list:
        temp_dict = {'sw1_name': element[0], 'sw2_name': element[1], 'vpc_id': int(element[2])}
        #        print (temp_dict)
        new_list.append(temp_dict)
        #    print (new_list)

    return new_list

def func_convert_list_to_dict(source_list):
    '''
    The function creates a list of list in which the inner list has always to entries.
    :param source_list: 
    :return new_dict: 
    Version: 1.1
    '''

    new_dict = {}
    for element in source_list:
        new_dict.update({element[0]: element[1]})
    return new_dict

def func_list_to_list_of_dict(source_list, switch_dict, username, password):
    '''
    Converts the list in a list of dictionaries with the follwing keys:
    reads the values for the keys sw_old, port_old, sw_new, port_new
    gets the following mandatory keys from the list switch_ip: ip_old_sw, ip_new_sw
    gets the following optional keys from the list nxos_switch if the old switch is a Nexus switch: vpc_id, sw_pair, ip_pair_sw
    :param source_list: 
    :param switch_dict: 
    :param username: 
    :param password: 
    :return new_list:
    Version: 1.3
    '''
    new_list = []
    used_ports = {}
    for element in source_list:
        dict_temp = {'error':None,'warning':None,'noerror':True}
# Ignore Header of csv. file
        if element[0].lower().startswith('swi'):
            None
# Ignore empty lines
        elif element[0] == '':
            None
        else:
            dict_temp["sw_old"] = element[0].lower()
# basic test if switchname is a valid switch name (must begin with de)
            if dict_temp["sw_old"].startswith('de'):
# Conversion of switchname to IP address
                if dict_temp['sw_old'] in switch_ip.keys():
                    dict_temp['ip_old_sw'] = switch_ip[dict_temp['sw_old']]
                else:
                    dict_temp['noerror'] = False
                    dict_temp["error"] = [dict_temp['sw_old'] + ' not in List of Switch IP Adresses']
                    new_list.append(dict_temp)
                    continue
# if the old switch is a nexus switch the pair_switch name and ip address and the vpc-id are added to the dictionary
                for switch in nxos_switch:
                    if switch['sw1_name'] == dict_temp["sw_old"]:
                        dict_temp['vpc_id'] = switch['vpc_id']
                        dict_temp['sw_pair'] = switch['sw2_name']
                        dict_temp['ip_pair_sw'] = switch_ip[switch['sw2_name']]
                        break
                    elif switch['sw2_name'] == dict_temp["sw_old"]:
                        dict_temp['vpc_id'] = switch['vpc_id']
                        dict_temp['sw_pair'] = switch['sw1_name']
                        dict_temp['ip_pair_sw'] = switch_ip[switch['sw1_name']]
                        break
            else:
                dict_temp['noerror'] = False
                dict_temp["error"] = [element[0] + ' is not a valid switchname']
                new_list.append(dict_temp)
                continue
# remove all characters right of the first number
            position = re.search("\d", element[1])
            dict_temp["port_old"] = element[1][position.start():]
            dict_temp["sw_new"] = element[2].lower()
# basic test if switchname is a valid switch name (must begin with de)
            if dict_temp["sw_new"].startswith('de'):
                if dict_temp["sw_new"].endswith('-1') or dict_temp["sw_new"].endswith('-2'):
                    None
                else:
# if the new switchname is not the name of an individual switch -1 is added to the name to have a complete switchname
                    dict_temp['sw_new'] = dict_temp['sw_new']+'-1'
                if dict_temp['sw_new'] in switch_ip.keys():
                    dict_temp['ip_new_sw'] = switch_ip[dict_temp['sw_new']]
                else:
                    dict_temp['noerror'] = False
                    dict_temp["error"] = [dict_temp['sw_new']+' not in List of Switch IP Adresses']
                    new_list.append(dict_temp)
                    continue
                # Check if target switch is correct target for old_switch
                if dict_temp["noerror"]:
                    if switch_dict[dict_temp['sw_old']][:-2] != dict_temp['sw_new'][:-2]:
                        dict_temp["noerror"] = False
                        dict_temp["error"] = [dict_temp['sw_new'] + ' is the wrong target switch. Target should be ' + switch_dict[dict_temp['sw_old']]]
                        new_list.append(dict_temp)
                        continue
            else:
                dict_temp["noerror"] = False
                dict_temp["error"] = [element[2]+' is not a valid switchname']
                new_list.append(dict_temp)
                continue
# remove all characters right of the first number
            position = re.search("\d", element[3])
            dict_temp["port_new"] = element[3][position.start():]
# check if new port is already assigned
            if func_is_fex_port(dict_temp['port_new']):
                new_sw_name = dict_temp['sw_new'][:-2]
            else:
                new_sw_name = dict_temp['sw_new']
                # If no key for the new switch exists the key will be created with an empty list as value
            if new_sw_name not in used_ports.keys():
                used_ports[new_sw_name] = []
            if dict_temp['port_new'] in used_ports[new_sw_name]:
                dict_temp["noerror"] = False
                dict_temp["error"] = ['Target Port is already assigned']
                new_list.append(dict_temp)
                continue
            else:
                used_ports[new_sw_name].append(dict_temp["port_new"])
            isdown = func_check_port_status(dict_temp['ip_new_sw'],dict_temp["port_new"],username,password)
            if isdown == 1:
                dict_temp["noerror"] = False
                dict_temp["error"] = ['Port '+str(dict_temp["port_new"])+' is already in use']
            elif isdown == 2:
                dict_temp["noerror"] = False
                dict_temp["error"] = ['Port ' + str(dict_temp["port_new"]) + ' is not valid port']
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
    """
    The function return a list containing two lists of dictionaries the first list for all IOS switches and the second for all NXOS switches.
    In the ios list is an entry for each switch and all interessting port-channel of the switch
    In the nxos list is an entry for each vpc_id and all interessting port-channel of the vpc
    :param source_list: 
    :return new_list: 
    Version 1.1
    """
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
    list_of_port_channels = func_list_of_port_ch(list_of_nxos_vpcs,source_list,'vpc_id')
    new_list = [list_of_port_channels]
    list_of_port_channels = func_list_of_port_ch(list_of_ios_switches,source_list,'sw_old')
    new_list.append(list_of_port_channels)
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
    :param source_list: 
    :return none: 
    Version 1.0
    '''
    keys = ('sw_new','port_new','ip_new_sw','port_ch_new','sw_mode','vlan_list','native_vlan','sw_old','port_old','ip_old_sw','port_ch_old','error','warning')
    target_file = open(output_file, 'w')
    target_file.write('sw_new;port_new;ip_new_sw;port_ch_new;sw_mode;vlan_list;native_vlan;sw_old;port_old;ip_old_sw;port_ch_old;error;warning\n')
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

def func_list_to_file(source_list, output_file):
    '''
    The function creates a output file in csv format which contains the values for all keys in the variable key for each dictionary from the list of dictionaries 'source_list'
    :param source_list, output_file: 
    :return none: 
    Version 1.1
    '''
    keys = ('sw_new','port_new','ip_new_sw','port_ch_new','sw_mode','vlan_list','native_vlan','sw_old','port_old','ip_old_sw','port_ch_old','error','warning')
    target_file = open(output_file, 'w')
    target_file.write('sw_new;port_new;ip_new_sw;port_ch_new;sw_mode;vlan_list;native_vlan;sw_old;port_old;ip_old_sw;port_ch_old;error;warning\n')
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
    :param list_from_file: 
    :return list_from_file:
    Version: 1.2
    '''
    mapping_list = [{'old_vlan': 400, 'new_vlan': 500}, {'old_vlan': 405, 'new_vlan': 505}]

    for element in list_from_file:
        if element['noerror']:
            index = 0
            for vlan in element['vlan_list']:
                for item in mapping_list:
                    if vlan == item['old_vlan']:
                        element['vlan_list'][index] = item['new_vlan']
                        if element['warning'] == None:
                            element['warning'] = ['Changed VLAN '+str(vlan)+' to Vlan '+str(item['new_vlan'])]
                        else:
                            element['warning'].append('Changed VLAN '+str(vlan)+' to Vlan '+str(item['new_vlan']))
                        if 'vlans_trans' in element.keys():
                            element['vlans_trans'].append(item)
                        else:
                            element['vlans_trans'] = [item]
                index += 1
            if element['sw_mode'] == 'trunk':
                for item in mapping_list:
                    if element['native_vlan'] == item['old_vlan']:
                        if element['warning'] == None:
                            element['warning'] = ['Native VLAN '+str(element['native_vlan'])+' changed to VLAN '+str(item['new_vlan'])]
                        else:
                            element['warning'].append('Native VLAN '+str(element['native_vlan'])+' changed to VLAN '+str(item['new_vlan']))
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
    """
    This function checks if all vlans from the variabl list_from_file are in a variable vlan_list
    If not the function will fill the key error
    :param list_from_file: 
    :param username: 
    :param pswd: 
    :return list_from_file: 
    Version: 1.2
    """
    for element in list_from_file:
        if element['noerror']:
            vlan_list = get_vlan_list_of_switch(element['ip_new_sw'], username, pswd)
            for vlan in element['vlan_list']:
                if vlan not in vlan_list:
                    element['noerror'] = False
                    if element['error'] == None:
                        element['error'] = [str(vlan)+' is not on the new switch']
                    else:
                        element['error'].append(str(vlan)+' is not on the new switch')
            if element['sw_mode'] == 'trunk':
                if element['native_vlan'] not in vlan_list:
                    if 'warning' not in element.keys() or element['warning'] == None:
                        element['warning'] = [str(element['native_vlan']) + ' is not on the new switch']
                    else:
                        element['warning'].append(str(element['native_vlan']) + ' is not on the new switch')
    return list_from_file
    
def func_ports_in_list(sw_name,port_list,list_from_file):
    '''
    the function checks if all the ports in the port_list of the switch with the name sw_name are in the input file
    :param sw_name: 
    :param port_list: 
    :param list_from_file: 
    :return all_in:
    Version: 1.3
    '''
    all_in = True
    for port in port_list:
# Reduce the port to the portnumber
        position = re.search("\d", port)
        port = port[position.start():]
        found = False
        for element in list_from_file:
# When there was already an error in this line of the input list this line will be ignored
            if element['noerror']:
# Reduce the port to the portnumber
                position = re.search("\d", element['port_old'])
                port_old = element['port_old'][position.start():]
                if element['sw_old'] == sw_name and port_old == port:
                    found = True
        if not found:
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
    :param list_from_file: 
    :return list_from_file:
    Version: 1.1
    '''
    for port in port_list:
        for element in list_from_file:
            if element['sw_old'] == sw_name and element['port_old'] == port:
                element['noerror'] = False
                if element['error'] == None:
                    element['error'] = ['not all ports of port-channel in list']
                else:
                    element['error'].append('not all ports of port-channel in list')
    return list_from_file

def func_write_po_error(source_list,list_from_file):
    """
    The function searches for incomplete port-channels and if it finds one forwards the information of the switchname(s) and the associated port_list to the function func_find_ports_of_pc
    :param source_list: 
    :param list_from_file: 
    :return list_from_file: 
    Version 1.1
    """
    for item in source_list:
        if not item['all_in']:
            list_from_file = func_find_ports_of_pc(item['sw_old'], item['ports'],list_from_file)
            if 'ports2' in item.keys():
                list_from_file = func_find_ports_of_pc(item['sw_old2'], item['ports2'],list_from_file)
    return list_from_file

def func_add_used_pcs(listofpcs, username, password):
    '''
    Adds two lists of used port-channels on ip_new1 and ip_new2 (the new switches).
    First list is used_fex_pc - it contains pc numbers up to 90
    2nd list is used_sw_pc - it contains pc numbers from 120 upwards
    '''
    
    new_list = []
    for item in listofpcs:      # process all items
        used_fex_pc = []        # list od used pc with number >=120
        used_sw_pc = []         # list of pc with number <=90
        for ip_addr in (item['ip_new1'], item['ip_new2']):  # process both switches
            net_connect = cli_open_session(ip_addr, username, password)
            if not net_connect:
                None    # error, unable to connect to the device
            pcsumm = cscofunc.get_cli_sh_etherchannel_summary_nxos(net_connect)
            net_connect.disconnect()
            for pc in pcsumm:
                if int(pc['pc_number']) <= 90:
                    if pc['pc_number'] not in used_sw_pc:   # is the number already in list ?
                        used_sw_pc.append(pc['pc_number'])  # no, append it
                if int(pc['pc_number']) >= 120:
                    if pc['pc_number'] not in used_fex_pc:  # is the number already in list ?
                        used_fex_pc.append(pc['pc_number']) # no, append it
        item['used_sw_pc'] = used_sw_pc
        item['used_fex_pc'] = used_fex_pc
        new_list.append(item)
    return new_list

def func_create_vpc_pc_list(source_list,nexus_switch_list,ip_list):
    '''
    The function creates a list of dictionaries. The list contains a dictionary for each vpc pair of new switches in the source list
    Each dictionary has three entries. The vpc_id the ip address of the first switch of the vpc-pair and the ip address of the second switch of the vpc-pair.
    :param source_list: 
    :param nexus_switch_list: 
    :param ip_list: 
    :return new_list:
    Version: 1.0
    '''
    list_of_switches = []
    new_list = []
    for element in source_list:
        if 'error' in element.keys() and element['error']!= None:
            None
        else:
            sw_name = element['sw_new'][:-2]
            if sw_name not in list_of_switches:
                list_of_switches.append(sw_name)
                for entry in nexus_switch_list:
                    temp_dict = {}
                    if (entry['sw1_name'] == element['sw_new']) or (entry['sw2_name'] == element['sw_new']):
                        temp_dict['vpc_id'] = entry['vpc_id']
                        temp_dict['ip_new1'] = ip_list[entry['sw1_name']]
                        temp_dict['ip_new2'] = ip_list[entry['sw2_name']]
                        new_list.append(temp_dict)
    return new_list


def func_add_vpc_new_to_list(source_list,old_new,nexus_switch):
    '''
    The function adds the vpc_id of the target switch to the list containing port-channels and all old ports belonging to the port-channel
    :param source_list: 
    :param old_new: 
    :param nexus_switch: 
    :return source_list: 
    Version: 1.0
    '''
    for element in source_list:
        if element['all_in']:
            new_switch = old_new[element['sw_old']]
            for vpc_pair in nexus_switch:
                if (vpc_pair['sw1_name'] == new_switch) or (vpc_pair['sw2_name'] == new_switch):
                    element['vpc_new'] = vpc_pair['vpc_id']
    return source_list


def func_is_fex_port(port):
    '''
    The function returns True if the port in the variable port is a fex port
    :param port: 
    :return Boolean: 
    '''
    position = re.search("\d", port)
    port_number = port[position.start():]
    if len(port_number) > 6:
        return True
    else:
        return False


def func_assign_new_pc(source_list,pcs_in_use,input_list):
    for element in source_list:
        if element['all_in']:
            for input in input_list:
                if (input['sw_old'] == element['sw_old']) and (input['port_old'] == element['ports'][0]):
                    fex_port = func_is_fex_port(input['port_new'])
                    for vpcs in pcs_in_use:
                        if element['vpc_new'] == vpcs['vpc_id']:
                            not_found = True
                            if fex_port:
                                number = 120
                                list = vpcs['used_fex_pc']
                                while not_found:
                                    if number in list:
                                        number += 1
                                        if number > 1000:
                                            number = -1
                                            not_found = False
                                    else:
                                        vpcs['used_fex_pc'].append(number)
                                        not_found = False
                                        print ('Neue Liste PC '+str(vpcs['used_fex_pc']))
                            else:
                                number = 90
                                list = vpcs['used_sw_pc']
                                while not_found:
                                    if number in list:
                                        number -= 1
                                        if number == 1:
                                            number = -1
                                            not_found = False
                                    else:
                                        not_found = False
                                        vpcs['used_sw_pc'].append(number)
            for port in element['ports']:
                for entry in input_list:
                    if (entry['sw_old'] == element['sw_old']) and (entry['port_old'] == port):
                        entry['port_ch_new'] = number
            if 'ports2' in element.keys():
                for port in element['ports2']:
                    for entry in input_list:
                        if (entry['sw_old'] == element['sw_old2']) and (entry['port_old'] == port):
                            entry['port_ch_new'] = number
    return input_list

def func_check_port_status(ip_addr, port, username, password):
    '''
    '''

    net_connect = cli_open_session(ip_addr, username, password)
    if not net_connect:
        print("Unable to connect to device " + ip_addr)
        return 3   
    port_stat = cscofunc.get_cli_sh_int_status(net_connect)
    for item in port_stat:
        if port in item['port']:            # is port substring of item['port'], i.e. 3/11 is substr of Eth3/11
            if item['status'] == 'connected':
                return 1            # port is used
            # if item['status'] == 'notconnec' or item['status'] == 'disabled' or item['status'] == 'sfpAbsent' or item['status'] == 'xcvrInval':
            if item['status'] in ('notconnec','disabled','sfpAbsent','xcvrInval') :
                return 0            # port is not used
            return 3                # status value is unexpected ... error
    return 2            # port not found, port is not valid

def func_read_cfg_file(config_file):
    '''
    Reads configuration file
    ''' 
    if os.path.isfile(config_file):
        try:
            with open(config_file) as data_file:
                config_yaml = yaml.load(data_file.read())
        except IOError:
            print("Unable to read the file", config_file)
            exit(1)
    else:
        print("Cannot find the file", config_file)
        exit(1)   

    return config_yaml 

def func_cfg_file_sanity_checks(config_dict):
    '''
    Checks if files in config dict exist, etc ...
    '''

    return_dict = {}
    if 'path' not in config_dict:
        path_to_cfgf = ''
    else:
        path_to_cfgf =  config_dict['path'] + '\\'
    
    if 'filenames' not in config_dict:
        return_dict['passed'] = False
    if 'ports' not in config_dict['filenames'] or 'sw_old_new' not in config_dict['filenames'] or 'switchip' not in config_dict['filenames'] or 'nxos' not in config_dict['filenames']:
        return_dict['passed'] = False
    portsf = path_to_cfgf+config_dict['filenames']['ports']
    nxosf = path_to_cfgf+config_dict['filenames']['nxos']
    switchipf = path_to_cfgf+config_dict['filenames']['switchip']
    sw_old_newf = path_to_cfgf+config_dict['filenames']['sw_old_new']

    for file in (portsf, nxosf, switchipf, sw_old_newf):
        if not os.path.isfile(file):
            return_dict['passed'] = False
    return_dict['passed'] = True
    return_dict['portsf'] = portsf
    return_dict['nxosf'] = nxosf
    return_dict['switch_ipf'] = switchipf
    return_dict['sw_old_newf'] = sw_old_newf
    return_dict['output'] = path_to_cfgf+config_dict['filenames']['output']
    return return_dict

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
    -c,     --cfgfile                   conmfiguration file
    '''
    argv = sys.argv[1:]

    try:
        opts, args = getopt.getopt(argv, "hp:u:c:", [ "help" "password=", "username=", "cfgfile="])
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
        elif opt in ("-c", "--cfgfile"):
            cfgfile = arg


    # sanity checks
    if not username:
        print("Username is not specified")
        sys.exit(2)
    if not cfgfile:
        print("Configuration file is not specified")
        sys.exit(2)

    
    cfg_dict = func_read_cfg_file(cfgfile)
    cfgfiles_dict = func_cfg_file_sanity_checks(cfg_dict)
    if not cfgfiles_dict['passed']:
        print("Something in config file is wrong ...")
        sys.exit(2) 


    file_name = cfgfiles_dict['portsf']
    file_name_sip = cfgfiles_dict['switch_ipf']
    file_name_nxos = cfgfiles_dict['nxosf']
    file_name_old_new = cfgfiles_dict['sw_old_newf']
    output_file = cfgfiles_dict['output']


    if pswd == '':
        pswd = getpass.getpass('Password:')

    
    list_of_switch_ips = func_lines_from_csv_to_list(file_name_sip) # list of device names and related IP addresses
    switch_ip = func_convert_list_to_dict(list_of_switch_ips) # dictionary device name : IP address
    list_of_vpcs = func_lines_from_csv_to_list(file_name_nxos) # list of entries with two devices and VPC number
    nxos_switch = func_new_list_from_list(list_of_vpcs) # list of dictionary with thow device names and VPC number
    list_of_switch_old_to_new = func_lines_from_csv_to_list(file_name_old_new)
    list_old_to_new = func_convert_list_to_dict(list_of_switch_old_to_new)

    list_from_file = func_lines_from_csv_to_list(file_name)
    list_from_file = func_list_to_list_of_dict(list_from_file, list_old_to_new, username, pswd)
  
    list_from_file = func_add_items_to_port_list(list_from_file, username, pswd)
    
    list_of_po = func_port_ch_switch2(list_from_file)
    list_of_po_ports = func_create_dict_with_pc_ports(list_from_file, list_of_po, username, pswd)
    list_of_po_ports = func_po_ch_all_in(list_of_po_ports,list_from_file)
    list_of_po_ports = func_add_vpc_new_to_list(list_of_po_ports,list_old_to_new,nxos_switch)
    list_from_file = func_write_po_error(list_of_po_ports,list_from_file)
    list_from_file = func_change_mapped_vlans(list_from_file)
    list_from_file = func_vlans_in_fabricpath(list_from_file, username, pswd)
    list_of_pcs_in_use = func_create_vpc_pc_list(list_from_file, nxos_switch, switch_ip)
    list_of_pcs_in_use = func_add_used_pcs(list_of_pcs_in_use, username, pswd) # list of used PC by two new switches

    list_from_file = func_assign_new_pc(list_of_po_ports,list_of_pcs_in_use,list_from_file)
    func_list_to_file(list_from_file, output_file)

   

if __name__ == '__main__':
    main()
    

