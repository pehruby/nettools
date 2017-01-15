# pylint: disable=C0301, C0103

import sys
import getpass
import re
import getopt
import os
from netmiko import ConnectHandler


def get_intlist_vlan(handler, vlan):
    ''' Returns list of all (both access andf trunks) interfaces where VLAN vlan is configured

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
                outset.append(str(subit))       # add number inside the range to output set
        else:
            outset.append(item)            # add number inputy set to output set
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
        tmps = intstr.group(1)
        tmps = tmps.replace('ALL', '1-4096')
        tmps = tmps.replace('\n', '')        # delete newlines
        tmps = tmps.replace(' ', '')         # delete spaces
        vlanlist = tmps.split(",")       # list VLANs
        #print(vlanlist)
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
            sys.exit("\n\nInvalid IP address: %s\n" % testedip)



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

    if isinstance(vnum, int):
        if vnum > 0 and vnum < 4097:
            return True
    return False


def process_cfg_file(fname):
    ''' Read IP addresses from cfg file
    '''
    # iplist = []
    if os.path.isfile(fname):        # check file exists
        try:
            with open(fname) as data_file:
                loadedfile = data_file.read()
        except IOError:
            print("Unable to read the file", fname)
            exit(1)
    else:
        print("Cannot find the file", fname)
        exit(1)
    loadedfile = loadedfile.replace(' ', '')         # delete spaces
    iplist = loadedfile.split("\n")
    iplist = list(filter(None, iplist))         # delete empty lines
    for ips in iplist:
        if not is_ip_valid(ips):
            print("Invalid IP address in config file:", ips)
            exit(1)
    return iplist



# ============================ Main ==========================================

def main():
    ''' Main
    '''

    usage_str = '''
    Usage: addvlan.py [OPTIONS]
    -v,     --verbose                   verbose
    -h,     --help                      display help
    -w,     --writeconf                 write device configuration after config change (wr m)
    -i,     --ipaddr                    IP address of the switch
    -a,     --action                    test, t, process, p
    -u,     --username                  username
    -p,     --password                  password, optional
    -c,     --cfgfile                   cfg file with IP addresses list, one IP per line
    -v,     --vlan                      vlan already configured in allowed list on trunk
    -n,     --newvlan                   new vlan added to allowed list
    '''

    int_trunk_list = []     # list of interfaces where vlan is configured and interface is in trunk mode
    device_ip_list = []       # list of IPs of devices whose configuration is going to be changed
    ip_of_switch = ''
    config_file = ''
    vlan_match = ''
    vlan_new = ''
    username = ''
    debug = False
    pswd = ''
    paction = 't'       # test mode is default
    write_conf = False

    argv = sys.argv[1:]

    try:
        opts, args = getopt.getopt(argv, "vwhp:i:c:u:a:m:n:", ["verbose", "help", "writeconf", "password=", "ipaddr=", "cfgfile=", "username=", "action=", "matchedvlan=", "newvlan="])
    except getopt.GetoptError:
        print(usage_str)
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print(usage_str)
            sys.exit()
        elif opt in ("-v", "--verbose"):
            debug = True
        elif opt in ("-w", "--write"):
            write_conf = True
        elif opt in ("-u", "--username"):
            username = arg
        elif opt in ("-i", "--ipaddr"):
            ip_of_switch = arg
        elif opt in ("-p", "--password"):
            pswd = arg
        elif opt in ("-c", "--cfgfile"):
            config_file = arg
        elif opt in ("-a", "--action"):
            paction = arg
        elif opt in ("-m", "--matchedvlan"):
            vlan_match = arg
        elif opt in ("-n", "--newvlan"):
            vlan_new = arg

    # sanity checks
    if (not ip_of_switch) and (not config_file):        # both variables are empty
        print("No IP address specified")
        print(ip_of_switch)
        sys.exit(2)
    if ip_of_switch and config_file:
        print("Both IP address and config file are specified")
        sys.exit(2)
    if ip_of_switch and (not is_ip_valid(ip_of_switch)):
        print("Invalid IP address")
        sys.exit(2)
    if not vlan_match:
        print("VLAN to be matched is not specified")
        sys.exit(2)
    if not vlan_new:
        print("New VLAN is not specified")
        sys.exit(2)
    if not username:
        print("Username is not specified")
        sys.exit(2)

    if pswd == '':
        pswd = getpass.getpass('Password:')

    if config_file:
        device_ip_list = process_cfg_file(config_file)  # list will contain IPs from config file
    else:
        device_ip_list.append(ip_of_switch) # list will contain only IP of one device

    print("")
    if paction == 't':
        print("Script is running in test mode. Devices configuration will not be affected")
    elif paction == 'p':
        print("Script is running in process mode. Devices Configuration WILL BE CHANGED !!!")

    for switch in device_ip_list:           # go throug all switches
        print("\nProcessing device:", switch)
        net_connect = ConnectHandler(device_type='cisco_ios', ip=switch, username=username, password=pswd)
        if not is_it_switch(net_connect):
            print("-device is probably not a switch")
            continue
        int_list = get_intlist_vlan(net_connect, vlan_match)    # get interfaces list where specific vlan configured

        if int_list:    # is any interface configured in vlan_match ?
            for interface in int_list:      # select trunk interfaces where "allowed vlans" command is configured
                #print("Interface: " + interface)
                tmplist = list_trunking_vlans_enabled(net_connect, interface) # trunks only
                #print(tmplist)
                if is_int_admin_trunk(net_connect, interface) and is_int_allowed_vlan_configured(net_connect, interface):
                    int_trunk_list.append(interface)


            #print(int_list)
            #print(int_trunk_list)
            for interface in int_trunk_list:
                if paction == 't':    # test only
                    print("-interface", interface, "would have been changed (test mode)")
        else:
            print("-no interface configured in Vlan", vlan_match)

        net_connect.disconnect()        # disconnect from the switch

if __name__ == "__main__":
    main()




