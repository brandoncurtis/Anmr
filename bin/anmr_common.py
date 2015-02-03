from __future__ import division
from __future__ import print_function

import time
import serial
import sys
import gtk
import os
import tempfile
import numpy
import struct

from threading import Thread
#import multiprocessing
import gc
import gobject

import anmr_compiler

VER = sys.version_info[0]

if sys.platform == "linux2":
    from anmr_platform_linux import *
elif sys.platform == "win32":
    from anmr_platform_win import *

IDENTIFIER = b'ANMR v0.9, Ready\r\n'
TMP_DIR = tempfile.gettempdir()
TEMP_DIR=os.path.join(TMP_DIR,'Anmr')
TEMP_PROG_NAME=os.path.join(TEMP_DIR,"anmr-prog.txt")
TEMP_BIN_PROG=os.path.join(TEMP_DIR,"anmr-prog.bin")
LOCKFILE=os.path.join(TEMP_DIR,"anmr-lockfile")

CLASS_USE = False
# sets image path different, and forces EXPERTMODE off

#if true, get extra options - arduino/soundcard input in FuncGen
#multi-echo processing in Anmr
#and can turn off auto alignment and circle corrections in image reconstruction.
EXPERTMODE = True

if CLASS_USE:
    EXPERTMODE = False

#104 us is the time per point we get from the arduino.
TIME_STEP=.000104

inited=False # True means we've talked successfully to the arduino in the past.
arduinoDev = None # the device we open to talk to, either a serial pipe or hardware
hardwareDev = None # the actual hardware device
portType = None #is arduinoDev hardware or software?
ardSer = None # the serial device 
arduinoBoard = None # uno or atmega328
        

def popupIdleWrap(message,win=None):
    popup_msg(message,win)
    return False
           
class popup_msg:

    def __init__ (self,message,window = None):
        dialog = gtk.Dialog("Anmr",window)
        label = gtk.Label(message)
        dialog.vbox.pack_start(label,True,True,0)
        button = gtk.Button("Okay")
        dialog.vbox.pack_end(button,True,True,0)
        button.connect_object("clicked", self.killDialog, dialog)
        dialog.show_all()
                
    def killDialog(self, toBeKilled):
        toBeKilled.destroy()
        return

def calc_lims(min,max):
    spread = (max-min)*1.1/2
    if spread == 0:
        spread = 0.1
    mid = (max+min) /2.
    max = mid+spread
    min = mid-spread
    return (min,max)


def readAFile(filename):
#    print 'in readFile with name:', filename
# if points has some value, we'll truncate to that many, or pad with zeros.
#unless we got  no points
    try:
        inFile = open(filename)
        lines = inFile.readlines()
        if lines == []:
            inFile.close()
            print('empty file, no lines')
            return [-1,-1]
        if lines[0][0] == '#':
            numScans = int(lines[0][1:])
            start = 1
        else:
            numScans = 0
            start = 0
        tnums = numpy.array(lines[start:])
        inFile.close()
        return [tnums.astype(int),numScans]
    except:
        inFile.close()
        return [-1,-1]

abort = False
def setAbortFlag():
    global abort
    print('setting abort flag')
    abort = True


def runProgram(dataFileName,data,scans): 
    global ardSer,abort
    abort = False
    try:
        runReading = True
        adata = "" #this will be the string of data for all the reads
#returns a retVal = 1 is ok, the data
#        ardSer.timeout=0.2 
        ardSer.timeout=1 #I'd rather do this after the readline, but
# on windows we sometimes lose characters if we change timeouts
# after the readline.
#        stime = time.time()
        ardSer.flushInput() #windows seems to need this.
        ardSer.write(b'\x09') # go is 9
#        print 'wrote go'
#        print 'after write: ',time.time()-stime
        line = ardSer.readline()
#        print 'after read: ',time.time()-stime
#        print ('read: ',line)
        if line[0:9] != b'Executing':
            return "Arduino didn't start up correctly",None
#        print ('with len:',len(line))
        dat_list = bytearray()
        while runReading:
            line = b''
            #read a line, with periodic checks for abort flag.
            for i in range(20): # 20 s to start receiving data
#                print 'bytes for line waiting: ',ardSer.inWaiting()
#                print 'before read: ',time.time()-stime
                fline = ardSer.readline()
#                print 'after read: ',time.time()-stime
#                print ('fline is:',fline)
#                print('with length:',len(fline))
#                for i in range(len(fline)):
#                    print(ord(fline[i]))
                if abort:
                    return "aborted", None
                line = line + fline
                if len(line) > 0:
                    if line[-1] == b'\n'[0]:
                        break
                if i == 19:
                    return "Serial read timeout",None
            if line == b'EOP\r\n':
                runReading = False
