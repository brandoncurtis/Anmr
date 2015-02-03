import os

END_OF_PROGRAM=0
START_OF_PROGRAM=1
DELAY_IN_CLOCKS=2
DELAY_IN_MS=3
CHANGE_PIN=4
WAIT_FOR_PIN=5
SET_PULSE_PINS=6
PULSE=7
READ_DATA=8
GO=9
SET_FREQ=10
LOOP=11
END_LOOP=12
SYNC=13
QUERY=14
TOGGLE_PIN=15
TABLE=16

#now, go through lines of files
#first line of file must start with PULSE_PROGRAM
#if first char of a line is %, its a variable definition
# of the form %somebody = something
# build a table of variable/value pairs
#need to check a variable isn't already in the table with the same name. If so,
#replace its value with the new one.
# if line starts with #, throw it away.
#then deal with commands one at a time
#DELAY_IN_CLOCKS 
#DELAY_IN_MS 
#CHANGE_PIN
#WAIT_FOR_PIN 
#PULSE 
#READ_DATA
#SET_FREQ
#SET_PULSE_PINS
#LOOP
#END_LOOP
#SYNC

inFile = None
outFile = None
vars=[]
vals=[]
numVars = 0

def cleanup():
    global inFile,outFile
    if inFile is not None:
        inFile.close()
    if outFile is not None:
        outFile.close()
    return

#useful when we know exactly how many arguments to read:
def getArgs(line,number):
    global vars,vals,numVars
    args=[]

    fields = line.split()
    if len(fields) != number+1: # first is the command.
        return False,None
    for i in range(number):
        isVariable = False
        if fields[i+1][0] == '%': #its a variable, look it up
            for j in range(numVars):
                if fields[i+1] == vars[j]: # match!
                    args.append(vals[j])
#                    print 'variable match: ',fields[i+1],vals[j]
                    isVariable = True
        if isVariable == False:
            try: #translate directly to an int
                ivalue = int(fields[i+1])
            except:
                print('failed to translate field: ',fields[i+1],'to an int')
                return False,None
            args.append(ivalue)
#    print 'getArgs returning: ',args
    return True,args


#look for header line:
def compile(inName,outName):
    global inFile,outFile,vars,vals,numVars
    prog = b""
    freqSet = False
    pinsSet = False
    nullLoop = False
    totalReadings = 0
    loopNum = 1
    loopStarted = False

    try:
        inFile = open(inName)
    except:
        print("couldn't open input file ",inName)
        return "couldn't open input file"
    try:
        outFile = open(outName,"w")
    except:
        print("couldn't open output file ",outName)
        cleanup()
        return "couldn't open output file"
    os.chmod(outName,0o666)

    tables_defined = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
    try:
        if inFile.readline().strip() != "PULSE_PROGRAM":
            print("invalid pulse program file")
            return "invalid pulse program file (PULSE_PROGRAM not found)"
    except:
        print("error reading first line of file!")
        return "Error reading first line of pulse program"

    lines = inFile.readlines()

#now parse, looking for commands, %'s and #'s
    for i in range(len(lines)):
        myline = lines[i].split('#')[0] # remove any trailing comments
        myline = myline.strip()
#        print '\nparsing line: ',myline
        if len(myline) >0 and (myline[0]) != '#': # not a comment
            if myline[0] == '%': # variable defintion
                fields = myline.split("=")
                if len(fields) != 2:
                    print("Error parsing variable definition:",myline)
                    return "Error parsing variable definition: "+myline
                variable = fields[0].strip()
                value = fields[1].strip()
#                print 'variable: ',variable,', value: ',value
                try:
                    ivalue = int(value)
                except:
                    print("failed to turn variable value into an int")
                    return "failed to convert a variable value into an int: "+myline
                # see if its already in the table:
                mustAppend = True
                for j in range(numVars):
                    if vars[j] == variable:
#                        print 'match found with previous variable'
                        vals[j] = ivalue
                        mustAppend = False
                if mustAppend:
                    vars.append(variable)
                    vals.append(ivalue)
                    numVars += 1
                #done!

            elif myline.startswith("DELAY_IN_CLOCKS"):
