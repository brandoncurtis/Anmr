#from matplotlib.backends.backend_gtk import NavigationToolbar2GTK as NavigationToolbar2
from matplotlib.backends.backend_gtkagg import NavigationToolbar2GTKAgg as NavigationToolbar2
import subprocess
import shlex
import re
import posixpath
from anmr_common import *

# use hub4com ?
USE_SERIAL_PIPE=False

#external helper programs:
#hub4com is quoted differently than sox because its arguments are tricky.
HUB4COM='C:\\Program Files\\hub4com\\hub4com.exe'
SOX_EXEC='"c:\\Program Files\\sox-14-4-0\\sox.exe"'
AVRDUDE='c:\\Anmr\\avrdude\\avrdude.exe'
AVRDUDE_CONF='C:\\Anmr\\avrdude\\avrdude.conf'

#standard windows install:
IMAGE_VIEWER = 'rundll32.exe "c:\\WINDOWS\\System32\\shimgvw.dll,ImageView_Fullscreen"'

#Anmr installs:
#this one is also in Shim.py
ICON_PATH='c:\\Anmr\\Icons'

#our firmware
#ARDUINO_CODE = 'c:\\Anmr\\arduinoCode'
FIRMWARE='c:\\Anmr\\arduinoCode\\arduinoCode.hex'

#pulse programs:
PROG_DIR = 'c:\\Anmr\\PulsePrograms'

#pulse program header file:
HEADER_NAME = 'defaults.include'

#hardware config
# board : atmega328 for duemilanove
# board is uno for uno
# if ARDUINO_DEV is None, we'll guess
# otherwise all of these must be set.
ARDUINO_DEV = 'auto'
ARDUINO_BOARD = 'auto'

#these are com0com fake ports used for a serial pipe.
HUB1 = None #autodetect
HUB2 = None

################ End of configuration variables. TMPDIR is in anmr_common

#To force DEV and BOARD settings: 
#ARDUINO_DEV is something like: 'COM3'
#ARDUINO_BOARD is 'uno' or 'atmega328'
#it's used by scons -> avrdude to program it.


#eg ARDUINO_DEV='COM6' HUB1='COM7' HUB2='COM8'

ICON_EXTENSION="24.xpm"

# used to find serial ports:
try:
    import winreg as winreg
except:
    import _winreg as winreg
import itertools


#used to list processes
import win32com.client
import ctypes

class MyToolbar(NavigationToolbar2):
#idea borrowed from: http://dalelane.co.uk/blog/?p=778
# but redone a bit differently.

# we inhereit the navigation toolbar, but redefine the toolitems

    # list of toolitems to add to the toolbar, format is:
    # text, tooltip_text, image_file, callback(str)
    toolitems = (
        ('Home', 'Reset original view', 'home', 'home'),
        ('Back', 'Back to  previous view','back', 'back'),
        ('Forward', 'Forward to next view','forward', 'forward'),
        ('Pan', 'Pan axes with left mouse, zoom with right', 'move','pan'),
        ('Zoom', 'Zoom to rectangle','zoom_to_rect', 'zoom'),
        (None, None, None, None),
#        ('Subplots', 'Configure subplots','subplots.png', 'configure_subplots'),
        ('Save', 'Save the figure','filesave', 'save_figure'),
        )




#windows specific count serial ports:
def enumerate_serial_ports():
    """ Uses the Win32 registry to return an iterator of serial 
        (COM) ports existing on this computer.
    """
    path = 'HARDWARE\\DEVICEMAP\\SERIALCOMM'
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
    except WindowsError:
        raise IterationError

    for i in itertools.count():
        try:
            val = winreg.EnumValue(key, i)
            yield (str(val[1]), str(val[0]))
        except EnvironmentError:
            break


def pipeRunning(tempDir): #tempDir is ignored here, is used in linux version
# this is simplified from:
# http://www.blog.pythonlibrary.org/2010/10/03/how-to-find-and-list-all-running-processes-with-python/
    head,tail = os.path.split(HUB4COM)
    wmi=win32com.client.GetObject('winmgmts:')
    for p in wmi.InstancesOf('win32_process'):
#        if p.Name == 'hub4com.exe':
        if p.Name == tail:
            return True
    return False

def detectArduino(tempDir): #tempDir is ignored here, used in linux version
    global ARDUINO_DEV,ARDUINO_BOARD,HUB1,HUB2
    myArduinoDev = ARDUINO_DEV
    if myArduinoDev == 'auto':
        ARDUINO_BOARD = 'auto'
        HUB1 = None
        HUB2 = None
        for port, desc in enumerate_serial_ports():
            print("port: ",port," desc: ",desc)
            if desc[8:15] == 'com0com':
                if HUB1 is None:
                    HUB1 = port
                    print('first pseudo port is: ',HUB1)
                elif HUB2 is None:
                    HUB2 = port
                    print('second pseudo port is: ',HUB2)
            if desc[8:11] == 'VCP':
                print('deumilanove at: ',port)
                myArduinoDev = port
                ARDUINO_BOARD='atmega328'
            if desc[8:14] == 'USBSER':
                print('found Uno at:',port)
                myArduinoDev = port
                ARDUINO_BOARD = 'uno'
    if myArduinoDev == 'auto' or (USE_SERIAL_PIPE == True and (HUB1 is None or HUB2 is None)):
        print("have a missing device?")
        print("ARDUINO_DEV: ", myArduinoDev)
        print("HUB1: ",HUB1)
        print("HUB2: ",HUB2)
        #popup_msg("Couldn't find a serial device?")
        return None,None,None,None
    if USE_SERIAL_PIPE:
        return myArduinoDev,HUB2,ARDUINO_BOARD,'software'
    else:
        return myArduinoDev,myArduinoDev,ARDUINO_BOARD,'hardware'

def startSerialPipe(hardwareDev,arduinoDev):
    #in here arduinoDev is ignored, used in linux version. We link the 
    #hardwareDev to HUM1, then HUB2 is what's talked to.
        args = [HUB4COM,'--route=All:All','--octs=off','--baud=1000000','\\\\.\\'+hardwareDev,'--baud=1000000','\\\\.\\'+HUB1]
        print('args are:',args)
        try:
            proc = subprocess.Popen(args)
            #should do a better job of checking this?
            return True
        except:
            return False

def killSerialPipe(tempDir):
    head,tail = os.path.split(HUB4COM)
    wmi=win32com.client.GetObject('winmgmts:')
    for p in wmi.InstancesOf('win32_process'):
#        if p.Name == 'hub4com.exe':
        if p.Name == tail:
            pid = int(p.Properties_('ProcessId'))
            print('Found: ',p.Name, 'pid: ',pid, ' Killing.')

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(1,0,pid)
            kernel32.TerminateProcess(handle,0)
    #it still gets detected unless we wait a moment:
    time.sleep(0.1)
    if pipeRunning(None) == False:
        print('successfully killed hub4com')
        return True
    print('tried to kill hub4com, but seems to still be running')
    return False
