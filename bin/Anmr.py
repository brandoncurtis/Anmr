#!/usr/bin/python2.7

# 19 make circle correction optional,
# 18 align projections before reconstruction.
# ver 14 came from 12, skipped the noise reduction in 13.
# ver 15 includes gamma correction of output image and adds a width field to the peak stats
# also a bunch of fixes to handle cases where user click x's to close dialogs, or doesn't click peak limits properly etc.
#ver 16 changes abort behaviour slightly (so the abort scan is read in)
# and plans to change the extra projection to be a normalization projection - swap
# to full bottle, then fits to semicircle.
# completely reworked file save UI
# reworked arduino detection - wipe out lock file now if the pty doesn't exist.



import pango
import shutil
#we do a little manual garbage collecting when a data window is destroyed

import matplotlib.artist as Artist
from matplotlib.lines import Line2D
from matplotlib.figure import Figure
from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvas
#from matplotlib.backends.backend_gtkagg import NavigationToolbar2GTKAgg as NavigationToolbar2
#from matplotlib.backends.backend_gtk import FigureCanvasGTK as FigureCanvas
#from matplotlib.backends.backend_gtk import NavigationToolbar2GTK as NavigationToolbar2
import scipy.optimize as optimize
from PIL import Image

from anmr_common import *

if EXPERTMODE:
# this will show or hide the controls for handling single/multiple full echoes:
    hideEchoCheck = False
    hideProjectionCorrections = False
else:
    hideEchoCheck = True
#give options for image corrections
    hideProjectionCorrections = True

#by default, we keep data here:
DATA_DIR = os.path.join(os.path.expanduser('~'),'anmr-data')

gtk.gdk.threads_init()

#flashes entire screen for a moment.
def flashScreen():

    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.set_decorated(False)
    window.present()
    window.maximize()
    while gtk.events_pending():         #makes sure the GUI updates
        gtk.main_iteration()
    time.sleep(.15)
    window.destroy()


def syntaxError(name):
    popup_msg("Pulse program syntax error\n"+name,base.window)

def parse_prog_defs(filename):
    inFile = open(filename)

    found = False
    varNames = []
    varMins = []
    varMaxs = []
    varDefaults = []
    varUnits = []

    for line in inFile:
        if found:
            if line.strip() == "#END":
                #        print 'got #END, breaking'
                break
            if line.strip() != []:
                line2 = line.split()
                if len(line2) < 4 or len(line2) >5 : # min, max and default are mandatory. Units optional
                    syntaxError("Definitions")
                    inFile.close()
                    return [0, 0]
           #remove leading #'s
                if line2[0][0] != "#": #syntax error should be #variable_name
                    syntaxError("Definitions")
                    inFile.close()
                    return [0, 0]
                line2[0]=line2[0][1:]
                varNames.append(line2[0])
                try:
                    varMins.append(int(line2[1]))
                    varMaxs.append(int(line2[2]))
                    varDefaults.append(int(line2[3]))
                except:
                    syntaxError("Definitions")
                    inFile.close()
                    return [0, 0]
                if len(line2) == 5:
                    varUnits.append(line2[4])
                else:
                    varUnits.append("")
#should sanity check the rest of the program and make sure that the user didn't set any variables that we're going to set.
        if line.strip() == "#DEFINITIONS":
            #        print 'found #DEFINITIONS'
            found = True

    for line in inFile:
        line2=line.split()
        if line2 != []:
            if line2[0] == '%': #that's a variable defintion check to see if its in our list
                for i in range(len(varNames)):
                    if varNames[i] == line2[0][1:]:
                        syntaxError("Adjustable variable assigned in program")
                        inFile.close()
                        return [0, 0]
    inFile.close()
    return [varNames, varMins, varMaxs, varDefaults, varUnits]

def addUnderscores (string):
    #this function looks through the input string and adds an underscore to any underscores
    #this is needed for menu objects, since with a single underscore it just underlines the next character
    indeces = []
    for i in range(len(string)):
        if string[i] == '_':
            indeces.append(i)
    counter = 0
    for i in range(len(indeces)):
        string = string[:indeces[i] + counter] + '_' + string[indeces[i] + counter:]
        counter += 1
    return string


class runProgramThread(Thread):

    def null(self): #dummy routine for idle_add.  This unblocks the main_iteration call that blocks.
        return

    def __init__ (self, dataFileName,data,scans):

        Thread.__init__(self)
        self.dataFileName = dataFileName
        self.data = data
        self.scans = scans
        self.doneFlag = False

    def run (self):
        self.retVal, self.retData = runProgram(self.dataFileName,self.data,self.scans)
        self.doneFlag =True
        gobject.idle_add(self.null) #unblock the main_iteration
        return




class progressBarWindow:
    #creates a window with a progress bar in it
    #auto deletes once it reaches 100%
    #iteration() progresses it one step

    def __init__ (self, numOperations=None, name = "",window = None, text = None):

        self.abortFlag = False

        #numOperations is total number of steps to completion

        self.win = gtk.Window()         #make a window
        try:
            self.win.set_icon_from_file(os.path.join(ICON_PATH,"Anmr-icon"+ICON_EXTENSION))
        except:
            pass
        self.win.connect("delete_event", self.delete_event)
        self.win.set_default_size(200,125)
        self.win.set_title("Progress")
        if window is not None:
            self.win.set_transient_for(window)
#           self.win.set_keep_above(True)

        vbox = gtk.VBox(False, 0)           #and a vertical box
        self.win.add(vbox)

        self.totalOps = numOperations
        self.currentOp = 0

        title = gtk.Label("Process: "+name)     #label with name of the process
        vbox.pack_start(title,True,True,0)
        self.progBar = gtk.ProgressBar()    #make a progress bar
        self.progBar.set_orientation(gtk.PROGRESS_LEFT_TO_RIGHT)

        self.progBar.set_fraction(self.currentOp/ float(self.totalOps))
        if text is None:
            self.progBar.set_text( str(self.currentOp)+' / ' + str(self.totalOps))  #update the bar's text
        else:
            self.progBar.set_text(text)
        vbox.pack_start(self.progBar,True,True,0)   #pack the progress bar into the box

        self.abortButton = gtk.Button("Abort")
        self.abortButton.connect_object("clicked", self.abort, self.abortFlag)
        vbox.pack_start(self.abortButton,True,True,0)

#set position of progress bar:
#        position = self.win.get_position()

        self.win.show_all()                 #show everything
#        self.win.move(0, 0)
        ww = gtk.gdk.screen_width()
        hh = gtk.gdk.screen_height()
        self.win.move(ww-200,0)
 
    def delete_event(self, widget, event, data=None):
        return True

    def abort(self, flag):          #this function is called when the abort button is clicked
        self.abortFlag = True
        self.abortButton.set_label("Aborting, please hold...")
        self.abortButton.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("red"))
        setAbortFlag()

    def getNumOps(self):                #getter: returns the number of total operations
        return self.totalOps

    def setNumOps(self, numOperations):         #setter: sets the number of total operations
        self.totalOps = numOperations

    def getCurrentOp(self):
        return self.currentOp


    def setTransient(self, window):         #sets the progress bar window's transient to the argument
        self.window.set_transient_for(window)

    def failure(self):                  #called when catastrophic failure occurs, destroys the window
        self.progBar.destroy()
        self.win.destroy()

    def iteration(self,text = None):
        #this method is called when one step is complete
        #note that the window is destroyed if the current number of operations is zero

        if not self.totalOps:
            self.failure()
            return

        self.currentOp += 1             #increment current step
        self.progBar.set_fraction(self.currentOp/ float(self.totalOps) )    #update the bar length
        if text is None:
            self.progBar.set_text( str(self.currentOp)+' / ' + str(self.totalOps))  #update the bar's text
        else:
            self.progBar.set_text(text)
#           self.progBar.set_text( str( round(self.currentOp / float(self.totalOps) * 100 , 2) ) +"%")      #update the bar's text



class DataSet:


    def __init__ (self, numRuns, string, path):

#create a dataset object and window.  Data needs to exist on disk.
        # string can be "Image" "Array" or "Single"
        # streeng is always the directory name where we find the data and metadata.

        self.index = 0
        self.new = True
        self.string = string
        self.acqName = path
        self.saveName = None
        self.numRuns = numRuns
        self.measuring = False
        self.measureDialogOpen = False
        self.phaseOpen = False
        self.numScans = []
        self.procChangedNoRecur = 0 #this might not be necessary...

    def make_td_plot_data(self,rawData,leftShift,necho,npts):

        # do left shift and baseline correct, accounting for multiple echoes
        av = numpy.average(rawData)
