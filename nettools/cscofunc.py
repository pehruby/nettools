''' Module implements functions which read/change configuration of Cisco equipment

'''

# pylint: disable=C0301, C0103

import sys
import re
import requests
import json
import ipaddress
from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException
from paramiko.ssh_exception import SSHException

requests.packages.urllib3.disable_warnings()
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_intlist_vlan(handler, vlan):
    ''' Returns list of all (both access andf trunks) interfaces where VLAN 'vlan' is configured
        paremeter 'handler' is existing handler created using Netmiko CreateHandler function

    '''
    str_vlan = str(vlan)
    cli_param = "sh vlan id " + str_vlan
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('\n')
    for i in range(len(cli_out_split)-2):
        if re.match(r"VLAN Name\s+Status\s+Ports", cli_out_split[i]):   #find line with column names
            # print("Matched line in "sh vlan id" with interfaces configured in Vlan", vlan)
            intstr = re.match("^"+str_vlan+r"\s+(.+?)\s+(.+?)\s+(.+)", cli_out_split[i+2]) # interfaces are on 2nd line after column names line
            if intstr:
                return intstr.group(3).split(",")       # list of interfaces
            else:
                print("Expected line with interface list for VLAN" + str_vlan + "was not found !!!")
                return ""


def is_int_admin_trunk(handler, iface):
    ''' Is interface in administrative mode trunk ?

    '''
    cli_param = "sh int " + iface + " switchport"
    cli_output = handler.send_command(cli_param)
    if re.search(r"Administrative Mode: trunk", cli_output):
        return True
    return False

def is_int_allowed_vlan_configured(handler, iface):
    ''' Is command "trunk allowed vlan" configured ?

    '''
    cli_param = "sh run int " + iface
    cli_output = handler.send_command(cli_param)
    if re.search(r"switchport trunk allowed vlan", cli_output):
        return True
    return False

def normalize_vlan_list(vlset):
    ''' Returns list of VLAN numbers. In vlset changes VLAN ranges (i.e 2345-2348) into list of VLANs
    contained in range (2345,2346,2347,2348)
    '''

    outset = list()      # empty list
    for item in vlset:
        intstr = re.match(r"([0-9]+)-([0-9]+)", item)   # matches for example 2345-2358
        if intstr:
            for subit in range(int(intstr.group(1)), int(intstr.group(2))+1): # +1 because last number is excluded from iteration
                outset.append(str(subit))       # add number inside the range to output list
        else:
            outset.append(item)            # add number input set to output list
    return outset


def list_trunking_vlans_enabled(handler, iface):
    ''' Returns list of trunking vlans enabled on specific interface

    '''
    cli_param = "sh int " + iface + " switchport"
    cli_output = handler.send_command(cli_param)
    intstr = re.search(r"Trunking VLANs Enabled:\s+([0-9\-,\n ]+)[A-Za-z]+", cli_output)
    if not intstr:
        intstr = re.search(r"Trunking VLANs Enabled:\s+(ALL)", cli_output)
    if intstr:
        vlanlist = process_raw_vlan_list(intstr.group(1))
        vlanlist = normalize_vlan_list(vlanlist)
        # print("Normalized list: ", vlanlist)
        return vlanlist
    else:
        print("Expected line with interface list for iface" + iface + "was not found !!!")
        return ""

def is_it_switch(handler):
    ''' Check if the equipment is switch

    '''
    cli_param = "sh vlan"
    cli_output = handler.send_command(cli_param)
    intstr = re.search(r"1\s+default", cli_output)
    if intstr:
        return True
    else:
        return False

def is_ip_valid(testedip):
    ''' Test if string is valid IP address
    '''
    result = True
    list_ip = testedip.split('.')

    for i, octet in enumerate(list_ip):
        try:
            list_ip[i] = int(octet)
        except ValueError:
            # couldn't convert octet to an integer
            result = False
            return result
            # sys.exit("\n\nInvalid IP address: %s\n" % testedip)



    if len(list_ip) == 4:
        prvni, druhy, treti, ctvrty = list_ip
        if ((prvni >= 1) and (prvni <= 223)) and (prvni != 127) and ((prvni != 169) and (druhy != 254)):
            for item in list_ip[1:]:
                if (item < 0) or (item > 255):
                    result = result and False
        else:
            result = False
    else:
        result = False

    return result


def is_valid_vlan_number(vnum):
    ''' Check if vnum is valid VLAN number
    '''
    try:
        vnum = int(vnum)
    except ValueError:
        return False

    if vnum > 0 and vnum < 4095:
        return True
    return False

def add_vlan_to_int_trunk_allowed(handler, interface, vlan):
    ''' Adds VLAN to allowed vlan on trunk interface
    '''
    cfg_cmds = ['interface '+ interface, 'switchport trunk allowed vlan add '+ vlan]
    output = handler.send_config_set(cfg_cmds)
    # print(output)
    if ('^' in output) or ('%' in output):      # probably something wrong happened
        return False
    return True

def is_vlan_in_allowed_list(handler, interface, vlan):
    ''' Is VLAN in allowed vlan on trunk interface ?
    '''
    enabled_trunk_vlan_list = list_trunking_vlans_enabled(handler, interface) # list of Vlan configured as allowed on the interface
    if vlan in enabled_trunk_vlan_list:
        return True
    return False

def is_vlan_configured(handler, vlan):
    ''' Checks if vlan is configured on the switch
    '''
    cli_param = "sh vlan"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('\n')
    for line in cli_out_split:
        if re.match(r"^" + vlan, line):   #find line with vlan number
            return True

    return False

def is_valid_vlan_name(name):
    ''' Is it valid VLAN name ?
    '''
    #matchobj = re.match(r"^[a-zA-Z0-9]+$", name)
    if re.match(r"^[a-zA-Z0-9_\-]+$", name) and (len(name) <= 32):
        return True
    return False


def configure_vlan(handler, vlan, vlan_name=''):
    ''' Configure (add) vlan on the switch
    '''
    if vlan_name:
        cfg_cmds = ['vlan '+ vlan, 'name '+ vlan_name]
    else:
        cfg_cmds = ['vlan '+ vlan]
    output = handler.send_config_set(cfg_cmds)
    if ('^' in output) or ('%' in output):      # probably something wrong happened
        return False
    return True

