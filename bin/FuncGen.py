#!/usr/bin/python2.7




from matplotlib.lines import Line2D
from matplotlib.figure import Figure
from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvas
from matplotlib.backends.backend_gtkagg import NavigationToolbar2GTKAgg as NavigationToolbar

from anmr_common import *

PROG_NAME = os.path.join(TEMP_DIR,"funcgen-prog.txt")
BIN_NAME = os.path.join(TEMP_DIR,"funcgen-prog.bin")
RAW_DATA = os.path.join(TEMP_DIR,"funcgen-data.raw")

if EXPERTMODE:
    HIDESOURCESELECT = False
else:
    HIDESOURCESELECT = True

#time we allow play to run before starting data acquisition.
AUDIO_PLAY_DELAY = 0.25

#capture frequency for audio
AUDIO_FREQ = 44100
#44100 or 48000? 

#how long to read for live view/sweep measurements:
#for arduino at 1/104us per point:
NUM_SAMPLES = 1124
#NUM_SAMPLES=2048
#for sound card:
AUDIO_DUR = "0:00.15"
#AUDIO_DUR="0:00.22"

gtk.gdk.threads_init()

#this isn't the truth:
mode = 'soundcard' 


class myStreamThread(Thread):

    def __init__ (self, main):

        Thread.__init__(self)
        self.main = main


    def unpressLiveView(self):
        print(' in idle function to unpress')
        base.liveView.set_active(False)
        return False # so it doesn't repeat.

    def run (self):
#always pass AUDIO_DUR to get_data, but it only uses it for soundcard. For the arduino, it is set by the program
#downloaded earlier.
        if mode == 'arduino':
            rate = 1/float(TIME_STEP)
        else:
            rate = AUDIO_FREQ
        
        while self.main.live:
            self.main.streamWin.tyvals = self.main.get_data(AUDIO_DUR)
#            print 'first yvals are:',self.main.streamWin.tyvals[0],self.main.streamWin.tyvals[1]
            if self.main.streamWin.tyvals is not None:                
            # is it possible that the number of points varies for audio capture?
                if self.main.streamWin.tyvals.size != self.main.streamWin.txvals.size or self.main.streamWin.rate != rate:
#                    print 'in run, calculating xvals'
                    self.main.streamWin.calcXvals(self.main.streamWin.tyvals.size, rate)
                    print('done calculating xvals')
#               print ' streaming, got: ', self.main.streamWin.tyvals.size, ' points'
            #calculate the spectrum too
                self.main.streamWin.fyvals = numpy.abs(numpy.fft.rfft(self.main.streamWin.tyvals)/self.main.streamWin.txvals.size)
            #then plot it, and we're done.
                gobject.idle_add(self.main.streamWin.updatePlot)
            else:
#                print 'got no data, setting idle function to unpress live view'
                gobject.idle_add(self.unpressLiveView)
                return False
        return True

#used for noise and sweep acquisition.  Just runs play and get_data is a separate thread, and deposits the data
class getDataThread(Thread):

    def null(self): #dummy routine for idle_add.  This unblocks the main_iteration call that blocks.
        return False

    def __init__ (self, main, duration):

        Thread.__init__(self)
        self.main = main
        self.duration = duration
        self.doneFlag = False
        self.data = None

    def run (self):
        retVal = self.main.play()
        time.sleep(AUDIO_PLAY_DELAY)
        self.data = self.main.get_data(self.duration)
        if retVal is False:
            self.data = None
        self.main.killPlay()
        self.doneFlag = True
        gobject.idle_add(self.null) #unblock main_iteration
        return

class plotWindow:
#multipurpose plot window used for live streaming, sweep, and noise spectrum
    def __init__(self, title, tfbutton = False, trigButton = False):
        #title is the title of the window.

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        try:
            print('trying to load icon: ', os.path.join(ICON_PATH, "FuncGen-icon"+ICON_EXTENSION))
            self.window.set_icon_from_file(os.path.join(ICON_PATH, "FuncGen-icon"+ICON_EXTENSION))
        except:
            pass
        vbox = gtk.VBox(False)
        self.window.add(vbox)
