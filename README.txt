LICENSE
======

See COPYING

All Anmr code is made available under the GNU GPL, version 3.

A Windows binary of AVRDUDE is bundled into this distribution. It,
along with the cygwin library it uses, was copied straight out of the
arduino-1.03 package. Source code is available from 
http://download.savannah.gnu.org/releases/avrdude/
and
http://cygwin.com/snapshots/

The precompiled arduino firmware provided includes libraries from the
arduino-1.0.4 release. Source code is available here:
http://arduino.cc/en/Main/Software

INTRODUCTION
============

This is the software used to drive the arduino NMR setup used in the
Physics 102 laboratory at UBC. The hardware is based on that described
in: Meas. Sci. Technol. 21 (2010) 105902. In addition to the hardware
described there, the current system incorporates gradient coils for
simple 2D imaging. The software was been developed on Linux systems,
but has also now been ported for Windows. Mac shouldn't be difficult,
but hasn't been done yet. Instructions and an install script for
Ubuntu 11.04 -> 12.04 is supplied. The software should be usable with
other Linux flavours with minor changes to the install instructions. A
separate file describes installation instructions for Windows.

The main part of the software is written in python2, using the pygtk
toolkit. The components are described in more detail below. The
feature set here has been chosen to be only just exceed what we need
for the teaching lab, many other features could be added
straightforwardly.

Arduino Duemilanove and Uno have been tested. The recent Leonardo is
guaranteed not to work. Be aware that 1st generation Uno's shipped
with buggy firmware in the USB-Serial interface. This can be updated,
see:  http://arduino.cc/en/Hacking/DFUProgramming8U2
(The firmware file required, Arduino-usbserial-uno.hex, is included
with any moderately recent arduino package) 

If you find this software useful, please let me know! If you build a
project derived from this, please let me know! Improvements to the
code are welcome. I cannot promise any level of support, but will help
if I can as time allows. 

Carl Michal
michal@physics.ubc.ca

INSTALL
=======

To install in Windows, see the separate instructions.

to install in ubuntu: 

1) tar -zxvf Anmr-X.X.tar.gz

2) cd Anmr-X.X

3) edit ubuntu_install.sh, set HDIR to the home directory of the user who
will use the arduino NMR.

Be aware that the install script will remove /usr/local/share/Anmr
and all subdirectories.  If there is anything in there that you want
to keep, back it up before running the install script.

4) sudo ./ubuntu_install.sh

5) ensure that required packages are installed (you may need to enable
the universe repository)

sudo apt-get install arduino scons socat python-matplotlib python-serial python-scipy sox eog dpkg-dev libssl-dev

I would recommend removing a couple of packages (to prevent capture of
the main menubar which makes Anmr look very strange on startup):

sudo apt-get autoremove appmenu-gtk appmenu-gtk3 appmenu-qt

After logging out and back in again, you should find Anmr, FuncGen and
Shim as applications (in the Education category).

6) the location of the arduino files (ARDUINO_HOME_DEFAULT) may need
to be changed in /usr/local/share/SConstruct


COMPONENTS
==========

We install three gui programs (python):
FuncGen, Anmr and Shim

Shim
----
Shim is very simple: it guides a user through the process of
shimming. It is rather hardware specific to our setup at UBC. Our
gradient system has three coils whose currents are controlled by
10-turn potentiometers. The shim program asks the user to input the
starting values of the three 10-turn pots, and then enter the FWQM
(full-width at quarter maximum) of the NMR spectrum. FWQM values are
calculated within Anmr using the 'Pick Peak Limits' or 'Measure With
Previous Limits' button. Shim then makes "good" guesses as to step
sizes of the shim currents, and guides the user to optimal shim
values.

FuncGen
-------
FuncGen is a general purpose audio function generator and single
channel 'oscilloscope.' It makes use of some command-line helper 
programs (eg sox and friends) to generate audio frequency
waveforms. It can read voltage data from an arduino or from a
soundcard. This can be shown in an oscilloscope mode ('Live View') in
the time or frequency domain.

The UI should be mostly self-explanatory, except possibly that the
upper and lower limits of the frequency selection of the function
generator are set by the start and stop frequencies of the frequency
sweep.

'Measure using frequency sweep' plays tones at the indicated number of
frequencies, and samples the response from the arduino or soundcard at
each frequency, plotting rms values as it goes. We use this to measure the
response of an RLC resonant circuit and of a band-pass filter.

A measurement can also be done with broadband white noise, where a
long measurement is made and the FT of the response is displayed.

Anmr
----
Anmr is the main program for running our spectrometer. On startup the
user can choose to open existing data, or to select a pulse program
(under Data Acquisition) for collecting new data. Selecting a pulse
program gives the user a display with adjustable parameters, and three
buttons to acquire data in various modes.

'Acquire' runs the program the indicated number of times with the
given parameters.