def write_running_to_startup(handler):
    ''' wr mem
    '''
    cli_param = "write mem"
    cli_output = handler.send_command(cli_param)

    return True

def get_cli_sh_mac_address_table_dyn_dict(handler):
    ''' Returns dynamic entries of mac address table
    Table is dict with Vlan number as key and value is list of (mac,int) items
    '''
    mactable = {}       # dict of vlans
    cli_param = "sh mac address-table"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('\n')
    for line in cli_out_split:
        match = False
        # *  713  6480.9998.fc6a   dynamic  Yes        215   Te1/6/16
        intstr = re.match(r"[*]?\s+([0-9]+)\s+([0-9a-f.]+)\s+dynamic\s+Yes\s+[0-9]+\s+(.*)$", line)
        if intstr:
            match = True
        else:
            # 172    0050.5682.003c    DYNAMIC     Gi2/1/4
            intstr = re.match(r"\s?([0-9]+)\s+([0-9a-f.]+)\s+DYNAMIC\s+(.*)$", line)
            if intstr:
                match = True
            else:
                # IOS-XE
                # 503      001e.be4c.8180   dynamic ip,ipx,assigned,other TenGigabitEthernet1/1
                intstr = re.match(r"\s?([0-9]+)\s+([0-9a-f.]+)\s+dynamic\s+[A-Za-z,]+\s+([A-Za-z0-9/\-\.]+)", line)
                if intstr:
                    match = True

        if match:
            vlan = intstr.group(1)
            if vlan not in mactable.keys():
                mactable[vlan] = []
            mactable[vlan].append({'mac':intstr.group(2), 'int':intstr.group(3)})


    return mactable

def get_cli_sh_mac_address_table(handler):
    '''
    Returns list of show mac-address-table entries
    dynamic a static entries only, no multicast
    Each entry is dict which contains vlan, mac, type, int
    '''
    
    mac_tab = []
    cli_param = "sh mac address-table"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('\n')
    for line in cli_out_split:
        match = False
        # *  713  6480.9998.fc6a   dynamic  Yes        215   Te1/6/16
        intstr = re.match(r"[*]?\s+([0-9]+)\s+([0-9a-f.]+)\s+(dynamic|static)\s+[A-Za-z]+\s+[0-9\-]+\s+([A-Za-z0-9/\-\.]+)", line)
        if intstr:
            match = True
        else:
            # 172    0050.5682.003c    DYNAMIC     Gi2/1/4
            # All    0180.c200.0004    STATIC      CPU
            intstr = re.match(r"\s?([0-9A-Za-z]+)\s+([0-9a-f.]+)\s+(DYNAMIC|STATIC)\s+([A-Za-z0-9/\-\.]+)", line)
            if intstr:
                match = True
            else:
                # IOS-XE
                # 503      001e.be4c.8180   dynamic ip,ipx,assigned,other TenGigabitEthernet1/1
                intstr = re.match(r"\s?([0-9]+)\s+([0-9a-f.]+)\s+(dynamic|static)\s+[A-Za-z,]+\s+([A-Za-z0-9/\-\.]+)", line)
                if intstr:
                    match = True

        if match:
            int_dict = {}
            int_dict['vlan'] = intstr.group(1)
            int_dict['mac'] = intstr.group(2)
            int_dict['type'] = intstr.group(3)
            int_dict['int'] = intstr.group(4)
            mac_tab.append(int_dict)
    return mac_tab
            
def get_vlan_list_trunk(macadrtab, trunk):
    '''
    Returns list of VLANs which are visible on trunk based on mac address table list
    variable trunks is interface name
    '''
    vlanlist = []
    for vlan in macadrtab.keys():
        for item in macadrtab[vlan]:
            if item['int'] == trunk:
                vlanlist.append(vlan)
                break
    return vlanlist


def get_cli_ip_int_br_dict(handler):
    ''' Returns dictionary of L3 interfaces with valid IP address configured like this:
    {'Vlan904': {'status': 'up', 'protocol': 'up', 'ip': '192.168.100.33'},'Vlan555': {'status': 'up', 'protocol': 'up', 'ip': '10.76.77.254'}}

    '''
    ip_l3_table = {}
    cli_param = "sh ip interface brief"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('\n')
    for line in cli_out_split:
        intstr = re.match(r"([a-zA-Z0-9/.\-]+)\s+([0-9a-z.]+)\s+(YES|NO)\s+([A-Za-z]+)\s+(([a-z]+(\sdown)?))\s+([a-z]+)\s+$", line)
        if intstr:
            if is_ip_valid(intstr.group(2)):
                ip_l3_table[intstr.group(1)] = {'ip':intstr.group(2), 'status':intstr.group(6), 'protocol':intstr.group(8)}
    return ip_l3_table

def get_cli_sh_ip_int_brie(handler):
    '''
    Returns list of dict entries from sh ip int brie
    '''
    sh_ip_int_list = []
    cli_param = "sh ip interface brief"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('\n')
    for line in cli_out_split:
        intstr = re.match(r"([a-zA-Z0-9/.\-]+)\s+([0-9a-z.]+)\s+(YES|NO)\s+([A-Za-z]+)\s+(([a-z]+(\sdown)?))\s+([a-z]+)\s+$", line)
        if intstr:
            int_dict = {}
            int_dict['interface'] = intstr.group(1)
            int_dict['ip'] = intstr.group(2)
            int_dict['status'] = intstr.group(6)
            int_dict['protocol'] = intstr.group(8)
            sh_ip_int_list.append(int_dict)
    return sh_ip_int_list



def print_vlan_cfg(handler, vlannrlist):
    '''
    Lists Vlans config
    '''
    for vlan in vlannrlist:
        exclreach = False
        cli_param = "sh run vlan " + vlan
        cli_output = handler.send_command(cli_param)
        cli_out_split = cli_output.split('\n')
        for line in cli_out_split:
            if line == '!':
                exclreach = True
                continue
            if line == 'end':
                continue
            if exclreach:
                print(line)




