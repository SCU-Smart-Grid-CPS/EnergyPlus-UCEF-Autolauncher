# epautoparallel.py
# Author(s):    Brian Woo-Shem
# Version:      2.01
# Last Updated: 2023-04-25
# Project: EnergyPlus + UCEF Superscalable Simulation -> Autolaunch v8.00
# Runs EnergyPlus simulations in parallel
# Assumes simulations follow the file naming convention created by ep2ucef_fmu_setup.py

import subprocess
import time
#import platform
from configparser import ConfigParser


starttime = int(round(time.time())) #for simulation runtime

# Get starting port number from settings file
#  we typically use 6789, but adding this feature in case different port numbers are needed in the future
cp = ConfigParser()
cp.read('autosim_settings.ini')
try:
	pn = int(cp.get('Basic_Info', 'Starting_Port_Number'))
except (NameError, ValueError, KeyError): #note ConfigParser.NoOptionError is not catchable. could use Exception
	# Using warning instead of terminate program because we use 6789 by convention
	print("Warning: Could not get initial port number from config settings. \n Using default port number = 6789. \n If this is a problem, check autosim_settings.ini")
	pn = 6789
# Get wait_time_between_launches, the number of seconds delay between launching the simulations
#  to prevent crashing/CPU overload during E+ warmup if all activate at once
try:
	wait_time_between_launches = int(cp.get('Basic_Info', 'Wait_Time_Between_Launches'))
except (NameError, ValueError, KeyError):
	# Using warning instead of terminate program because typically 30 seconds works fine
	print("Warning: Could not get Wait_Time_Between_Launches from config settings. \n Using default wait time = 30 seconds. \n If this is a problem, check autosim_settings.ini")
	wait_time_between_launches = 30

# Folder delimiter
folderDelim = '/'

# Get number of simulations
setnumsimsfile = open("copy2UCEF\setNumSims.txt", 'r')
n = int(setnumsimsfile.read())
print("Queued ", n, " E+ sims, starting with Port Number ", pn)
print('This will take approximately ', wait_time_between_launches * n / 60, ' minutes.\n')

#math for last port aka. simulation number
last = pn + n
#Initialize a list to hold all subprocesses, each which runs one simulation
simprocesses = []

# Iteratively start codes to run each simulation in parallel
# each run_####.py code is needed to handle the relaunch and the parallelization
# time.sleep(seconds) is a delay to account for the time needed to connect to UCEF so they connect in order
while pn < last:
	#edit - changed to launchcodes\run####.py folder
	pname = "Py launchcodes" + folderDelim + "run_" + str(pn) + ".py"
	print("Launching: ", pname)
	p = subprocess.Popen(pname, shell=True)
	simprocesses.append(p)
	time.sleep(wait_time_between_launches)
	pn = pn+1

# At this point, all simulations are running in parallel
print('\nAll simulations launched!\n\nPlease wait while simulations run. This typically takes 5 minutes per simulated day, so take a break and be patient...\n')
simtime = int(round(time.time()))

# Wait for all simulations to complete
for sp in simprocesses:
	sp.wait()

# All simulations complete
print("Done running simulations!\n")

# Simulation runtime data
endtime = int(round(time.time()))
duration = endtime - starttime
print("Program Runtime (incl. launch) = ", duration, " seconds = ", duration/60, " minutes")
duration2 = endtime - simtime
print("Simulation Runtime = ", duration2, " seconds = ", duration2/60, " minutes")