#                print ("EOP")
#                sys.stdout.flush()
            elif line == b'DEB\r\n':
                ndata=areSer.read(2)
                print ('got DEB with val:',struct.unpack("H",str(ndata))[0])
            elif line == b'DAT\r\n':
#                print 'bytes for DAT waiting: ',ardSer.inWaiting()
#                print 'elapsed: ',time.time()-stime
                ndata = ardSer.read(4)
                if VER == 2:
                    num_points = struct.unpack("i",str(ndata))[0]
                else:
                    num_points = struct.unpack("i",ndata)[0]
                    
#                print ('got DAT: ',num_points)
                num_read = 0
            # i specifies 32 bits, h for 16 bits
            # I and H for unsigned

#                print "DAT",num_points,
#                sys.stdout.flush()
                ndata = "" #ndata is the data from this DAT
                #read the data, with periodic checks for abort flag.
                doneRead = False
                while not doneRead:
                    pts_to_acquire = num_points*2 - num_read
                    if pts_to_acquire > 10000: #this is about 0.5 sec.
                        pts_to_acquire = 10000
                    new_dat = ardSer.read(pts_to_acquire)
                    dat_list.extend(new_dat)
                    this_num_read = len(new_dat)
                    num_read += this_num_read
                    if this_num_read == 0:
                        doneRead = True #should never happen
#                    print ('read ',this_num_read,' bytes')
                    if abort:
                        print('aborting')
                        return "aborted",None
#are there any points?
#                    ndata = ndata+rdata
                    if num_read == num_points*2:
                        doneRead = True

                    #done read.
                if num_read != num_points*2:
                    return "Serial read timeout\n expected "+str(num_points*2) +" bytes, found only: "+str(num_read),None
                #add data from this read on to all data
                # is this too slow?
#                adata = adata+ndata
                    
            else:
                print("got unexpected header: ",line)
                return "Unexpected header message from arduino",None
        
    except:
        print('got an error while reading data')
        return "Serial exception while reading data",None

###
    # join all the strings together:
#    adata = ''.join(dat_list)
    fmt = str(len(dat_list)//2)+'h'
        #    print 'fmt is ',fmt
    if VER == 2:
        adata = numpy.array( struct.unpack(fmt,str(dat_list)))
    else:
        adata = numpy.array( struct.unpack(fmt,dat_list))
                
###
# add to old data:
    if data is None:
        data = adata
    else: # check the lengths are the same
        if data.size != adata.size:
            return "runProgram found new data of a different length than old data",None
        data = data + adata
# write the data to the file
    if  dataFileName is not None:
        try:
            fd=open(dataFileName,'w')
        except:
            return "runProgram couldn't open output file "+dataFileName+" for writing",None
        fd.write('#'+str(scans+1)+'\n')
        if data.size > 0:
            data.astype(int).tofile(fd,sep='\n')
        fd.close()
        
#return the retVal and the data
#    print 'returning data of len: ',data.size
    return True,data

def downloadProgram(fileName):
    global ardSer
    INTER_DELAY=150e-6
    if ardSer is None:
        return 'serial device not open'
    try:
        inFile = open(fileName)
    except:
        return "Couldn't open binary program file: "+fileName
    lines = inFile.readlines()
    tnums = numpy.array(lines)
    inFile.close()
    tnums = tnums.astype(int)
    startFlag = tnums[0]
    num_bytes = tnums[1]
#    print 'num_bytes is: ',num_bytes
    num_points = tnums[2]
#    print 'num_points: ', num_points

#now we have num_bytes more bytes, which include END_OF_PROGRAM at end
# so the points from tnums[3]
#then have checksums
#for i in range(num_bytes):
#    print tnums[i+3]
    checksum1 = tnums[3+num_bytes]
    checksum2 = tnums[4+num_bytes]
    print('checksums read from file: ',checksum1,checksum2)
    try:
        ardSer.timeout=0.2
        ardSer.flushInput() #windows seems to need this
        ardSer.write(b'\x0e')
        line = ardSer.readline()
        print('sent query, got: ',line)
#        if line != 'ANMR v0.8, Ready\r\n':
        if line != IDENTIFIER:
            return "Didn't find ready from arduino"
#        print 'sending header'
        ardSer.write(bytearray([startFlag]))
        time.sleep(INTER_DELAY)
        
        ardSer.write(bytearray([num_bytes & 255]))
        time.sleep(INTER_DELAY)
        ardSer.write(bytearray([(num_bytes >> 8) & 255]))
        time.sleep(INTER_DELAY)
        ardSer.write(bytearray([(num_points & 255)]))
        time.sleep(INTER_DELAY)
        ardSer.write(bytearray([(num_points>>8) & 255]))
        time.sleep(INTER_DELAY)
        ardSer.write(bytearray([(num_points>>16) & 255]))
        time.sleep(INTER_DELAY)
        ardSer.write(bytearray([(num_points>>24) & 255]))
        time.sleep(INTER_DELAY)
        
        line = ardSer.readline()   # read a '\n' terminated line
 #       print ('sent header, got: ',line)
        sys.stdout.flush()
        check1=0
        check2=0
        for i in range(num_bytes):
            ardSer.write(bytearray([tnums[i+3]]))
            time.sleep(INTER_DELAY)
            check1 += (i+1)*tnums[i+3]
            check2 += (i+2)*tnums[i+3]
#ardSer.write(chr(0))

        checkline1 = ardSer.readline()   # read a '\n' terminated line
#        print ('checksum1: ',checkline1)
        checkline2 = ardSer.readline()   # read a '\n' terminated line
#        print ('checksum2: ',checkline2)
#print "my checksums: ",check1,check2
        
    # should check that files checksums and arduinos checksums match
    except:
        return "Exception occurred while downloading program"
    try:
        check1 = int(checkline1)
        check2 = int(checkline2)
    except:
        return "Exception converting "+checkline1+" or "+checkline2+" to integers."
    if check1 == checksum1 and check2 == checksum2:
        print('Program downloaded successfully')
        return True
    else:
        print('checksums off?')
        return "Checksum error while downloading program"
        

#this routine will replace checkArduino, and will be the only interface to Anmr and FuncGen
def openArduino(window = None): # window is just so we can set it as a parent
#for any idialogs we open.
    global inited, arduinoDev, hardwareDev,portType,arduinoBoard

#look for lockfile:
    try:
        stat=os.stat(LOCKFILE)
        lockFile=True
    except:
        lockFile=False

    #look for ptyfile:
    ptyFile = pipeRunning(TEMP_DIR) # TEMP_DIR only matter on Linux, ignored on win

    if lockFile and USE_SERIAL_PIPE and not ptyFile:
    #wipe out the lockfile, it shouldn't be there if we should be should
    #be using the serial pipe, but the serial pipe isn't running.
        print('wiping lockfile')
        try:
            os.remove(LOCKFILE)
            lockFile = False
        except:
            return "A lockfile exists and could not be automatically removed.\nRemove "+LOCKFILE+" by hand and retry."

    if lockFile:
        dialog = gtk.Dialog("Attention!",window)
        label = gtk.Label("A lockfile exists indicating the arduino is in use.\nIF YOU ARE CERTAIN IT IS NOT BEING ACCESSED by another instance of FuncGen or Anmr,\n Select REMOVE to try to remove it automatically.")
        dialog.vbox.pack_start(label,True,True,0)
        dialog.add_buttons("No", gtk.RESPONSE_NO, "REMOVE", gtk.RESPONSE_YES)
        dialog.show_all()
        response = dialog.run() # -8 is yes, and -9 is no
        dialog.destroy()
        
        if response == gtk.RESPONSE_YES:
            dialog = gtk.Dialog("Attention!",window)
            label = gtk.Label("Are you really, really sure you want to remove the lockfile?")
            dialog.vbox.pack_start(label,True,True,0)
            dialog.add_buttons("No", gtk.RESPONSE_NO, "REMOVE", gtk.RESPONSE_YES)
            dialog.show_all()
            response = dialog.run() # -8 is yes, and -9 is no
            dialog.destroy()
            if response == gtk.RESPONSE_YES:
                try:
                    os.remove(LOCKFILE)
                except:
                    return "A lockfile exists and could not be removed. Remove:\n"+LOCKFILE+"\nmanually and try again."
            else:
                return "A lockfile exists, removal aborted."
        else:
            return "A lockfile exists, removal aborted."           

# ok, no lockfile


    if inited:
        if openDev(arduinoDev,portType) == 1:
            #port is open, talks ok, we're golden.
            return True
        else:
            inited = False
#            return 

#not inited, need to sort out which port/board we have
    hardwareDev,arduinoDev,arduinoBoard,portType = detectArduino(TEMP_DIR)
    if hardwareDev is None:
        return "Couldn't find an arduino?"

    if USE_SERIAL_PIPE and ptyFile:
        if openDev(arduinoDev,'software') == 1:
            return True
        else:
#could be here because could't create lockfile, couldn't open port, or the server's not running
#if the pipe was running though, it needs to go.
            if killSerialPipe(TEMP_DIR) == False:
                return "The serial pipe (socat or hub4com) was running, but\nI couldn't talk to the arduino and couldn't kill the pipe.\nRetry, if this error persists, kill the serial pipe manually and try again."
            else:
                ptyFile = False

# now check hardware:
    retVal = openDev(hardwareDev,'hardware')
    if retVal == -2:
        #offer to flash?
        dialog = gtk.Dialog("Attention!",window)
        label = gtk.Label("Arduino does not hold server. Upload server?")
        dialog.vbox.pack_start(label,True,True,0)
        dialog.add_buttons("No", gtk.RESPONSE_NO, "Yes", gtk.RESPONSE_YES)
        dialog.show_all()
        response = dialog.run() # -8 is yes, and -9 is no
        dialog.destroy()
        if response == gtk.RESPONSE_YES:
            try:
                if arduinoBoard == 'atmega328':
                    print('flashing deum')
                    call =AVRDUDE + ' -C'+AVRDUDE_CONF+' -patmega328p -carduino -P'+hardwareDev+' -b57600 -D -V -Uflash:w:'+FIRMWARE+':i'
                    print('call is: ',call)
                    rsVal = subprocess.call(call,shell=True)
                        
                elif arduinoBoard == 'uno': 
                    print('flashing uno')
                    call =AVRDUDE + ' -C'+AVRDUDE_CONF+' -patmega328p -carduino -P'+hardwareDev+' -b115200 -D -V -Uflash:w:'+FIRMWARE+':i'
                    print('call is: ',call)
                    rsVal = subprocess.call(call,shell=True)
# this way actually calls scons to build the firmware and download it.                        
#                    os.chdir(ARDUINO_CODE)
#                    os.system("scons ARDUINO_PORT="+ ARDUINO_PORT + " ARDUINO_BOARD="+ _ARDUINO_BOARD+" uploa
                if rsVal is not 0:
                    return "Attempt to flash failed"
            except:
                return "Attempt to flash failed"

            if openDev(hardwareDev,'hardware') == False:
                return "Server flashed, but arduino not responding correctly"
        else: #user doesn't want to flash
            return "Flash of firmware cancelled."
    elif retVal == 0:
        return "Couldn't create lockfile: "+LOCKFILE
    elif retVal == -1:
        return "opening hardware device failed. Unplug/replug arduino?"
#so at this point, we've opened the hardware port successfully and talked to the arduino.
    if USE_SERIAL_PIPE == False:
        inited = True
        return True #We're done
    closeDev() 
    if startSerialPipe(hardwareDev,arduinoDev) == False:
        return "Problem staring serial pipe (socat or hub4com)"
    time.sleep(1.6)
    if openDev(arduinoDev,'software') != 1:
        return "Problem opening serial pipe"
    inited = True
    return True


#openDev returns 1 if all is well, (lockfile created)
#0 if it couldn't open the lockfile 
#-1 if the port couldn't be opened (lockfile removed)
# -2 if the port opened but didn't have our server on it. (lockfile removed)
def openDev(serialDev,myType):
    global ardSer
#to be here, there isn't a lockfile
    try:
        lFile  = open(LOCKFILE,"w")
        lFile.close()
        os.chmod(LOCKFILE,0o666) 
        print('created lockfile')
    except:
        return 0

    print('trying to open device: ',serialDev)
                    
    try:
# full set of settings is: speed, parity, bytesize, stopbits
#timeout rtscts xonoff interCharTimeout dsrdtr writeTimeout, RTS DTR Break
        ardSer = serial.Serial(serialDev, 9600, parity='N',rtscts=False,xonxoff=False,timeout = 0.2)
        if (myType == 'hardware'):
            ardSer.setRTS(True)
            ardSer.setDTR(True)
            ardSer.setBreak(False)
            ardSer.bytesize=serial.EIGHTBITS
            ardSer.parity = serial.PARITY_NONE
            ardSer.stopbits=serial.STOPBITS_ONE
        ardSer.baudrate=1000000 #weirdly, some ports don't work unless you open
# then change the speed after.  Weird weird weird.
    except:
        print('serial exception')
        os.remove(LOCKFILE)
        return -1
    if myType == 'hardware':
        print('in open, sleeping')
        time.sleep(1.6)
    try:
        #flush any waiting input:
        ardSer.flushInput()
        ardSer.write(bytearray([14])) #14 is QUERY
        line = ardSer.readline()   # read a '\n' terminated line
    except:
        print('exception while trying to write query or read response')
        closeDev()
        return -1
    print('got ',line)
    if line == IDENTIFIER:
        print('openDev sent query, got: ',line)
        print('leaving openDev with device open')
        return 1
    closeDev() # close and remove lockfile
    return -2 # didn't get correct response from server.

def closeDev():
    global ardSer
    if ardSer is not None:
        try:
            ardSer.close()
        except:
            pass
        ardSer = None
        print('Serial device closed')
    #remove lockfile
    try:
        os.remove(LOCKFILE)
    except:
        pass
    return True
        


def makeAnmrTempDir(TEMP_DIR):
    if not os.path.isdir(TEMP_DIR):
        try:
            os.mkdir(TEMP_DIR)
            os.chmod(TEMP_DIR, 0o777) 
        except:
            gobject.idle_add(popupIdleWrap, "problem creating directory: "+TEMP_DIR, base.window)
            