#        av = 0.
        newData=numpy.array(())
        if abs(leftShift) > npts//necho: # shift everything away!
            return numpy.zeros(npts)
        if leftShift > 0 :
            for i in (list(range(necho))) :
                newData = numpy.hstack((newData,rawData[i*npts//necho+leftShift:(i+1)*npts//necho]-av,numpy.zeros(leftShift)) )
        else:
            for i in (list(range(necho))) :
                newData = numpy.hstack( (newData,numpy.zeros(-leftShift),rawData[i*npts//necho:(i+1)*npts//necho+leftShift]-av) )

#           print ' make td data, returning: ',newData.shape
        return newData

    def processData(self, start = 0,filler2 = None,new=True):

        # start is which record to start processing - so we don't always do them all.
        # we get new = False if we don't need to recreate data buffers.

#this routine starts from rawData, reads all the process parameters, and
#provides processedData. Cases: multiple echoes (though 1 is just a special case of more)
        # full echo is quite different.
        # four cases: single fid, single full echo. multiple fid, multiple echo.
        # except, multiple echo is treated differently for images.

#single fid is a special case of multiple fid. single full echo is a special case of multiple echo.
#So really, we have fid, and echo image, echo array - just three cases.
        sys.stdout.flush()
        if new:
            #               print ' got new true'
            start = 0

#first, collect all the processing parameters
        leftShift = int( self.leftShift.get_value() )
        fnpts = int( self.freqDomExpand.get_value()) # number of points in spectrum
        phase = self.appliedPhase
#           print ' in processing, start is: ',start
        broadening = self.lbAdjust.get_value()

        if ( self.multCheck.get_active() ):
            necho = int ( self.multNumAdj.get_value() )
        else:
            necho = 1

        self.rawData.shape = (self.numDataFiles,-1)

        nrec = self.numDataFiles
        npts = (self.rawData.shape)[1]

# this is the wrong place for this...
        if npts == 0: # no data points returned - turn off buttons
            self.button3.set_sensitive(False)
            self.radButton.set_sensitive(False)
            self.saveDataButton.set_sensitive(False)
            self.saveSpecButton.set_sensitive(False)
            self.phaseButton.set_sensitive(False)
            return
#           print 'nrec: ',nrec,' npts is: ',npts
        rnpts = npts//necho # number of points in final fid

        # how many points in our final spectrum?
        # we're going to give it fnpts.  We get fnpts//2 + 1 if even or odd.
        
        self.cfreqs=(numpy.fft.fftfreq(fnpts,TIME_STEP))[0:fnpts//2+1] # fnpts//2+1 is correct!
#           print 'cfreq is: ',self.cfreqs.size
        if self.cfreqs[-1] < 0:
            self.cfreqs[-1] *= -1

        self.step=1./TIME_STEP/fnpts # FIXME: fnpts even/odd?
        if self.leftFreq and self.rightFreq:
            self.leftEdge =  int (self.leftFreq/self.step)      #this is to find the index of the left side of the peak
            self.rightEdge = int (self.rightFreq/self.step) + 1


#first do left shift, and baseline correct: this is universal

        if new:
            self.tdData = numpy.empty((nrec,npts))
            self.specData=numpy.zeros((nrec,self.cfreqs.size),complex) # prepare the array to receive the data

        if nrec > self.tdData.shape[0]: #the data set is longer than it was
            self.tdData = numpy.append(self.tdData,numpy.zeros((nrec-self.tdData.shape[0])*self.tdData.shape[1]))
            self.tdData.shape=(nrec,-1)

            self.specData = numpy.append(self.specData,numpy.zeros((nrec-self.specData.shape[0])*self.specData.shape[1]) )
            self.specData.shape=(nrec,-1)

        for i in range(nrec)[start:nrec]:
            self.tdData[i] = self.make_td_plot_data(self.rawData[i],leftShift,necho,npts)

        self.times_ms = numpy.arange(npts)*TIME_STEP*1000
        #so data to plot in fid display is self.tdData[n] vs self.times_ms
        #           print 'shape of tdData is:', self.tdData.shape

        # for rest of processing: do the not full echoes case first:
        if (self.echoCheck.get_active() == 0):
            #line broadening
            broad_vals = numpy.exp( - (self.times_ms[0:rnpts]/1000*numpy.pi*broadening/1.6651) **2 )
            # collapse multiple echoes into one.
            for i in range(nrec)[start:nrec]:
                collapsedData=numpy.zeros(rnpts)
                for j in range(necho):
                    collapsedData = collapsedData + self.tdData[i][j*rnpts:(j+1)*rnpts]
                #line broaden
                broadenedData = broad_vals*collapsedData
                broadenedData[0] /= 2.  #get baseline right...
                #ft and phase.
                self.specData[i] = numpy.exp(1j*numpy.pi*phase/180)*numpy.fft.rfft(broadenedData,n=fnpts)/(fnpts/2.)
#                   print 'specData size:',self.specData[i].size,' fnpts was: ',fnpts
            sys.stdout.flush()

            return
        else: #full echoes - two cases: array/single or image.
            #               print 'made specData with ', self.cfreqs.size
#in full echo mode, throw away the phase? Maybe not actually...
            #               self.phaselabel = gtk.Label(str(0))
            #               self.appliedPhase = 0
            for i in range(necho):
                for j in range(nrec)[start:nrec]:
                    if (j == start ): #for images, we always phase based on record 0.
                        args = self.findFullEchoPhase(self.tdData[0][i*rnpts:(i+1)*rnpts],fnpts)
                    elif (self.string == 'Array'):
                        args = self.findFullEchoPhase(self.tdData[j][i*rnpts:(i+1)*rnpts],fnpts)
#                       print 'echo phases: ',args[0]/2/numpy.pi,args[1]/2/numpy.pi
                    if (j == start or self.string == 'Array'):
                        offset = args[1] / ( 2 * numpy.pi) # this is how far off the center is, in seconds.
                        phase_vals = numpy.exp(-(args[1]* self.cfreqs +args[0])*1j)
                        broad_vals = numpy.exp( - ( ( ( ( (numpy.arange(rnpts)-rnpts/2.)*TIME_STEP + offset)*numpy.pi*broadening) /1.6651) **2 ))

                    #broaden
                    broadenedData = self.tdData[j][i*rnpts:(i+1)*rnpts]*broad_vals
#                       print 'broadened size: ',broadenedData.size


                    #zero fill
                    toAddFront = ( fnpts - rnpts ) // 2
                    if toAddFront >=0:
                        filledData = numpy.hstack((numpy.zeros(toAddFront),broadenedData,numpy.zeros(fnpts-rnpts-toAddFront)))
                    else:
                        filledData = broadenedData[-toAddFront:fnpts-toAddFront]
#                           print 'reduced size of data to: ',filledData.size,' fnpts is: ',fnpts

                    filledData = numpy.fft.fftshift(filledData)
#dump data before FT.
#                       for i in range(fnpts):
#                           print i,filledData[i]
#                       print ' calling fft with points: ',filledData.size
                    transformedData = numpy.fft.rfft(filledData,n=fnpts)/(filledData.size/2.)
                    if transformedData.size != self.cfreqs.size:
                        popup_msg("size mismatch in processing data",self.window)
                    self.specData[j] += transformedData*phase_vals


    def phasing(self, filler = None, event = None):
        #this function 'cheats' a little: it only updates what the user sees; this allows the UI to update much more smoothly
        #it is called when the phase slider is moved
        #when one of the buttons on the phase window are clicked, the change seen is either applied or discarded
        if self.radButton.get_active() is False: # we're in FID mode
            return

        deltaPhase = self.phaseAdjust.get_value() - self.appliedPhase

        phasor = numpy.exp( numpy.pi * deltaPhase/180. * 1j)

        a = self.fig.gca()
        lims = a.get_xlim()

        leftIndex = lims[0] / self.step
        rightIndex = lims[1] / self.step

        if leftIndex < 0:       #then we've reached a limit
            leftIndex = 0

        if rightIndex > (self.specData[self.index].size):       #then we've reached a limit
            rightIndex = (self.specData[self.index].size-1)

        toDraw = (self.specData[self.index][leftIndex:rightIndex+1]*phasor).real
        toDrawFreq = self.cfreqs[leftIndex:rightIndex+1]

        self.line.set_data(toDrawFreq,toDraw)
        self.canvas.draw_idle()

        while gtk.events_pending():         #makes sure the GUI updates
            gtk.main_iteration()


    def procParamChanged(self,filler=None):
        # means that line broadening, left shift, freq domain points, or the number of echos/full echo has changed
        # phase is separate
        if self.procChangedNoRecur == 1:
            return
        if filler == "broad":
            base.broadening = self.lbAdjust.get_value()
        elif filler == "leftShift":
            base.leftShift = int(self.leftShift.get_value())
        elif filler == "freqDom":
            val = int(self.freqDomExpand.get_value())
            if val%64 != 0:
                self.procChangedNoRecur = 1
                self.freqDomExpand.set_value(((val+31)//64)*64)
                self.procChangedNoRecur = 0
            base.freqDomExpand = int(self.freqDomExpand.get_value())

        elif filler == "multCheck":
            base.multCheck = self.multCheck.get_active()
        elif filler == 'echoCheck':
            base.echoCheck = self.echoCheck.get_active()
        elif filler == 'multNum':
            base.necho = int ( self.multNumAdj.get_value() )
        elif filler == "autoAlignCheck":
            base.autoAlign = self.autoAlignCheck.get_active()
            return
        elif filler == "circleCheck":
            base.circleCheck = self.circleCheck.get_active()
            return
        self.processData(self)
        self.drawData()


    def findFullEchoPhase(self, data, tnpts):
        if tnpts < 8192:
            tnpts = 8192


        step = (1./TIME_STEP) / tnpts
        leftEdge =  int (self.leftFreq/step)        #this is to find the index of the left side of the peak
        rightEdge = int (self.rightFreq/step) + 1


        toAddFront = ( tnpts - data.size ) // 2

        if toAddFront >= 0:
            finalData = numpy.hstack((numpy.zeros(toAddFront),data,numpy.zeros(tnpts-data.size-toAddFront)))
        else:
            finalData = data[-toAddFront:tnpts-toAddFront]
        freqs = numpy.fft.fftfreq(finalData.size, TIME_STEP)[0:tnpts//2+1]
        if freqs[-1] < 0:
            freqs[-1] *= -1

        finalData = numpy.fft.fftshift(finalData)

        transformedData = numpy.fft.rfft(finalData)
        transformedData /= transformedData.size


        phase = numpy.angle(transformedData[leftEdge:rightEdge])

#find wrap around and fix
        for i in range(phase.size)[1:]:
            if( numpy.fabs(phase[i] - phase[i-1]) > numpy.pi ):
                phase[0:i] -= 2*numpy.pi * numpy.signbit( phase[i]-phase[i-1] )


#        oneOverMiSquared = 0
#        FiOverMiSquared = 0
#        FiSquaredOverMiSquared = 0
#        FiPiOverMiSquared = 0
#        PiOverMiSquared = 0
#        for i in range(phase.size):
#            MiSquared = (abs(transformedData[i+leftEdge]))**2
#            oneOverMiSquared +=   MiSquared
#            FiOverMiSquared += freqs[i+leftEdge] *  MiSquared
#            FiSquaredOverMiSquared += ((freqs[i+leftEdge])**2 )*  MiSquared
#            FiPiOverMiSquared +=  freqs[i+leftEdge] * phase[i]  *  MiSquared
#            PiOverMiSquared += phase[i] *  MiSquared
#TEMP: output
#           outFile = open("phases.txt","w")
#           for i in range(phase.size):
#               outFile.write(str(freqs[i+leftEdge])+" "+str(phase[i])+" "+str(abs(transformedData[i+leftEdge]))+"\n")
#           outFile.close()

#        D = oneOverMiSquared * FiSquaredOverMiSquared - (FiOverMiSquared)**2
#        b = ( FiSquaredOverMiSquared * PiOverMiSquared - FiOverMiSquared * FiPiOverMiSquared ) / D
#        m = ( oneOverMiSquared * FiPiOverMiSquared - FiOverMiSquared * PiOverMiSquared ) / D


## faster:
        MiSquared = numpy.abs(transformedData[leftEdge:leftEdge+phase.size])**2
        oneOverMiSquared = numpy.sum(MiSquared)
        FiOverMiSquared = numpy.sum(freqs[leftEdge:leftEdge+phase.size]*MiSquared)
        FiSquaredOverMiSquared =numpy.sum(((freqs[leftEdge:leftEdge+phase.size])**2 )*  MiSquared)
        FiPiOverMiSquared = numpy.sum(  freqs[leftEdge:leftEdge+phase.size] * phase  *  MiSquared)
        PiOverMiSquared = numpy.sum(phase *  MiSquared)

        D = oneOverMiSquared * FiSquaredOverMiSquared - (FiOverMiSquared)**2
        b = ( FiSquaredOverMiSquared * PiOverMiSquared - FiOverMiSquared * FiPiOverMiSquared ) / D
        m = ( oneOverMiSquared * FiPiOverMiSquared - FiOverMiSquared * PiOverMiSquared ) / D
#        print (" b,m ",b,m)
                                     

        return [b, m]

    def drawData(self):
        #this function updates the spectrum graph on the GUI
        if self.rawData.shape[1] == 0:
            #           if self.tdData[self.index].size == 0:
            return

        a= self.fig.gca()
        if self.new:

            #               xmin = 0
            #               xmax = self.cfreqs[-1]
            # much of this duplicates autoscale...
            xmin = 1700
            xmax = 2400 #default frequencies
            leftEdge =  int (xmin/self.step)
            rightEdge = int (xmax/self.step) + 1
            if leftEdge < 0:
                leftEdge = 0
            if rightEdge > self.specData[self.index].size:
                rightEdge = self.specData[self.index].size
            ymin=numpy.amin(self.specData[self.index][leftEdge:rightEdge].real)
            ymax=numpy.amax(self.specData[self.index][leftEdge:rightEdge].real)
            (ymin,ymax) = calc_lims(ymin,ymax)
            self.Fxlims = (xmin,xmax)
            self.Fylims = (ymin,ymax)

            ymin = numpy.amin(self.tdData[self.index])
            ymax = numpy.amax(self.tdData[self.index])
            (ymin,ymax)=calc_lims(ymin,ymax)
            xmin = 0
            xmax = self.times_ms[-1]
            self.Txlims= (xmin,xmax)
            self.Tylims=(ymin,ymax)
            # new windows open in time domain.
            #               print 'xlims:',xmin,xmax,' ylims:',ymin,ymax
            a.set_xlim((xmin,xmax))
            a.set_ylim((ymin,ymax))
            self.pax.set_xlabel("Time (ms)")
            self.pax.set_ylabel("FID")
#               self.pax.plot(self.times_ms, self.tdData[self.index])       #plot!
            self.line = Line2D(self.times_ms,self.tdData[self.index])
            a.add_line(self.line)

        if self.radButton.get_active(): # spectrum view
            self.line.set_data(self.cfreqs,self.specData[self.index].real)
        else: #FID view
            self.line.set_data(self.times_ms,self.tdData[self.index])

        self.canvas.draw_idle()

    def autoScale(self, dummy):
        #find the x limits so we only scale the viewable data.

        a= self.fig.gca()
        xlims =a.get_xlim()
        if self.radButton.get_active(): # is spectrum
            leftEdge =  int (xlims[0]/self.step)
            rightEdge = int (xlims[1]/self.step) + 1
            if leftEdge < 0:
                leftEdge = 0
            if rightEdge > self.specData[self.index].size:
                rightEdge = self.specData[self.index].size
            max = numpy.amax(self.specData[self.index,leftEdge:rightEdge].real)
            min = numpy.amin(self.specData[self.index,leftEdge:rightEdge].real)
        else:
            leftEdge =  int (xlims[0]/TIME_STEP/1000)
            rightEdge = int (xlims[1]/TIME_STEP/1000) + 1
#               print leftEdge,rightEdge
            if leftEdge < 0:
                leftEdge = 0
            if rightEdge > self.tdData[self.index].size:
                rightEdge = self.tdData[self.index].size
            max = numpy.amax(self.tdData[self.index,leftEdge:rightEdge])
            min = numpy.amin(self.tdData[self.index,leftEdge:rightEdge])
        a= self.fig.gca()
        a.set_ylim(calc_lims(min,max))
        self.canvas.draw_idle()

    def dialog_nodelete(self, widget, event, data=None):
        print("got delete event, ignoring")
        return True
    def measurePoints(self, ToolBar):
        #this function is called when the measure peak button is clicked
        #it prompts the user to click on the graph for the left and right limits of the calculations
        #it measures the data displayed, and shows a few numbers of interest and the limits clicked

        if self.measureDialogOpen:
            self.dialog.present()
            return
        self.measureDialogOpen = True

        #this ought to deselect any cursor option before going into edge selection mode
        self.toolbar._active = None
        if self.toolbar._idPress is not None:
            self.toolbar._idPress = self.toolbar.canvas.mpl_disconnect(self.toolbar._idPress)
            self.toolbar.mode = ''
        if self.toolbar._idRelease is not None:
            self.toolbar._idRelease = self.toolbar.canvas.mpl_disconnect(self.toolbar._idRelease)
            self.toolbar.mode = ''

        self.xdata=0.0
        self.leftEdge =0
        self.rightEdge =0
        self.dialog = gtk.Dialog("Pick Limits", self.window)        #make a dialog box that states:click on the left limit of the peak
        self.label = gtk.Label("Please click on the left limit of the peak")
        self.dialog.vbox.pack_start(self.label,True,True,0)
        position = self.dialog.get_position()
        self.dialog.move(position[0]-100, position[1] + 100)
        self.dialog.connect("delete_event",self.dialog_nodelete)
        self.dialog.show_all()

        self.waitForButton=1

        self.click = self.canvas.mpl_connect('button_press_event', self.onclick)
        return

    def onclick(self, event):
        #this callback is called when the graph is clicked when in measure peak mode
        if event.xdata is None: # in case we click outside the graph...
            return
#bounds check the xdata:
        self.xdata = event.xdata
        if self.xdata < 0:
            self.xdata =0
        if self.xdata > 1./TIME_STEP/2.:
            self.xdata = 1./TIME_STEP/2.
        if self.waitForButton == 0:
            return False
        elif self.waitForButton == 1:                   #waiting for left edge
            if self.lineLeft is not None:               #if another line exists
                Artist.setp(self.lineLeft, visible = True,xdata=self.xdata) #moves the old line
            else:
                self.lineLeft = self.pax.axvline(x=self.xdata)  #draws a line where the mouse was clicked
            self.leftFreq = self.xdata
            self.waitForButton = 2
            self.canvas.draw_idle()
            self.label.set_text("Please click on the right limit of the peak")
            self.dialog.show()
            return True
        elif self.waitForButton == 2:                   #waiting for right edge
            if self.lineRight is not None:              #if another line exists
                Artist.setp(self.lineRight, visible = True, xdata=self.xdata)
            else:
                self.lineRight = self.pax.axvline(x=self.xdata)
            self.rightFreq = self.xdata
            self.canvas.draw_idle()
            self.waitForButton = 0
            self.canvas.mpl_disconnect(self.click)

            if (self.leftFreq > self.rightFreq): #swap if they're backwards.
                temp = self.rightFreq
                self.rightFreq =self.leftFreq
                self.leftFreq=temp
            base.leftFreq = self.leftFreq
            base.rightFreq = self.rightFreq

            self.leftEdge =  int (self.leftFreq/self.step)
            self.rightEdge = int (self.rightFreq/self.step) + 1

            if self.leftEdge < 0:           #set to the edge
                self.leftEdge = 0
            if self.rightEdge >= self.specData[0].size:     #set to the edge
                self.rightEdge = self.specData[0].size-2
            self.measureDialogOpen = False
            self.dialog.destroy()
            self.usingOldLims(self)
            return True

        else: # should never be here!
            self.waitForButton = 0
            self.canvas.mpl_disconnect(self.click)
            return
        return True

    def killDialog(self, toBeKilled):
        toBeKilled.destroy()
        return

    def usingOldLims(self, TRUE):
        #this function is called when the 'using old limits' button is clicked
        #           print 'using old lims'
        #it measures the data displayed, and shows a few numbers of interest
        if self.leftFreq != 0 and self.rightFreq != 0:
            self.limsSet = True
        elif base.leftFreq and base.rightFreq:
            self.leftFreq =  base.leftFreq
            self.rightFreq = base.rightFreq
            self.limsSet = True
            # in case it wasn't already

        if not self.limsSet:
            popup_msg("The limits have not been set yet!",self.window)
            return
        self.echoCheck.set_sensitive(True)

        self.leftEdge =  int (self.leftFreq/self.step)
        self.rightEdge = int (self.rightFreq/self.step) + 1
        if self.leftEdge <0:
            self.leftEdge = 0
        if self.leftEdge >= self.specData[0].size:
            self.leftEdge = self.specData[0].size-1
        if self.rightEdge <0:
            self.rightEdge = 0
        if self.rightEdge >= self.specData[0].size:
            self.rightEdge = self.specData[0].size-1

        if self.lineLeft is not None:
            Artist.setp(self.lineLeft,xdata=self.leftFreq, visible = True)
        else:
            self.lineLeft = self.pax.axvline(x=(self.leftFreq))     #draws a line where the mouse was clicked
        if self.lineRight is not None:
            Artist.setp(self.lineRight,xdata=self.rightFreq,visible = True)
        else:
            self.lineRight = self.pax.axvline(x=(self.rightFreq))   #draws a line where the mouse was clicked
        self.canvas.draw_idle()

        Sofw = self.step*numpy.sum(self.specData[self.index][self.leftEdge:self.rightEdge+1].real)
        wSofw = self.step*numpy.sum(self.specData[self.index][self.leftEdge:self.rightEdge+1].real * self.cfreqs[self.leftEdge:self.rightEdge+1])
        w2Sofw = self.step*numpy.sum(self.specData[self.index][self.leftEdge:self.rightEdge+1].real * self.cfreqs[self.leftEdge:self.rightEdge+1]*self.cfreqs[self.leftEdge:self.rightEdge+1])
        maxVal = numpy.amax(self.specData[self.index][self.leftEdge:self.rightEdge+1].real)

        centroid = wSofw / Sofw
        stdDev =  numpy.sqrt( abs((w2Sofw/Sofw) - ( (wSofw / Sofw) ** 2 )) )

        integral = Sofw / float(self.step)

# want to find width at 10% of max.
        maxindex = numpy.argmax(self.specData[self.index][self.leftEdge:self.rightEdge+1].real)
#           print "maxindex is: ",maxindex," with maxval: ",self.specData[self.index][maxindex+self.leftEdge]
#now go up and down till we get below maxval*0.1
        highPoint = numpy.argmax(self.specData[self.index][self.leftEdge+maxindex:self.rightEdge+1].real < 0.1*maxVal)
        if highPoint == 0:
            highPoint = self.rightEdge
        else:
            highPoint += self.leftEdge+maxindex
        lowPoint = numpy.argmax(self.specData[self.index][self.leftEdge:self.leftEdge+maxindex+1][::-1].real < 0.1*maxVal)
        if lowPoint == 0:
            lowPoint = self.leftEdge
        else:
            lowPoint = self.leftEdge+maxindex-lowPoint
        width = highPoint-lowPoint

#calculate std dev based on stuff between 10% points.
        Sofw = self.step*numpy.sum(self.specData[self.index][lowPoint:highPoint+1].real)
        wSofw = self.step*numpy.sum(self.specData[self.index][lowPoint:highPoint+1].real * self.cfreqs[lowPoint:highPoint+1])
        w2Sofw = self.step*numpy.sum(self.specData[self.index][lowPoint:highPoint+1].real * self.cfreqs[lowPoint:highPoint+1]*self.cfreqs[lowPoint:highPoint+1])
        stdDev2 =  numpy.sqrt( abs((w2Sofw/Sofw) - ( (wSofw / Sofw) ** 2 )) )


#next, find FWHM, but start from edges and go inwards
#this could be optimized
        for h in range(maxindex):
            if (self.specData[self.index][self.leftEdge+h].real > 0.5*maxVal):
                lowPoint = self.leftEdge + h -1
                break
        for h in range(self.rightEdge+1-(maxindex+self.leftEdge)):
            if(self.specData[self.index][self.rightEdge-h].real > 0.5*maxVal):
                highPoint = self.rightEdge-h
                break
#           print "low: ",lowPoint*self.step," high: ",highPoint*self.step
        widFWHM = highPoint-lowPoint+1

#finally, find FWQM, but start from edges and go inwards
        for h in range(maxindex):
            if (self.specData[self.index][self.leftEdge+h].real > 0.25*maxVal):
                lowPoint = self.leftEdge + h -1
                break
        for h in range(self.rightEdge+1-(maxindex+self.leftEdge)):
            if(self.specData[self.index][self.rightEdge-h].real > 0.25*maxVal):
                highPoint = self.rightEdge-h
                break
#           print "low: ",lowPoint*self.step," high: ",highPoint*self.step
        widFWQM = highPoint-lowPoint+1


        dialog = gtk.Dialog("Peak Data",self.window)        #make a dialog box that shows the limits and the peakVal
        label = gtk.Label("The limits were " + str (round( (self.leftEdge * self.step), 2)) + " and "+ str (round( (self.rightEdge * self.step), 2) )+" Hz.\nThe max value in that range is " + str(round(maxVal,2))+"\nThe integral of the region is "+ str(round(integral,2)) + "\nThe centroid  is " + str(round(centroid,2))+ "\nThe standard deviation is " + str(round(stdDev2,2))+"\nFWHM: "+str(round(widFWHM*self.step,1))+" FWQM: "+str(round(widFWQM*self.step,1)))

        dialog.vbox.pack_start(label,True,True,0)
        position = dialog.get_position()
        dialog.move(position[0]-100, position[1] + 100)
        button = gtk.Button("Ok")
        dialog.vbox.pack_end(button,True,True,0)
        dialog.show_all()
        button.connect_object("clicked", self.killDialog, dialog)




###


    def hideUnhide(self, dummy1, dummy2):
        #this function toggles between showing the FID graph or the FT graph

        a = self.fig.gca()

        if self.radButton.get_active(): # changing to spectrum
            #               print 'changing to spectrum'
            # store old limits
            self.Txlims = a.get_xlim()
#               print 'Txlims',self.Txlims,a.get_xlim()
            self.Tylims = a.get_ylim()
#set new limits
            a.set_xlim(self.Fxlims,auto=False)
            a.set_ylim(self.Fylims,auto=False)
#set new labels
            self.pax.set_xlabel("Frequency(Hz)")
            self.pax.set_ylabel("Spectrum")
            self.drawData()
#allow measure points:
            self.button1.set_sensitive(True)    #enable edge selection
            self.button2.set_sensitive(True)    #since spectrum is shown
        else:
            #               print 'changing to FID'
#store old limits
            self.Fxlims = a.get_xlim()
            self.Fylims = a.get_ylim()
# set new limits
            a.set_xlim(self.Txlims,auto=False)
            a.set_ylim(self.Tylims,auto=False)

#               print 'Fxlims',self.Fxlims, a.get_xlim()
# set labels
            self.pax.set_xlabel("Time (ms)")
            self.pax.set_ylabel("FID")

#if measure lines are showing, wipe them out.
            if self.lineLeft is not None:              #if another line exists
                Artist.setp(self.lineLeft, visible = False)     #colours the old line white
            if self.lineRight is not None:              #if another line exists
                Artist.setp(self.lineRight, visible = False)    #colours the old line white


            self.drawData()
#disallow measure points
            self.button1.set_sensitive(False)       #since when FID shown
            self.button2.set_sensitive(False)       #inable to choose edges


        self.canvas.draw_idle()
        return

    def calculateEdges(self,record): #argument is which record to use
        #this function calculates the center of the region for image reconstruction. Uses the final projection twice
#        print (' in calculateEdges, edges are:',self.leftEdge,self.rightEdge)
        width = self.rightEdge - self.leftEdge
        if width%2 != 0:
            width += 1
        #want an even number.
        cropped1 = self.specData[record][self.leftEdge:self.leftEdge+width].real
        cropped2 = self.specData[record][self.leftEdge+width:self.leftEdge:-1].real # reverse direction

#really, should determine if the object spans an even or odd number of pixels and
#then choose where the center should be and if the number of pixels is even of odd based on that.
#This all assumes our projections are of objects that are reasonably similar to circles
        maxVal = 0
        maxPoint = 0
        for h in range(width//8): #only do even values out to width/4
            cropped3 = numpy.hstack((cropped1[2*h:width],cropped1[0:2*h]))
            corr  = numpy.dot(cropped2,cropped3)
            if corr > maxVal: 
                maxVal = corr
                maxPoint = 2*h

        for h in range(width//8-1): # we only do even values of h
            cropped3 = numpy.hstack((cropped1[width-2*(h+1):width],cropped1[0:width-2*(h+1)]))
            corr  = numpy.dot(cropped2,cropped3)
            if corr > maxVal:
                maxVal = corr
                maxPoint = -2*(h+1)

# need to increase size here too...
#        print 'before extra width: left,right: ',self.leftEdge+maxPoint//2,self.leftEdge+maxPoint//2+width,'center:',(self.leftEdge+self.leftEdge+maxPoint//2+maxPoint//2+width)/2.
        extrawid = int(width//4)
        if maxPoint %2 == 0:
            left = self.leftEdge+maxPoint//2 -extrawid
            right = self.leftEdge+width+extrawid+maxPoint//2
#               print 'using even number of points'
        else: # center is a point, not a space, want odd number of points
            #               print 'using odd number of points'
            maxPoint -= 1
            left = self.leftEdge+maxPoint//2 -extrawid
            right = self.leftEdge+width+extrawid+maxPoint//2 + 1

#           print 'bounds for recon: leftEdge: ',self.leftEdge,' rightEdge: ',self.leftEdge+width, 'offset: ',maxPoint
#        print 'after extra width: left,right: ',left,right,'center:',(left+right)/2.

#if we hit an edge, can't expect anything to work...
        if left < 0:
            left = 0
        if right > self.specData[0].size-1:
            right = self.specData[0].size-1
#        print 'max right is:',self.specData[0].size
#        print 'after extra width: left,right: ',left,right,'center:',(left+right)/2.

        return  left,right

    # for fitting to circle!
    def reconstructImage(self,filler=None):

        def circle_func(parms,x0):
            radius = (parms[1]-parms[0])/2.
            center = (parms[0]+parms[1])/2.
#               print 'circle parms: ',radius,center,parms[2]
            yvals = (radius*radius - (x0-center)*(x0-center))
            yvals[yvals < 0] = 0
            yvals = numpy.sqrt(yvals)
            return  yvals*parms[2]/radius

        def circle_residuals(parms,x0,ydata):
            return ydata - circle_func(parms,x0)

        #this function reconstructs an image based on the data collected
        if not self.limsSet:
            dialog = gtk.Dialog("Error", self.window)
            label = gtk.Label("Please use 'Pick Peak Limits' to set bounds for reconstruction.")
            dialog.vbox.pack_start(label,True,True,0)
            label.show()
            dialog.add_button("Ok", gtk.RESPONSE_CLOSE)
            dialog.show()
            response = dialog.run()
            dialog.destroy()
            return

        # sanity
        if self.string != 'Image':
            #               print "In reconstruct image, but isn't an image.  Shouldn't be here"
            return
        if self.numDataFiles < 3:
            #               print "In reconstruct image, but only have ", self.numDataFiles," files. Need at least 3."
            return
        progBarWin = progressBarWindow(self.numDataFiles-1, "Image Reconstruction",self.window)#creates a progressBarWindow and shows it, blank
        while gtk.events_pending():         #makes sure the GUI updates
            gtk.main_iteration()
# TASK 1: find center of projections

        ll = numpy.zeros(self.numDataFiles)
        rr = numpy.zeros(self.numDataFiles)

        if self.autoAlignCheck.get_active():
#            print 'doing autoalign'
            for i in range (self.numDataFiles):
                args = self.calculateEdges(i)    #this recalculates the edges, re-centers
                ll[i] = args[0]
                rr[i] = args[1]
                while gtk.events_pending():         #makes sure the GUI updates
                    gtk.main_iteration()
            left = args[0] # keep the last ones
            right = args[1]  
        else:
#            print ' not doing autoalign'
            args = self.calculateEdges(self.numDataFiles-1)
#            args = self.calculateEdges(128)
            left = args[0] # keep the last ones
            right = args[1]  
            for i in range(self.numDataFiles):
                ll[i] = left
                rr[i] = right
            while gtk.events_pending():         #makes sure the GUI updates
                gtk.main_iteration()
            
        #left and right are the limits for the reconstructed region.
#        print 'left: ',left,' right: ',right
#        for i in range(right-left):
#            print i,self.specData[-1][i+left].real

# TASK 2: measure width of projections to prepare filter

        #we go through the whole data set to determine the middle and the width for the Hann filter
        summ = numpy.zeros(right-left)
#        print 'left and right:',left,right
        for i in range(self.numDataFiles-1):            #note:  We do not care about the last file.
            summ += self.specData[i][ll[i]:rr[i]].real

        maxIndex = numpy.argmax(summ)
        maxVal = summ[maxIndex]
#        print ("maxVal, maxIndex:",maxVal,maxIndex)

        boundaryVal = maxVal / float(20)
        leftEdge = 0
        rightEdge = len(summ) -1

        caught = False

        for i in range(maxIndex):
            if summ[maxIndex - i] <= boundaryVal:
                leftEdge = maxIndex - i
                caught = True
                break

        if not caught:
            popup_msg("Warning - didn't find an edge?\nMaybe choose larger bounds?",self.window)
            progBarWin.failure()
            return
        caught = False

        for i in range(len(summ) - maxIndex):
            if summ[maxIndex + i] <= boundaryVal:
                rightEdge = maxIndex + i
                caught = True
                break

        if not caught:
            popup_msg("Warning - didn't find an edge?\nMaybe choose larger bounds?",self.window)
            progBarWin.failure() #test?
            return

# TASK 3: prepare filter
#what fraction of the region do the proejections actually take?
#originalWidth is the reconstruction region - from calculate edges, uses the width from peak peak limits
#newWidth is the width of the projection within it.
        originalWidth = right-left
        newWidth = rightEdge-leftEdge+1  # so here edges are inclusive - but this is just for filter width

#           print "originalWidth = " + str(originalWidth)
#           print "newWidth (width of peak) = " + str(newWidth)

#now construct the filter.
#this is based on 
#Kak, A. C., and M. Slaney, Principles of Computerized Tomographic Imaging, 
#New York, NY, IEEE Press, 1988. Chapter 3 I think.
#its a modified ramp that gets the DC offset right.

        # first load in 1/n^2/pi^2 in odd values of n
        width = 2*originalWidth
        indices = numpy.arange(width)
        filterArray = indices.copy()
        filterArray[0] = 1
        filterArray = -1/numpy.pi/numpy.pi/filterArray/filterArray
        filterArray = filterArray - filterArray*(indices%2 == 0)
        filterArray[0] = 0.25
        filterArray[(width+1)//2:width] = filterArray[::-1][(width+1)//2-1:width-1]
        filterArray = numpy.fft.fft(filterArray) *2 #

        
#ok, now had Hahn filter
        jc = 15 * (width) / float(newWidth) 
        filterArray[0:width//2+1] *= 0.5*(1+numpy.cos(numpy.pi*indices[0:width//2+1]/jc))
        if jc < width//2:
            filterArray[jc:width//2+1] *= 0
        filterArray[(width+1)//2:width] = filterArray[::-1][(width+1)//2-1:width-1]
#ok, filter is done!                              

        width = originalWidth

#        for i in range(width):
#            print filterArray[i].real

#        width = originalWidth
#        jc = 15 * (originalWidth) / float(newWidth) 
## this gives quite a bit of line broadening (a few hundred might be better)
##           print "JC is " + str(jc)

#        filterArray=numpy.zeros(width)
#        jval = numpy.arange(width//2+1)
        # this should work for width either odd or even.
#Hann filter:
#        filterArray[0:width//2+1] = 1.*jval/width * 0.5*(1+numpy.cos(numpy.pi*jval/jc))
#        if jc < width//2:
#            filterArray[jc:width//2+1] *= 0
#        filterArray[(width+1)//2:width] = filterArray[::-1][(width+1)//2-1:width-1]
#        filterArray[0] = 0.25/width



# TASK 4: fit a circle to the last record for amplitude corrections

# this could be used above to find the center and select the filter...
# left and right are the region, leftEdge, rightEdge are the guesses at the edges
#           print " doing circle stuff!"
#           print 'left edge:',leftEdge,' rightEdge: ',rightEdge
#           print 'left ',left,' right: ',right

        fleft = leftEdge
        fright = rightEdge-1
        fheight = 1.
        parms = numpy.array([fleft,fright,fheight])
        xvals=numpy.arange(right-left)

        fparms,cov,infodict,mesg,ier = optimize.leastsq(circle_residuals,parms,args=(xvals,self.specData[-1][left:right].real),full_output=True)
#           print 'guess params: ',parms
#           print 'fit params: ',fparms
        yvals=circle_func(fparms,xvals)

#ok, have a best fit semicircle, now calc correction factors
        cfactors = yvals/self.specData[-1][left:right].real
        cfactors[cfactors < 0.05 ] = 1.0
# don't do circle corrections if not wanted:
        if not self.circleCheck.get_active():
            cfactors = 1.0

#TASK 5: apply correction factors and filter
# print correction factors and spectrum the circle was fit to:
#        for j in range(right-left):
#            print xvals[j], self.specData[-1][left+j].real,yvals[j],cfactors[j]

        finalData = numpy.zeros((self.numDataFiles-1,width),complex)
        for i in range(self.numDataFiles-1):            #note:  We do not include the last file.
            peakData = numpy.hstack((self.specData[i][ll[i]:rr[i]].real*cfactors,numpy.zeros(width)))
            #zero fill by a factor of 2.

            #since FFTs switch around the order of the data
#            peakData = numpy.fft.fftshift(peakData)

            #inverse fourier transform and filter
            finalData[i] = numpy.fft.fft(numpy.fft.ifft(peakData) * filterArray)[0:width] #un zero-fill


# TASK 6: do the filtered backprojection. Why is this a separate routine?
        self.backproject(finalData, progBarWin)
        return


    def backproject(self, dataArray, progBarWin):
        #as the name suggests, this function is called to actually make the picture.
        #the picture is saved along with the data in its folder

        readings = dataArray.shape[0]
        size = dataArray[0].size
        angle = 180. / readings

        newSize = int (size * 1.4143 + 2)
        toAdd = newSize - size

        if toAdd % 2 != 0:
            toAdd += 1
        border = toAdd//2
        newSize = size +2*border
# prep for rotation:
        rotData = numpy.zeros((newSize,newSize))
        if newSize %2 == 0:
            bs2 = newSize/2.-0.5
#               print 'even pixels newSize: ',newSize,' offset from 0: ',bs2,' should be an 0.5'
        else:
            bs2 = float(newSize/2.)
#               print 'odd pixels newSize: ',newSize,' offset from 0: ',bs2, 'should be integer'
#           print 'size is: ', size
        #create arrays of i's and j's
        i_ = numpy.arange(newSize)-bs2
        i_ = i_[border:border+size]
#        iss = numpy.tile(i_ ,(size,1))
#        jss = numpy.tile(i_,(size,1)).transpose()
#will hold the final image data
        sumData = numpy.zeros((size,size))
        for k in range(readings):

            #stick zeros on front and back
            tempD = numpy.hstack((numpy.zeros(toAdd//2),dataArray[k].real,numpy.zeros(toAdd//2)))

            cang=-numpy.cos(angle * k* numpy.pi / 180)
            sang=numpy.sin(angle * k* numpy.pi / 180)
# now calculate where the points come from:
#            oif = iss * cang + jss * sang + bs2  
#this is expensive:
            oif = numpy.tile( i_ *cang, (size,1)) + numpy.tile(i_ *sang,(size,1)).transpose()+bs2
#            oif = numpy.outer(i_ * cang,ones) + numpy.outer(ones, i_ * sang)+bs2
            #New!
#            oif = oif[border:border+size,border:border+size]            
            oi = numpy.int_(oif) # truncate

#coefficients for linear interpolation
            co2 = oif-oi # +ve, less than 1.
            co1 = 1.-co2

#               for i in numpy.arange(border,newSize-border):
#                   for j in numpy.arange(border,newSize-border):
#                       ii = oi[i,j]
#                       rotData[i,j] = co1[i,j]* tempD[ii] + co2[i,j]* tempD[ii+1]
# vectorize:
            val1 = tempD[oi] #produces new 2D array
            val2 = tempD[oi+1]
#this is also expensive:
            rotData = co1*val1+co2*val2

#               sumData += rotData[border:border+size,border:border+size]
            sumData += rotData
            progBarWin.iteration()
            if progBarWin.abortFlag:
                progBarWin.failure() #close the window
                return
            while gtk.events_pending():
                gtk.main_iteration()

        max = numpy.amax(sumData)
        min = numpy.amin(sumData)
#        print ('max, min:',max,min)
# set anything less than 0 to 0
        max = numpy.amax(sumData)
        min = numpy.amin(sumData)
# scale and gamma correct
#To get the scaling 'correct' (back to original projections, should multiply by: pi/2/NPROJ
#rather than divide by max, but that's irrelevant for experimental data.
        
        sumData = sumData*255.49999/max + 0.5  #highest point is 255.99999
# so that -0.5 -> 0.5 will map to 0
#and 254.5 -> 255.5 will map to 255.5
        sumData = sumData*(sumData>0)
        gamma = 2.0
        sumData = numpy.uint8(numpy.power(sumData/256,gamma)*256)
        max = numpy.amax(sumData)
#        print " after gamma encode, max is: ",max

        temp0 = Image.frombuffer('L',(size,size),sumData,'raw','L',0,1)
#parameters for raw decoder are mode, stride, orientation:
# mode L = 8bit grey, stride = 0 - no padding, orientation 1 - first line is top of image
        if self.saveName is None:
            pathName = self.acqName
        else:
            pathName = self.saveName
#           print 'saving image to: ',pathName+'/Image.png'
        temp0.save(os.path.join(pathName,"Image.png"))
        if CLASS_USE:
            temp0.save(os.path.join(TEMP_DIR,"Image.png"))

        #make image_proc_params.txt
        outFile = open(os.path.join(pathName, 'image_proc_params.txt'), 'w')
        outFile.write("phase: " + str(self.appliedPhase) + "\n")
        outFile.write("line broadening: " + str(self.lbAdjust.get_value()) + "\n")
        outFile.write("left shift: " + str(int(self.leftShift.get_value())) + "\n")
        outFile.write("spectrum points: " + str(int(self.freqDomExpand.get_value())) + "\n")
        outFile.write("echo: "+str(self.echoCheck.get_active())+"\n")
        outFile.write("multiple: "+str(self.multCheck.get_active())+"\n")
        outFile.write("num echoes: "+str(self.multNumAdj.get_value())+"\n")
        outFile.close()

        if CLASS_USE:
            npathName=os.path.join(TEMP_DIR,'Image.png')
        else:
            npathName=os.path.join(pathName ,'Image.png')

        call = IMAGE_VIEWER + ' "'+ npathName + '"'
#        print('call for view is: ',call)
        args = shlex.split(call)
#           print 'args: ',args
        subprocess.Popen(args)
#           os.system(call)
        self.leftEdge =  int (self.leftFreq/self.step)      #this is to find the index of the left side of the peak
        self.rightEdge = int (self.rightFreq/self.step) + 1
        progBarWin.failure() #close the window

    def delete_event(self, widget, event, data=None):
        if (self.measuring):
            #               popup_msg("You are currently measuring, and cannot close this window.",self.window)
            return True
        else:
            if self.measureDialogOpen:
                self.dialog.destroy()
            self.window.destroy()
            del self
            gc.collect()
            return False


    def blink(self, killCommand = None, source_id = None):
        if not self.measuring or killCommand == "Kill":

            self.ebBlinker.modify_bg(gtk.STATE_NORMAL, None)
            if source_id is not None:
                gobject.source_remove(source_id)
            return False
        else:
            #               self.blinker.set_sensitive(True)
            if self.coloured:
                self.ebBlinker.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("yellow"))
                self.coloured = False
            else:
                if self.waiting:
                    self.ebBlinker.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("blue"))
                else:
                    self.ebBlinker.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("red"))
                self.coloured = True
            return True

    def plusMinus(self, value):
        #this function is called to change the index of the data displayed
        #in arrayed data and image data

        if value == "Plus" and (self.index < self.numDataFiles-1):
            self.index += 1
            self.minusButton.set_sensitive(True)
            if self.index == self.numDataFiles-1:
                self.plusButton.set_sensitive(False)
        elif value == "Minus" and (self.index > 0):
            self.index -= 1
            self.plusButton.set_sensitive(True)
            if self.index == 0:
                self.minusButton.set_sensitive(False)
        else:
            return
        if self.phaseOpen:
            self.phaseDialog.destroy()
            self.phaseAdjust.destroy()
            self.phaseOpen = False
        if self.string == "Array":
            self.varValLabel.set_text(str(self.arrVal[self.index]))
            self.varValLabel.show()
        self.indexVal.set_text(str(self.index+1) + '/' + str(self.numDataFiles))
        self.indexVal.show()
        self.scanLabel.set_text(str(self.numScans[self.index]))

        self.drawData()

    def phaseDone(self, button=None):
        #this function is called when either the cancel or apply buttons are clicked
        #either applies or discards the phasing changes made

        if button == "Cancel":
            if self.phaseOpen:
                self.phaseDialog.destroy()
                self.phaseAdjust.destroy()
                self.phaseOpen = False
            self.drawData()
        elif button == "Apply":
            #               print 'phaseDone, doing phase'
            self.specData *= numpy.exp(1j*numpy.pi/180.*(self.phaseAdjust.get_value()-self.appliedPhase))

            self.appliedPhase = self.phaseAdjust.get_value()
            base.phase = self.phaseAdjust.get_value()
            self.phaselabel.set_text(str(self.appliedPhase))
            self.phaseDialog.destroy()
            self.phaseAdjust.destroy()
            self.phaseOpen = False
#               print 'phaseDone, doing drawData'
            self.drawData()
#               print 'phaseDone, leaving'
        else:
            return
    def phaseDelete(self, widget, event,data = None):
        self.phaseDone("Cancel")


    def phaseClicked(self, filler = None):
        #this function is called when the phase button is clicked
        #brings up a window with a slider, an apply and a cancel button
        #allows the phasing of the data

        if not self.phaseOpen:
            dialog = gtk.Dialog("Phase Adjust", self.window,gtk.DIALOG_DESTROY_WITH_PARENT)
            dialog.set_default_size(300,100)
            position = dialog.get_position()
            dialog.move(position[0], position[1] + 200)
            label = gtk.Label("Phase")
            label.show()
            dialog.vbox.pack_start(label,True,True,0)
            self.phaseAdjust = gtk.Adjustment(self.appliedPhase, 0, 360, 1, 1)
            phaseSlider = gtk.HScale(self.phaseAdjust)
            phaseSlider.connect_object("value-changed", self.phasing, None )
            phaseSlider.show()
            dialog.vbox.pack_start(phaseSlider,True,True,0)
            hbox = gtk.HBox()
            hbox.show()
            dialog.vbox.pack_start(hbox,True,True,0)
            cancelButton = gtk.Button("Cancel")
            cancelButton.connect_object("clicked", self.phaseDone, "Cancel")
            cancelButton.show()
            dialog.connect("delete_event",self.phaseDelete)
            applyButton = gtk.Button("Apply")
            applyButton.connect_object("clicked", self.phaseDone, "Apply")
            applyButton.show()
            hbox.pack_start(cancelButton,True,True,0)
            hbox.pack_start(applyButton,True,True,0)
            dialog.show()
            self.phaseDialog = dialog
            self.phaseOpen = True
        else:
            self.phaseDialog.present()



# this will copy the raw data into the selected directory and and also write the FT'd spectra.
    def saveData(self, filler=None):
        # first thing, need to get a name from the user with gtkdialog, check overwrite etc.
        fileChooser = gtk.FileChooserDialog(title = "Save As...", parent=self.window, action=gtk.FILE_CHOOSER_ACTION_CREATE_FOLDER, buttons=("Cancel",gtk.RESPONSE_CANCEL, "Open", gtk.RESPONSE_OK) )
        fileChooser.set_current_folder(DATA_DIR)
        response = fileChooser.run()

        foldName = fileChooser.get_current_folder()
        fileName = fileChooser.get_filename()

        # for select_folder, these seem to be the same.
        # from the docs, create_folder should be what we want, but select seems better...
        # either way, the file choose creates the directory for us. Argh!

        fileChooser.destroy()

        if response != gtk.RESPONSE_OK:
            return

        path,name = os.path.split(fileName)
        print('got path: ',path, ' and name ',name)

        if fileName == self.acqName: # then we're writing on top of what we'll delete!
            #               print "looks like you're writing on top of yourself. Not doing anything."
            return # the good news is we don't need to do anything!
        if not os.path.isdir(fileName): #file name is fully qualified
        #it doesn't look like the filechooser would let us get here anyway
            popup_msg(fileName+" is a bare file, won't overwrite",self.window)
            return


        # check if the selected name exists (chooser creates it, so it always does!)
        dirList = os.listdir(path)
        if name in dirList:
            dirList2 = os.listdir(fileName)
            if dirList2 != []: # if the directory is empty, go ahead and remove it
        #otherwise ask for overwrite confirmation
                dialog = gtk.Dialog("Overwrite?", self.window)
                label = gtk.Label(fileName+"\nAlready exists, Overwrite?")
                dialog.vbox.pack_start(label,True,True,0)
                dialog.add_buttons("Cancel", gtk.RESPONSE_NO, "Overwrite", gtk.RESPONSE_YES)
                dialog.show_all()
                response = dialog.run() # -8 is yes, and -9 is no
                dialog.destroy()
                if (response != gtk.RESPONSE_YES ):
                    popup_msg("Save aborted, not overwriting",self.window)
                    return

            #delete stuff
            try:
                print('trying to remove ',fileName)
                shutil.rmtree(fileName)
            except:
                popup_msg("Problem clearing the old directory. Check permissions?",self.window)
                return

        # now need to copy the data.
        try:
            print('trying to copy from ',self.acqName,' to ',fileName)
            shutil.copytree(self.acqName,fileName) #from shutil
        except:
            popup_msg("trouble creating the data directory, permission problem?",self.window)
            return

        self.saveName = fileName
        self.window.set_title(fileName)
        return

# so all that was only done if saveName was None. We write the processed spectrum only the second time.
# on file open, we set saveName and acqName to the same thing


    def saveSpec(self,filler=None):
#this could be optimized - use tofile...
        if self.saveName is None:
            mySaveName = self.acqName
        else:
            mySaveName = self.saveName
        if (self.string == "Image") or (self.string == "Array"):
            savedTo = "spectrumN.txt"
            for h in range(self.specData.shape[0]):
                outFile = open(os.path.join(mySaveName,'spectrum') + str(h) + '.txt', 'w')
                numpy.savetxt(outFile,numpy.vstack((self.cfreqs,self.specData[h].real,self.specData[h].imag)).transpose(),fmt='%-12.5e')
                outFile.close()
        else:
            savedTo = "spectrum.txt"
            outFile = open(os.path.join(mySaveName,'spectrum.txt'), 'w')
            numpy.savetxt(outFile,numpy.vstack((self.cfreqs,self.specData[0].real,self.specData[0].imag)).transpose(),fmt='%-12.5e')
            outFile.close()

        outFile = open(os.path.join(mySaveName,'proc_params.txt'), 'w')
        outFile.write("phase: " + str(self.appliedPhase) + "\n")
        outFile.write("line broadening: " + str(self.lbAdjust.get_value()) + "\n")
        outFile.write("left shift: " + str(int(self.leftShift.get_value())) + "\n")
        outFile.write("spectrum points: " + str(int(self.freqDomExpand.get_value())) + "\n")
        outFile.write("echo: "+str(self.echoCheck.get_active())+"\n")
        outFile.write("multiple: "+str(self.multCheck.get_active())+"\n")
        outFile.write("num echoes: "+str(self.multNumAdj.get_value())+"\n")
        outFile.close()
        if self.saveName is None:
            popup_msg("Warning! Frequency domain data has been saved to:\n"+os.path.join(mySaveName,savedTo)+
                  "\nbut will be deleted on program close.  Use 'Save Data' first to keep permanently.",self.window)
        else:
            popup_msg("Frequency domain data has been saved to:\n"+os.path.join(mySaveName,savedTo),self.window)
        return

    def on_key_press_event(self, widget, event):
        keyname = gtk.gdk.keyval_name(event.keyval)
#        print ('key %s (%d) pressed' % (keyname,event.keyval))
        if event.state & gtk.gdk.CONTROL_MASK and keyname == 'w':
            self.delete_event(widget,event)
            return True
        return False

    def run (self):
        self.lineLeft = None
        self.lineRight = None
        self.step = 1
        self.numDataFiles =0
        self.rawData = numpy.array(())
        self.index = 0
        self.idleProcess = None
        self.appliedPhase = base.phase
        self.phaseOpen = False
        self.leftFreq = base.leftFreq
        self.rightFreq = base.rightFreq
        if self.leftFreq != 0 and self.rightFreq != 0:
            self.limsSet = True
        else:
            self.limsSet = False #measure with old will set this.
#read in a file
#           print 'in run with string: ',self.string
        incomplete = 0
        junk,fileName = os.path.split(self.acqName)
        if (self.string == "Single"):
            args = readAFile(os.path.join(self.acqName,"data.txt"))
            if args[1] == -1:
                popup_msg("Trouble reading file: "+os.path.join(self.acqName,"data.txt"),base.window)
                return
            self.rawData = args[0]
            self.numScans.append(args[1])
            self.numDataFiles = 1
##              print 'numScans:',self.numScans

        elif (self.string == "Image") or (self.string == "Array"):
            dirList = os.listdir(self.acqName)
            for i in range(len(dirList)):
                if "data" in dirList[i] and dirList[i][-4:] == ".txt":
                    self.numDataFiles += 1
            if self.numDataFiles == 0:
                popup_msg("Didn't find any data files?",base.window)
                return
#               print 'going to look for: ',self.numDataFiles,' files.'
            warned = 0
            for i in range(self.numDataFiles):
                args = readAFile(os.path.join(self.acqName,"data") + str(i) + ".txt")
                if args[1] == -1:
                    popup_msg("Trouble reading file: "+ os.path.join(self.acqName,"data")+str(i)+".txt",base.window)
                    return
                if i == 0:
                    npts = args[0].size
                elif npts != args[0].size:
                    if warned == 0:
                        popup_msg("Data File # points mismatch.\nThis may happen if data is corrupt, or number of points acquired is arrayed.",base.window)
                        warned = 1
                    if npts < args[0].size:
                        args[0] = args[0][0:npts]
                    else:
                        args[0] = numpy.hstack((args[0],numpy.zeros(npts-args[0].size)))

                if i == 0:
                    self.rawData = args[0].copy()
                elif i > 0 and args[0].size == self.rawData.shape[-1] :
                    self.rawData = numpy.vstack((self.rawData,args[0]))
                else:
                    popup_msg('It appears there is some corrupt data here, size mismatch in file: '+str(i),base.window)
                    return
                self.numScans.append(args[1])
                if self.numScans[i] != self.numScans[0]:
                    incomplete = 1
#                   print 'numScans:',self.numScans
#                   print 'read data file ',i,'shape is ',self.rawData.shape

            if (self.string == "Array"):
                try:
                    self.arrVal = []
                    inFile = open(os.path.join(self.acqName,"array.txt"))
                    temp = inFile.readline()
                    self.arrVar = temp[1:]
                    while 1:
                        string = inFile.readline()

                        if (string == ''):          #then end of file reached
                            break
                        if string[0] != '#':
                            self.arrVal.append(int(string))
                    inFile.close()
                except:
                    pass

        self.waitForButton = 0  #this is for edge determining

        datetime = time.asctime()
        mydate = datetime[0:10] + ' ' +datetime[-4:]
        mytime = datetime[11:19]

#build the window for this data set.
        self.window = gtk.Window()
        try:
            self.window.set_icon_from_file(os.path.join(ICON_PATH,"Anmr-icon"+ICON_EXTENSION))
        except:
            pass
        self.window.set_default_size(400,400)
        self.window.set_title(fileName)
        self.window.connect("delete_event", self.delete_event)
        
        self.window.connect('key_press_event', self.on_key_press_event)
        vboxTop = gtk.VBox()

        vboxTop.set_homogeneous(False)
        self.window.add(vboxTop)

        hbox = gtk.HBox()
        vboxTop.pack_start(hbox,True,True,0)
        hbox.show()

        vbox = gtk.VBox()
        hbox.pack_start(vbox,True,True,0)

        fig = Figure(figsize=(4,3), dpi=100)
        pax = fig.add_subplot(111,autoscalex_on=False,autoscaley_on=False)
        pax.set_position([0.2, 0.2, 0.7, 0.70])
        self.canvas = FigureCanvas(fig)  # a gtk.DrawingArea
        self.canvas.set_property('height-request', 150)
        vbox.pack_start(self.canvas, True, True,0)
#can't find icons in windows - fixed
#           self.toolbar = NavigationToolbar2(self.canvas, self.window)
        self.toolbar = MyToolbar(self.canvas, self.window)

        self.fig = fig
        self.pax = pax

        vbox.pack_start(self.toolbar, False, False,0)
        #variables

#        self.canvas = canvas

        vboxPrime = gtk.VBox(False,8)
        hbox.pack_start(vboxPrime,False,True,0)

        value = gtk.Label(self.acqName)
        value.set_ellipsize(pango.ELLIPSIZE_START)
        vboxPrime.pack_start(value,True,True,0)

#parse the variables
        varNames = []
        varVals = []
        varUnits = []

        inFile = open(os.path.join(self.acqName,"commands.txt"))    #assuming the folder name is provided in streeng

        args = parse_prog_defs(os.path.join(self.acqName,"commands.txt"))
        if args[0] == 0:
            popup_msg("Error reading program for parameters",self.window)
        else:
            inFile = open(os.path.join(self.acqName,"commands.txt"))    #assuming the folder name is provided in streeng

            if self.string != 'Array':
                self.arrVar = "__XX__"
            for line in inFile:
                line2 = line.split()
                if line2 != []:
                    for j in range(len(args[0])):
                        if line2[0][1:] == args[0][j] and line2[1] == '=' : #match for value
                            #                               print 'match:', args[0][j],args[3][j],args[4][j]
                            #                               print line2
                            varNames.append(args[0][j])
                            varVals.append(line2[2])
                            varUnits.append(args[4][j])
#args[0] is the names, then min, max value, units

        if self.string == 'Array':
            hboxtemp = gtk.HBox()
            label = gtk.Label("Arrayed Variable:")
            label.show()
            hboxtemp.pack_start(label,True,True,0)
            label = gtk.Label(self.arrVar.strip())
            label.show()
            hboxtemp.pack_start(label,True,True,0)
            vboxPrime.pack_start(hboxtemp,True,True,0)
            hboxtemp = gtk.HBox()
            label = gtk.Label("Current Value:")
            label.show()
            hboxtemp.pack_start(label,True,True,0)
            self.varValLabel = gtk.Label(str(self.arrVal[self.index]))
            self.varValLabel.show()
            hboxtemp.pack_start(self.varValLabel,True,True,0)
            vboxPrime.pack_start(hboxtemp,True,True,0)

        inFile.close()

        varHbox = gtk.HBox(False,0)
        vboxPrime.pack_start(varHbox,True,True,0)
        vbox1 = gtk.VBox(True,2)
        vbox2 = gtk.VBox(True,2)
        varHbox.pack_start(vbox1,False,True,8)
        varHbox.pack_start(vbox2,False,True,8) #want options to not expand?

        for i in range(len (varNames) ):

            if varUnits[i] == "''" or varUnits[i] == '""' or varUnits[i] == '':
                toInsert = varNames[i]
            else:
                toInsert = varNames[i] + " (" + varUnits[i] + ")"
            name = gtk.Label( toInsert +" :")
            value = gtk.Label( varVals[i] )
            vbox1.pack_start(name,True,True,0)
            vbox2.pack_start(value,True,True,0)
            name.show()
            value.show()

        if self.string == "Image":

            name = gtk.Label("Number of Projections: ")

            if not self.measuring:
                value = gtk.Label( str(self.numDataFiles -1)+'+1')
            else:
                value = gtk.Label("1")
            vbox1.pack_start(name,True,True,0)
            vbox2.pack_start(value,True,True,0)
            self.numProjsLabel = value

        name = gtk.Label("Total time domain points: ")
        value = gtk.Label( str(self.rawData.shape[-1]))
        vbox1.pack_start(name,True,True,0)
        vbox2.pack_start(value,True,True,0)

        hboxtemp = gtk.HBox(False)
        vboxPrime.pack_start(hboxtemp,True,True,0)
        name = gtk.Label("Scans: ")
        self.scanLabel = gtk.Label(str(self.numScans[0]))
        vbox1.pack_start(name,True,True,0)
        vbox2.pack_start(self.scanLabel,True,True,0)
        varHbox.show_all()

        indexLabel = gtk.Label("Index: ")
        indexLabel.show()
        self.indexVal = gtk.Label(str(self.index+1) +'/'+str(self.numDataFiles))
        self.indexVal.show()
        self.indexLabel = indexLabel

        hboxtemp = gtk.HBox()
        vboxPrime.pack_start(hboxtemp,True,True,0)
        hboxtemp.show()
        hboxtemp.pack_start(indexLabel,True,True,0)
        hboxtemp.pack_start(self.indexVal,True,True,0)

        self.minusButton = gtk.Button("-")
        self.minusButton.set_property('height-request', 50)
        self.minusButton.show()
        self.minusButton.connect_object("clicked", self.plusMinus, "Minus")

        self.plusButton = gtk.Button("+")
        self.plusButton.set_property('height-request', 50)
        self.plusButton.show()
        self.plusButton.connect_object("clicked", self.plusMinus, "Plus")
        self.plusButton.set_sensitive(False)
        self.minusButton.set_sensitive(False)
        if self.numDataFiles > 1:
            self.plusButton.set_sensitive(True)

        hboxtemp = gtk.HBox()
        vboxPrime.pack_start(hboxtemp,True,True,0)
        hboxtemp.show()
        hboxtemp.pack_start(self.plusButton,True,True,0)
        hboxtemp.pack_start(self.minusButton,True,True,0)

        #sliders and such
        hboxPrime = gtk.HBox()      #hboxPrime is the box that holds the buttons and sliders at the bottom
        hboxPrime.set_property('height-request', 90)
        vboxTop.pack_end(hboxPrime, False, False,0)

        vboxTemp = gtk.VBox()
        hboxPrime.pack_start(vboxTemp,True,True,0)

        self.phaseButton = gtk.Button("Phase")
        vboxTemp.pack_start(self.phaseButton,True,True,0)
        self.phaseButton.connect_object("clicked", self.phaseClicked, True)
        self.phaselabel = gtk.Label(str(self.appliedPhase))
        vboxTemp.pack_start(self.phaselabel,True,True,0)
        label = gtk.Label("Broadening")
        vboxTemp.pack_start(label,True,True,0)
        self.lbAdjust = gtk.Adjustment(value = base.broadening, lower = 0, upper = 50, step_incr = 0.1)
        self.lbspin_button = gtk.SpinButton(self.lbAdjust, 0.1, 1) #args are climb_rate and digits
        vboxTemp.pack_start(self.lbspin_button,True,True,0)

        vboxTemp = gtk.VBox()
        hboxPrime.pack_start(vboxTemp,True,True,0)
        label = gtk.Label("Left Shift")
        vboxTemp.pack_start(label,True,True,0)
        self.leftShift = gtk.Adjustment(base.leftShift, -100000, 100000, 1)
        self.shiftSpinButton = gtk.SpinButton(self.leftShift,1,0)
        vboxTemp.pack_start(self.shiftSpinButton,True,True,0)

        label = gtk.Label("Spectrum Points")
        vboxTemp.pack_start(label,True,True,0)

        fnpts = base.freqDomExpand
        self.freqDomExpand = gtk.Adjustment(fnpts, 64, 131072, 64)
        self.freqDomExpandButton = gtk.SpinButton(self.freqDomExpand,64,0)
        vboxTemp.pack_start(self.freqDomExpandButton,True,True,0)

        #add check buttons
        self.checkVbox = gtk.VBox()
        hboxPrime.pack_start(self.checkVbox,True,True,0)


        self.echoCheck = gtk.CheckButton("Full Echo")
        multCheckHbox = gtk.HBox()
        self.multCheck = gtk.CheckButton("Multiple Echoes")
        if base.multCheck:
            self.multCheck.set_active(True)
        if base.echoCheck:
            self.echoCheck.set_active(True)


        self.multNumAdj = gtk.Adjustment(base.necho,1,64,1)
        spinButton = gtk.SpinButton(self.multNumAdj, 1, 0)

        multCheckHbox.pack_start(self.multCheck,True,True,0)
        multCheckHbox.pack_start(spinButton,True,True,0)

        self.checkVbox.pack_start(multCheckHbox,True,True,0)
        self.checkVbox.pack_start(self.echoCheck,True,True,0)


        if not base.leftFreq or not base.rightFreq:
            self.echoCheck.set_sensitive(False)


        self.button3 = gtk.Button("Auto\nScale")
        self.button3.connect_object("clicked", self.autoScale, self.toolbar)
        hboxPrime.pack_start(self.button3,True,True,0)
        self.button1 = gtk.Button("Pick Peak\n  Limits")
        self.button1.connect_object("clicked", self.measurePoints, self.toolbar)
        hboxPrime.pack_start(self.button1,True,True,0)
        self.button2 = gtk.Button("Measure With\n  Prior Limits")
        self.button2.connect_object("clicked", self.usingOldLims, True)
        hboxPrime.pack_start(self.button2,True,True,0)

        self.button1.set_sensitive(False)
        self.button2.set_sensitive(False)

        self.radButton = gtk.ToggleButton("    FID/\nspectrum")
        self.radButton.connect_object("clicked", self.hideUnhide, self.canvas, self.canvas)

        hboxPrime.pack_start(self.radButton,True,True,0)

        #add write spectrum button

        self.saveDataButton = gtk.Button("Save Data")
        self.saveDataButton.connect_object("clicked", self.saveData, None)

        hboxPrime.pack_start(self.saveDataButton,True,True,0)

        self.saveSpecButton = gtk.Button(" Write\nSpectrum")
        self.saveSpecButton.show()
        self.saveSpecButton.connect_object("clicked",self.saveSpec,None)
        hboxPrime.pack_start(self.saveSpecButton,True,True,0)


        makeImageButton = gtk.Button("Reconstruct\n  Image")
#           makeImageButton.set_property('height-request', 75)
        makeImageButton.show()
        makeImageButton.connect_object("clicked", self.reconstructImage,None)
        self.makeImageButton = makeImageButton
        hboxPrime.pack_start(makeImageButton, False, False,0)

        self.autoAlignCheck = gtk.CheckButton("Auto Align\nProjections")
        hboxPrime.pack_start(self.autoAlignCheck,True,True,0)
        if base.autoAlign:
            self.autoAlignCheck.set_active(True)

        self.circleCheck = gtk.CheckButton("Circle Correct\nProjections")
        hboxPrime.pack_start(self.circleCheck,True,True,0)
        if base.circleCheck:
            self.circleCheck.set_active(True)


        if (self.string == "Image" and incomplete == 0 and self.numDataFiles >2 ):
            makeImageButton.set_sensitive(True)
        else:
            makeImageButton.set_sensitive(False)        #this greys it out

        if (self.string == "Image") or (self.string == "Array"):
            indexLabel.show()
            self.indexVal.show()
            self.plusButton.show()
            self.minusButton.show()
        else:
            indexLabel.set_sensitive(False)
            self.indexVal.set_sensitive(False)
            self.plusButton.set_sensitive(False)
            self.minusButton.set_sensitive(False)




        self.lbspin_button.connect_object("value-changed", self.procParamChanged, "broad")
        leftHandler = self.shiftSpinButton.connect_object("value-changed", self.procParamChanged, "leftShift")
        freqDomHandler = self.freqDomExpandButton.connect_object("value-changed", self.procParamChanged, "freqDom")
        self.multCheck.connect_object("toggled", self.procParamChanged, "multCheck")
        self.echoCheck.connect_object("toggled", self.procParamChanged, "echoCheck")
        self.multNumAdj.connect_object("value_changed",self.procParamChanged, "multNum")
        self.autoAlignCheck.connect_object("toggled",self.procParamChanged,"autoAlignCheck")
        self.circleCheck.connect_object("toggled",self.procParamChanged,"circleCheck")
        retValues = []


        inFile = open(os.path.join(self.acqName,"commands.txt"), "r")   #assuming the folder name is provided in path
        while 1:
            string = inFile.readline()
            if (string == ''):                  #then end of file reached
                break
            iden = string[0:5]
            if ( iden == "#from"):
                oldfileName = string[7:]
            if ( iden == "#date"):
                olddate = string[7:22]
            if ( iden == "#time"):
                oldtime = string[7:15]
        inFile.close()
        if not self.measuring:
            hboxtemp = gtk.HBox()
            vboxPrime.pack_start(hboxtemp,True,True,0)
            if incomplete == 1:
                name = gtk.Label("INCOMPLETE Date: ")
            else:
                name = gtk.Label("Date: ")
            value = gtk.Label(olddate)
            hboxtemp.pack_start(name,True,True,0)
            hboxtemp.pack_start(value,True,True,0)

            hboxtemp = gtk.HBox()
            vboxPrime.pack_start(hboxtemp,True,True,0)
            name = gtk.Label("Time: ")
            value = gtk.Label(oldtime)
            hboxtemp.pack_start(name,True,True,0)
            hboxtemp.pack_start(value,True,True,0)

        hboxtemp = gtk.HBox()
        vboxPrime.pack_start(hboxtemp,True,True,0)
        name = gtk.Label("Program: ")
        value = gtk.Label(oldfileName.strip())
        hboxtemp.pack_start(name,True,True,0)
        hboxtemp.pack_start(value,True,True,0)

        if self.measuring:

            self.blinker = gtk.Label("In Progress...")
            self.ebBlinker = gtk.EventBox()
            self.ebBlinker.add(self.blinker)

            vboxPrime.pack_start(self.ebBlinker,True,True,0)
            self.blinker.show()

            self.coloured = False
            self.waiting = False
            base.measuring = True
            self.source_id = gobject.timeout_add(250, self.blink)   #500 ms, calls blink

        self.window.show_all()
        if hideEchoCheck:
            self.checkVbox.hide()
        if hideProjectionCorrections:
            self.circleCheck.hide()
            self.autoAlignCheck.hide()



        self.shiftSpinButton.handler_block(leftHandler)
#           self.freqDomExpandButton.handler_block(freqDomHandler)
        self.shiftSpinButton.set_range(-self.rawData.shape[-1],self.rawData.shape[-1])
#           self.freqDomExpandButton.set_range(self.rawData.shape[-1],262144)
        self.shiftSpinButton.handler_unblock(leftHandler)
#           self.freqDomExpandButton.handler_unblock(freqDomHandler)
        self.processData(self)
        self.drawData() # image - live or old
        self.new = False
#force window to open on top, but don't make it stay there.
        self.window.set_keep_above(True)
        self.window.set_keep_above(False)
        return
class progSelect:

    measuring = False
    vbox = gtk.VBox(False, 0)       #this box is the global box for this window
    comps = []          #this list contains all the static components at the bottom
    varList = []        #this list contains all current variable names, and values
    varEntries = []     #this list contains all the text and adjustment objects to reference
    varNames = []       #list of variable names in the acquisition window currently
    boxList = []        #this list contains all the boxes used to contain the variable value entry boxes
    progList = []
    oldDataList = []
    numRuns = 4
    fileLabel = ''
#       win = ''
#       ax = ''

#"global" processing parameters
    phase = 0.
    broadening = 0.
    freqDomExpand = 65536
    leftShift = 0
    necho = 1
    multCheck = 0
    echoCheck = 0
    leftFreq=0
    rightFreq=0
    autoAlign = True
    circleCheck = True
    data_set_num = -1 # we increment this each time acquire is pressed.



    def __init__(self):

        try:    # to check whether the path to the data is a valid path
            os.chdir(DATA_DIR)
        except: #if it isn't, make it so
            os.mkdir(DATA_DIR)
        os.chdir(DATA_DIR)
        self.definedVars = []
        self.leftEdge = None
        self.rightEdge = None
        self.measuring = False
        self.progMenuLabel = None
        self.menuLabel = None
        self.leftFreq = 0
        self.rightFreq = 0

        rawList = []
        varEntries = []     #this list contains all the text and adjustment objects to reference

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)   #creates a new window
#           self.window.set_size_request(400,300)
        try:
            self.window.set_icon_from_file(os.path.join(ICON_PATH,"Anmr-icon"+ICON_EXTENSION))

        except:
            pass
        self.window.set_property('allow-grow', True)
        self.window.set_title("ANMR")
        self.window.connect("delete_event", self.delete_event)

        self.vbox = gtk.VBox(False,1) # false - not homogeneous, and 1 pixel spacing.

        self.window.add(self.vbox)
        self.vbox.show()

        self.menuBar = gtk.MenuBar()
        self.menuBar.show()
        menuBar = self.menuBar

#File menu.
        fileMenu = gtk.Menu()           #constructs a menu object

        openFold = gtk.MenuItem("Open Saved Data")
        fileMenu.append(openFold)
        openFold.connect("activate", self.openData, "saved")
        openFold.show()


        openAcqFold = gtk.MenuItem("Open Session Data")
        fileMenu.append(openAcqFold)
        openAcqFold.connect("activate", self.openData, "acq")
        openAcqFold.show()

        changeFold = gtk.MenuItem("Change Data Directory")
        fileMenu.append(changeFold)
        changeFold.connect("activate", self.changeFold, "hh")
        changeFold.show()

        self.menuLabel = gtk.MenuItem("File")
        self.menuLabel.show()

        self.menuLabel.set_submenu(fileMenu)
        self.menuBar.append (self.menuLabel)

        self.updateProgMenu()
        self.vbox.pack_start(self.menuBar, False, False, 2)

#rest of the main window

        hbox = gtk.HBox(False, 0)               #add a horizontal box
        self.vbox.pack_end(hbox, True, True, 0)     #pack it inside the vert box at the end
        hbox.show()


        hbox = gtk.HBox(False, 0)               #add a horizontal box
        self.vbox.pack_end(hbox, True, True, 0)     #pack it inside the vert box at the end of the available space
        hbox.show()

        numRuns = gtk.Label("Number of Runs")
        self.comps.append(numRuns)              #just to be able to reference it (1)

        hbox.pack_start(numRuns, True, True, 0)     #pack into the horiz box

        adjustment = gtk.Adjustment(4, 1, 9001, 1)      #making an adjustment object
        spin_button = gtk.SpinButton(adjustment, 1, 0)  #using adjustment obj to make spin button obj

        hbox.pack_start(spin_button, True, True, 0)     #pack into the horiz box

        self.comps.append(spin_button)          #just to be able to reference it (2)

        hbox = gtk.HBox(False, 0)               #add a horizontal box
        self.vbox.pack_end(hbox, True, True, 10)        #pack it inside the vert box at the end of the available space
        hbox.show()

        goButton = gtk.Button("Acquire")
        goButton.connect_object("clicked", self.acquire, 'Single')

        hbox.pack_start(goButton, True, True,0) #pack into the horiz box

        self.comps.append(goButton)             #just to be able to reference it (3)

        arrayButton = gtk.Button("Arrayed Acquire")
        arrayButton.connect_object("clicked", self.acquire, 'Array')

        hbox.pack_start(arrayButton, True, True, 0)     #pack into the horiz box

        self.comps.append(arrayButton)          #just to be able to reference it (4)

        spectraButton = gtk.Button("Acquire image data")
        spectraButton.connect_object("clicked", self.acquire, 'Image')

        hbox.pack_start(spectraButton, True, True, 0)   #pack into the horiz box

        self.comps.append(spectraButton)        #just to be able to reference it (5)

        self.window.show()
        self.window.deiconify()

        self.getData = [goButton, arrayButton, spectraButton]

        # create a directory in /tmp where our data will go.
        makeAnmrTempDir(TEMP_DIR)


        self.tDirName = tempfile.mkdtemp(prefix="anmr.",dir=TMP_DIR)

    def updateDataMenu(self):
        # mode is acq or saved
        if self.menuLabel is not None:
            self.menuLabel.destroy()

    def openData(self,widget,mode):
        # mode is acq or saved
        fileChooser = gtk.FileChooserDialog(title = "Open folder...", parent=self.window, action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER, buttons=("Cancel",gtk.RESPONSE_CANCEL, "Open", gtk.RESPONSE_OK) )
        if mode == 'acq':
            fileChooser.set_current_folder(self.tDirName)
        else:
            fileChooser.set_current_folder(DATA_DIR)
        response = fileChooser.run()
        foldName = fileChooser.get_current_folder()

        name = fileChooser.get_filename()
#           print ' got : ',response, 'from filechooser, and foldName: ',foldName, 'and name: ',fileChooser.get_filename()

        fileChooser.destroy()

        if response != gtk.RESPONSE_OK:
            return

        tempo = os.listdir(name)
        try:
            inFile = open(os.path.join(name,"commands.txt"))
        except:
            popup_msg( "command.txt file not found. Data corrupt?",base.window)
            return

        inFile.close()
        if "data0.txt" in tempo:
            if "array.txt" in tempo:        #then it's an arrayed acquisition
                set = DataSet(0, "Array", name)
            else:
                set = DataSet(0, "Image", name)     #is Image
            dirList = os.listdir(name)


        elif "data.txt" in tempo:
            set = DataSet(0, "Single", name)    #is not Image
        else:
            popup_msg("couldn't find data in "+str(name),base.window)
            return
        set.run()
        if mode == 'saved':
            set.saveName = name
        else:
            set.saveName = None # just as if it were newly acquired (which it is!)
        return

    def updateProgMenu(self):

        if self.progMenuLabel is not None:
            self.progMenuLabel.destroy()

        progMenuList = gtk.Menu()               #constructs a menu object

        #this one's for programs

        rawList = os.listdir(PROG_DIR)          #make a list of menu items

        self.progList = []
        self.progListShow = []
        for i in range(len(rawList)):           #searching the entire directory

            if ((rawList[i])[-5:] == ".prog"):      #if it ends with ".prog"
                self.progList.append(rawList[i])    #then add it to the list of programs
                self.progListShow.append(addUnderscores(rawList[i]))

        for i in range(len(self.progListShow)):         #makes an a MenuItem object for each file
            name = self.progListShow[i]

            tempMenuItem = gtk.MenuItem(name)
            progMenuList.append(tempMenuItem)
            tempMenuItem.connect("activate", self.menuItemSelected, name)
            tempMenuItem.show()

        self.progMenuLabel = gtk.MenuItem("Data Acquisition")
        self.progMenuLabel.show()
        self.progMenuLabel.set_submenu(progMenuList)
        self.menuBar.append (self.progMenuLabel)

        # create a bogus empty label to take up space in the window
        # this label gets destroyed when a program is selected.
        self.fileLabel = gtk.Label("\t \t \t ")
        self.fileLabel.set_property('height-request', 50)
        self.fileLabel.show()
        self.vbox.pack_end(self.fileLabel,True,True,0)

        progMenuList.show()
        self.menuBar.show()

    def changeFold(self, widget, string):
        global DATA_DIR
        fileChooser = gtk.FileChooserDialog(title = "Select Default Data folder...", parent=self.window, action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER, buttons=("Cancel",gtk.RESPONSE_CANCEL, "Open", gtk.RESPONSE_OK) )
        fileChooser.set_current_folder(DATA_DIR)
        response = fileChooser.run()
        foldName = fileChooser.get_current_folder()
        name = fileChooser.get_filename()
        fileChooser.destroy()

        if response == gtk.RESPONSE_OK:
            if not os.path.isdir(name):
                popup_msg("Error getting folder name",base.window)
                return
            DATA_DIR = name + os.sep
            popup_msg("Default data directory is now: "+DATA_DIR,base.window)

    def delete_event(self, widget, naught):
        if self.measuring:
            #               popup_msg("You are currently measuring, and cannot close this window.",self.window)
            return True
# confirm ?
        if self.data_set_num > -1:
            dialog = gtk.Dialog("Really Quit?", self.window)
            label = gtk.Label("Really Quit? All unsaved session data will be lost.")
            dialog.vbox.pack_start(label,True,True,0)
            dialog.add_buttons("Cancel", gtk.RESPONSE_NO, "Quit", gtk.RESPONSE_YES)
            dialog.show_all()
            response = dialog.run() # -8 is yes, and -9 is no
            dialog.destroy()
            if (response != gtk.RESPONSE_YES ):
                return True
        #remove all our temp data
        shutil.rmtree(self.tDirName)
        gtk.main_quit()

    def downloadProg(self, arrVarName, arrVarVal):
        #downloads the arduino program onto the arduino's server
        inFile = open(os.path.join(PROG_DIR,base.inProgName), 'r')
        try:
            outFile = open(TEMP_PROG_NAME, 'w')
        except:
            popup_msg("Trouble opening output pulse program file",base.window)
            return False
        outFile.write("PULSE_PROGRAM\n")    #pulse program identifier line
        os.chmod(TEMP_PROG_NAME,0o666) # so anyone can delete it.
        try:                    #definition header file
            headFile = open(os.path.join(PROG_DIR,HEADER_NAME), 'r')
            header = headFile.read()
            headFile.close()
            outFile.write(header)
        except:
            popup_msg("WARNING\nPulse program header file not found!",base.window)
        if arrVarName != "__XX__":
            outFile.write('%' + arrVarName + ' = ' + str(arrVarVal) + '\n')

        for i in range(len(base.varNames)):
            valName = base.varNames[i]
            (base.varEntries[i])[1].update()#updates the values in all the spin buttons

            val = str ( (base.varEntries[i])[1].get_value_as_int() )

            valName = valName.strip()

            if valName != arrVarName:
                outFile.write('%' + valName + ' = ' + val + '\n')

        temp = inFile.read()
        outFile.write(temp)
        inFile.close()
        #this one's for the address to the commands, held in temp.txt

        outFile.close()
        retVal = 0
        #now execute compAndDown with temp.txt as the instruction
###
#           ntemp_prog_name = trim_name(TEMP_PROG_NAME)
#           ntemp_bin_prog = trim_name(TEMP_BIN_PROG)
#           call = ANMR_COMPILER + ' ' + ntemp_prog_name+' ' + ntemp_bin_prog
#           print 'call is ',call
#           try:
#               retVal = subprocess.call(call,shell=True)
#           except:
#               popup_msg("Trouble starting compiler, check call:\n"+call)
#               return False
        retVal = anmr_compiler.compile(TEMP_PROG_NAME,TEMP_BIN_PROG)
        if retVal is not True:                    #then trouble!
            popup_msg("Pulse Program compiler failed with code: "+retVal,base.window)
            return False
        os.chmod(TEMP_BIN_PROG,0o666)
        retVal = downloadProgram(TEMP_BIN_PROG)
        if retVal is not True:
            popup_msg("Error downloading program: "+retVal,base.window)
            return False
        return True

    def cleanup(self,set,string,remove = True):
        #cleanup at end of acqusition
        self.measuring = False
        if self.mainProgBarWin is not None:
            self.mainProgBarWin.failure()
        if set is not None :
            set.measuring = False
            datetime = time.asctime()
#               mydate = datetime[0:10] + ' ' +datetime[-4:]
#               mytime = datetime[11:19]
            set.blinker.set_text(string+' ' +datetime)
        #enable acquire buttons
        base.getData[0].set_sensitive(True)
        base.getData[1].set_sensitive(True)
        base.getData[2].set_sensitive(True)
        if remove:
            closeDev()
        return

    def acquire(self,type):

        # should grey it out...
        if self.measuring:
            popup_msg( "You're already measuring! Shouldn't be here",base.window)
            return



# check the arduino out.

        self.data_set_num += 1
        acqName = os.path.join(self.tDirName, 'set_') + str(self.data_set_num)
        print("creating: ",acqName)
        os.mkdir(acqName)                   #make a directory

        if type == 'Array':
            # ask user to give us variables
            dialog = gtk.Dialog("Arrayed Acquire", self.window)

            label = gtk.Label("Variable to array:")
            dialog.vbox.pack_start(label,True,True,0)

            combobox = gtk.combo_box_new_text()
            for i in range(len(self.varNames)):
                combobox.append_text(self.varNames[i])
            combobox.set_active(0)
            dialog.vbox.pack_start(combobox,True,True,0)

            label = gtk.Label("Number of values:")
            dialog.vbox.pack_start(label,True,True,0)

#spin button for number of values to take
            adjustment = gtk.Adjustment(2,2, 9000, 1)
            spinButton = gtk.SpinButton(adjustment,1,0)
            dialog.vbox.pack_start(spinButton,True,True,0)

#okay and abort buttons
            dialog.add_button("Abort", gtk.RESPONSE_CLOSE)
            dialog.add_button("Ok", gtk.RESPONSE_YES)

            dialog.show_all()
            response = dialog.run()
            dialog.destroy()

            if response != gtk.RESPONSE_YES:
                return

            index = combobox.get_active()
            varName = self.varNames[index]
#               print 'got variable:',self.varNames[index]
            numReads = int(spinButton.get_value())

            dialog = gtk.Dialog("Define Variables", self.window)

        #with the name of the variable at the top
            if self.varUnits == "" or self.varUnits == "''" or self.varUnits == '""':
                varLabel = gtk.Label(varName)
            else:
                varLabel = gtk.Label(varName + ' ('+self.varUnits[index]+')')
            dialog.vbox.pack_start(varLabel,True,True,0)

            spinButtonList = []
        #use limits and current value.
            val =  (base.varEntries[index])[1].get_value_as_int()
            for i in range(numReads):
                tempAdj = gtk.Adjustment(val, self.varMins[index], self.varMaxs[index], 1)
                tempSpinBut = gtk.SpinButton(tempAdj,1,0)
                spinButtonList.append(tempSpinBut)
                dialog.vbox.pack_start(tempSpinBut,True,True,0)
        #open a dialog box with a combo box and spin button in it
        #okay and abort buttons

            dialog.add_button("Abort", gtk.RESPONSE_CLOSE)
            dialog.add_button("Ok", gtk.RESPONSE_YES)

            dialog.show_all()
            response = dialog.run()
            dialog.destroy()

            if response == gtk.RESPONSE_YES:
                varVals = []
                for i in range(len(spinButtonList)):
                    varVals.append( int(spinButtonList[i].get_value()) )
            else:
                return
            #write array.txt
            outFile = open( os.path.join(acqName,"array.txt"), 'w')
            outFile.write("#"+varName+"\n")
            for i in range(len(varVals)):
                temp = str(varVals[i]) + "\n"
                outFile.write(temp)
            outFile.close()
#               print 'got variables: '
#               print varName,varVals
        elif type == 'Image':
        #ask user to tell us how many projections.
            dialog = gtk.Dialog("Number of Projections", self.window)
            label = gtk.Label("Please input the number of projections you wish to take")
            dialog.vbox.pack_start(label,True,True,0)
            adjustment = gtk.Adjustment(12, 2, 9001, 1)     #making an adjustment object
            spin_button = gtk.SpinButton(adjustment, 1, 0)  #using adjustment obj to make spin button obj
            dialog.vbox.pack_start(spin_button,True,True,0)
            dialog.add_button("Ok", gtk.RESPONSE_OK)
            dialog.set_keep_above(True)
            dialog.show_all()
            while True:
                response = dialog.run()
                if response == gtk.RESPONSE_OK: 
                    break
            numReads = int( adjustment.get_value() ) +1 # do an extra for images!
            dialog.destroy()
        else: # not image or array
            #               print 'Just a simple single acquisition'
            numReads = 1

        numRuns = self.comps[1].get_value_as_int()
#           print 'Will be doing a total of numReads x numRuns: ',numReads,' x ',numRuns

        self.mainProgBarWin = None # cleanup will want this to exist

        errorWindow = base.window # used as a parent if there is an error message to display.
        #this is updated later after the data set window is created.

        retVal = openArduino(errorWindow)
        if retVal is not True:
            popup_msg("Error opening arduino: "+retVal,errorWindow)
            self.cleanup(None,"",False)
            return

        if type == 'Image':
            dialog = gtk.Dialog("Anmr", base.window,gtk.DIALOG_MODAL)
            label = gtk.Label(" ")
            dialog.vbox.pack_start(label,True,True,0)
            dialog.add_button("Abort", gtk.RESPONSE_CLOSE)      #this is -7
            backButton = dialog.add_button("Back",gtk.RESPONSE_CANCEL)          #this is -6
            dialog.add_button("Ok", gtk.RESPONSE_OK)        #this is -5


        #build the progress bar
        numOps = numReads*numRuns
        if type == 'Array' or type == 'Image':
            self.mainProgBarWin =progressBarWindow(numOps,"Acquisition",self.window,'0/'+str(numRuns)+' for record: '+'1/'+str(numReads))
        else:
            self.mainProgBarWin = progressBarWindow(numOps, "Acquisition",self.window)
#disable measure buttons
        base.getData[0].set_sensitive(False)
        base.getData[1].set_sensitive(False)
        base.getData[2].set_sensitive(False)


        set = None # will be the data set.
        warned = 0 # used when checking for data file size mismatch, way below

        # start the main acquisition (outer) loop.
        readList = list(range(numReads))
        for counter in readList:
            i = counter
            if (i == 0 or type == 'Array'): #then download program
                if type == 'Array':
                    v1 = varName
                    v2 = varVals[i]
                else:
                    v1 = '__XX__' #never get that as a variable name
                    v2 = None
                if self.downloadProg( v1,v2 ) is not True:
                    self.cleanup(set,"")
                    return

            if type == 'Single':
                dataFileName = os.path.join(acqName,'data.txt')
            else: #for array or image:
                dataFileName = os.path.join(acqName,'data')+str(i)+'.txt'

            base.measuring = True
# this isn't for our window, this is main program's flag.

            if type == 'Image': # all this is to deal with being able to go back to previous runs and confirming cancel
                go_on = False
                if ( i > 0):
                    flashScreen()
                while (go_on is False):
                    if ( i == numReads-1 ):
                        label.set_text("Replace the sample with a plain full water bottle,\ntaking care to not move any of the coils.\nHit 'Ok' when ready")
                        dialog.modify_bg(gtk.STATE_NORMAL,gtk.gdk.color_parse('yellow'))
                    else:
                        dialog.modify_bg(gtk.STATE_NORMAL,None)
                        label.set_text("Please set the sample orientation to "+ str(round(180 / float(numReads-1) * i ,2)) +" degrees.\nAbout to collect projection "+ str((i+1)) +" of " + str(numReads)+ ".\n(There is an extra for center finding.)\nClick 'Ok' when the sample is in position.")
                    if set is not None:
                        set.blinker.set_text("Waiting for sample position")
                        set.waiting = True
                    dialog.show_all()
                    if i == 0:
                        backButton.hide()
                    while True:
                        response = dialog.run()
                        if response == gtk.RESPONSE_CLOSE or response == gtk.RESPONSE_CANCEL or response == gtk.RESPONSE_OK:
                            break
                    dialog.hide()
                    if set is not None:
                        set.waiting = False
                        set.blinker.set_text("In Progress...")
                    if response == gtk.RESPONSE_CLOSE:
                        confirmDialog = gtk.Dialog("Confirmation dialog",base.window)
                        nlabel = gtk.Label("Are you sure? \nYou will be unable to continue this acquisition.")
                        confirmDialog.vbox.pack_start(nlabel,True,True,0)
                        confirmDialog.add_buttons("No", gtk.RESPONSE_NO, "Yes, Abort", gtk.RESPONSE_YES)
                        confirmDialog.show_all()
                        cResponse = confirmDialog.run()
                        confirmDialog.destroy()
                        if cResponse == gtk.RESPONSE_YES:
                            self.cleanup(set,"Cancelled")
                            return
                    elif response == gtk.RESPONSE_CANCEL: #"Back"
                        if i == 0:
                            popup_msg("BUG: shouldn't have back button, i is 0")
                        else:
                            #insert an extra item in list so we do them all
                            readList.insert(counter,i-1)
#                            print 'readList is:',readList
#                            print 'i was: ',i
                            i = i-1
#                            print 'but is now: ',i,'and counter is',counter
                            set.numScans[i] = 0
                            numOps += numRuns
                            self.mainProgBarWin.setNumOps(numOps)
                            try: #this may fail if we've gone back and forth.
                                os.remove(os.path.join(acqName,'data')+str(i)+'.txt') # so we don't just add to it.
                            except:
                                pass # new data file name.
                            dataFileName = os.path.join(acqName,'data')+str(i)+'.txt'

                    else:
                        go_on = True
            counter += 1
            # now start the main inner loop.
            for j in range(numRuns):
                if j == 0:
                    aData = None
                else:
                    aData = set.rawData[i]
                myThread = runProgramThread(dataFileName,aData,j)
#for slow cpu's next two lines help to prevent lost read data points
                while gtk.events_pending():         #clear any gui events
                    gtk.main_iteration()
                myThread.start() #this actually executes runProgram
                while not myThread.doneFlag:
                    gtk.main_iteration(block = True) # run the gui
                    time.sleep(0) #ensure data reading thread gets a chance
                retVal = myThread.retVal
                retData = myThread.retData
                myThread.join()
                if retVal is not True: # Houston, we have a problem
                    if not self.mainProgBarWin.abortFlag:
                        popup_msg("Error running program: "+retVal,errorWindow)
                        self.cleanup(set,"Failed")
                        return
                    else:
#                        popup_msg("Aborted",errorWindow) # user hit abort:
                        self.cleanup(set,"Aborted")
                        return
                if (j==0 and i==0 and set is None): # its possible we got a back to the beginning. Don't redo this.
                    #write the commands file
                    commands = open( TEMP_PROG_NAME, "r")
                    temp = commands.read()
                    commands.close()
                    commands = open ( os.path.join(acqName,"commands.txt") , "w" )
                    datetime = time.asctime()
                    mydate = datetime[0:10] + ' ' +datetime[-4:]
                    mytime = datetime[11:19]
                    commands.write(temp)
                    commands.write("\n#from: " + base.inProgName + "\n")      #date-stamp
                    commands.write("#date: " + str(mydate) + "\n#time: " + str(mytime) + "\n")
                    commands.close()
                    commandsWritten = True
                    #make the window
                    set = DataSet(0,type,acqName )
                    set.measuring = True
                    set.run()
                    self.mainProgBarWin.win.set_transient_for(set.window)
                    errorWindow = set.window #used as parent in case we have an error message to display
                    if type == 'Image':
                        dialog.set_transient_for(set.window) # so future prompts appear in the right place
                        set.makeImageButton.set_sensitive(False) # don't allow till finished.
                else:
                    if (i > 0 and j == 0):  # first scan of 2nd or third or ...record.
                        if set.rawData.shape[0] < i+1: # if we went back, we don't need all this:
                            set.rawData = numpy.append(set.rawData,numpy.zeros(set.rawData.shape[1]))
                            set.rawData.shape=(i+1,-1)
                            set.numDataFiles += 1
                            set.numScans.append(0)
                            set.indexVal.set_text(str(set.index+1) + '/' + str(set.numDataFiles))
                            set.plusButton.set_sensitive(True)
                        if type == 'Image':
                            set.numProjsLabel.set_text(str(set.numDataFiles))

                    if retData is not None and retData.size != set.rawData[0].size:
                        if warned == 0:
                            popup_msg("Data File # points mismatch.\nThis may happen if data is corrupt, or number of points acquired is arrayed.",errorWindow)
                            warned = 1
                        if set.rawData[0].size < args[0].size: #make the new data the same length as old data
                            retData = retData[0:set.rawData[0].size] # by truncate
                        else:   #or padding with zeros
                            retData[0] = numpy.hstack((retData,numpy.zeros(set.rawData[0].size-retData.size)))

                    set.rawData[i] = retData #copy the new data into the rawData array.

#TODO: just update the gui/data, update numdatafiles label, enable +/- buttons
                    set.processData(i,False) # process the data, but starting from record i.
                    set.numScans[i] += 1
                    if set.index == i:
                        set.scanLabel.set_text(str(set.numScans[i]))
                        if set.phaseOpen is False:
                            set.drawData()# if the user is looking at the current record, then redraw it - but not if we're phasing.
                if self.mainProgBarWin.abortFlag: # user hit abort:
                    self.cleanup(set,"Aborted")
                    return

                if type == 'Image' or type == 'Array':
                    self.mainProgBarWin.iteration(str(j+1)+'/'+str(numRuns)+' for record: '+str(i+1)+'/'+str(numReads) )
                else:
                    self.mainProgBarWin.iteration()

        self.cleanup(set,"Completed")
        if type == 'Image':
            flashScreen()
            if set.rawData[0].size != 0:
                set.makeImageButton.set_sensitive(True)
            set.numProjsLabel.set_text(str(set.numDataFiles -1)+'+1')
        return

    def menuItemSelected(self, widget, string):     #note: string is the file name
#user chose a pulse program.
        found = False

        for i in range(len(self.progListShow)):
            if string == self.progListShow[i]:
                string = self.progList[i]
                found = True
                break
        if not found:
            return

        if (self.fileLabel != ''):          #then there is already a fileLabel
            self.fileLabel.destroy()
        self.fileLabel = gtk.Label(string)
        self.vbox.pack_start(self.fileLabel,True,True,0)
        self.fileLabel.show()           #title bar showing the program name

        temp = []
        self.inProgName = string
        args = parse_prog_defs(os.path.join(PROG_DIR, string))

        if args[0] == 0 :
            return #failed

        varNames = args[0]
        varMins = args[1]
        varMaxs = args[2]
        varVals = args[3]
        varUnits = args[4]

        for i in range(len(varNames)): # copy over old values
            for j in range(len(self.varNames)):
                if varNames[i] == self.varNames[j]:
                    varVals[i]=(base.varEntries[j])[1].get_value_as_int()


        for i in range(len(self.comps)):        #show the comps at the bottom
            self.comps[i].show()            #if already showing, does nothing at all

        self.varNames = varNames
        self.varVals = varVals
        self.varMins = varMins
        self.varMaxs = varMaxs
        self.varUnits = varUnits

        #destroy all old objects

        for i in range(len(self.varEntries)):
            (self.varEntries[i])[0].destroy()
            (self.varEntries[i])[1].destroy()
            self.boxList[i].destroy()

        self.varEntries = []
        self.boxList = []

        for i in range(len(self.varNames)):             #creation of new objects
            hbox = gtk.HBox(True)

            self.vbox.pack_start(hbox, True, True, 0)

            self.boxList.append(hbox)

            if self.varUnits[i] == "''" or self.varUnits[i] == '""' or self.varUnits[i] == '':
                toInsert = self.varNames[i]
            else:
                toInsert = self.varNames[i] + " (" + self.varUnits[i] + ")"
            text = gtk.Label(toInsert)

            self.varEntries.append( [text,0] )
            hbox.pack_start(text, True, True, 0)

            adjustment = gtk.Adjustment(self.varVals[i],self.varMins[i],self.varMaxs[i], 1, 10,0)
            spin_button = gtk.SpinButton(adjustment, 1, 0)

            (self.varEntries[i])[1] = spin_button

            hbox.pack_start(spin_button, True, True, 0)

            hbox.show()
            text.show()
            spin_button.show()

    def main(self):     #this is necessary
        gtk.gdk.threads_enter()
        gtk.main()      #control ends here and waits for event
        gtk.gdk.threads_leave()


if __name__ == "__main__":
    base = progSelect()
    base.main()
