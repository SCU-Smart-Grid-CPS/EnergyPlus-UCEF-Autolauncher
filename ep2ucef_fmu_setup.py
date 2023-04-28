# ep2ucef.py
# Author(s):    Brian Woo-Shem
# Version:      3.01
# Last Updated: 2023-04-25
# Project: EnergyPlus + UCEF Superscalable Simulation -> Autolaunch v8.00
# Usage:
# - start with idf file you want to change
# - put all blocks of text you want to have removed (keys) in the findkeys.txt file. Separate each block with '@'
# - in replacekeys.txt, put the corresponding block of text to replace each key with, in the same order that keys are given in findkeys. Separate each block with '@'
# - The delimiter '@' is chosen because none of the files we are working with should contain this character. This can be changed if needed.

#Imports needed to create fmu file
from zipfile import ZipFile
import os
from configparser import ConfigParser
#import platform
import csv

# Some file names that we generally don't change unless there's a good reason:

# ===> Name of file with sections of text that will be found and replaced <===
findkeyfile = "findkeys.txt"

# ===> Name of file with the text to replace each thing we find <===
replacekeyfile = "replacekeys.txt"

# ===> Name of file with the text to add at the end <===
appendfile = 'add2idf.txt'

# ===> Delimiter <===
delimiter = '@'

#Add specified file extension if it is not already present to a string representing the output file name
def addExt(c, ext):
	if c[len(c)-len(ext): len(c)] != ext: c = c + ext
	return c

#Remove specified file extension if it is present from a string representing the output file name
def remExt(c, ext):
	if c[len(c)-len(ext): len(c)] == ext: c = c[:len(c)-len(ext)]
	return c

folderDelim = '/'

# Lists which will have each element correspond to a particular simulation which must be setup later
sourcefiles = [] #path and filename if input .idf
targetfiles = [] # path and filename of output (modified) .idf
modes = [] # list of HVAC control modes
weatherfiles = [] # weather file (.epw) for each simulation

# Get settings
cp = ConfigParser()
cp.read('autosim_settings.ini')
try:
	sectionName = cp.get('Basic_Info', 'Simulation_Name')
	print("Simulation Name = ", sectionName)
	pn1 = int(cp.get('Basic_Info', 'Starting_Port_Number'))
	ep_dir = cp.get('Basic_Info', 'EnergyPlus_Directory')
	heatorcool = cp.get(sectionName, 'heatorcool')
	simSetType = cp.get(sectionName, 'Type_of_EnergyPlus_Simulation_Set')
except (NameError, ValueError):
	print("Fatal Error: Could not get config settings. Check autosim_settings.ini \n\nx x\n >\n ⁔\n")
	exit()

pn = pn1

# Methods for determining which simulations (.idf) files to run
# Each should output 4 lists of the same length, where ith item corresponds to ith simulation
# these are sourcefiles, targetfiles, modes, weatherfiles

# Categorical: There are a certain number of simulations of several different categories predefined
# - Must have same # of sims per category
# - category names for the input files and the output file names must be given in autosim_settings.ini
# - this is the original mode used by Brian when running simulations for the Income-level fairness 2023 paper
if 'categorical' in simSetType:
	# Additional settings for categorical simulation sets
	try: 
		n_sims = int(cp.get(sectionName, 'Number_of_Simulations_Per_Category'))
		CAT_LIST = cp.get(sectionName, 'Input_Category_List')
		CAT_LIST = CAT_LIST.split(',')
		n_cat = len(CAT_LIST) # number of categories
		CAT_OUT_LIST = cp.get(sectionName, 'Output_Category_List')
		CAT_OUT_LIST = CAT_OUT_LIST.split(',')
		MODELIST = cp.get(sectionName, 'List_of_HVAC_control_modes')
		MODELIST = MODELIST.split(',')
		n_modes = len(MODELIST) # number of modes
		weatherfilename = cp.get(sectionName, 'Weather_File')
		weatherfilename = addExt(weatherfilename, '.epw') #Check if .epw is added to end, if not, add it.
	except (NameError, ValueError):
		print("Fatal Error: Could not get config settings. Check autosim_settings.ini \n\nx x\n >\n ⁔\n")
		exit()
	
	# Loop for all categories
	b = 0
	while b < n_cat:
		# Loop for all models of this type
		m = 1
		while m <= n_sims:
			# Loop for all of the HVAC control modes
			c = 0
			while c < n_modes:
				# Source file name
				sourcefiles.append(CAT_LIST[b] + str(m) + ".idf")
				# Change to name you want for the file after replacing contents
				targetfiles.append(str(pn) + folderDelim + CAT_OUT_LIST[b] + '_' + MODELIST[c] + "_" + str(m) + ".idf")
				modes.append(MODELIST[c])
				weatherfiles.append(weatherfilename)
				#increment indices
				c = c + 1
				pn = pn+1
			m = m + 1
		b = b + 1