#                print "got delay in clocks"
                #should have one argument
                rVal,args = getArgs(myline,1)
                if rVal == False:
                    print("failed to getArgs in line: ",myline)
                    return "failed to retrieve arguments in: "+myline
                if args[0] <= 104:
                    args[0] = 105
                if nullLoop == False:
                    prog = prog + bytearray([DELAY_IN_CLOCKS])
                    prog = prog + bytearray([args[0] & 255,args[0]>>8 &255,args[0]>>16 & 255,args[0]>>24 &255])
#                    prog = prog + bytearray([args[0]>>8 & 255])
#                    prog = prog + bytearray([args[0]>>16 & 255])
#                    prog = prog + bytearray([args[0]>>24 & 255])


            elif myline.startswith("DELAY_IN_MS"):
#                print "got delay in ms"
                rVal,args = getArgs(myline,1)
                if rVal == False:
                    print("failed to getArgs in line: ",myline)
                    return "failed to retrieve arguments in line: "+myline
                if nullLoop == False and args[0] > 0:
                    prog = prog + bytearray([DELAY_IN_MS])
                    prog = prog + bytearray([args[0] & 255,args[0]>>8 & 255])
#                    prog = prog + bytearray([args[0]>>8 & 255])
                    
            elif myline.startswith("CHANGE_PIN"):
                rVal,args = getArgs(myline,2)
                if rVal == False:
                    print("failed to getArgs in line: ",myline)
#                print "got change pin with args: ",args
                if nullLoop == False:
                    prog = prog+bytearray([CHANGE_PIN])
                    prog = prog+bytearray([args[0],args[1]]) #pin,value
#                    prog = prog+bytearray([args[1]]) #value

            elif myline.startswith("TOGGLE_PIN"):
                rVal,args = getArgs(myline,2)
                if rVal == False:
                    print("failed to getArgs in line: ",myline)
#                print "got change pin with args: ",args
                if nullLoop == False:
                    prog = prog+bytearray([TOGGLE_PIN])
                    prog = prog+bytearray([args[0],args[1]]) #pin, start value
#                    prog = prog+bytearray([args[1]]) #value

            elif myline.startswith("WAIT_FOR_PIN"):
                rVal,args = getArgs(myline,2)
                if rVal == False:
                    print("failed to getArgs in line: ",myline)
                    return "failed to retrieve arguments in line: "+myline
#                print "got wait_for_pin with args: ",args
                if nullLoop == False:
                    prog = prog+bytearray([WAIT_FOR_PIN])
                    prog = prog+bytearray([args[0],args[1]])#pin
#                    prog = prog+bytearray([args[1]])#code for waiting.
                
                
            elif myline.startswith("PULSE"):
                if freqSet == False or pinsSet == False:
                    print("Pulse, but freqSet or pinsSet is False")
                    return "PULSE requested, but freqSet or pinsSet is False"
