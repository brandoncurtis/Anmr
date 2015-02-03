#!/bin/sh
# this all works for Ubuntu 11.04 not tested elsewhere.

#user's home directory:
export HDIR=/home/student

# need to be executed as root, in the directory where this was unpacked
#get rid of any previous installation:
rm -rf /usr/local/share/Anmr
mkdir /usr/local/share/Anmr

#install the code, python, C (source and executables), arduino, and pulse programs:
mv bin/Anmr.py /usr/local/bin/
mv bin/FuncGen.py /usr/local/bin/
mv bin/Shim.py /usr/local/bin/
mv bin/anmr_common.py /usr/local/bin/
mv bin/anmr_platform_linux.py /usr/local/bin
mv bin/anmr_compiler.py /usr/local/bin

chmod ugo+rx /usr/local/bin/Anmr.py
chmod ugo+rx /usr/local/bin/FuncGen.py
chmod ugo+rx /usr/local/bin/Shim.py
chmod ugo+rx /usr/local/bin/anmr_common.py
chmod ugo+rx /usr/local/bin/anmr_platform_linux.py
chmod ugo+rw /usr/local/bin/anmr_compiler.py

mv arduinoCode /usr/local/share/Anmr/
mv PulsePrograms /usr/local/share/Anmr/

chmod ugo+rx /usr/local/share/Anmr/arduinoCode
chmod ugo+rx /usr/local/share/Anmr/PulsePrograms


#fix permissions so users can build and download the arduino code
chmod ugo+rwx /usr/local/share/Anmr/arduinoCode
chmod ugo+rwx /usr/local/share/Anmr/arduinoCode/build

#icons:
mv Icons /usr/local/share/Anmr/

#.desktop files for our python progs to work nicely on the menus
mkdir -p /usr/local/share/applications
mv Linux_desktop_files/* /usr/local/share/applications/


mkdir -p $HDIR/anmr-data
chown student $HDIR/anmr-data


echo ""
echo "The user needs to be in the dialout group"