#        self.window.set_size_request(600, 400)
        self.window.set_default_size(600, 400)
        self.window.set_title(title)
        
        self.fig = Figure(figsize=(4, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_position([0.2, 0.2, 0.7, 0.7])
        self.canvas = FigureCanvas(self.fig)  # a gtk.DrawingArea
        vbox.pack_start(self.canvas, True, True,0)
        
#           toolbar = NavigationToolbar(self.canvas, self.window)
        toolbar = MyToolbar(self.canvas, self.window)
        vbox.pack_start(toolbar, False, False,0)
        
        hbox = gtk.HBox(True)
        vbox.pack_start(hbox, False,True,0)
        self.lowerLim = gtk.Label()
        hbox.pack_start(self.lowerLim,True,True,0)
        self.upperLim = gtk.Label()
        hbox.pack_start(self.upperLim,True,True,0)
        self.RMSLabel = gtk.Label()
        hbox.pack_start(self.RMSLabel,True,True,0)
        if trigButton:
            self.triggeringButton = gtk.ToggleButton("Triggering")
            hbox.pack_start(self.triggeringButton,True,True,0)
        if tfbutton:
            self.autoScaleButton = gtk.Button("AutoScale")
            self.autoScaleButton.connect_object("clicked",self.autoScale,None)
            hbox.pack_start(self.autoScaleButton,True,True,0)

            self.logLinButton = gtk.ToggleButton("Log/Linear")
            self.logLinButton.connect_object("clicked",self.logLin,None)
            hbox.pack_start(self.logLinButton,True,True,0)
            self.logLinButton.set_sensitive(False)

            self.tfbutton = gtk.ToggleButton("Time/Freq")
            self.tfbutton.connect_object("clicked", self.timeFreq, None)
            hbox.pack_start(self.tfbutton,True,True,0)

            
            
        
        self.saveButton = gtk.Button("Save")
        vbox.pack_start(self.saveButton, False,True,0)
        self.saveButton.connect_object("clicked", self.save, None)

#data stored here:
        self.txvals = None
        self.tyvals = None
        self.fxvals = None
        self.fyvals = None
# time or freq domain?
        self.view = "freq"
#initial limits 
        self.txlims = None
        self.tylims = None
        self.fxlims = None
        self.fylims = None

    def calcXvals(self, np, rate):
        self.txvals = numpy.arange(np)/float(rate)*1000
        self.fxvals = numpy.fft.fftfreq(np, 1/float(rate))[0:np//2+1]
        if self.fxvals[-1] < 0:
            self.fxvals[-1] *= -1
        self.rate = rate

    def logLin(self,button):
        # change the y axes from log to linear
#        print ' in logLin'
        (min,max) = self.ax.get_ylim()
        if self.logLinButton.get_active():
            self.fylims = (min,max)
            self.ax.set_ylim(self.fyloglims)
            
            self.ax.set_yscale('log')            
        else:
            self.fyloglims=(min,max)
            self.ax.set_yscale('linear')
            self.ax.set_ylim(self.fylims)
        self.canvas.draw_idle()

    def autoScale(self, button):
        # find the limits of what we're viewing
        (minX,maxX) = self.ax.get_xlim()
        #need to find which points correspond to those limits
        if self.view == 'freq':
            if minX > self.fxvals[-1]:
                return
            if maxX < self.fxvals[0]:
                return
            if minX < self.fxvals[0]:
                minXpt = 0 
            else: # so minX is in range
                minXpt = numpy.argmax(self.fxvals >= minX)
            if maxX > self.fxvals[-1]:
                maxXpt = self.fxvals.size
            else:
                maxXpt = numpy.argmax(self.fxvals >= maxX)
            if minXpt == 0:
                minXpt = 1
            min = numpy.amin(self.fyvals[minXpt:maxXpt])
            max = numpy.amax(self.fyvals[minXpt:maxXpt])
        else: #time domain
            if minX > self.txvals[-1]:
                return
            if maxX < self.txvals[0]:
                return
            if minX < self.txvals[0]:
                minXpt = 0
            else:
                minXpt = numpy.argmax(self.txvals >= minX)
            if maxX > self.txvals[-1]:
                maxXpt = self.txvals.size
            else:
                maxXpt = numpy.argmax(self.txvals >= maxX)
            min = numpy.amin(self.tyvals[minXpt:maxXpt])
            max = numpy.amax(self.tyvals[minXpt:maxXpt])
#        print ''
#        print 'using min pt',minXpt
#        print 'using max pt',maxXpt
#        print 'got min and max of:',min,max

        if self.logLinButton.get_active(): #can only be active in freq mode.
            if min <= 0:
                min = 1e-4
            if max <= min:
                max = min*10
            min = min /2.
            max = max*2.
            self.ax.set_ylim(min,max)
        else:
            (min,max) = calc_lims(min,max)
            self.ax.set_ylim((min,max))

        self.canvas.draw_idle()

    def timeFreq(self, button):
#change from time to freq domain or back
        if self.tfbutton.get_active() and self.view == 'time':
            self.view = 'freq'
            self.txlims = self.ax.get_xlim()
            self.tylims = self.ax.get_ylim()
            if self.fxlims is None:
                self.wasLog = False
                min = numpy.amin(self.fxvals)
                max = numpy.amax(self.fxvals)
                (min, max) = calc_lims(min, max)

                self.ax.set_xlim((min, max))

                min = numpy.amin(self.fyvals)
                max = numpy.amax(self.fyvals)
                (min, max) = calc_lims(min, max)
                
                self.ax.set_ylim((min, max))
                # now for log:
                if min <= 0:
                    min = 1e-4
                if max <= min:
                    max = min*10
                min = min /2.
                max = max*2.
                self.fyloglims = (min,max)
            else:
                self.ax.set_xlim(self.fxlims)
                self.ax.set_ylim(self.fylims)
            self.ax.set_xlabel("Frequency (Hz)")
            self.ax.set_ylabel("Amplitude")
            self.logLinButton.set_sensitive(True)
            

            if self.wasLog:
                self.logLinButton.set_active(True)
            self.line.set_data(self.fxvals, self.fyvals)
            self.canvas.draw_idle()
            
        elif not self.tfbutton.get_active() and self.view == 'freq': # going to time tomain
            self.wasLog = self.logLinButton.get_active()
            self.logLinButton.set_active(False) #will store the loglims if was log
            self.view = 'time'
            self.fxlims = self.ax.get_xlim()
            self.fylims = self.ax.get_ylim()
            self.logLinButton.set_sensitive(False)
            if self.txlims is None:

                min = numpy.amin(self.txvals)
                max = numpy.amax(self.txvals)
                (min, max) = calc_lims(min, max)

                self.ax.set_xlim((min, max))

                min = numpy.amin(self.tyvals)
                max = numpy.amax(self.tyvals)
                (min, max) = calc_lims(min, max)

                self.ax.set_ylim((min, max))

            else:
                self.ax.set_xlim(self.txlims)
                self.ax.set_ylim(self.tylims)
            self.ax.set_xlabel("Time (ms)")
            self.ax.set_ylabel("Amplitude")

            self.line.set_data(self.txvals, self.tyvals)
            self.canvas.draw_idle()
        return

#used for live streaming and noise spectrum
    def updatePlot(self): 
#        print 'in updatePlot, view is',self.view
#        print 'ylims: ',self.ax.get_ylim()
#        print 'yscale is:',self.ax.get_yscale()
        if self.view == 'time':
# do some 'triggering'
#Strategy: find the transition from < 5 to > 5 that is nearest the middle
#then relabel the xvals so that the transition appears at 0.
            if self.triggeringButton.get_active():
                i=self.tyvals.size/2
                lval = numpy.argmax(self.tyvals[i:]<5) # ival is the index of the first point past halfway that is <5
                gval = numpy.argmax(self.tyvals[lval+i:]>5) #look for next rise through 5.
                #so, we want lval+i+gval as our trigger point!
                #if there is no transition from low to high, lval = 0 and gval = 0
                shifted_txvals = self.txvals-(self.txvals[i+lval+gval]-self.txvals[i])
            else:
                shifted_txvals = self.txvals

            self.line.set_data(shifted_txvals, self.tyvals)
            rms = numpy.sqrt(numpy.sum(self.tyvals *self.tyvals )/self.tyvals.size)
            self.RMSLabel.set_text("rms: "+str(round(rms, 2)))
            self.lowerLim.set_text("min: "+str(round(numpy.amin(self.tyvals))))
            self.upperLim.set_text("max: "+str(round(numpy.amax(self.tyvals))))
        else:
            maxindex = numpy.argmax(self.fyvals)
            self.RMSLabel.set_text("")
            self.lowerLim.set_text("max: "+str(round(self.fyvals[maxindex], 2)))
            self.upperLim.set_text("at: "+str(round(self.fxvals[maxindex], 1))+" Hz")
            self.line.set_data(self.fxvals, self.fyvals)
        self.canvas.draw_idle()
        return False #this is an idle function, must return False

    def save(self, dummy):
        # make a copy of the data so we get what we asked for.

        if self.view == 'time':
            yvals = self.tyvals.copy()
            xvals = self.txvals.copy()
        else:
            yvals = self.fyvals.copy()
            xvals = self.fxvals.copy()

        fileChooser = gtk.FileChooserDialog(title = "Save file...", parent=None, action=gtk.FILE_CHOOSER_ACTION_SAVE, buttons=("Cancel", gtk.RESPONSE_CANCEL, "Save", gtk.RESPONSE_OK ))
        response = fileChooser.run()
        fileName = fileChooser.get_filename()
        fileChooser.destroy()

        if response == gtk.RESPONSE_CANCEL:
            return
        elif response == gtk.RESPONSE_OK:
            if fileName[-4:] != ".txt":
                fileName = fileName + ".txt"
            try:    #check if fileName exists
                inFile = open(fileName, "r")
                inFile.close()
                #prompt if want to overwrite
                dialog = gtk.Dialog("Attention!")
                label = gtk.Label("Duplicate file found! Overwrite?")
                dialog.vbox.pack_start(label,True,True,0)
                dialog.add_buttons("Yes", gtk.RESPONSE_YES, "No", gtk.RESPONSE_NO)
                dialog.show_all()
                response = dialog.run() # -8 is yes, and -9 is no
                dialog.hide()
                dialog.destroy()
                if (response == -8 ):   #delete stuff
                    try:
                        os.remove(fileName)
                    except:     #meh.
                        pass
                elif (response == -9):  #do not overwrite. abort
                    return
            except: #file does not currently exist. Okay.
                pass
            #save
            outFile = open(fileName, "w")
            for i in range(xvals.size):     #assuming they're of the same length
                outFile.write(str(xvals[i]) + ' ' + str(yvals[i]) + '\n')
            outFile.close()
            return
        else:
            return

class topWin:

    def wrapper(self, widget, null):
        self.killPlay()
        self.liveView.set_active(False)
        gtk.main_quit()

    def __init__(self):

        self.pid = None
        self.wave = None
        self.playing = None
        self.prevRadBut = "off"
        self.live = None
        self.saveSweepSteps = 40
        self.saveNoiseTime = 1

        window = gtk.Window(gtk.WINDOW_TOPLEVEL)    #creates a new window
        try:
            window.set_icon_from_file(os.path.join(ICON_PATH, "FuncGen-icon"+ICON_EXTENSION))
        except:
            pass

#        window.set_size_request(400, 300)
        window.set_title("Function Generator/Spectrometer")
        window.connect("delete_event", self.wrapper)
        self.window = window

        hbox = gtk.HBox(homogeneous=False)
        window.add(hbox)

        leftVbox = gtk.VBox(homogeneous=False)
        hbox.pack_start(leftVbox,True,True,2)
        rightVbox = gtk.VBox()
        hbox.pack_start(rightVbox,True,True,2)

        thbox = gtk.HBox()
        rightVbox.pack_start(thbox,True,True,0)
        label = gtk.Label("Waveform:")
        thbox.pack_start(label,True,True,0)

        combobox = gtk.combo_box_new_text()
        combobox.append_text('Sine')
        combobox.append_text('Square')
        combobox.append_text('Triangular')
        combobox.append_text('White Noise')
        combobox.connect('changed', self.changed_cb)
        combobox.set_active(0)
        thbox.pack_start(combobox,True,True,0)

        self.comboBox = combobox

        radButton = gtk.RadioButton(None, "Off")
        radButton.connect("toggled", self.radButtonChanged, "off")
        rightVbox.pack_start(radButton,True,True,0)
        self.rad1 = radButton

        radButton = gtk.RadioButton(self.rad1, "Function Generator")
        radButton.connect("toggled", self.radButtonChanged, "funcGen")
        rightVbox.pack_start(radButton,True,True,0)
        self.rad2 = radButton

        radButton = gtk.RadioButton( self.rad1, "Measure Using Frequency Sweep")
        radButton.connect("toggled", self.radButtonChanged, "freqSweep")
        rightVbox.pack_start(radButton,True,True,0)
        self.rad3 = radButton

        radButton = gtk.RadioButton( self.rad1, "Measure Using White Noise")
        radButton.connect("toggled", self.radButtonChanged, "whiteNoise")
        rightVbox.pack_start(radButton,True,True,0)
        self.rad4 = radButton

        thbox = gtk.HBox()
        rightVbox.pack_start(thbox,True,True,0)
        label = gtk.Label("Input Signal Source:")
        thbox.pack_start(label,True,True,0)

        combobox = gtk.combo_box_new_text()
        combobox.append_text('Arduino')
        combobox.append_text('Soundcard')
        combobox.connect('changed', self.changed_sig_source)
        self.sourceCB = combobox
        thbox.pack_start(combobox,True,True,0)
        
        freqStepView = gtk.Label("Number of Frequency Steps")
        self.freqStepLabel = freqStepView
        self.freqStepAdjustment = gtk.Adjustment(40, 2, 200, 1)
        self.freqStepButton = gtk.SpinButton(self.freqStepAdjustment,1,0)
        self.freqStepButton.set_sensitive(False)


        rightVbox.pack_start(freqStepView,True,True,0)
        rightVbox.pack_start(self.freqStepButton,True,True,0)

        goButton = gtk.Button("Go")
        goButton.connect_object("clicked", self.go, True)
        goButton.set_sensitive(False)

        self.goButton = goButton

        rightVbox.pack_end(goButton,True,True,0)


        startFreqView = gtk.Label("Start Frequency")
        self.startFreqAdjust = gtk.Adjustment(200, 1, 9000, 100)
        startFreqSpin = gtk.SpinButton(self.startFreqAdjust,100,0)

        endFreqView = gtk.Label("End Frequency")
        self.endFreqAdjust = gtk.Adjustment(4000, 200, 9000, 1000)
        endFreqSpin = gtk.SpinButton(self.endFreqAdjust,1000,0)

        startVal = startFreqSpin.get_value_as_int()
        endVal = endFreqSpin.get_value_as_int()
        stepVal = self.freqStepButton.get_value_as_int()

        freqLabel = gtk.Label("Frequency")
        self.freqAdjust = gtk.Adjustment(startVal, startVal, endVal, 10,100)

        self.freqAdjust.connect("value-changed", self.freqChanged, True)
        self.startFreqAdjust.connect("value-changed", self.limitChanged, True)
        self.endFreqAdjust.connect("value-changed", self.limitChanged, True)

        self.freq = self.freqAdjust.get_value()

        freqSpinButton = gtk.SpinButton(self.freqAdjust, 10,1)
        freqSlider = gtk.HScale(self.freqAdjust)
        freqSlider.set_digits(1)

        self.liveView = gtk.ToggleButton("Live View")

        self.ampAdjust = gtk.Adjustment(50,1,100,5) #default, lower, upper,step,page
        self.ampSpin = gtk.SpinButton(self.ampAdjust,5,0)
        ampLabel = gtk.Label("Amplitude")
        self.amp = self.ampAdjust.get_value()
        
        frame1 = gtk.Frame()
        
        leftVbox.pack_start(frame1,True,True,0)
        frameVbox = gtk.VBox(True)
        frame1.add(frameVbox)
        frameVbox.pack_start(freqLabel,True,True,0)
        frameVbox.pack_start(freqSpinButton,True,True,0)
        frameVbox.pack_start(freqSlider,True,True,0)
#        leftVbox.pack_start(freqLabel,True,True,0)
#        leftVbox.pack_start(freqSpinButton,True,True,0)
#        leftVbox.pack_start(freqSlider,True,True,0)
        
        frame1 = gtk.Frame()
        frameVbox =gtk.VBox(True)
        frame1.add(frameVbox)
        leftVbox.pack_start(frame1,True,True,0)
        frameVbox.pack_start(ampLabel,True,True,0)
        frameVbox.pack_start(self.ampSpin,True,True,0)
        self.ampAdjust.connect("value-changed", self.ampChanged,True)

        leftVbox.pack_start(self.liveView,True,True,0)
    
        leftVbox.pack_end(endFreqSpin,True,True,0)
        leftVbox.pack_end(endFreqView,True,True,2)
        leftVbox.pack_end(startFreqSpin,True,True,0)
        leftVbox.pack_end(startFreqView,True,True,2)

        self.freq1 = freqSpinButton
        self.freq2 = freqSlider
        self.freq3 = startFreqSpin
        self.freq4 = endFreqSpin
        window.show_all()
        if HIDESOURCESELECT:
            combobox.hide()
            label.hide()
        window.deiconify()
        #build the streamwindow
        streamWin = plotWindow("Live View", tfbutton=True, trigButton=True)
        streamWin.window.connect("delete_event", self.streamKilled)

        self.liveView.connect("clicked", self.cmstream, streamWin)

        #plot zeros for now
        streamWin.ax.set_xlim([0, 100])
        streamWin.ax.set_xlabel("Time (ms)")
        streamWin.ax.set_ylabel("Amplitude")
        streamWin.calcXvals(NUM_SAMPLES, 1/float(TIME_STEP))
        streamWin.tyvals = numpy.zeros(NUM_SAMPLES)
        streamWin.fyvals = numpy.zeros(streamWin.fxvals.size)
        streamWin.view = 'time'
        streamWin.line = Line2D(streamWin.txvals, streamWin.tyvals)
        streamWin.ax.add_line(streamWin.line)

        self.streamWin = streamWin

        combobox.set_active(0) #sets to arduino, and sets default ylimits for streamWin
        # create a directory in /tmp where input data will go, and lockfile for arduino lives.
        makeAnmrTempDir(TEMP_DIR)


    def runLast(self): # just does a runProgram - used when we want to turn off the arduino outputs, used with sendProgram ( . , False)
        retVal, retData = runProgram(None, None, 0)
#        print("doing runLast")
        if retVal is not True: # Houston, we have a problem
            popup_msg("Error running program for runLast:"+retVal, base.window)
            return None 


    def sendProgram(self, readings, start):

        try:
            inFile = open(PROG_NAME, "r")   #if this succeeds, it currently exists
            inFile.close()
            os.remove( PROG_NAME )  #<dalek>    EXTERMINATE, EXTERMINATE    </dalek>
        except:
            pass    #then does not exist, good

        try:
            outFile = open(PROG_NAME, "w")      #make new file
        except:
            popup_msg("Trouble opening pulse program temp file", base.window)
            return False
        outFile.write("PULSE_PROGRAM\n")        #pulse program identifier
        os.chmod(PROG_NAME, 0o666) # so anyone can delete it.

#copy the header file:
        try:                  
            headFile = open(os.path.join(PROG_DIR, HEADER_NAME), 'r')
            header = headFile.read()
            headFile.close()
            outFile.write(header)
        except:
            popup_msg("WARNING\nPulse program header file not found!", base.window)

        
# ugh - hardcoded pin assignments...
        outFile.write("CHANGE_PIN %polarise_enable 0\n")    #
        outFile.write("CHANGE_PIN %short_rec_coil 0\n")
        if start:
            outFile.write("CHANGE_PIN %short_pol_coil 1\n") #
            outFile.write("CHANGE_PIN %transmitter_connect 1\n")    #
            outFile.write("CHANGE_PIN %receiver_connect 1\n")
            outFile.write("DELAY_IN_MS 2\n")        #wait for relays
            outFile.write("READ_DATA 0 0 1 "+str(readings)+"\n")      
        else:
            outFile.write("CHANGE_PIN %short_pol_coil 0\n") #
            outFile.write("CHANGE_PIN %transmitter_connect 0\n")    #
            outFile.write("CHANGE_PIN %receiver_connect 0\n")
#               print "writing file to disable output"

        outFile.write("DELAY_IN_MS 2\n")        #wait for relays
        outFile.close()



#           nprog_name = trim_name(PROG_NAME)
#           nbin_name = trim_name(BIN_NAME)
#           call = ANMR_COMPILER + ' ' + nprog_name+' ' + nbin_name
#           print 'call is ',call
#           try:
#               retVal = subprocess.call(call,shell=True)
#           except:
#               popup_msg("Trouble starting compiler, check call:\n"+call)
#               return False
        retVal = anmr_compiler.compile(PROG_NAME, BIN_NAME)
        if retVal is not True:                    #then trouble!
            popup_msg("Pulse Program compiler failed with code: "+retVal, base.window)
            return False
        os.chmod(BIN_NAME, 0o666)
        retVal = downloadProgram(BIN_NAME)
        if retVal is not True:
            popup_msg("Downloading pulse program failed with error: "+retVal, base.window)
            return False
        return True


    def setRadState(self, state):
        self.rad1.set_sensitive(state)
        self.rad2.set_sensitive(state)
        self.rad3.set_sensitive(state)
        self.rad4.set_sensitive(state)

    def streamKilled(self, event, meh):
#           self.live = False # cmstream will do this
        self.wasLive = False #  in case we're doing a sweep
        self.liveView.set_active(False)
        return True

    def cmstream(self, button, streamWin):
        #this is the call back for the live view button
    #here we start the acquisitions in a separate thread
        if button.get_active():
            #draw the window:
            if mode == "arduino":
            #check lock, download program.
# temp disable for windows
                #create the lockfile, open the device
                retVal = openArduino(base.window)
                if retVal is not True:
                    popup_msg("Error opening arduino: "+retVal, base.window)
                    button.set_active(False)
                    return True
                if not self.sendProgram(NUM_SAMPLES, True):
                    button.set_active(False)
                    closeDev()
                    return True

            streamWin.window.show_all()
            self.live = True
            self.sourceCB.set_sensitive(False)
            self.streamThread = myStreamThread(self)
            self.streamThread.start()
        else:
            self.sourceCB.set_sensitive(True)
#            if streamWin.view == 'freq' and streamWin.logLinButton.get_active():
#                streamWin.logLinButton.set_active(False) #prevents crashes!
#if we open live view in log view and change from arduino to soundcard or vice versa, crash. Why?
            streamWin.window.hide()
            if self.live:
                self.live = False
                self.streamThread.join()
                if mode == 'arduino':
                    if self.sendProgram(0, False):
                        self.runLast()
                    closeDev()

        return True

    def get_data(self, duration):
#duration is how long we read for. It only matters for sound card, for arduino it is set by the program downloaded earlier
#it is a string

        if mode == "arduino":

            #run flashed program
            retVal, data = runProgram(None, None, 0)

            if retVal is not True: # Houston, we have a problem 
#                   popup_msg("Error running program: "+retVal)
                gobject.idle_add(popupIdleWrap, "Error running program: "+retVal, base.window)
                return None 
                

        else:

            call = SOX_EXEC +' -d -c 1  -r '+str(AUDIO_FREQ)+' '+ RAW_DATA +' trim 0 '+ duration 
#               print 'call for record is: ',call
            try:
                rval = subprocess.call(call, shell=True) # this doesn't give an error if its not found...
            except:
                gobject.idle_add(popupIdleWrap, "Problem starting sox to record", base.window)
                return None
            if rval != 0:
                gobject.idle_add(popupIdleWrap, "Problem starting sox to record", base.window)
                return None
            inFile = open(RAW_DATA, "r")
            data = numpy.fromfile(inFile, dtype=numpy.int16)
            inFile.close()
            os.chmod(RAW_DATA, 0o666) # so anyone can overwrite it.
            print(' got size: ', data.size)
            #throw away a few samples at the start
            if data.size > 50:
                data = data[50:]
#on windows, last 20 ms is no good?
            if data.size > 1600:
                data = data[0:-1600]
        data = data - numpy.average(data)
        return data

    def go(self, true):

        #disable most of ui while sweeping or noise-ing
        self.liveView.set_sensitive(False)
        self.sourceCB.set_sensitive(False)
        self.setRadState(False)
        self.goButton.set_sensitive(False)
        self.ampSpin.set_sensitive(False)

        #if we were live, stop it for now.
        self.wasLive = self.live
        if self.wasLive:
            self.live = False
            #end the thread. will start it later.
            self.streamThread.join()
            
# do it:
        if self.prevRadBut == "freqSweep":
            self.sweep()
        if self.prevRadBut == "whiteNoise":
            self.noise()
# done
        if self.wasLive:  #restart it.
            self.live = True
            self.streamThread = myStreamThread(self)
            self.streamThread.start()
        else:
            self.sourceCB.set_sensitive(True)
        self.liveView.set_sensitive(True)
        self.goButton.set_sensitive(True)
        self.ampSpin.set_sensitive(True)
        self.setRadState(True)

        return

    def freqChanged(self, signal, filler):
        self.freq = self.freqAdjust.get_value()
        if self.playing:
            self.killPlay()
            self.play()

    def ampChanged(self, signal, filler):
        self.amp = self.ampAdjust.get_value()
        if self.playing:
            self.killPlay()
            self.play()


    def limitChanged(self, signal, true):
        startFreq = self.startFreqAdjust.get_value()
        endFreq = self.endFreqAdjust.get_value()
        
        if startFreq >= endFreq:                #not a possible operation
            self.endFreqAdjust.set_value(startFreq + 1)
            endFreq = self.endFreqAdjust.get_value()

        if self.freqAdjust.get_value() < startFreq:
            self.freqAdjust.set_value(startFreq)
        if self.freqAdjust.get_value() > endFreq:
            self.freqAdjust.set_value(endFreq)

        self.freqAdjust.set_lower(startFreq)
        self.freqAdjust.set_upper(endFreq)

    def radButtonChanged(self, widget, data=None):
        

        if data is None or data == self.prevRadBut:     #this method is called whenever any button is toggle
            return                  #this makes it only execute when it's toggled to true
        if self.prevRadBut == "whiteNoise":
            self.saveNoiseTime = self.freqStepAdjustment.get_value()
        if self.prevRadBut == "freqSweep":
            self.saveSweepSteps = self.freqStepAdjustment.get_value()
        self.prevRadBut = data

        if data == "off":
            self.freqSen(True)
            self.comboBox.set_sensitive(True)
            self.goButton.set_sensitive(False)
            self.freqStepButton.set_sensitive(False)
            if self.playing:
                self.killPlay()
        elif data == "funcGen":
            #update frequency
            self.freqSen(True)
            if self.playing:
                self.killPlay()
            self.play()
            #grey out "Go" button
            self.goButton.set_sensitive(False)
            self.freqStepButton.set_sensitive(False)
            self.comboBox.set_sensitive(True)
        elif data == "freqSweep":
            self.freqStepLabel.set_text("Number of Frequency Steps")
            self.freqStepAdjustment.set_lower(2)
            self.freqStepAdjustment.set_upper(200)
            self.freqStepAdjustment.set_value(self.saveSweepSteps)
            self.freqStepButton.set_digits(0)
            self.freqStepButton.update()
            if self.playing:
                self.killPlay()
            #set the wave type to sine
            self.comboBox.set_active(0)
            self.comboBox.set_sensitive(False)

            self.freq1.set_sensitive(False)
            self.freq2.set_sensitive(False)
            self.freq3.set_sensitive(True)
            self.freq4.set_sensitive(True)
            self.goButton.set_sensitive(True)
            self.freqStepButton.set_sensitive(True)         

        elif data == "whiteNoise":
            self.freqStepLabel.set_text("Duration(s)")
            self.freqStepAdjustment.set_lower(0.1)
            self.freqStepAdjustment.set_upper(20)
            self.freqStepAdjustment.set_value(self.saveNoiseTime)
            self.freqStepButton.set_digits(2)
            self.freqStepButton.update()
            if self.playing:
                self.killPlay()
            #set the wave type to white noise
            self.comboBox.set_active(3)
            self.comboBox.set_sensitive(False)

            self.freqSen(False)             #grey out all freq things, except freq steps
            self.goButton.set_sensitive(True)
            self.freqStepButton.set_sensitive(True)
            self.comboBox.set_sensitive(False)              

    def freqSen(self, status):
        self.freq1.set_sensitive(status)
        self.freq2.set_sensitive(status)
        self.freq3.set_sensitive(status)
        self.freq4.set_sensitive(status)
            
    def changed_sig_source(self, combobox):
        global mode
        if combobox.get_active() == 0:
            mode = 'arduino'
            if self.streamWin.view == 'time':
                self.streamWin.ax.set_ylim([-512, 512])
            else:
                self.streamWin.tylims=(-512,512)
        else:
            mode = 'soundcard'
            if self.streamWin.view == 'time':
                self.streamWin.ax.set_ylim([-20000, 20000])
            else:
                self.streamWin.tylims=(-20000,20000)



    def changed_cb(self, combobox):
        index = combobox.get_active()
            
        if index == 0:  #sine wave
            self.wave = "sine"
            if self.playing:
                self.killPlay()
                self.play()
        elif index == 1: #square wave
            self.wave = "square"
            if self.playing:
                self.killPlay()
                self.play()
        elif index == 2: #triangular wave
            self.wave = "triangle"
            if self.playing:
                self.killPlay()
                self.play()
        elif index == 3: #white noise
            self.wave = "noise"
            if self.playing:
                self.killPlay()
                self.play()
        return  
    

    def sweepWinClosed(self, widget, junk, sweepWin):
        if sweepWin.sweepFlag: # if its running, stop it.
            popup_msg("Sweep Aborted", sweepWin.window)
            self.sweepWinAborted = True
            return True
        else:
#seems to help in memory usage
            del sweepWin
            gc.collect()
            return False

    def sweep(self):
        #if live view is open, stop that thread
        if not self.wasLive and mode == 'arduino':
#temp disable for windows
            retVal = openArduino(base.window)
            if retVal is not True:
                popup_msg("Error opening arduino: "+retVal, base.window)
                return True
            if not self.sendProgram(NUM_SAMPLES, True):
                return True
                
        self.sweepFlag = True # true while we're sweeping
        self.sweepWinAborted = False #if sweep aborted by delete event
        #set radio buttons insensitive while sweeping

        #updating the start and end frequency spin button values - in case new values entered but not 'entered'
        self.freq3.update()
        self.freq4.update()
        
        #build the sweep window
        sweepWin = plotWindow("Frequency Sweep", tfbutton = False)
        sweepWin.sweepFlag = True
        base.sweepWin = sweepWin
        sweepWin.window.connect("delete_event", self.sweepWinClosed, sweepWin)


        #reading the values
        startFreq = self.startFreqAdjust.get_value()
        endFreq = self.endFreqAdjust.get_value()
        n = self.freqStepButton.get_value_as_int()

        f = (endFreq - startFreq) / float(n-1)

        sweepWin.fxvals = numpy.arange(n)*f+startFreq
        sweepWin.fyvals = numpy.zeros(n)
        sweepWin.view = 'freq'
        sweepWin.window.show_all()

        a = sweepWin.fig.gca()
        a.set_xlim([startFreq, endFreq])

# do a first play to wake up audio hardware
        self.freq = sweepWin.fxvals[0]          
        dataThread = getDataThread(self, str(AUDIO_DUR))
        dataThread.start()
        while not dataThread.doneFlag:
            gtk.main_iteration(block=True)
        data = dataThread.data
        dataThread.join()
###
        if data is None:
            popup_msg("Error acquiring data, sweep aborted", sweepWin.window)
            self.sweepWinAborted = True

        for i in range(n):      
            if self.sweepWinAborted:
                break

            self.freq = sweepWin.fxvals[i]

            dataThread = getDataThread(self, str(AUDIO_DUR))
            dataThread.start()
            while not dataThread.doneFlag:
                gtk.main_iteration(block=True)
            dataThread.join()
            data = dataThread.data
            if data is None:
                popup_msg("Error acquiring data, sweep aborted", sweepWin.window)
                break
            rms = numpy.sqrt(numpy.sum(data*data)/data.size)
            sweepWin.fyvals[i] = rms

            sweepWin.ax.cla()
            sweepWin.ax.set_xlabel("Frequency (Hz)")
            sweepWin.ax.set_ylabel("RMS")
            sweepWin.ax.plot(sweepWin.fxvals, sweepWin.fyvals)
            sweepWin.ax.plot(sweepWin.fxvals, sweepWin.fyvals, '.')
            sweepWin.window.show_all()

            sweepWin.canvas.draw_idle()
            if self.wasLive:                #then we're streaming
                self.streamWin.tyvals = data
                self.streamWin.fyvals = numpy.abs(numpy.fft.rfft(data)/data.size)
                self.streamWin.updatePlot()

            while gtk.events_pending():         #makes sure the GUI updates
                gtk.main_iteration()
        if not self.wasLive and mode == 'arduino':
            if self.sendProgram(0, False):
                self.runLast()
            closeDev()

        sweepWin.sweepFlag = False
        self.freq = self.freqAdjust.get_value()

    def noiseWinClosed(self, widget, junk, noiseWin):
#seems to help in memory usage
        del noiseWin
        gc.collect()
        return False


    def noise(self):

        label = gtk.Label("Doing noise measurement, please wait")
        idialog = gtk.Dialog("Noise measurement", self.window)
        idialog.vbox.pack_start(label,True,True,0)

#           abortButton = gtk.Button("Abort")
#           abortButton.connect_object("clicked", self.abort, self.abortFlag)
#           idialog.vbox.pack_start(abortButton,True,True,0)
        idialog.show_all()


        while gtk.events_pending():         #to actually show the dialog.
            gtk.main_iteration()
        time.sleep(.05) #seems to be necessary to see the whole thing...
        while gtk.events_pending():         #to actually show the dialog.
            gtk.main_iteration()


        
        nWin = plotWindow("Noise Spectrum", tfbutton=True)

#this appears to prevent some of nWin's variables from being inexplicably garbage collected.
        global base
        base.nWin = nWin
        nWin.window.connect("delete_event", self.noiseWinClosed, nWin)

        duration = self.freqStepButton.get_value()
        if mode == "arduino":
            rate = 1/float(TIME_STEP)
            if not self.wasLive:
                retVal = openArduino(base.window)
                if retVal is not True:
                    idialog.destroy()
                    popup_msg("Error opening arduino: "+retVal, base.window)
                    return True
            if not self.sendProgram(int(duration/TIME_STEP), True):
                idialog.destroy()
                return True
        else:
            rate = AUDIO_FREQ
        
        dataThread = getDataThread(self, str(duration))
        dataThread.start()
        while not dataThread.doneFlag:
            gtk.main_iteration(block=True)

        dataThread.join()
        
        nWin.tyvals = dataThread.data
        if nWin.tyvals is None:
            popup_msg("Error acquiring data, no data returned",nWin.window)
            closeDev()
            idialog.destroy()
            return
        nWin.calcXvals(nWin.tyvals.size, rate)

        #do the fourier transform:
        nWin.fyvals = numpy.abs(numpy.fft.rfft(nWin.tyvals)/nWin.txvals.size)


        #plot the magnitude of the FT'd data
        a = nWin.fig.gca()
        nWin.view = 'freq'
        nWin.tfbutton.set_active(True)
        nWin.logLinButton.set_sensitive(True)
        nWin.line = Line2D(nWin.fxvals, nWin.fyvals)
        min = numpy.amin(nWin.fxvals)
        max = numpy.amax(nWin.fxvals)
        nWin.ax.set_xlim(calc_lims(min, max))
        min = numpy.amin(nWin.fyvals[1:])
        max = numpy.amax(nWin.fyvals)
        nWin.ax.set_ylim(calc_lims(min, max))
        nWin.fyloglims=(min/2,max*2) # same as in autoscale
        nWin.ax.add_line(nWin.line)
        nWin.ax.set_xlabel("Frequency (Hz)")
        nWin.ax.set_ylabel("Amplitude")

        nWin.window.show_all()

        if mode == "arduino" and self.wasLive:
            self.sendProgram(NUM_SAMPLES, True)
        if mode == "arduino" and not self.wasLive:
            self.sendProgram(0, False)
            self.runLast()
            closeDev()
        idialog.destroy()
        return

    def play(self):
        #note:frequency is in hertz
#           call = '/usr/bin/play -q -n synth 216000 ' + self.wave + ' ' + str(self.freq) + ' gain -12'
        #figure out amplitude:
        my_gain = 20*numpy.log10(self.amp/100.)
        print('my_gain is',my_gain)

        call = SOX_EXEC+' -b 16 -c 2 -q -n -r '+str(AUDIO_FREQ)+' -d synth 21600 ' + self.wave + ' ' + str(self.freq) + ' gain '+str(my_gain-12)
        print(' call for play is: ', call)
        args = shlex.split(call)
        try:
#           print 'args: ',args
            self.pid = subprocess.Popen(args)
        except:
            popup_msg("Problem starting sox to play audio,\ncheck path: "+SOX_EXEC, base.window)
            return False
        self.playing = True
        return True

    def killPlay(self):
        if not self.pid:
            return
        try:
            self.pid.kill()
            self.playing = None
        except:
            pass


    def main(self):    
        gtk.gdk.threads_enter()
        gtk.main() 
        gtk.gdk.threads_leave()

#print __name__
if __name__ == "__main__":
    base = topWin()
    base.main()