# Use an input simulation queue with pre-specified mode and weather files
# note these modes and weather file settings will override whatever is in autosim_settings.ini
# MUST have a file called simulation_queue.csv with 4 columns
# Filepath | Filename | Mode | Weather
# Filepath = entire path to the .idf file
# Filename = just name of .idf file
# Mode = HVAC control setting (fixed, adaptive, occupancy, can implement others in the future)
# Weather = path from current run directory to the .epw weather file. Different simulations can have different weather files
# order of columns can vary
elif 'use_list' in simSetType:
	#read csv with headers
	with open('simulation_queue.csv') as csvfile:
		readCSV = csv.DictReader(csvfile, delimiter=',')
		for row in readCSV:
			sourcefiles.append(row['Filepath'])
			# sets name of new .idf to be created
			targetfiles.append(str(pn) + folderDelim + 'UCEF_' + addExt(remExt(row['Filename'],'.idf'),'.idf'))
			modes.append(row['Mode'])
			weatherfiles.append(row['Weather'])
			pn = pn + 1
# Automatically detect all simulations in the parent directory (including subdirectories)
# and run them for all modes
#  Note: code is based on detect_sims.py, but the version here does not write to .csv
elif 'autodetect' in simSetType:
	try: 
		MODELIST = cp.get(sectionName, 'List_of_HVAC_control_modes')
		MODELIST = MODELIST.split(',')
		n_modes = len(MODELIST) # number of modes
	except (NameError, ValueError):
		print("Fatal Error: Could not get config settings. Check autosim_settings.ini \n\nx x\n >\n ⁔\n")
		exit() 
	
	idffiles = []
	idfpaths = []
	# Perform search to detect all .idf files in the parent and subdirectories
	#  and get their full directory paths
	for root, dirs, files in os.walk(os.getcwd()):
		for file in files:
			#Find all .idf files. Autoignores "failsafe.idf" file used as a backup when another fails.
			if file.endswith('.idf') and 'failsafe' not in file:
				idfpaths.append(os.path.join(root,file))
				idffiles.append(file)

	# Get number of simulations
	numSims = len(idffiles)
	print('Found ', numSims, ' .idf simulation files.')

	# Alphabetize the list of simulations (they are random otherwise)
	simtuples = [(idffiles[i], idfpaths[i]) for i in range(0, numSims)]
	simsSorted = sorted(simtuples, key=lambda s: s[0])
	
	#autodetect weather files
	epwfiles = []
	for file in os.listdir(os.getcwd()):
		#Find all .epw files
		if file.endswith('.epw'):
			epwfiles.append(file)
			print(file)
	# handles if it finds more than 1 .epw file
	if len(epwfiles) > 0:
		weatherfilename = epwfiles[0]
	elif len(epwfiles) > 1:
		print('WARNING: Detected multiple weather files, using first one.')
	
	print('Using weather file: ', weatherfilename)
	
	# for all simulation files (idf) found
	i = 0
	while i<numSims:
		# for all modes
		c = 0
		while c < n_modes:
			sourcefiles.append(simsSorted[i][1])
			# sets name of new .idf to be created
			targetfiles.append(str(pn) + folderDelim + 'UCEF_' + addExt(remExt(simsSorted[i][0],'.idf') + "_" + MODELIST[c],'.idf'))
			modes.append(MODELIST[c])
			weatherfiles.append(weatherfilename)
			pn = pn + 1
			c = c + 1
		i = i + 1
else:
	print("Fatal Error: Invalid Type_of_EnergyPlus_Simulation_Set setting. Check autosim_settings.ini \n\nx x\n >\n ⁔\n")
	exit()
	

'''
# Pre-run check
# comment out if running this from ep_ucef_autosim.py
print("\nPRE-FLIGHT CHECK: Did you...\n1. Paste all simulations in to the folder\n2. Change config_base.txt to match heat vs cool setting depending on season\n3. Change ipconfig_template.txt to use the IP you get from running ifconfig in the terminal on the UCEF VM.\n4. Change\n\ta. aweatherfilename\n\tb. n_sims\n\tc. n_modes\n\td. MODELIST\n\te. sourcefile name format\n")

if 'y' not in input("[Y or N?]: ").lower():
	print("ERROR: Complete the above tasks and re-run.")
	exit()
'''

print('\nCreating simulation files...\n')

# Opening files
config_template = "config_base.txt"
ctemplatefile = open(config_template, 'r')
config_contents = ctemplatefile.read()