'Arrayed Acquire' allows the user to vary one of the parameters and
collect a simple 2D data set.

'Acquire image data' walks the student through collection of
projections for an image to be reconstructed with filtered
backprojection. In this mode, the user can set how many projections
are desired, and the software prompts at the end for one additional
spectrum to be collected with the sample replaced with a plain sample
bottle filled with water. This final projection is used to normalize
the intensity vs frequency. 

In the data windows, the data can be displayed in the time or
frequency domain (FID/spectrum button). 'Auto-Scale' adjusts the y
scale to fit the displayed region of data. 'Phase' opens a window to
allow the user to phase the data. 'Broadening' sets the FWHM of a
Gaussian broadening function applied before Fourier transformation.
'Left Shift' allows the user to shift the 0 of time to the left or
right. 'Spectrum Points' is the number of points the data set is
zero-filled to before Fourier Transform. The toolbar below the plot
allows for the plot scale to be manipulated (the four arrows or the
magnifying glass) and also for an image of the plot to be saved. This
toolbar is a standard matplotlib widget.

'Multiple Echoes' allows data sets with more than one echo to be
handled. The idea here is a CPMG data set can be chopped into pieces
which are then added together to increase the signal to noise in the
frequency domain. 'Full Echo' tells the program that the data set
contains not an FID, but the rising part of an echo as well. In this
case, the data is shifted to put t=0 in the right place (and get the
phase right) automatically. To do this, the program needs to know the
frequency range of the spectrum.  This is set by selecting 'Pick Peak
Limits' in the frequency domain, and then clicking to either side of
the peak. 'Full Echo' is greyed out until this is done.

'Save Data' allows the data to be saved. Each data set is a directory
that has a separate text file for each time domain record, along with
a file that contains the pulse program and parameters used. The first
line of each data set begins with #<number of transients>, followed by
integers representing the FID. The dwell time is always 104us. 'Write
Spectrum' will write the time domain data as text into this same
directory.

For data acquired with 'Arrayed acquisition' or 'Acquire image data'
which contain multiple records, the + and - buttons below the
parameters are available to scroll between the different records.

'Reconstruct Image' is available for image data sets to
perform the filtered backprojection. The reconstructed image is
written as Image.png in the data directory, and displayed. The image
viewer can be set in the platform specific .py file. In linux, the
default is eog, in Windows the windows built-in image viewer is used.

Two options for extra processing in the image reconstruction are
available. 'Auto Align Projections' tries to line up the centers of
all of the projections before the reconstruction. 'Circle Correct
Projections' when checked, assumes that the final projection in an
image data set is of a full water bottle that should give a
semi-circular shaped spectrum. This final spectrum is fitted to a
semi-circle, and then correction factors are calculated to measure
distortion from the circle. These correction factors are applied to
all the other projections.

Example Data
======= ====

Three example data sets are provided to allow the UI to be explored
with no hardware connected.

00shimmed is a nice spectrum of a well shimmed water bottle.

