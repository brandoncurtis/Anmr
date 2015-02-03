from matplotlib.backends.backend_gtk import NavigationToolbar2GTK as NavigationToolbar2GTK
from matplotlib.backends.backend_gtkagg import NavigationToolbar2GTKAgg as NavigationToolbar2GTKAgg
from matplotlib import __version__ as matplotlib_version
import subprocess
import shlex
from anmr_common import *

# use socat?
#USE_SERIAL_PIPE = True
USE_SERIAL_PIPE = False

#external helper programs:
SOCAT='/usr/bin/socat'
SOX_EXEC='/usr/bin/sox'
AVRDUDE='/usr/share/arduino/hardware/tools/avrdude'
AVRDUDE_CONF='/usr/share/arduino/hardware/tools/avrdude.conf'
IMAGE_VIEWER = "/usr/bin/eog -n"
KILLALL = "/usr/bin/killall"

#Anmr installs:
#this is also in Shim.py
ICON_PATH='/usr/local/share/Anmr/Icons'

#our firmware
#ARDUINO_CODE = '/usr/local/share/Anmr/arduinoCode'
FIRMWARE='/usr/local/share/Anmr/arduinoCode/arduinoCode.hex'

#pulse programs:
PROG_DIR = '/usr/local/share/Anmr/PulsePrograms'

#pulse program header file:
HEADER_NAME = 'defaults.include'

#hardware config
#these will force us to guess - if ttyACM0 exists, we'll assume uno
#if not, we'll try ttyUSB0 and assume deumillanove (atmega328) 
ARDUINO_DEV = 'auto'
ARDUINO_BOARD = 'auto'

################ End of configuration variables. TMPDIR is in anmr_common

#To force DEV and BOARD settings: 
#ARDUINO_DEV is something like: /dev/ttyUSB0 or /dev/ttyACM0
#ARDUINO_BOARD is used by scons -> avrdude to program it. 'uno' or 'atmega328'

###### for Deumillanove
#ARDUINO_DEV = '/dev/ttyUSB1'
#ARDUINO_BOARD = 'atmega328'

###### for Uno:
#ARDUINO_DEV = '/dev/ttyACM0'
#ARDUINO_BOARD = 'uno'

# the linux cdc-acm module needed for the arduino uno has a nasty habit of resetting the
# uno on every open of the file descriptor. To avoid it, we call socat to
# pipe the arduino to a pty, and then we talk to the pty.
PTY_FILE="anmr-pty"

ICON_EXTENSION=".svg"

#platform specific since the file names seem to change on windows
class MyToolbar(NavigationToolbar2GTKAgg):
#idea borrowed from: http://dalelane.co.uk/blog/?p=778
# but redone a bit differently.

# we inhereit the navigation toolbar, but redefine the toolitems

    # list of toolitems to add to the toolbar, format is:
    # text, tooltip_text, image_file, callback(str)
    vers = matplotlib_version.split('.')
    if int(vers[0]) <= 1 and int(vers[1]) < 2:
        toolitems = ( #icon names are different in older versions
            ('Home', 'Reset original view', 'home.png', 'home'),
            ('Back', 'Back to  previous view','back.png', 'back'),
            ('Forward', 'Forward to next view','forward.png', 'forward'),
            ('Pan', 'Pan axes with left mouse, zoom with right', 'move.png','pan'),
            ('Zoom', 'Zoom to rectangle','zoom_to_rect.png', 'zoom'),
            (None, None, None, None),
            #        ('Subplots', 'Configure subplots','subplots', 'configure_subplots'),
            ('Save', 'Save the figure','filesave.png', 'save_figure'),
            )
    else:
        toolitems = ( #first home used to be home.png etc
            ('Home', 'Reset original view', 'home', 'home'),
            ('Back', 'Back to  previous view','back', 'back'),
            ('Forward', 'Forward to next view','forward', 'forward'),
            ('Pan', 'Pan axes with left mouse, zoom with right', 'move','pan'),
            ('Zoom', 'Zoom to rectangle','zoom_to_rect', 'zoom'),
            (None, None, None, None),
            #        ('Subplots', 'Configure subplots','subplots', 'configure_subplots'),
            ('Save', 'Save the figure','filesave', 'save_figure'),
            )


def pipeRunning(tempDir):
    pipeName = os.path.join(tempDir,PTY_FILE)
    try:
        os.stat(pipeName)
        return True
    except:
        return False

def detectArduino(tempDir):
    global ARDUINO_DEV, ARDUINO_BOARD
    if ARDUINO_DEV == 'auto':
        try:
            print('looking for uno')
            os.stat('/dev/ttyACM0')
            print('found an uno!')
            ARDUINO_DEV='/dev/ttyACM0'
            ARDUINO_BOARD='uno'
        except:
            pass
    if ARDUINO_DEV == 'auto':
        try:
            print('looking for deum:')
            os.stat('/dev/ttyUSB0')
            print('found a deum')
            ARDUINO_DEV='/dev/ttyUSB0'
            ARDUINO_BOARD='atmega328'
        except:
            return None,None,None,None
    if USE_SERIAL_PIPE:
        print('devices: ',ARDUINO_DEV,os.path.join(tempDir,PTY_FILE),ARDUINO_BOARD,'software')
        return ARDUINO_DEV,os.path.join(tempDir,PTY_FILE),ARDUINO_BOARD,'software'
    else:
        print('devices: ',ARDUINO_DEV,ARDUINO_DEV,ARDUINO_BOARD,'hardware')
        return ARDUINO_DEV,ARDUINO_DEV,ARDUINO_BOARD,'hardware'

def startSerialPipe(hardwareDev,arduinoDev):
    call = SOCAT+' pty,raw,echo=0,link='+arduinoDev+',mode=666 '+ hardwareDev+',raw,echo=0,b1000000'
    print('call for socat is: ',call)
    args=shlex.split(call)
    try:
        subprocess.Popen(args)
        return True
    except:
        return False



def killSerialPipe(tempDir):
    head,tail = os.path.split(SOCAT)
    call = KILLALL + ' '+ tail
    args =shlex.split(call)
    print('trying to kill socat with: ',call)
    try:
        subprocess.Popen(args)
        time.sleep(.05) # need to let the kill do its thing before we check to see if it worked.
        print('call to kill socat completed')
    except:
        pass
    if pipeRunning(tempDir) == False:
        return True
    return False