def get_cli_sh_int_switchport(handler):
    '''
    Returns list of switchport interfaces with parameters. One item of list is directory.
    '''
    sp_list = []
    cli_param = "sh interface switchport"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('Name: ')      # split output into blocks of interfaces
    for block in cli_out_split:
        intstr = re.search(r"([A-Za-z0-9/.]+)\n", block)
        if intstr:                                  # interface name was found, process the interface
            name = intstr.group(1)
            int_dict = {}
            int_dict['int'] = conv_int_to_interface_name(name) # gi1/3/4 -> GigabitEthernet1/3/4
            int_dict['switchport'] = find_regex_value_in_string(block, re.compile(r"Switchport:\s([A-Za-z]+)\n"))
            int_dict['admin_mode'] = find_regex_value_in_string(block, re.compile(r"Administrative Mode:\s([A-Za-z\s]+)[\n\(]"))
            int_dict['admin_mode'] = int_dict['admin_mode'].rstrip()      # get rid of spaces at the end of 
            int_dict['oper_mode'] = find_regex_value_in_string(block, re.compile(r"Operational Mode:\s([A-Za-z\s]+)[\n\(]"))
            int_dict['oper_mode'] = int_dict['oper_mode'].rstrip()      # get rid of spaces at the end of the string
            int_dict['admin_trunc_enc'] = find_regex_value_in_string(block, re.compile(r"Administrative Trunking Encapsulation:\s([A-Za-z0-9\.]+)\n"))
            int_dict['trunk_negot'] = find_regex_value_in_string(block, re.compile(r"Negotiation of Trunking:\s([A-Za-z0-9\.]+)\n"))
            int_dict['access_mode_vlan'] = find_regex_value_in_string(block, re.compile(r"Access Mode VLAN:\s([0-9]+).+\n"))
            int_dict['trunk_native_mode_vlan'] = find_regex_value_in_string(block, re.compile(r"Trunking Native Mode VLAN:\s([0-9]+).+\n"))
            int_dict['admin_native_vlan_tagging'] = find_regex_value_in_string(block, re.compile(r"Administrative Native VLAN tagging:\s([A-Za-z0-9\.]+)\n"))
            int_dict['voice_vlan'] = find_regex_value_in_string(block, re.compile(r"Voice VLAN:\s([A-Za-z0-9]+)\n"))
            int_dict['bundle_member'] = find_regex_value_in_string(block, re.compile(r"member of bundle\s(Po[0-9]+)\)"))
            tmps = find_regex_value_in_string(block, re.compile(r"Trunking VLANs Enabled:\s([A-Za-z0-9,\-\s]+)\n"))
            vlanlist = process_raw_vlan_list(tmps)          # remove spaces, newlines
            vlanlist = normalize_vlan_list(vlanlist)        # convert vlan ranges (i.e.5-8, ...) to list (5,6,7,8)
            int_dict['trunk_vlans'] = vlanlist
            sp_list.append(int_dict)

    return sp_list

def get_cli_sh_int_switchport_nxos(handler):
    '''
    Returns list of switchport interfaces with parameters. One item of list is directory.
    '''
    sp_list = []
    cli_param = "sh interface switchport"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('Name: ')      # split output into blocks of interfaces
    for block in cli_out_split:
        intstr = re.search(r"([A-Za-z0-9/.]+)\n", block)
        if intstr:                                  # interface name was found, process the interface
            name = intstr.group(1)
            int_dict = {}
            int_dict['int'] = conv_int_to_interface_name(name) # gi1/3/4 -> GigabitEthernet1/3/4
            int_dict['switchport'] = find_regex_value_in_string(block, re.compile(r"Switchport:\s([A-Za-z]+)\n"))
        
            int_dict['oper_mode'] = find_regex_value_in_string(block, re.compile(r"Operational Mode:\s([A-Za-z\s]+)[\n\(]"))
            int_dict['oper_mode'] = int_dict['oper_mode'].rstrip()      # get rid of spaces at the end of the string
            int_dict['access_mode_vlan'] = find_regex_value_in_string(block, re.compile(r"Access Mode VLAN:\s([0-9]+).+\n"))
            int_dict['trunk_native_mode_vlan'] = find_regex_value_in_string(block, re.compile(r"Trunking Native Mode VLAN:\s([0-9]+).+\n"))
            int_dict['voice_vlan'] = find_regex_value_in_string(block, re.compile(r"Voice VLAN:\s([A-Za-z0-9]+)\n"))
            tmps = find_regex_value_in_string(block, re.compile(r"Trunking VLANs Allowed:\s([A-Za-z0-9,\-\s]+)\n"))
            vlanlist = process_raw_vlan_list(tmps)          # remove spaces, newlines
            vlanlist = normalize_vlan_list(vlanlist)        # convert vlan ranges (i.e.5-8, ...) to list (5,6,7,8)
            int_dict['trunk_vlans'] = vlanlist
            sp_list.append(int_dict)

    return sp_list

def get_cli_sh_int_switchport_dict(handler):
    '''
    Get dictionary where key is interface name and value are switchport parameters (in dictionary)
    '''
    int_dict = {}
    int_list = get_cli_sh_int_switchport(handler)
    for item in int_list:
        int_dict[item['int']] = item
    return int_dict

def get_cli_sh_int_switchport_dict_nxos(handler):
    '''
    Get dictionary where key is interface name and value are switchport parameters (in dictionary)
    '''
    int_dict = {}
    int_list = get_cli_sh_int_switchport_nxos(handler)
    for item in int_list:
        int_dict[item['int']] = item
    return int_dict

def process_raw_vlan_list(rawlist):
    ''' Process raw list of trunk vlan numbers obtained from show command, i.e. removes spaces, newlines, commas ...
     4,10,11,75,135,172,302,303,306,311,330,555-560,704,706,
     708,710,712-717,750,751,755-770,772-778,781-785,788-790,792,794,796,797,
     830-833,840-843,848-854,859-863,869-878,880-885,890-904,910-914,970-979,

    '''
    rawlist = rawlist.replace('ALL', '1-4096')
    rawlist = rawlist.replace('\n', '')        # delete newlines
    rawlist = rawlist.replace(' ', '')         # delete spaces
    vlanlist = rawlist.split(",")       # list VLANs
    return vlanlist

def find_regex_value_in_string(sstring, regexp):
    '''
    Searches for regexp group(1) inside sstring

    :param sstring: list of devices (list of CDP entries)
    :param regexp: device to be checked against dlist
    :return : founded group(1) value or ''
    '''
    intstr = re.search(regexp, sstring)
    if intstr:
        value = intstr.group(1)
    else:
        value = ''
    return value


