## ---------------------------------------------------------------------------------------------------------------------------------------------------------------
#
#   rtl_process.py
#    process rtl_433 hits, compare againse a known list if if temperature log to influx
# --------------------------------------------------------------------------------------------------------------------------------------------------------------
import sys
from subprocess import PIPE, Popen, STDOUT
from threading  import Thread
import json
#   import urllib
import datetime
from influxdb import InfluxDBClient

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
#rtl_433 '-M', 'level', '-M', 'time', '-F', 'json', '-f', '433.92M', '-f', '868.045M', '-H', '600'  -F csv:rtl.csv
cmd = [ '/usr/local/bin/rtl_433', '-M', 'level', '-M', 'time', '-F', 'json', '-f', '433.92M', '-f', '868.045M', '-H', '6000']
#cmd = [ '/usr/local/bin/rtl_433', '-F', 'json']
encoding = 'utf-8'
def nowStr():
    return( datetime.datetime.now().strftime( '%Y-%m-%d %H:%M:%S'))
#   We're using a queue to capture output as it occurs
try:
    from Queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty  # python 3.x
ON_POSIX = 'posix' in sys.builtin_module_names

def enqueue_output(src, out, queue):
    temp=out
    for line in iter(out.readline,''):
        queue.put(( src, line))
    out.close()
def model_in_list(json_data):
    #print("------checking if in linst-----------------------")
    models_to_exlude =['Bresser-3CH','Toyota','Schrader-EG53MA4','Ford','Abarth 124 Spider','Efergy-e2CT','Springfield-Soil','Schrader','Renault','Citroen','Ford-CarRemote','Sharp-SPC775','Rubicson-Temperature','Acurite-Tower','Oregon-SL109H']
    if 'model'  in json_data:
        for model in models_to_exlude:
            if model == str(json_data['model']):
                #print("RETURNING TRUE")
                return True
    else:
        #print("RETURNING FALSE")
        return False


#   Create our sub-process...
#   Note that we need to either ignore output from STDERR or merge it with STDOUT due to a limitation/bug somewhere under the covers of "subprocess"
#   > this took awhile to figure out a reliable approach for handling it...
p = Popen( cmd, stdout=PIPE, stderr=STDOUT, bufsize=1, close_fds=ON_POSIX)
q = Queue()

t = Thread(target=enqueue_output, args=('stdout', p.stdout, q))

t.daemon = True # thread dies with the program
t.start()

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
client = InfluxDBClient('server', 'port', 'user', 'passs','dbname')
record = {}
pulse = 0
sys.stdout.write('running....\n')

while True:
    #   Other processing can occur here as needed...

    try:
        src, line = q.get(timeout = 1)
    except Empty:
        pulse += 1
    else: # got line
        pulse -= 1
        line_string = str(line,encoding)
        matched=False
        #sys.stdout.write(line_string.find("{"))
        #   See if the data is something we need to act on...
        if (line_string.find("{") >= 0):
            data = json.loads(line_string)
            if ( line_string.find("Fineoffset-WH1050") != -1):
                matched=True
                model = str(data['model'])
                temperature = str(data['temperature_C']) 
            if ( line_string.find("Nexus-TH") != -1):
                matched=True
                model = str(data['model'])
                temperature = str(data['temperature_C'])
            if ( line_string.find("Fineoffset-WH2") != -1):
                matched=True
                model = str(data['model'])
                temperature = str(data['temperature_C'])
            if ( line_string.find("GT-WT02") != -1):
                matched=True
                model = str(data['model'])
                temperature = str(data['temperature_C'])    
            if ( line_string.find("Prologue-TH") != -1):
                matched=True
                model = str(data['model'])
                temperature = str(data['temperature_C'])
            if (matched == False) and not model_in_list(data):
                if 'model'  in data:
                    model_str = str(data['model'])
                else:
                    model_str = ""
                if 'freq'  in data:
                    freq_str = str(data['freq'])
                else:
                    freq_str = ""
                sys.stdout.write('\n'+ nowStr()+':'+ model_str+':'+ freq_str+ ': keys==')
                for key, value in data.items():
                    sys.stdout.write(':'+key+ ','+str(value))
                #sys.stdout.write('\n')
            if (( line_string.find( 'Failed') != -1) or ( line_string.find( 'No supported devices') != -1)):
                sys.stdout.write( '   >>>---> ERROR, exiting...\n\n')
                exit( 1)
            #---write to infux---
            if matched:
                sys.stdout.write('.')
                json_body = [
                        {
                            "measurement": "°C",
                            "tags": {
                                "model": model,
                                "type": "rtl"
                            },
                            "time": str(datetime.datetime.utcnow()),
                            "fields": {
                                "temperature": float(temperature)
                            }
                        }
                    ]
                #print("Write points: {0}".format(json_body))
                client.write_points(json_body)
    sys.stdout.flush()
