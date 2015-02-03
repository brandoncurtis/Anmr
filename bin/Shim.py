#!/usr/bin/python2.7

from __future__ import division
from __future__ import print_function
import numpy

#import matplotlib.artist as Artist
#import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.figure import Figure
import gtk
import sys
import os.path

from matplotlib.backends.backend_gtkagg import FigureCanvasGTKAgg as FigureCanvas


#these are also defined in anmr_platform_linux.py and anmr_platform_win.py
if sys.platform == "win32":
    ICON_PATH = "c:\\Anmr\\Icons"
    ICON_EXTENSION = "24.xpm"
elif sys.platform == "linux2":
    ICON_PATH = "/usr/local/share/Anmr/Icons"
    ICON_EXTENSION = ".svg"


class plotWindow:
    def __init__(self, title):
    #title is the title of the window.

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
#mod for win:
        try:
            self.window.set_icon_from_file(os.path.join(ICON_PATH, "Shim-icon"+ICON_EXTENSION))
        except:
            pass
        vbox = gtk.VBox(False)
        self.window.add(vbox)
        self.window.set_size_request(600, 400)
        self.window.set_title(title)

        self.fig = Figure(figsize=(4, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_position([0.2, 0.2, 0.7, 0.7])
        self.canvas = FigureCanvas(self.fig)  # a gtk.DrawingArea
        vbox.pack_start(self.canvas, True, True,0)

        self.ax.set_xlabel("Shim dial value")
        self.ax.set_ylabel("FWQM")


    def updatePlot(self, xmin, xmax, ymin, ymax, xvals, yvals, name):
        plotWin.ax.cla() # clear out what was there.
        plotWin.ax.set_xlim([xmin, xmax])
        plotWin.ax.set_ylim([ymin, ymax])
        plotWin.ax.set_xlabel(name+ " shim dial value")
        plotWin.ax.set_ylabel("FWQM")
        plotWin.ax.plot(xvals, yvals,'bo')

        self.canvas.draw_idle()
        return False


def do_a_shim(s0, q0, name, a, valLabel, blinker):
#sval is the starting value of the shim, qval is the starting FWQM value, and name is the name of the shim to adjust
    # A is the coefficient of the quadratic term expected in the equation: FWQM = sqrt(A*(x-x0)**2+c)


    blinker.modify_bg(gtk.STATE_NORMAL,gtk.gdk.color_parse("red"))
    # how big a step to make?
    svals = numpy.zeros(5)
    qvals = numpy.zeros(5) # max of 5 points?
    svals[0] = s0
    qvals[0] = q0
    num_p = 1

    step_size = q0/numpy.sqrt(a)/1.25 # go most of the way...
    svals[1] = round(s0 + step_size, 2)
    print ("step size is: ", step_size)

# get the plot ready:
    xmax = svals[0] + 1.2*step_size
    xmin = svals[0] - 1.2*step_size
    ymax = qvals[0] * 1.2
    ymin = qvals[0] /1.2
    plotWin.updatePlot(xmin, xmax, ymin, ymax, svals[0:num_p], qvals[0:num_p], name)


    # start by always going up first
    going_up = True
    label.set_text("1: Set the "+name+" dial to "+str(svals[1]))
    valLabel.set_text(str(svals[1]))
    fwqmButton.hide()
    dialog.set_default_response(gtk.RESPONSE_ACCEPT)
    response = dialog.run()
    if response == gtk.RESPONSE_DELETE_EVENT:
        exit()
    if response == gtk.RESPONSE_REJECT:
        blinker.modify_bg(gtk.STATE_NORMAL,None)
        return (s0,q0,-1)

    fwqmButton.show()
    label.set_text("Now collect a spectrum and enter the FWQM below")
    fwqmButton.grab_focus()
    response = dialog.run()
    if response == gtk.RESPONSE_DELETE_EVENT:
        exit()
    if response == gtk.RESPONSE_REJECT:
        blinker.modify_bg(gtk.STATE_NORMAL,None)
        return (s0,q0,-1)


    qvals[1] = fwqmAdjust.get_value()
    num_p += 1
# plot the point
    if qvals[1] > ymax:
        ymax = qvals[1] + (qvals[1] - ymax)*0.2
    if qvals[1] < ymin:
        ymin = qvals[1] - (ymin - qvals[1])*0.2
    plotWin.updatePlot(xmin, xmax, ymin, ymax, svals[0:num_p], qvals[0:num_p], name)


# if it's better, keep going in same direction, if its worse, go the other way.
    if qvals[1] < qvals[0]:
        svals[2] = round(svals[1]+step_size, 2)
        xmax += step_size
        xmin += step_size
    else:
        going_up = False
        svals[2] = round(svals[0]-step_size, 2)
    label.set_text("2: Set the "+name+" dial to "+str(svals[2]))
    valLabel.set_text(str(svals[2]))
    fwqmButton.hide()
    dialog.set_default_response(gtk.RESPONSE_ACCEPT)
    response = dialog.run()
    if response == gtk.RESPONSE_DELETE_EVENT:
        exit()
    if response == gtk.RESPONSE_REJECT:
        blinker.modify_bg(gtk.STATE_NORMAL,None)
        return (s0,q0,-1)

    label.set_text("Now collect a spectrum and enter the FWQM below")

    fwqmButton.show()
    fwqmButton.grab_focus()
    response = dialog.run()
    if response == gtk.RESPONSE_DELETE_EVENT:
        exit()
    if response == gtk.RESPONSE_REJECT:
        blinker.modify_bg(gtk.STATE_NORMAL,None)
        return (s0,q0,-1)
    qvals[2] = fwqmAdjust.get_value()
    num_p += 1
# plot the point
    if qvals[2] > ymax:
        ymax = qvals[2] + (qvals[2] - ymax)*0.2
    if qvals[2] < ymin:
        ymin = qvals[2] - (ymin - qvals[2])*0.2
    plotWin.updatePlot(xmin, xmax, ymin, ymax, svals[0:num_p], qvals[0:num_p], name)


#if we were better the second time but worse the first, we need one more point:
# this is if going up made it worse, but going down made it better
    if qvals[2] < qvals[0] and qvals[1] > qvals[0]:
        xmin -= step_size
        svals[3] = round(svals[2]-step_size, 2)
        label.set_text("3: Set the "+name+" dial to "+str(svals[3]))
        valLabel.set_text(str(svals[3]))
        fwqmButton.hide()
        dialog.set_default_response(gtk.RESPONSE_ACCEPT)
        response = dialog.run()
        if response == gtk.RESPONSE_DELETE_EVENT:
            exit()
        if response == gtk.RESPONSE_REJECT:
            blinker.modify_bg(gtk.STATE_NORMAL,None)
            return (s0,q0,-1)
        label.set_text("Now collect a spectrum and enter the FWQM below")
        fwqmButton.show()
        fwqmButton.grab_focus()
        response = dialog.run()
        if response == gtk.RESPONSE_DELETE_EVENT:
            exit()
        if response == gtk.RESPONSE_REJECT:
            blinker.modify_bg(gtk.STATE_NORMAL,None)
            return (s0,q0,-1)
        qvals[3] = fwqmAdjust.get_value()
        num_p += 1
#plot the point:
        if qvals[3] > ymax:
            ymax = qvals[3] + (qvals[3] - ymax)*0.2
        if qvals[3] < ymin:
            ymin = qvals[3] - (ymin - qvals[3])*0.2
        plotWin.updatePlot(xmin, xmax, ymin, ymax, svals[0:num_p], qvals[0:num_p], name)

#now, in either case of going up or down, if the last point is the best, do one more.
    if qvals[num_p-1] == numpy.amin(qvals[0:num_p]):
        if going_up:
            xmax += step_size
            svals[num_p] = round(svals[num_p-1]+step_size, 2)
        else:
            xmin -= step_size
            svals[num_p] = round(svals[num_p-1]-step_size, 2)
        label.set_text("5: Set the "+name+" dial to "+str(svals[num_p]))
        valLabel.set_text(str(svals[num_p]))
        fwqmButton.hide()
        dialog.set_default_response(gtk.RESPONSE_ACCEPT)
        response = dialog.run()
        if response == gtk.RESPONSE_DELETE_EVENT:
            exit()
        if response == gtk.RESPONSE_REJECT:
            blinker.modify_bg(gtk.STATE_NORMAL,None)
            return (s0,q0,-1)
        label.set_text("Now collect a spectrum and enter the FWQM below")
        fwqmButton.show()
        fwqmButton.grab_focus()
        response = dialog.run()
        if response == gtk.RESPONSE_DELETE_EVENT:
            exit()
        if response == gtk.RESPONSE_REJECT:
            blinker.modify_bg(gtk.STATE_NORMAL,None)
            return (s0,q0,-1)
        qvals[num_p] = fwqmAdjust.get_value()
        num_p += 1
#plot the point:
        if qvals[num_p-1] > ymax:
            ymax = qvals[num_p-1] + (qvals[num_p-1] - ymax)*0.2
        if qvals[3] < ymin:
            ymin = qvals[num_p-1] - (ymin - qvals[num_p-1])*0.2
        plotWin.updatePlot(xmin, xmax, ymin, ymax, svals[0:num_p], qvals[0:num_p], name)


    q2 = qvals*qvals # should be fitting squares - for second moments.
    print("have ", num_p, " points")
    s40 = numpy.sum(svals[0:num_p]*svals[0:num_p]*svals[0:num_p]*svals[0:num_p])
    s30 = numpy.sum(svals[0:num_p]*svals[0:num_p]*svals[0:num_p])
    s20 = numpy.sum(svals[0:num_p]*svals[0:num_p])
    s10 = numpy.sum(svals[0:num_p])
    s21 = numpy.sum(svals[0:num_p]*svals[0:num_p]*q2[0:num_p])
    s11 = numpy.sum(svals[0:num_p]*q2[0:num_p])
    s01 = numpy.sum(q2[0:num_p])
    s00 = num_p
    # now get the fit:
    denom = s00*s20*s40-s10*s10*s40-s00*s30*s30+2*s10*s20*s30-s20*s20*s20
    a = 0.
    if denom != 0:
        a = (s01*s10*s30-s11*s00*s30-s01*s20*s20+s11*s10*s20+s21*s00*s20-s21*s10*s10)/denom
        b = (s11*s00*s40-s01*s10*s40+s01*s20*s30-s21*s00*s30-s11*s20*s20+s21*s10*s20)/denom
        c = (s01*s20*s40-s11*s10*s40-s01*s30*s30+s11*s20*s30+s21*s10*s30-s21*s20*s20)/denom
        print ("fit says: a ", a, " b: ", b, " c: ", c, " min at: ", -b/2/a, " min of: ", numpy.sqrt(c-a*b*b/4/a/a))
        best = round(-b/2/a, 2)

#       ymax = numpy.amax(qvals[0:num_p])
#       xmax = numpy.amax(svals[0:num_p])
#       xmin = numpy.amin(svals[0:num_p])
#       ymin = numpy.amin(qvals[0:num_p])
    if a <= 0.1 or best > xmax or best < xmin or denom == 0: # then our parabola is upside down or we're trying to go out of range, or the denominator was 0.
        #find the best value we've seen:
        bestq = qvals[0]
        bests = svals[0]
        for i in range(num_p):
            if qvals[i] < bestq:
                bests = svals[i]
                bestq = qvals[i]
        sf = round(bests, 2)
        bailed_out = True
    else:
        sf = best
        bailed_out = False
        if c-a*b*b/4/a/a < ymin:
            ymin = c-a*b*b/4/a/a
## plot it:

#       xd = xmax-xmin
#       yd = ymax-ymin
#       if xd == 0:
#           xd = 0.1
#       if yd == 0:
#           yd= 0.1
#       xmax = xmax+0.2*xd
#       xmin = xmin-0.2*xd
#       ymax = ymax+0.2*yd
#       ymin = ymin-0.2*yd

    if bailed_out is False :
#plot the parabola fit and a red line for where we hope to be
        xr = numpy.linspace(xmin, xmax, 50)
        yr = numpy.sqrt(a*xr*xr+b*xr+c)
        plotWin.line = Line2D(xr, yr)
        plotWin.ax.add_line(plotWin.line)
        plotWin.line = plotWin.ax.axvline(sf, color = 'r')
        plotWin.canvas.draw_idle()

        label.set_text("4: Set the "+name+" dial to "+str(sf)+"\nThis is the estimated best position.")
        valLabel.set_text(str(sf))

    else:
        label.set_text("4: Set the "+name+" dial to "+str(sf)+"\nThis is the best value encountered for this shim.\nThe data did not conform to expectations.\nIs the signal to noise adequate?")
        valLabel.set_text(str(sf))
# don't bother to do it again...
        fwqmButton.hide()
        dialog.set_default_response(gtk.RESPONSE_ACCEPT)
        response = dialog.run()
        if response == gtk.RESPONSE_DELETE_EVENT:
            exit()
        if response == gtk.RESPONSE_REJECT:
            blinker.modify_bg(gtk.STATE_NORMAL,None)
            return (s0,q0,-1)
        fwqmButton.show()
        blinker.modify_bg(gtk.STATE_NORMAL,None)
        return (bests,bestq,1)

    fwqmButton.hide()
    dialog.set_default_response(gtk.RESPONSE_ACCEPT)
    response = dialog.run()
    if response == gtk.RESPONSE_DELETE_EVENT:
        exit()
    if response == gtk.RESPONSE_REJECT:
        blinker.modify_bg(gtk.STATE_NORMAL,None)
        return (s0,q0,-1)
    label.set_text("Now collect a spectrum and enter the FWQM below")
    fwqmButton.show()
    fwqmButton.grab_focus()
    response = dialog.run()
    if response == gtk.RESPONSE_DELETE_EVENT:
        exit()
    if response == gtk.RESPONSE_REJECT:
        blinker.modify_bg(gtk.STATE_NORMAL,None)
        return (s0,q0,-1)
    qf = fwqmAdjust.get_value()
    if qf > qvals[0]*1.2 and sf != svals[0]: # we're at least not too much worse:
        print ("Help, we're worse, should go back to start val!")
    blinker.modify_bg(gtk.STATE_NORMAL,None)
    return(sf, qf, 1)


def pltWinClose(myself, widget, junk, pltWin):
    print("tried to close window")
    return True # don't allow to close




def getInitial():
    prelabel.show()
    valuesHbox.hide()
#    labelHbox.hide()
    shimButton1.show()
    shimButton2.show()
    shimButton3.show()
    label.hide()
    combobox.hide()
    fwqmButton.hide()
    dialog.set_response_sensitive(gtk.RESPONSE_REJECT,False)
    shimButton1.grab_focus()
    response = dialog.run()
    if response == gtk.RESPONSE_DELETE_EVENT:
        exit()

    print ("got entry val:", shimAdjust1.get_value())
    print ("got entry val:", shimAdjust2.get_value())
    print ("got entry val:", shimAdjust3.get_value())

    
    s1 = shimAdjust1.get_value()
    s2 = shimAdjust2.get_value()
    s3 = shimAdjust3.get_value()
    valueX.set_text(str(round(s1,2)))
    valueZ.set_text(str(round(s2,2)))
    valueY.set_text(str(round(s3,2)))


    label.set_text("Enter the starting FWQM")
    label.show()
    prelabel.hide()
    frame.hide()

    shimButton3.hide()
    shimButton2.hide()
    shimButton1.hide()
    fwqmButton.show()

    fwqmButton.grab_focus()
    response = dialog.run()
    if response == gtk.RESPONSE_DELETE_EVENT:
        exit()

    q1 = fwqmButton.get_value()
    print ("got starting Q:", q1)

    fwqmButton.hide()

    combobox.show()
    label.set_text("Which shim do you want to start with?")
    combobox.grab_focus()
    response = dialog.run()
    if response == gtk.RESPONSE_DELETE_EVENT:
        exit()
    i = combobox.get_active()
    print ('got i:',i)
    combobox.hide()

    valuesHbox.show()
#    labelHbox.show()
    frame.show()
    dialog.set_response_sensitive(gtk.RESPONSE_REJECT,True)
    return (s1, s2, s3, q1, i)


#print __name__
if __name__ == "__main__":

    # build a plot window
    plotWin = plotWindow("Shimming")
#catch delete events.
    connection = plotWin.window.connect("delete_event", pltWinClose, plotWin)
    plotWin.first = True
    plotWin.window.show_all()
    plotWin.window.deiconify()
    

    dialog = gtk.Dialog("Shimming Oracle", None, 0, ("Restart",gtk.RESPONSE_REJECT,gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
#    dialog = gtk.Dialog("Shimming Oracle", None, 0, (gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
    dialog.set_transient_for(plotWin.window)
    position = dialog.get_position()

    
    prelabel = gtk.Label("Enter values of the X1, Z1, and Y1 gradient\ncurrent dials (in that order) and hit OK")
    dialog.vbox.pack_start(prelabel,True,True,0)

    frame = gtk.Frame()
    dialog.vbox.pack_start(frame,True,True,0)
    frameVbox = gtk.VBox()
    frame.add(frameVbox)

    labelHbox = gtk.HBox()
    frameVbox.pack_start(labelHbox,True,True,0)
#    dialog.vbox.pack_start(labelHbox,True,True,0)
    valuesHbox = gtk.HBox()
    frameVbox.pack_start(valuesHbox,True,True,0)
#    dialog.vbox.pack_start(valuesHbox,True,True,0)
    labelX = gtk.Label("X1")
    labelZ = gtk.Label("Z1")
    labelY = gtk.Label("Y1")
    labelHbox.pack_start(labelX,True,True,0)
    labelHbox.pack_start(labelZ,True,True,0)
    labelHbox.pack_start(labelY,True,True,0)
    valueX = gtk.Label("5.00")
    valueZ = gtk.Label("5.00")
    valueY = gtk.Label("5.00")
    blinkerX = gtk.EventBox()
    blinkerZ = gtk.EventBox()
    blinkerY = gtk.EventBox()
    blinkerX.add(valueX)
    blinkerZ.add(valueZ)
    blinkerY.add(valueY)
    valuesHbox.pack_start(blinkerX,True,True,0)
    valuesHbox.pack_start(blinkerZ,True,True,0)
    valuesHbox.pack_start(blinkerY,True,True,0)


    label = gtk.Label("blank")
    dialog.vbox.pack_start(label,True,True,0)

    comboboxHbox = gtk.HBox()
    blabel = gtk.Label("")
    comboboxHbox.pack_start(blabel,True,True,0)
    
    combobox = gtk.combo_box_new_text()
    combobox.append_text('X1')
    combobox.append_text('Z1')
    combobox.append_text('Y1')
    combobox.set_active(0)
    #dialog.vbox.pack_start(combobox,False,True,0) #expand,fill,padding
    comboboxHbox.pack_start(combobox,False,True,0)
    dialog.vbox.pack_start(comboboxHbox,False,True,0)

    shimHbox = gtk.HBox()
#    dialog.vbox.pack_start(shimHbox)
    frameVbox.pack_start(shimHbox,True,True,0)
    shimAdjust1 = gtk.Adjustment(value = 5.00, lower = 0, upper = 10.0, step_incr = 0.01)
    shimButton1 = gtk.SpinButton(shimAdjust1, 0.1, 2) #args are climb_rate and digits
    shimHbox.pack_start(shimButton1,True,True,0)

    shimAdjust2 = gtk.Adjustment(value = 5.00, lower = 0, upper = 10.0, step_incr = 0.01)
    shimButton2 = gtk.SpinButton(shimAdjust2, 0.1, 2) #args are climb_rate and digits
    shimHbox.pack_start(shimButton2,True,True,0)

    shimAdjust3 = gtk.Adjustment(value = 5.00, lower = 0, upper = 10.0, step_incr = 0.01)
    shimButton3 = gtk.SpinButton(shimAdjust3, 0.1, 2) #args are climb_rate and digits
    shimHbox.pack_start(shimButton3,True,True,0)

#    valuesHbox.hide()
#    label.hide()


    fwqmAdjust = gtk.Adjustment(value = 5.00, lower = 0, upper = 99.0, step_incr = 0.01)
    fwqmButton = gtk.SpinButton(fwqmAdjust, 0.1, 2) #args are climb_rate and digits
#    dialog.vbox.pack_start(fwqmButton,True,True,0)
#    shimHbox.pack_start(fwqmButton,True,True,0)
    comboboxHbox.pack_start(fwqmButton,True,True,0)
    blabel = gtk.Label("")
    comboboxHbox.pack_start(blabel,True,True,0)
    fwqmButton.show()
    dialog.show_all()

## position the windows
#    dialog.move(position[0], position[1]+200)
# move the window to the lower right:
    dialog.set_gravity(gtk.gdk.GRAVITY_SOUTH_EAST)
    w,h = dialog.get_size()
    ww = gtk.gdk.screen_width()
    hh = gtk.gdk.screen_height()
    dialog.move(ww - w -64, hh - h-54)
    plotWin.window.set_gravity(gtk.gdk.GRAVITY_SOUTH_EAST)
    w2,h2 = plotWin.window.get_size()
    print (w,h,ww,hh,w2,h2)
    plotWin.window.move(ww-w2,hh-h-h2-25-54)





    (s1, s2, s3, q1,i) = getInitial()
    print ('back from initial: ',s1,s2,s3,q1)
    iend=i+6

# first one used to be 500, but I think it gave steps a little too small.
    while (i < iend):

        if i%3 == 0:
            (s1, q1, status) = do_a_shim(s1, q1, "X1", 400,valueX,blinkerX)
        if i%3 == 1:
            (s2, q1, status) = do_a_shim(s2, q1, "Z1", 300,valueZ,blinkerZ)
        if i%3 == 2:
            (s3, q1, status) = do_a_shim(s3, q1, "Y1", 400,valueY,blinkerY)
        if status == -1: #restart!
            shimAdjust1.set_value(s1)
            shimAdjust2.set_value(s2)
            shimAdjust3.set_value(s3)
            fwqmAdjust.set_value(q1)
            combobox.set_active(i%3)
            (s1, s2, s3, q1,i) = getInitial()
            print ('back from initial: ',s1,s2,s3,q1)
            iend=i+6
        else:
            i += 1



    fwqmButton.hide()
    label.set_text("If all went well, the FWHM is now approximately 1 Hz\nIf it is greater than 1.5 Hz, you can try\nstarting this program again to optimize the currents further.")
    dialog.set_default_response(gtk.RESPONSE_ACCEPT)
    response = dialog.run()