def conv_int_to_interface_name(intname):
    '''
    Converts interface shortname to standartd name, i.e Gi1/1/1 to GigabitEthernet1/1/1
    '''
    res = re.match(r"Gi[0-9].*", intname)
    if res:
        intname = intname.replace('Gi', 'GigabitEthernet')
        return intname
    res = re.match(r"Te[0-9].*", intname)
    if res:
        intname = intname.replace('Te', 'TenGigabitEthernet')
        return intname
    res = re.match(r"Fa[0-9].*", intname)
    if res:
        intname = intname.replace('Fa', 'FastEthernet')
        return intname
    res = re.match(r"Po[0-9].*", intname)
    if res:
        intname = intname.replace('Po', 'Port-channel')
        return intname
    res = re.match(r"Eth[0-9].*", intname)
    if res:
        intname = intname.replace('Eth', 'Ethernet')
        return intname
    res = re.match(r"Vl[0-9].*", intname)
    if res:
        intname = intname.replace('Vl', 'Vlan')
        return intname
    res = re.match(r"Lo[0-9].*", intname)
    if res:
        intname = intname.replace('Lo', 'Loopback')
        return intname
    return "Error"
    
def conv_interface_to_int_name(intname):
    '''
    Converts interface standartd name to interface shortname, i.e  GigabitEthernet1/1/1 to Gi1/1/1
    '''
    res = re.match(r"GigabitEthernet[0-9].*", intname)
    if res:
        intname = intname.replace('GigabitEthernet', 'Gi')
        return intname
    res = re.match(r"TenGigabitEthernet[0-9].*", intname)
    if res:
        intname = intname.replace('TenGigabitEthernet', 'Te')
        return intname
    res = re.match(r"FastEthernet[0-9].*", intname)
    if res:
        intname = intname.replace('FastEthernet', 'Fa')
        return intname
    res = re.match(r"Port-channel[0-9].*", intname)
    if res:
        intname = intname.replace('Port-channel', 'Po')
        return intname
    res = re.match(r"Ethernet[0-9].*", intname)
    if res:
        intname = intname.replace('Ethernet', 'Eth')
        return intname
    res = re.match(r"Vlan[0-9].*", intname)
    if res:
        intname = intname.replace('Vlan', 'Vl')
        return intname
    res = re.match(r"Loopback[0-9].*", intname)
    if res:
        intname = intname.replace('Loopback', 'Lo')
        return intname
    return "Error"

def get_cli_sh_cdp_neighbor(handler):
    '''
    Returns CDP table.
    '''
    its_nxos = False
    cdp_list = []
    cli_param = "sh cdp entry *"
    cli_output = handler.send_command(cli_param)
    if 'Invalid command at' in cli_output:  # it's probably NX-OS
        cli_param = "sh cdp entry all"
        cli_output = handler.send_command(cli_param)
        its_nxos = True
    cli_out_split = cli_output.split('----------------')      # split output into blocks (list) of devices
    for block in cli_out_split:
        if its_nxos:
            intstr = re.search(r"Device ID:([A-Za-z0-9/\._\-\(\)]+)\n", block)
        else:  
            intstr = re.search(r"Device ID:\s+([A-Za-z0-9/\._\-\(\)]+)\n", block)         # ?what characters can be in CDP device name?
        if intstr:                                  # device name was found, process the device entry
            name = intstr.group(1)
            int_dict = {}
            int_dict['device_id'] = name
            if its_nxos:
                int_dict['ip_addr'] = find_regex_value_in_string(block, re.compile(r"IPv4 Address:\s+([0-9\.]+)\n"))
            else:
                int_dict['ip_addr'] = find_regex_value_in_string(block, re.compile(r"Entry address\(es\):\s+\n\s+IP address:\s+([0-9\.]+)\n"))
            int_dict['platform_id'] = find_regex_value_in_string(block, re.compile(r"Platform:\s+[a-z]{0,20}\s?([A-Za-z0-9\.\-\s/]+),")) # cisco WS-6506-E -> WS-6506-E
            cap_raw = find_regex_value_in_string(block, re.compile(r"Capabilities:\s+([A-Za-z0-9\-\s]+)\n"))
            cap_raw = cap_raw.rstrip(' ')           # remove trailing space
            int_dict['capability'] = cap_raw.split(' ')         # split capabilities int list
            int_dict['intf_id'] = find_regex_value_in_string(block, re.compile(r"Interface:\s+([A-Za-z0-9\./]+),"))
            int_dict['port_id'] = find_regex_value_in_string(block, re.compile(r" Port ID \(outgoing port\):\s+([A-Za-z0-9\./\s]+)\n"))
            int_dict['software'] = find_regex_value_in_string(block, re.compile(r"\(([A-Za-z0-9\-_]+)\),\s+Version"))
            if int_dict['software'] == '':
                int_dict['software'] = find_regex_value_in_string(block, re.compile(r"\(([A-Za-z0-9\-_]+)\)\s+Software"))       # NX-OS
            if 'Phone' in int_dict['capability']:
                # Version :
                # SCCP 9.4.1.3.SR1
                #
                # Version :
                # SCCP11.9-3-1SR4-1S
                int_dict['version'] = find_regex_value_in_string(block, re.compile(r"Version\s+:\n([A-Za-z0-9\.\- ]+)\n"))
            else:
                int_dict['version'] = find_regex_value_in_string(block, re.compile(r"Version\s+([A-Za-z0-9\.\s\(\)]+),"))
                if int_dict['version'] == '':
                    int_dict['version'] = find_regex_value_in_string(block, re.compile(r"Version\s+([A-Za-z0-9\.\(\)]+)\s"))    # IOS XE, ',' is not after version number
                if int_dict['version'] == '':
                    int_dict['version'] = find_regex_value_in_string(block, re.compile(r"Version :\n([A-Za-z0-9\.\- ]+)\n"))    # ATA is not Phone :(
            cdp_list.append(int_dict)
    return cdp_list