ip_template = "ipconfig_template.txt"
iptempfile = open(ip_template, 'r')
ip_contents = iptempfile.read()

run_template = "run_TEMPLATE.py"
runtempfile = open(run_template, 'r')
run_contents = runtempfile.read()

# Create or replace list_simulations.txt - this will be needed for UCEF
simulation_list_file = 'list_simulations.txt'
simlist = open(simulation_list_file, "a") #a = "append" mode
simlist.truncate(0) #clears out any existing contents


# Opens and reads contents of each file.
try: 
	ffile = open(findkeyfile, 'r')
	findkeycontents = ffile.read()
	findkeys = findkeycontents.split(delimiter)

	rfile = open(replacekeyfile, 'r')
	replacecontents = rfile.read()
	replacements = replacecontents.split(delimiter)
except (OSError, IOError) as ee:
	findkeys = ['']
	replacements = ['']
	print("Warning: No find and/or replace contents of .IDF file found")

try:
	afile = open(appendfile, 'r')
	appendme = afile.read()
except (OSError, IOError) as ee:
	appendme = ''
	print("Warning: No append to .IDF file found")

# Make directories for files to copy to UCEF and the launch Python codes if they don't already exist
if not os.path.exists("copy2UCEF"):
	os.makedirs("copy2UCEF")

if not os.path.exists("launchcodes"):
	os.makedirs("launchcodes")


print('Processing simfiles...')

#reset
pn_max = pn
num_sims = pn_max - pn1
pn = pn1