01image is an image of a water bottle with a plastic x inside. To
reconstruct the image, first press FID/spectrum to view the first
projection in the time domain. Then Press 'Pick Peak Limits,' and when
prompted click once on the baseline at either edge of the peak (around
2056 and 2078 Hz, exact values aren't crucial). Finally, click
'Reconstruct Image.' 

02fullecho contains spin-echo data with both the rising and falling
portion of the echo. After opening the file, view it in the frequency
domain, and using Pick Peak Limits, set the peak limits to ~2120 Hz
and 2200 Hz. Then tick the 'Full Echo' check box, and Anmr will
calculate where t=0 is, and phase the spectrum automatically.

To test the acquisition portion of the software, connect an arduino
Deumilanove or Uno.  No other hardware is required for Anmr to
function. You can connect a signal source to the arduino input A0.

Arduino Code
======= ====

Firmware for the arduino has been written to allow pulse programs to
be executed without requiring a new firmware flash for each change in
parameter. The first time Anmr or FuncGen tries to access the arduino,
it checks to see if the firmware it expects is present, if not, it
will attempt to download it (using avrdude). This is not foolproof
unfortunately.  Sometimes the read call that attempts to collect the
arduino's response to the query fails to time-out properly, and this
query process hangs.  If this happens, using the arduino gui to flash
the example 'Blink' program usually results in an arduino that can
then be flashed automatically.

This code makes heavy use of direct register read/writes of the Atmel
ATMEGA328P and is very unlikely to work with any other microcontroller
without heavy modification. Stick with Uno or Duemilanove.

LOCKFILE
========

Anmr and FuncGen use a trivial lock file system to prevent more than
one of them from trying to access the arduino at the same time. The
lockfile lives in <system temp dir>/Anmr/anmr-lockfile. If FuncGen or
Anmr hangs or crashes, the lockfile may need to be removed
manually. Anmr will let you know if this is the case.


SOCAT & HUB4COM
===============

Because the arduino Uno resets each time the pseudo serial port device
representing it is opened, a pseudo serial bridge can be used to keep
a single connection to the arduino is used. Socat does the job in
linux, a combination of HUB4COM and COM0COM can be used in windows.
By default these are not used. This can be controlled by setting the
USE_SERIAL_PIPE variable in the platform specific .py file in the bin
directory. 

On Linux, the model of the socat bridge also allows for transparent remote
operation of the system. socat can easily be set up to bridge the
arduino's serial port (eg /dev/ttyUSB0 or /dev/ttyACM0) to a pseudo
serial port on a distant computer. In this way, the gui runs at native
speed, and only relatively low volumes of data travel over the network.

PULSE PROGRAMMING
===== ===========

The pulse program compiler offers a simple pulse programming language
with adjustable parameters, simple looping, and simple phase cycling.

Each pulse program is begun by including
/usr/local/share/Anmr/PulsePrograms/defaults.include
We use this file to define the hardware pin locations.

The pulse program itself can begin with a section similar to:

#DEFINITIONS
#frequency 100 3000 2050 ''
#polarization_time 0 10000 3000 ms
#90_half_cycles 0 60 10 ''
#echo_delay 0 5000 25 ms
#180_half_cycles 0 60 18 ''
#receiver_delay 0 5000 5 ms
#repetition_delay 0 7000 1000 ''
#num_points 1 20000 12000 ''
#END

where each line between #DEFINTIONS and #END defines an adjustable
parameter that will be available in the gui for the user to set. The
first and second values following the variable number are the minimum
and maximum of the parameter.  The third value is the default. The
final entry (or '') is a label shown in the gui (eg units)

After #END, other variables can be defined, and pulse program
statements can be given.

Simple variables can be defined as:

%var_name = 3

There are no floating point numbers. All values are integers. 

Pulse program statements that are understood are:


	DELAY_IN_CLOCKS <# of clock cycles>

		This function instructs the micro-controller to wait
		the specified number of (16 MHz) clock cycles.

	DELAY_IN_MS <# of milliseconds>

		This function instructs the micro-controller to wait
		the specified number of milliseconds.

	SET_PULSE_PINS <ppin> <mpin>
	
		This function sets which pins are used to generate
		pulses.  Must be set before a pulse is used.

	CHANGE_PIN <pin#> <state>

		This function changes the state of a pin on the
		micro-controller. 0 for low, non-0 for high.

	WAIT_FOR_PIN <pin#> <edge>
		
		This function watches for an edge in the specified
		pin. 0 for any edge, 1 for rising edge, >1 for falling
		edge. The pin is set to be an input.

	PULSE <start phase> <phase increment> <steps till increment> <# of half-cycles>
or
	PULSE <phase table> <# of half-cycles>
		This function produces a pulse for the
		specified number of half cycles.
		
		For the first syntax:
		
		The first argument sets the phase value for the first
		time through. It's an integer number of degrees. The
		next two arguments are used for phase cycling. The
		increment would usually be 0, 90, or 180, and the
		steps till increment sets how many transients go by
		till the increment is applied. For example, if a
		sequence of 0, 180, 0, 180 is desired, the first
		three arguments are 0 180 1, meaning start at 0,
		increment by 180, and increment each time.

		For 0, 0, 180, 180, the parameters would be 0 180 2.

		For 0, 90, 180, 270, the parameters would be 0 90 1

		For 180, 0, 180, 0: 180 180 1
		
		For the second syntax, the table must have been previously
		defined with a TABLE command. Valid table numbers are T0
		up to T15. Example usage:
		PULSE T0 8

		In either case, phases can be set to a resolution of 2 degrees
		(they are stored as single bytes, and the values multiplied by 2
		to get the phase in degrees).

	READ_DATA <phase> <phase increment> <steps till increment> <# of data points>
or
	READ_DATA <phase table> <# of half-cycles>

		This function instructs the micro-controller to read
		the voltage on the ADC and send it to the host program
		to be written. Phases are the same as for pulses.

	SET_FREQ <frequency>

		This function instructs the micro-controller to
		initialise the internal timer and variables used to
		produce pulses.
		
	SYNC
		Waits till the end of the current audio-frequency
		cycle (SET_FREQ must have previously called).

	TABLE
		defines a phase table. Syntax is:
		TABLE T0 {0,180,180,0}
		Valid table numbers are T0 up to T15. Each table can be as
		long as you like, (though remember the arduino doesn't have much ram!)

	TOGGLE_PIN <pinNum> <startVal>
		allows a pin on the arduino to be toggled to alternate values 
		on alternate scans. pinNum is set to startVal on scan 0, then
		toggled on or each on each scan.

Warning: in our arduino code, arduino pin D7 is always set to be an input.
This is set in arduinoCode.pde.


Copyright 2013 Carl Michal and Daniel Hon-Kit Chong