def ping(host):
    """
    Returns True if host responds to a ping request
    (c) www.rudiwiki.de

    :param host: IP address
    :return Boolean: True if IP responds to ping
    """
    import subprocess, platform

    # Ping parameters as function of OS
    ping_str = "-n 1" if  platform.system().lower()=="windows" else "-c 1"
    args = "ping " + " " + ping_str + " " + host
    need_sh = False if  platform.system().lower()=="windows" else True

    # Ping
    return subprocess.call(args, shell=need_sh) == 0


def get_device_list_cdp_subnet(ip_ranges, big_cdp_dict):
    """
    Discovers devices specified by IP ranges of management interface

    :param ip_ranges: list of ranges, each entry contains dict with range, username, password
    :param big_cdp_dict: dictionary of two list of found devices (hosts, nodes)
    :return big_cdp_dict: dictionary of two list of found devices (hosts, nodes)
    """

    

    for ip_range in ip_ranges:
        net = ipaddress.ip_network(ip_range['range'])
        for host in net.hosts():        # go through every IP in subnet range
            if ping(host.exploded):              # does IP responds to ping ?
                one_item = get_device_info(host.exploded, ip_range['username'], ip_range['password'])    # get info about device
                if one_item:            # one_item is not None
                    retval = is_cdp_device_in_list(big_cdp_dict['nodes'], one_item)
                    if retval == 0:     # device is not in big_cdp_dict
                        one_item['found_via_cdp'] = False
                        big_cdp_dict['nodes'].append(one_item)
                    elif retval != 3:    # device is in big_cdp_dict but was not yet analyzed for CDP info
                        big_cdp_dict = get_device_list_cdp_recur(host.exploded, ip_range['username'], ip_range['password'], big_cdp_dict, 0)

#    for item in big_cdp_dict['hosts']:
#        big_cdp_list.append(item)
#    for item in big_cdp_dict['nodes']:
#        big_cdp_list.append(item)
    return big_cdp_dict

def get_device_list_cdp_seed(seeds, big_cdp_dict):
    """
    Discovers network devices using CDP protocol
    Check level. In case level is 0, calls get_device_info and then get_device_list_cdp_recur.
    If level is > 0 it calls get_device_list_cdp_recur only
    seeds is list of dict, keys: ip, level, username, password

    :param seeds: list of seeds (each item contains ip, username, password, level)
    :param big_cdp_dict: dictionary of two list of found devices (hosts, nodes)
    :return big_cdp_dict: dictionary of two list of found devices (hosts, nodes)
    """



    for seed in seeds:
        if seed['level'] < 0:
            return big_cdp_dict
        if seed['level'] == 0:
            seed_item = get_device_info(seed['ip'], seed['username'], seed['passsword'])    # get info about seed device
            if not is_cdp_device_in_list(big_cdp_dict['nodes'], seed_item):
                seed_item['was_cdp_analyzed'] = True
                big_cdp_dict['nodes'].append(seed_item)
        big_cdp_dict = get_device_list_cdp_recur(seed['ip'], seed['username'], seed['password'], big_cdp_dict, seed['level'])

#   ADD INFO THAT SEED WAS CDP ANALYZED !!! ('was_cdp_analyzed'). IF level > 1

    return big_cdp_dict


def get_device_list_cdp_recur(ip_seed, username, pswd, big_cdp_dict, level):
    """
    Discovers network devices using CDP protocol by recurrent way. 'level' defines level of recurency, i.e level 0 means that only seed device is conntacted and neighbors of this device are not
    It doesn't contain info about seed device if called with level = 0 !!!
    Returs dict which contains two list. 'nodes' list contains routers, switches, ..., 'hosts' list contains phones
    Both lists contain found devices. Each item in list is dictionary whose structure is defined in get_cli_sh_cdp_neighbor function. Keys port_id, intf_id contain unusable values

    To do: ad device name which is end device (phone) connected to

    :param ip_seed: IP address of seed device
    :param username: for connection
    :param pswd: password
    :param big_cdp_dict: contains dictionary (lists of hosts and nodes) of already found devices
    :param level: the level of recurrsion
    :return big_cdp_dict: dict of found devices
    """

    this_cdp_list = []
    neigbors_to_conntact = []
    big_cdp_dict_for_neighbor = {}
    big_cdp_dict_for_neighbor['hosts'] = []
    big_cdp_dict_for_neighbor['nodes'] = []
    cdp_analyzed_item = []
    tmp_node_list = []

    try:
        net_connect = ConnectHandler(device_type='cisco_ios', ip=ip_seed, username=username, password=pswd)     # connect to seed
    except NetMikoTimeoutException:
        print("- unable to connect to the device", ip_seed, ", timeout")
        return big_cdp_dict_for_neighbor            # empty dict
    except (EOFError, SSHException):
        print("- unable to connect to the device", ip_seed, ", error")
        return big_cdp_dict_for_neighbor

    big_cdp_dict_for_neighbor['nodes'] = big_cdp_dict['nodes'][:]     # device list which is to be passed to neighbors recurently, at the beginning it is copy of obtained 'big_cdp_list'
    
    # Collect CDP info of this device
    this_cdp_list = get_cli_sh_cdp_neighbor(net_connect)        # get list of neighbors of this device
    net_connect.disconnect()
    for item in this_cdp_list:          # go through all neighbors
        if is_cdp_device_endnode(item):  # is it end node (phone, ...) ?
            big_cdp_dict['hosts'].append(item)      # add it without any checks
        else:
            is_in_list = is_cdp_device_in_list(big_cdp_dict_for_neighbor['nodes'], item)  # is new device? i.e. not already contained in big list which is to be sent recurently to other neighbors
            if is_in_list == 0:
                big_cdp_dict_for_neighbor['nodes'].append(item)                      # yes it is
                if not is_cdp_device_in_list(neigbors_to_conntact, item):
                    neigbors_to_conntact.append(item)                       # add it to neighbors which we are going to recurently call (if level > 0)
            if is_in_list == 1:     # it is already in list but value in list is not obtained using CDP
                None             # to be processed
    
    # Process each neighbor device (routers, switches) using this function recurrently (ip_seed is neighbor's IP)
    if level > 0:
        for item in neigbors_to_conntact:           # go through all newly found neighbors
            if 'Router' in item['capability'] or 'Switch' in item['capability']:        # is device router or switch?:
                if is_ip_valid(item['ip_addr']):
                    print("Going to analyze:", item['device_id'], item['ip_addr'])        # test
                    big_cdp_dict_for_neighbor['hosts'] = []     # don't pass hosts to child (otherwise they are returned back and added to target dict again)
                    neighbor_cdp_dict = get_device_list_cdp_recur(item['ip_addr'], username, pswd, big_cdp_dict_for_neighbor, level-1)    # call recurently neighbor, decrement level
                    for neigh_item in neighbor_cdp_dict['nodes']:        # go through all neighbors behind 'item'
                        if not is_cdp_device_in_list(big_cdp_dict['nodes'], neigh_item): # neigh_item not yet in big_cdp_list ?
                            big_cdp_dict['nodes'].append(neigh_item)                     # add it
                        if not is_cdp_device_in_list(big_cdp_dict_for_neighbor['nodes'], neigh_item):    #neigh_item not yet in list which is to be sent to other neighbors?
                            big_cdp_dict_for_neighbor['nodes'].append(neigh_item)                        # add it
                    for neigh_item in neighbor_cdp_dict['hosts']:
                        big_cdp_dict['hosts'].append(neigh_item)    # add hosts behind neighbor directly to target (returned) dict
                        # print("Debug - host append, seed:", ip_seed, "host ip", neigh_item['ip_addr'])
                else:
                    print("Invalid IP address:", item['ip_addr'], "device:", item['device_id'])

    # Add neighbors of "child" devices to target dict, if they are not already there. Nodes only. Hosts are already in target dict.
    for item in this_cdp_list:
        if not is_cdp_device_endnode(item):        # end nodes are already in 'hosts' list
            if not is_cdp_device_in_list(big_cdp_dict['nodes'], item):
                if level > 0:               # if level > 0, the device was analyzed using get_device_list_cdp_rec in this call of the function (couple of lines above), the info is used is range discovery
                    item['was_cdp_analyzed'] = True
                big_cdp_dict['nodes'].append(item)       # add neigbors of this current device to big_cdp_list (if they are not already there)
            else:
                if level > 0:
                    cdp_analyzed_item.append(item)      # list of items which were CDP analyzed but were already added in big_cdp_dict without this information
    for item in big_cdp_dict['nodes']:
        if is_cdp_device_in_list(cdp_analyzed_item, item):
            item['was_cdp_analyzed'] = True         # add info that item was CDP analyzed, this info is useful when range based discovery follows
        tmp_node_list.append(item)
    big_cdp_dict['nodes'] = tmp_node_list
    return big_cdp_dict


