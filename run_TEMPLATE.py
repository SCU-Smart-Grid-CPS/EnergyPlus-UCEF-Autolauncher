# run_template.py
# Author(s):    Brian Woo-Shem
# Version:      2.1
# Last Updated: 2023-01-08
# Code to run a single EnergyPlus sim, with repetition in case of warmup anomaly errors and failsafe for total .idf implosion.
# Intended for use with ep_ucef_autosim

#Port & Simulation Number
pn = PPPP

print("run_" + str(pn) + ".py ===>")

import subprocess

# === Directories used ===
ep_dir = 'ENERGYPLUS_DIRECTORY'

wfile = 'WEATHER_FILENAME'

simfile = 'SIMULATION_FILENAME'

# === Create run command ===
runcmd = ep_dir + ' --readvars --output-directory ' + str(pn) + ' -w ' + wfile + ' ' + simfile

#print("Sim ", pn, " running: ")
print(runcmd)

# === Initial run ===
#Launch subprocess in the shell
epproc = subprocess.run(runcmd, capture_output=True, shell=True)

#Display result. 0 = success; else failure
print(pn, " returned: ", epproc.returncode)

# === Re-attempt to run the simulation if it crashed ===
# There is probably a more elegant way to combine this with above run, but this works well enough

#Sanity check to ensure it does not have infinite loop of crashing
insanity = 1

# If previous run was not successful and it ran fewer than 12 times, run it again
while epproc.returncode!=0 and insanity < 13:
	epproc = subprocess.run(runcmd, capture_output=True, shell=True)
	print("Warning: ", pn, " failed -> rerunning")
	print(pn, " returned: ", epproc.returncode)
	insanity = insanity + 1

# === Display result to user ===
if insanity < 13:
	print(pn, " success!")
else:
	print("ERROR: ", pn, " Failed repeatedly, using default sim.")
	
	#Use failsafe sim so the entire system doesn't get stuck
	# Clumsy way to copy a file
	import os #don't import until now to speed up nominal operation
	import platform
	
	failsafesim = "failsafe.idf"
	fsfile = open(failsafesim, 'r')
	failsafe_contents = fsfile.read()
	catchallfile = str(pn) + '\failsafe.idf'
	cfile = open(catchallfile, "a")
	cfile.truncate(0)
	cfile.write(failsafe_contents)
	cfile.close()
	fsfile.close()
	
	while epproc.returncode!=0 and insanity < 15:
		print(pn, ' running failsafe to protect overall simulation')
		runcmd = ep_dir + ' --readvars --output-directory ' + str(pn) + ' -w ' + wfile + ' ' + catchallfile
		epproc = subprocess.run(runcmd, capture_output=True, shell=True)
		print(pn, " returned: ", epproc.returncode)
		insanity = insanity + 1
	
	if insanity < 15:
		print(pn, " failsafe only success!")
	else:
		print("ERROR: ", pn, " Failed repeatedly in failsafe -> giving up.\n\nUse CTRL+C to kill the simulation code.")
		exit()