# Loop for all simulations ======================================================
d = 0
while d < len(targetfiles):
	sourcefile = sourcefiles[d]
	targetfile = targetfiles[d]
	
	# file names that depend on pn = port number = simulation folder name
	config_file = "copy2UCEF" + folderDelim + "config_" + str(pn) + ".txt"
	ip_filename = "ipconfig.txt" #str(pn) + "/ipconfig.txt"
	run_filename = "launchcodes" + folderDelim + "run_" + str(pn) + ".py"
	
	# Create folder in the run directory with the 4 digit port number as its name
	if not os.path.exists(str(pn)):
		os.makedirs(str(pn))
	
	#print(sourcefile)
	#print(config_file)
	
	sfile = open(sourcefile, 'r')
	datatomodify = sfile.read()
	
	configmode = modes[d] #overwritten for fixed, otherwise it just contains the current mode
	
	#Automatically send fixed setpoints from EP to UCEF.
	# code to detect if the current mode is fixed, then read the setpoints specified in 
	# the .idf file and put them into the config file for the controller in UCEF
	if 'fixed'in modes[d]:
		#Find section in .idf file for cooling, and get the indices bounding the number
		istartc = datatomodify.find('cooling_sch,      !- Name\n\tTemperature,         !- Schedule Type Limits Name\n\tThrough: 12/31,          !- Field 1\n\tFor: AllDays,            !- Field 2\n\tUntil: 24:00,            !- Field 3\n\t') + 189
		#print('istartc init = ',istartc)
		#istartc = datatomodify.find('!- Field 3',istartc,istartc+200) + 1
		#print(datatomodify[istartc:istartc+50])
		iendc = datatomodify.find(';',istartc,istartc+50)
		if istartc < 1 or iendc < 1:
			istartc = datatomodify.find('cooling_sch,             !- Name') + 210
			iendc = datatomodify.find(';',istartc,istartc+50)
			print('istartc init = ',istartc)
			if istartc < 1 or iendc < 1:
				print("Error: ")
				print('istartc = ',istartc)
				print('iendc = ',iendc)
				exit()
		#print('Extract cool setpt from: ', datatomodify[istartc:iendc])
		fixedcooltemp = float(datatomodify[istartc:iendc])
		print("Initial fixed cooling temp = ", fixedcooltemp)
		
		istarth = datatomodify.find('heating_sch,      !- Name\n\tTemperature,         !- Schedule Type Limits Name\n\tThrough: 12/31,          !- Field 1\n\tFor: AllDays,            !- Field 2\n\tUntil: 24:00,            !- Field 3\n\t') + 189
		iendh = datatomodify.find(';',istarth,istarth+50)
		#sanity check
		if istarth < 1 or iendh < 1:
			istarth = datatomodify.find('heating_sch,             !- Name') + 210
			iendh = datatomodify.find(';',istarth,istarth+50)
			print('istarth init = ',istarth)
			if istarth < 1 or iendh < 1:
				print("Error: ")
				print('istarth = ',istarth)
				print('iendh = ',iendh)
				exit()
		#print('Extract heat setpt from: ', datatomodify[istarth:iendh])
		fixedheattemp = float(datatomodify[istarth:iendh])
		print("Initial fixed heating temp = ", fixedheattemp)
		
		dtemp = fixedcooltemp - fixedheattemp
		if (dtemp) < 2:
			fixedcooltemp = fixedcooltemp + (2-dtemp)/2
			fixedheattemp = fixedheattemp - (2-dtemp)/2
			print("Final fixed temp: cool = ", fixedcooltemp, "   heat = ", fixedheattemp)
		
		configmode = modes[d] + ',' + str(fixedheattemp) + ',' + str(fixedcooltemp)
		print("configmode = ", configmode)
	# End fixed setpoints
	
	# Create target file that contains the new .idf
	tfile = open(targetfile, "a")
	tfile.truncate(0) #delete existing contents
	
	# Set mode and create config file
	cfile = open(config_file, "a")
	cfile.truncate(0) #delete existing contents
	# change mode and heat or cool settings
	configtowrite = config_contents.replace("SWAPMODE",configmode)
	configtowrite = configtowrite.replace("SETHEATORCOOL",heatorcool)
	cfile.write(configtowrite)
	cfile.close() #save
	
	# Set port number in the ipconfig.txt file for this simulation
	ipfile = open(ip_filename, "a")
	ipfile.truncate(0) #delete existing contents
	iptowrite = ip_contents.replace("PPPP",str(pn))
	ipfile.write(iptowrite)
	ipfile.close()
	
	# "Launch code" from which simulation will be launched in Python -> Command line
	# run_PPPP.py - change port number = PPPP, filenames for .idf and .epw
	# uses a "template" launch code file called run_TEMPLATE.py and changes a few things.
	runfile = open(run_filename, "a")
	runfile.truncate(0) #delete existing contents
	# Replace variables (keystrings) from the template with their actual values for this simulation
	runtowrite = run_contents.replace("PPPP",str(pn))
	#runtowrite = runtowrite.replace("SIMULATION_FILENAME",targetfile.replace('/','\\'))
	#don't replace to avoid errors
	runtowrite = runtowrite.replace("SIMULATION_FILENAME",targetfile)
	runtowrite = runtowrite.replace("WEATHER_FILENAME",weatherfiles[d])
	runtowrite = runtowrite.replace("ENERGYPLUS_DIRECTORY",ep_dir)
	runfile.write(runtowrite)
	runfile.close()
	
	#Autocreate fmu file with the correct ipconfig.txt for each simulation
	# FMU is a .zip file but renamed with file extension .fmu
	# Automatically place it in the folder for the corresponding simulation
	with ZipFile(str(pn) + "/Joe_ep_fmu.fmu", 'w') as zip_object:
		zip_object.write(ip_filename) #add ipconfig.txt to the zip
		zip_object.write("modelDescription.xml") # add modelDescription.xml to the zip
		zip_object.write("binaries/win32/Joe_ep_fmu.dll") # adds the binaries folder to the zip
	
	#Modifying the .idf file to be UCEF compatible
	# Index for .idf file find and replace
	i = 0
	# Loop to do find and replace for each block of text
	# for each key to find, find it and replace it.
	for key in findkeys:
		datatomodify = datatomodify.replace(key,replacements[i])
		i = i+1
	
	# Add any code to be appended (added to the end) of the .idf
	datatomodify = datatomodify + appendme
	
	# Write modified .idf file contents to the new .idf file
	tfile.write(datatomodify)
	tfile.close() #saves file
	
	#Add simulation name = port number to a new line on the list of simulations file
	simlist.write(str(pn) + '\n')
	
	print('Created: ', targetfile)
	
	#increment indices
	d = d + 1
	pn = pn + 1

# End loop for all simulations ======================================================

simlist.close() #saves file

#Creates setNumSims.txt with the number of simulations we just created.
setnumsimsfile = open("copy2UCEF" + folderDelim + "setNumSims.txt", "a")
setnumsimsfile.truncate(0)
setnumsimsfile.write(str(num_sims))
print('Created data for ' + str(num_sims) + ' simulations')

print('\nAll files created successfully!')

#Print user instructions to the command line
#print('\nINSTRUCTIONS:\n1. In UCEF VM:\n\ta. Copy contents of copy2UCEF folder (config_####.txt and setNumSims.txt) to EP_Control_deployment\n\tb. Check config.txt\n\tc. in EP_Control_deployment folder, run: bash run-default.sh ../EP_Control_generated\n2. In Windows for EP, this folder\n\ta. open Command Prompt & navigate to this folder (open in File Explorer then type \"cmd\" into the file path and hit enter).\n\tb. run: Py epautorun.py')