def is_cdp_device_in_list(dlist, device):
    """
    Is device contained in dlist.

    :param dlist: list of devices (list of CDP entries)
    :param device: device to be checked against dlist
    :return int: 0 - not found, 1 - found, 2 -found (but device in list was not discovered using CDP), 3 - found (and was analyzed for CDP information)
    """

    for item in dlist:
        if item['device_id'] == device['device_id']:
            if 'found_via_cdp' in item:
                if not item['found_via_cdp']:
                    return 2
            if 'was_cdp_analyzed' in item:
                if item['was_cdp_analyzed']:
                    return 3
            return 1
    return 0

def is_cdp_device_endnode(device):
    """
    Is device an end device (phone) ?

    :param device: one cdp entry dict
    :return Boolean:
    """
    if 'Phone' in device['capability'] or 'Trans-Bridge' in device['capability']:
        return True
    return False


def get_device_info(ip_addr, username, pswd):
    """
    Get information about specific device. Returns dictionary with similar structure as get_cli_sh_cdp_neighbor,
    i.e. device name, IOS version, platform

    :param ip_addr: IP address of the device
    :param username: for connection
    :param pswd: password
    :return ret_value: dictionary with device information
    """


    ret_value = {}

    try:
        net_connect = ConnectHandler(device_type='cisco_ios', ip=ip_addr, username=username, password=pswd)     # connect to seed
    except NetMikoTimeoutException:
        print("- unable to connect to the device", ip_addr, ", timeout")
        return None
    except (EOFError, SSHException):
        print("- unable to connect to the device", ip_addr, ", error")
        return None

    cli_param = "sh version"
    cli_output = net_connect.send_command(cli_param)
    found = find_regex_value_in_string(cli_output, re.compile(r"(Cisco Internetwork Operating System)"))
    if found:
        os_type = 'IOS'
    else:
        found = find_regex_value_in_string(cli_output, re.compile(r"(Cisco IOS)"))
        if found:
            os_type = 'IOS'
        else:
            found = find_regex_value_in_string(cli_output, re.compile(r"(NX-OS)"))
            if found:
                os_type = 'NX-OS'
            else:
                found = find_regex_value_in_string(cli_output, re.compile(r"(IOS-XE)"))
                if found:
                    os_type = 'IOS-XE'
                else:
                    net_connect.disconnect()
                    return None     # OS not recognized
    ret_value['ip_addr'] = ip_addr
    sh_for_domainname = net_connect.send_command("show hosts")
    net_connect.disconnect()
    domain_name = find_regex_value_in_string(sh_for_domainname, re.compile(r"\sis\s([^\n]+)\n"))
    if os_type == 'IOS':
        name = find_regex_value_in_string(cli_output, re.compile(r"([^\s]+)\suptime is"))
        ret_value['platform_id'] = find_regex_value_in_string(cli_output, re.compile(r"([^\s]+)\s\([A-Z0-9]+\)\sprocessor"))
        ret_value['version'] = find_regex_value_in_string(cli_output, re.compile(r"Version\s+([A-Za-z0-9\.\s\(\)]+),"))
    elif os_type == 'IOS-XE':
        name = find_regex_value_in_string(cli_output, re.compile(r"([^\s]+)\suptime is"))
        ret_value['platform_id'] = find_regex_value_in_string(cli_output, re.compile(r"([^\s]+)\s\([A-Z0-9]+\)\s+processor with"))
        ret_value['version'] = find_regex_value_in_string(cli_output, re.compile(r"Version\s+([A-Za-z0-9\.\s\(\)]+),"))
    elif os_type == 'NX-OS':
        name = find_regex_value_in_string(cli_output, re.compile(r"Device name:\s+([^\s]+)"))
        ret_value['platform_id'] = find_regex_value_in_string(cli_output, re.compile(r"Hardware\n\s+cisco ([^\s]+)"))
        ret_value['version'] = find_regex_value_in_string(cli_output, re.compile(r"system:\s+version\s+([A-Za-z0-9\.\s\(\)]+)\n"))
    if domain_name:
        ret_value['device_id'] = name + '.' + domain_name
    else:
        ret_value['device_id'] = name

    return ret_value






        



