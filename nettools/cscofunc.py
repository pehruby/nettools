''' Module implements functions which read/change configuration of Cisco equipment

'''

# pylint: disable=C0301, C0103

import sys
import re

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

def get_dyn_mac_address_table(handler):
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
        if match:
            vlan = intstr.group(1)
            if vlan not in mactable.keys():
                mactable[vlan] = []
            mactable[vlan].append({'mac':intstr.group(2), 'int':intstr.group(3)})


    return mactable

def get_vlan_list_trunk(macadrtab, trunk):
    '''
    Returns list of VLANs which are visible on trunk based on mac address table list
    '''
    vlanlist = []
    for vlan in macadrtab.keys():
        for item in macadrtab[vlan]:
            if item['int'] == trunk:
                vlanlist.append(vlan)
                break
    return vlanlist


def get_ip_int_list(handler):
    ''' Returns directory of L3 interfaces with valid IP address configured like this:
    {'Vlan904': {'status': 'up', 'protocol': 'up', 'ip': '192.168.100.33'},'Vlan555': {'status': 'up', 'protocol': 'up', 'ip': '10.76.77.254'}}

    '''
    ip_l3_table = {}
    cli_param = "sh ip interface brief"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('\n')
    for line in cli_out_split:
        intstr = re.match(r"([a-zA-Z0-9/.]+)\s+([0-9a-z.]+)\s+(YES|NO)\s+(NVRAM|unset)\s+(([a-z]+(\sdown)?))\s+([a-z]+)\s+$", line)
        if intstr:
            if is_ip_valid(intstr.group(2)):
                ip_l3_table[intstr.group(1)] = {'ip':intstr.group(2),'status':intstr.group(6),'protocol':intstr.group(8)}
    return ip_l3_table

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




def get_sh_int_switchport(handler):
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
            int_dict['int'] = name
            int_dict['switchport'] = find_regex_value_in_string(block, re.compile(r"Switchport:\s([A-Za-z]+)\n"))
            int_dict['admin_mode'] = find_regex_value_in_string(block, re.compile(r"Administrative Mode:\s([A-Za-z\s]+)\n"))
            int_dict['oper_mode'] = find_regex_value_in_string(block, re.compile(r"Operational Mode:\s([A-Za-z\s]+)"))
            int_dict['admin_trunc_enc'] = find_regex_value_in_string(block, re.compile(r"Administrative Trunking Encapsulation:\s([A-Za-z0-9\.]+)\n"))
            int_dict['trunk_negot'] = find_regex_value_in_string(block, re.compile(r"Negotiation of Trunking:\s([A-Za-z0-9\.]+)\n"))
            int_dict['access_mode_vlan'] = find_regex_value_in_string(block, re.compile(r"Access Mode VLAN:\s([0-9]+).+\n"))
            int_dict['trunk_native_mode_vlan'] = find_regex_value_in_string(block, re.compile(r"Trunking Native Mode VLAN:\s([0-9]+).+\n"))
            int_dict['admin_native_vlan_tagging'] = find_regex_value_in_string(block, re.compile(r"Administrative Native VLAN tagging:\s([A-Za-z0-9\.]+)\n"))
            int_dict['voice_vlan'] = find_regex_value_in_string(block, re.compile(r"Voice VLAN:\s([A-Za-z0-9]+)\n"))
            int_dict['bundle_member'] = find_regex_value_in_string(block, re.compile(r"member of bundle\s(Po[0-9]+)\)"))
            tmps = find_regex_value_in_string(block, re.compile(r"Trunking VLANs Enabled:\s([A-Za-z0-9,\-\s]+)\n"))
            vlanlist = process_raw_vlan_list(tmps)          # remove spaces, newlines
            vlanlist = normalize_vlan_list(vlanlist)        # convert vlan ranges (i.e.5-300, ...) to list
            int_dict['trunk_vlans'] = vlanlist
            sp_list.append(int_dict)

    return sp_list

def process_raw_vlan_list(rawlist):
    ''' Process raw list of trunk vlan numbers obtained from show command, i.e. removes spaces, newlines,...
    '''
    rawlist = rawlist.replace('ALL', '1-4096')
    rawlist = rawlist.replace('\n', '')        # delete newlines
    rawlist = rawlist.replace(' ', '')         # delete spaces
    vlanlist = rawlist.split(",")       # list VLANs
    return vlanlist

def find_regex_value_in_string(sstring,regexp):
    '''
    Searches for regexp group(1) inside sstring
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
    intname.replace('Gi', 'GigabitEthernet')
    intname.replace('Te', 'TenGigabitEthernet')
    intname.replace('Po', 'Port-channel')
    return intname
