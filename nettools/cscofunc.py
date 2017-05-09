''' Module implements functions which read/change configuration of Cisco equipment

'''

# pylint: disable=C0301, C0103

import sys
import re
import requests
import json


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

def get_cli_sh_int_switchport_dict(handler):
    '''
    '''
    int_dict = {}
    int_list = get_cli_sh_int_switchport(handler)
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
    intname = intname.replace('Gi', 'GigabitEthernet')
    intname = intname.replace('Te', 'TenGigabitEthernet')
    intname = intname.replace('Po', 'Port-channel')
    return intname

def get_cli_sh_cdp_neighbor(handler):
    '''
    Returns CDP table.
    '''
    cdp_list = []
    cli_param = "sh cdp entry *"
    cli_output = handler.send_command(cli_param)
    cli_out_split = cli_output.split('----------------')      # split output into blocks (list) of devices
    for block in cli_out_split:
        intstr = re.search(r"Device ID:\s+([A-Za-z0-9/._\-]+)\n", block)         # ?what characters can be in device name?
        if intstr:                                  # device name was found, process the device entry
            name = intstr.group(1)
            int_dict = {}
            int_dict['device_id'] = name
            int_dict['ip_addr'] = find_regex_value_in_string(block, re.compile(r"Entry address\(es\):\s+\n\s+IP address:\s+([0-9\.]+)\n"))
            int_dict['platform_id'] = find_regex_value_in_string(block, re.compile(r"Platform:\s+[A-Za-z]{0,20}\s?([A-Za-z0-9\.\-\s]+),")) # cisco WS-6506-E -> WS-6506-E
            cap_raw = find_regex_value_in_string(block, re.compile(r"Capabilities:\s+([A-Za-z0-9\-\s]+)\n"))
            cap_raw = cap_raw.rstrip(' ')           # remove trailing space
            int_dict['capability'] = cap_raw.split(' ')         # split capabilities int list
            int_dict['intf_id'] = find_regex_value_in_string(block, re.compile(r"Interface:\s+([A-Za-z0-9\./]+),"))
            int_dict['port_id'] = find_regex_value_in_string(block, re.compile(r" Port ID \(outgoing port\):\s+([A-Za-z0-9\./\s]+)\n"))
            int_dict['software'] = find_regex_value_in_string(block, re.compile(r"\(([A-Za-z0-9\-_]+)\),\s+Version"))
            if 'Phone' in int_dict['capability']:
                int_dict['version'] = find_regex_value_in_string(block, re.compile(r"Version\s+:\n([A-Za-z0-9\.\-]+)\n"))
            else:
                int_dict['version'] = find_regex_value_in_string(block, re.compile(r"Version\s+([A-Za-z0-9\.\s\(\)]+),"))
            cdp_list.append(int_dict)
    return cdp_list

def get_cli_sh_vlan_plus(handler):
    '''
    Returns VLAN table.
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
