# pylint: disable=C0301, C0103, E0401, C0413

import sys
import getpass
import getopt
import os

scriptPath = os.path.realpath(os.path.dirname(sys.argv[0]))
os.chdir(scriptPath)


import cscofunc
import prtgfunc

def main():
    ''' Main

    The utility prints info about specific PRTG sensors of sensors defined defined under specific object (device, group)

    '''
    usage_str = '''
    Usage: prtgsensors.py [OPTIONS]
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
    sensorlist = []
    days_paused = 0
    obj_id = 0
    
    argv = sys.argv[1:]

    try:
        opts, args = getopt.getopt(argv, "hp:i:u:d:o:", ["help", "password=", "ipaddr=", "username=", "days=", "objid="])
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

    sensor_type = prtgfunc.get_objectid_type(ip_prtg, username, passhash, obj_id)
    if sensor_type == 0:
        print("Object ID "+str(obj_id)+" doesn't exist")
        sys.exit(0)
    if sensor_type == 999:
        print("Object ID "+str(obj_id)+" error")
        sys.exit(0)
    print('--------------')
    print('Sensors status')
    print('--------------')
    if sensor_type == 3:    # process sensor
        sensor = prtgfunc.get_sensor(ip_prtg, username, passhash, obj_id)
        sensorlist.append(sensor)
        prtgfunc.print_sensors_info(sensorlist)
    elif sensor_type == 2:    # device
        outlistlist = prtgfunc.get_sensors_under_device(ip_prtg, username, passhash, obj_id)
        for item in outlistlist['table']:
            sensor = prtgfunc.get_sensor(ip_prtg, username, passhash, item['objid'])
            sensorlist.append(sensor)
        prtgfunc.print_sensors_info(sensorlist)
    elif sensor_type == 1:    # process group
        devices = prtgfunc.get_device_list(ip_prtg, username, passhash, obj_id)
        for device in devices['devices']:
            print('')
            print('=================================')
            print('Device: '+device['device']+', Group:'+device['group'])
            print('=================================')
            outlistlist = prtgfunc.get_sensors_under_device(ip_prtg, username, passhash, device['objid'])
            for item in outlistlist['table']:
                sensor = prtgfunc.get_sensor(ip_prtg, username, passhash, item['objid'])
                sensorlist.append(sensor)
            prtgfunc.print_sensors_info(sensorlist)



if __name__ == "__main__":
     main()