def get_cli_sh_vlan(handler):
    '''
    Returns VLAN table (list of dictionaries).
    acc_int - ports where vlan is in access mode (column Ports in sh vlan)
 
    '''
    vlan_list = []
    cli_param = "sh vlan"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('\n')      # split output into lines
    for line in cli_out_split:
        # 10   vlan10                           active    Eth2/3, Eth2/4, Eth2/5
        intstr = re.match(r"([0-9]+)\s+([A-Za-z0-9_\-/\.]+)\s+([a-z]+)(\s+(.*))?$", line)
        if intstr:
            acc_vlan = intstr.group(5)
            if acc_vlan:
                acc_vlan = acc_vlan.replace(' ', '')         # delete spaces
                intlist = acc_vlan.split(",")       # list VLANs
            else:
                intlist = []
            vlan_entry = {'number':intstr.group(1), 'name':intstr.group(2), 'status':intstr.group(3), 'acc_int':intlist}
            vlan_list.append(vlan_entry)
    return vlan_list

def get_cli_sh_vlan_nxos(handler):
    '''
    Returns VLAN table (list of dictionaries).
    acc_int - ports where vlan is in access mode (column Ports in sh vlan)

    Just copy of get_cli_sh_vlan. I have to rewrite it
 
    '''
    vlan_list = []
    new_vlan_found = False
    cli_param = "sh vlan"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('\n')      # split output into lines
    for line in cli_out_split:
        # 10   vlan10                           active    Eth2/3, Eth2/4, Eth2/5
        intstr = re.match(r"([0-9]+)\s+([A-Za-z0-9_\-]+)\s+([a-z]+)(\s+(.*))?$", line)
        if intstr:
            new_vlan_found = True
            acc_vlan = intstr.group(5)
            if acc_vlan:
                acc_vlan = acc_vlan.replace(' ', '')         # delete spaces
                intlist = acc_vlan.split(",")       # list VLANs
            else:
                intlist = []
            vlan_entry = {'number':intstr.group(1), 'name':intstr.group(2), 'status':intstr.group(3), 'acc_int':intlist}
            vlan_list.append(vlan_entry)
    return vlan_list

def get_cli_sh_vlan_plus(handler):
    '''
    Returns VLAN table (list of dictionaries).
    ports - ports where vlan is active (column Ports in sh vlan id)
    acc_int - ports where vlan is in access mode (column Ports in sh vlan)
    Quite long processing when lot of Vlans ...
    '''
    vlan_list = []
    cli_param = "sh vlan"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('\n')      # split output into lines
    for line in cli_out_split:
        # 10   vlan10                           active    Eth2/3, Eth2/4, Eth2/5
        intstr = re.match(r"([0-9]+)\s+([A-Za-z0-9_\-]+)\s+([a-z]+)(\s+(.*))?$", line)
        if intstr:
            acc_vlan = intstr.group(5)
            if acc_vlan:
                acc_vlan = acc_vlan.replace(' ', '')         # delete spaces
                intlist = acc_vlan.split(",")       # list VLANs
            else:
                intlist = []
            intlist2 = get_cli_sh_vlan_id_int_list(handler, intstr.group(1))    # obtain list of interfaces where VLAN is active
            vlan_entry = {'number':intstr.group(1), 'name':intstr.group(2), 'status':intstr.group(3), 'acc_int':intlist, 'ports':intlist2}
            vlan_list.append(vlan_entry)
    return vlan_list

def get_cli_sh_vlan_id_int_list(handler, vlannr):
    '''
    Returns list of interfaces displayed in sh vlan id 'vlannr'.
    '''
    cli_param = "sh vlan id " + vlannr
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('\n')      # split output into lines
    for line in cli_out_split:
        # 10   vlan10                           active    Eth2/3, Eth2/4, Eth2/5
        intstr = re.match(r"([0-9]+)\s+([A-Za-z0-9_\-]+)\s+([a-z]+)(\s+(.*))?$", line)
        if intstr:
            intf = intstr.group(5)
            if intf:
                intf = intf.replace(' ', '')         # delete spaces
                intlist = intf.split(",")       # interfaces list
            else:
                intlist = []
            return intlist          # return after first match


def get_cli_sh_etherchannel_summary(handler):
    '''
    Returns list of port-channel entries.
    Each entry is directory with Po number and list of interfaces in this port-channel

    Notice: it doesn't work with automaticaly created Po which are outside the portchanel range
    for example Po for service module on Cat6k ...
    In that case the interface list is empty
    '''
    pc_list = []
    cli_param = "sh etherchannel"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('----------')
    for block in cli_out_split:
        int_dict = {}
        int_dict['pc_number'] = find_regex_value_in_string(block, re.compile(r"Group:\s+([0-9]+)\s+\n"))
        if int_dict['pc_number']:       # port-channel number found
            int_dict['int_list'] = []
            cli_param = "sh etherchannel " + int_dict['pc_number'] + " detail"
            cli_output = handler.send_command(cli_param)
            cli_out_split2 = cli_output.split('------------')
            for block2 in cli_out_split2:       # search for interfaces in specific port-channel
                iface = find_regex_value_in_string(block2, re.compile(r"Port:\s+([A-Za-z0-9/\.]+)\n"))
                if iface:       # interface found
                    int_dict['int_list'].append(iface)
            pc_list.append(int_dict)

    return pc_list

def get_cli_sh_etherchannel_summary_nxos(handler):
    '''
    Returns list of dictionaries
    pc_number - port-channel number
    int-list

    '''

    pc_list = []
    cli_param = "sh port-channel database"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('\n\n')
    for block in cli_out_split:
        int_dict = {}
        intstr = re.match(r"port-channel([0-9]+)\n", block)
        if intstr:
            int_dict['pc_number'] = intstr.group(1)
            int_dict['int_list'] = []
            cli_out_split2 = block.split('\n')
            for line in cli_out_split2:
                intstr = re.match(r"([\sA-Za-z:]+)?Ethernet([0-9/]+)\s+\[([a-z\s]+)\]\s+\[([a-z]+)\]", line)
                if intstr:
                    int_dict['int_list'].append("Ethernet"+intstr.group(2))
            pc_list.append(int_dict)
    return pc_list

