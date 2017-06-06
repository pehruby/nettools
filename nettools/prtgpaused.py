# pylint: disable=C0301, C0103, E0401, C0413

import sys
import getpass
import getopt
import os

scriptPath = os.path.realpath(os.path.dirname(sys.argv[0]))
os.chdir(scriptPath)


import cscofunc
import prtgfunc


def print_paused(devices):
    """
    """

    print("Device;host;prtg_id;message;location")
    for device in devices:
        print(device['device']+';'+device['host']+';'+str(device['objid'])+';'+device['message_raw']+';'+device['location_raw'])

def main():
    ''' Main
    '''
    usage_str = '''
    Usage: prtgpaused.py [OPTIONS]
    -h,     --help                      display help
    -i,     --ipaddr                    IP address of PRTG server
    -u,     --username                  username
    -p,     --password                  password, optional
    -d,     --days                      more than days paused, default 0
    -o,     --objid                     PRTG object id where to start, default 0
    '''
    username = ''
    pswd = ''
    ip_prtg = ''
    days_paused = 0
    obj_id = 0
    
    argv = sys.argv[1:]

    try:
        opts, args = getopt.getopt(argv, "hp:i:u:d:o:", [ "help" "password=", "ipaddr=", "username=", "days=", "objid="])
    except getopt.GetoptError:
        print(usage_str)
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print(usage_str)
            sys.exit()

        elif opt in ("-u", "--username"):
            username = arg
        elif opt in ("-i", "--ipaddr"):
            ip_prtg = arg
        elif opt in ("-p", "--password"):
            pswd = arg
        elif opt in ("-d", "--days"):
            days_paused = int(arg)
        elif opt in ("-o", "--objid"):
            obj_id = int(arg)




    # sanity checks
    if ip_prtg and (not cscofunc.is_ip_valid(ip_prtg)):
        print("Invalid IP address")
        sys.exit(2)
    if not username:
        print("Username is not specified")
        sys.exit(2)

    
    if pswd == '':
        pswd = getpass.getpass('Password:')


    passhash = prtgfunc.get_passhash(ip_prtg, username, pswd)
    if passhash == 'Error':
        print('Error - invalid credentials')
        sys.exit(2)
    output = prtgfunc.get_device_list(ip_prtg, username, passhash, obj_id)
    output2 = prtgfunc.get_paused_dev_list(output['devices'], days_paused)
    print_paused(output2)

if __name__ == "__main__":
    main()