#                print "got PULSE"
                if myline.split()[1][0] == 'T': # phase table style
                    #which table?
                    try:
                        tnum = int(myline.split()[1][1:])
                    except:
                        print("Error translating table number")
                        return "Error translating table number: "+myline
                    if tnum < 0 or tnum > 15:
                        print("Illegal table number")
                        return 'Illegal table number: '+myline
                    if tables_defined[tnum] != 1:
                        print("Table not defined")
                        return 'Table not defined: '+myline
                    # now get the number of half cycles in the pulse
                    rVal,args = getArgs(myline[5:].strip() , 1)
                    if rVal == False:
                        print("failed to getArgs in line: ",myline)
                        return "failed to retrieve arguments in line: "+myline
                    print ("number of cycles: ",args[0])
                    if nullLoop == False:
                        prog = prog + bytearray([PULSE])
                        prog = prog + bytearray([255-tnum])
                        prog = prog + bytearray([args[0] & 255])
                        prog = prog + bytearray([args[0]>>8 & 255])
                
                else:    
                    rVal,args = getArgs(myline,4)
                    if rVal == False:
                        print("failed to getArgs in line: ",myline)
                        return "failed to retrieve arguments in line: "+myline
                    #args are start phase, phase increment, 
                    #steps between phase increment and number of half periods
                    if args[2] == 0:
                        args[2] = 1
                    if nullLoop == False:
                        prog = prog + bytearray([PULSE])
                        prog = prog + bytearray([(args[0]%360)//2])
                        prog = prog + bytearray([(args[1]%360)//2])
                        prog = prog + bytearray([args[2] & 255])
                        prog = prog + bytearray([args[3] & 255])
                        prog = prog + bytearray([args[3]>>8 & 255])

            elif myline.startswith("READ_DATA"):
#                print( 'got read_data')

                if myline.split()[1][0] == 'T': # phase table style
                    #which table?
                    try:
                        tnum = int(myline.split()[1][1:])
                    except:
                        print("Error translating table number")
                        return "Error translating table number: "+myline
                    if tnum < 0 or tnum > 15:
                        print("Illegal table number")
                        return 'Illegal table number '+myline
                    if tables_defined[tnum] != 1:
                        print("Table not defined")
                        return 'Table not defined '+myline
                    if freqSet == 0:
                        print('need to set frequency before reading with phase table is possible')
                        return 'READ_DATA requested phase cycling with phase table is possible.'
                    # now get the number of half cycles in the pulse
                    rVal,args = getArgs(myline[9:].strip() , 1)
                    if rVal == False:
                        print("failed to getArgs in line: ",myline)
                        return "failed to retrieve arguments in line: "+myline
                    print ("number of points: ",args[0])
                    if nullLoop == False:
                        if loopStarted:
                            totalReadings += args[0]*loopNum
                        else:
                            totalReadings += args[0]
                        prog = prog + bytearray([READ_DATA])
                        prog = prog + bytearray([255-tnum]) #always more than 180
                        prog = prog + bytearray([args[0] & 255])
                        prog = prog + bytearray([args[0]>>8 & 255])
                        prog = prog + bytearray([args[0]>>16 & 255])
                        prog = prog + bytearray([args[0]>>24 & 255])
                else: #initial, increment, modulo style
#                    print("looking for old style")
                    rVal,args = getArgs(myline,4)
                    if rVal == False:
                        print("failed to getArgs in line: ",myline)
                        return "failed to retrieve arguments in line: "+myline
                    if args[1] > 0 and freqSet == 0:
                        print('need to set frequency before reading with phase increment '+args[1]+' is possible')
                        return 'READ_DATA requested phase cycling with increment '+args[1]+', but frequency not set'
                    if args[2] == 0:
                        args[2] = 1
                    if nullLoop == False:
                        if loopStarted:
                            totalReadings += args[3]*loopNum
                        else:
                            totalReadings += args[3]
                        prog = prog+bytearray([READ_DATA])
                        prog = prog + bytearray([(args[0]%360)//2]) #always less than 180
                        prog = prog + bytearray([(args[1]%360)//2])
                        prog = prog + bytearray([args[2] & 255])
                        prog = prog + bytearray([args[3] & 255])
                        prog = prog + bytearray([args[3]>>8 & 255])
                        prog = prog + bytearray([args[3]>>16 & 255])
                        prog = prog + bytearray([args[3]>>24 & 255])

            elif myline.startswith("SET_FREQ"):
#                print 'got set freq'
                rVal,args = getArgs(myline,1)
                if rVal == False:
                    print("failed to getArgs in line: ",myline)
                    return "failed to retrieve arguments in line: "+myline
                hperiod = int(8000000/args[0])
                delc1 = int(0.3591/3.14159*hperiod)
#                delc1 = int (hperiod/6) # for minimum 3rd harmonic
                delc2 = int(hperiod-2*delc1)
                if nullLoop == False:
                    prog = prog + bytearray([SET_FREQ])
                    prog = prog + bytearray([delc1 & 255])
                    prog = prog + bytearray([delc1>>8 & 255])
                    prog = prog + bytearray([delc2 & 255])
                    prog = prog + bytearray([delc2>>8 & 255])
                    prog = prog + bytearray([hperiod & 255])
                    prog = prog + bytearray([hperiod>>8 & 255])
                    freqSet = True
                
            elif myline.startswith('SET_PULSE_PINS'):
#                print 'got set pulse pins'
                rVal,args = getArgs(myline,2)
                if rVal == False:
                    print("failed to getArgs in line: ",myline)
                    return "failed to retrieve arguments in line: "+myline
                if nullLoop == False:
                    prog = prog+bytearray([SET_PULSE_PINS])
                    prog = prog+bytearray([args[0]])
                    prog = prog+bytearray([args[1]])
                    pinsSet = 1
#                    print 'set pinsSet'
                
            elif myline.startswith('LOOP'):
#                print 'got loop'
                if loopStarted:
                    print("can't nest loops")
                    return "can't nest loops"
                rVal,args = getArgs(myline,1)
                if rVal == False:
                    print("failed to getArgs in line: ",myline)
                    return "failed to retrieve arguments in line: "+myline
                if args[0] == 0:
                    nullLoop = True
                    loopStarted = True
                else:
                    loopStarted = True
                    loopNum = args[0]
                    prog = prog+bytearray([LOOP])
                    prog = prog+bytearray([args[0] & 255])
                    prog = prog+bytearray([args[0]>>8 & 255])
                
            elif myline.startswith('END_LOOP'):
#                print 'got end loop'
                if loopStarted == False:
                    print("ending a loop without starting?")
                    return "END_LOOP found without a LOOP start"
                loopStarted = False
                nullLoop = False
                prog = prog+bytearray([END_LOOP])

            elif myline.startswith('SYNC'):
#                print 'got SYNC'
                if nullLoop == False:
                    prog = prog + bytearray([SYNC])
                
            elif myline.startswith('TABLE'):
#define a phase table syntax: TABLE T0 {0,90,90,180,180,0}
#check that the line specifies a table number T0 - T15
                if myline.split()[1][0] != 'T':
                    print("Table number not Tn")
                    return "Table number not Tn: "+myline
#get the table number
                try: #translate directly to an int
                    tnum = int(myline.split()[1][1:])
                except:
                    print('Failed to translate table number')
                    return "Failed to translate table number: "+myline
                if tnum > 15 or tnum < 0:
                    print('Illegal table number')
                    return "Illegal table number: "+myline
#                print ' got table number ',tnum
                if len(myline.split('}')) != 2  or len(myline.split('{')) != 2:
                    print ("sytax error in table definition")
                    return "syntax error in table definition: "+myline
                phase_list = myline.split('{')[1].split('}')[0].split(',')
 #               print phase_list
                prog = prog+bytearray([TABLE])
                prog = prog+bytearray([255-tnum])
                prog = prog+bytearray([len(phase_list)])
                if len(phase_list) == 0:
                    print("empty phase table?")
                    return "empty phase table? "+myline
                for i in range(len(phase_list)):
                    try:
                        phval = int(phase_list[i])
                    except:
                        print("Failed to convert phase value in table to int")
                        return "Failed to convert phase value in table to int: "+myline
                    phval = (phval % 360)//2
#                    print phval
                    prog = prog+bytearray([phval])
                tables_defined[tnum] = 1 #flag that the table has been defined.
#first byte is TABLE, then 255-tnum, then length of table, then the table itself, each 
#phase is one byte: degrees/2 (0-179 -> 0-358deg)
            elif len(myline) == 0:
                print('got an empty line')
            else:
                print('got an unknown line: ',myline)
                return "got an unknown line: "+myline

    prog = prog +bytearray([END_OF_PROGRAM])
    print('Compilation successful')
    check1 = 0
    check2 = 0
    for i in range(len(prog)):
        check1 += (i+1)*(ord(prog[i:i+1]))
        check2 += (i+2)*(ord(prog[i:i+1]))
        
#    print 'got checksums: ',check1,check2
    outFile.write(str(START_OF_PROGRAM)+'\n')
    outFile.write(str(len(prog))+'\n')
    outFile.write(str(totalReadings)+'\n')
    for i in range(len(prog)):
        outFile.write(str(prog[i])+'\n')
    outFile.write(str(check1)+'\n')
    outFile.write(str(check2)+'\n')
    outFile.close()
    inFile.close()
    return True
#to write the file, we write:  1byte start, 2 byte number of bytes in program+1
# then 4 byte of number of points to read
# and 1 byte END_OF_PROGRAM
#then finally the two checksums.

#usage:
#compile('/tmp/Anmr/anmr-prog.txt','/tmp/Anmr/anmr-prog/bin')