def get_cli_sh_vpc_nxos(handler):
    '''
    Returns list of VPCs, eech entry in list is directory
    id - vpc ip (i.e. 46)
    port - vpc potr (i.e. Po46) 
    status - status of VPC
    '''
    vpc_list = []
    cli_param = "sh vpc"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('vPC status')      # split output into two parts
    cli_out_split2 = cli_out_split[1].split('\n')      # process 2nd part
    for line in cli_out_split2:
        # 1      Po1         up     success     success                    1,4,10-11,1
        int_dict = {}
        intstr = re.match(r"([0-9]+)\s+([A-Za-z0-9]+)\s+([a-z\*]+).*", line)
        if intstr:
            int_dict['id'] = intstr.group(1)
            int_dict['port'] = intstr.group(2)
            int_dict['status'] = intstr.group(3)
            vpc_list.append(int_dict)
    return vpc_list

def get_cli_sh_int_status(handler):
    '''
    '''
    int_stat = []
    cli_param = "sh interface status"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('\n')      # split output into lines
    for line in cli_out_split:
        # Eth1/2        c6506_hra_vss_2/3/ connected trunk     full    10G     10Gbase-SR
        int_dict = {}
        intstr = re.match(r"([A-Za-z0-9/]+)\s+(..................)\s+([A-Za-z]+)\s+([A-Za-z0-9]+)\s+([A-Za-z]+)\s+([A-Za-z0-9]+)\s+(.*)$", line)
        if intstr:
            if intstr.group(1) == 'Port':  # line with column names
                continue
            int_dict['port'] = intstr.group(1)
            int_dict['name'] = intstr.group(2).rstrip() # remove trailing spaces, it's shortened (18 char only) version of Description field
            int_dict['status'] = intstr.group(3)
            int_dict['vlan'] = intstr.group(4)
            int_dict['duplex'] = intstr.group(5)
            int_dict['speed'] = intstr.group(6)
            int_dict['type'] = intstr.group(7)
            int_stat.append(int_dict)
    return int_stat

def get_cli_sh_int_description_dict(handler):
    """
    Returns dictionary of interface_name : {descr: 'Description'}
    :param handler: 
    :return int_dict: 
    """
    int_stat = []
    cli_param = "sh interface description"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('\n')      # split output into lines
    int_dict = {}
    for line in cli_out_split:
        # IOS
        #Lo3                            admin down     down     management o2, nnmmlan
        #Po1                            up             up       ## MEC from Po1 to c5596_hra_1 and c5596_hra_2 ##
        #Po3                            down           down
        #
        # NX-OS
        #Eth1/26       eth    10G     HP VCE 101 #ESX-X2-SEC-INT
        intstr = re.match(r"([A-Za-z0-9\/\.]+)\s+(([A-Za-z]+)(\s[A-Za-z]+)?)\s+([A-Za-z0-9]+)\s+(.*)$", line)
        if intstr: 
            interface = intstr.group(1)
            if interface == 'Port' or interface == 'Interface':     # column names
                continue
            descr = intstr.group(6)
            if descr == '--':               # NX-OS, empty description
                descr = ''
            int_dict[intstr.group(1)] = {'descr':descr}
    return int_dict

def get_cli_username(handler):
    """
    Returns list of local users defined in IOS. Each user entry is a directory.
    User directory items:
        username
        privilege - privilege level
        password
        encr_type - password/secret encryption type (0,5,7,8,9)
        has_secret - is secret instead of password configured? (True/False)
        secret

    :param handler:
    :return users:
    """
    users = []
    cli_param = "sh run | i username"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('\n')      # split output into lines
    for line in cli_out_split:
        # username cisco privilege 15 password 0 cisco
        # username ocsic privilege 15 secret 5 $1$V8kL$qgqwmi1a9IV0/6fI1y72t0
        int_dict = {}
        intstr = re.match(r"username\s+([^\s]+).*", line)
        if intstr:
            int_dict['username'] = intstr.group(1)
            int_dict['has_secret'] = False
            intstr2 = re.search(r"privilege\s+([0-9]+).*", line)
            if intstr2:
                int_dict['privilege'] = intstr2.group(1)
            else:
                int_dict['privilege'] = 1
            intstr2 = re.search(r"password\s+([0-9]+)\s+(.*)", line)
            if intstr2:
                int_dict['encr_type'] = intstr2.group(1)
                int_dict['password'] = intstr2.group(2)
                int_dict['secret'] = ''
            else:                       # password is not configured, try to find secret
                int_dict['password'] = ''
                intstr2 = re.search(r"secret\s+([0-9]+)\s+(.*)", line)
                if intstr2:
                    int_dict['encr_type'] = intstr2.group(1)
                    int_dict['secret'] = intstr2.group(2)
                    int_dict['has_secret'] = True
            users.append(int_dict)
    return users

def nxapi_post_cmd(ip, port, username, password, cmdtype, cmd, secure = True):
    '''
    Performs NXAPI command (cli_show, cli_conf) JSON POST call
    cmd is string of commands separated by ;
        example: 'vlan 333 ;name ThreeThreeThree'
        it looks like there must be space before ;
    cmdtype can be cli_show,  cli_conf
    '''
    if secure:
        proto = "https"
    else:
        proto = "http"

    my_headers = {'content-type': 'application/json'}
    url = proto+"://"+ip+":"+str(port)+"/ins"


    payload = {'ins_api': {'chunk': '0', 'version': '1.2', 'sid': '1', 'input': cmd, 'type': cmdtype, 'output_format': 'json'}}

    try:
        response = requests.post(url, data=json.dumps(payload), headers=my_headers, auth=(username, password), verify=False)
    except (requests.ConnectionError, requests.ConnectTimeout):
        except_response = {'input': cmd, 'msgs' : 'Connection Error', 'code' : '500'}
        return except_response
    
    response_json = response.json()
    return response_json['ins_api']['outputs']['output']
