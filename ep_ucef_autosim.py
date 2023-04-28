# ep_ucef_autosim.py
# EnergyPlus + UCEF Auto Co-Simulation Superlauncher Script
# Author(s):    Brian Woo-Shem
# Version:      2.21
# Last Updated: 2023-04-26
# Project: EnergyPlus + UCEF Superscalable Co-Simulation -> Autolaunch v8.00
# Info:
# - This is a terminal UI for running the SCU team co-simulations
# - Run this script from Windows to do everything for a set of simulations in one go.
# - Need to respond to prompts in a few spots.

import subprocess
import time

starttime = int(round(time.time())) #for simulation runtime

print('\n=================== EnergyPlus + UCEF Auto Superscalable Co-Simulation Wizard ===================')
print('Project: SCU Smart Grid & Residential Energy Simulation Team (https://github.com/SCU-Smart-Grid-CPS)\nAuthor: Brian Woo-Shem (www.brianwooshem.com)\nVersion: 2.21')

print('\n===================> 1. Setup code <===================')
print('Generate port numbers, updated simulation files, and FMU files (ep2ucef_fmu_setup.py):')
print('\nINSTRUCTIONS:\n1. Change config_base.txt to match heat vs cool setting depending on season\n2. Change ipconfig_template.txt to use the IP you get from running ifconfig in the terminal on the UCEF VM.\n3. Change RunPeriod in replacekeys.txt (or in autosim_settings.ini)\n4. Check autosim_settings.ini\n5. Ensure the following are in the run folder:\n\ta. All .idf files\n\tb. autosim_settings.ini <=== Check & Update!\n\t\ti. Basic_Info: Simulation_Name\n\t\tii. Pricing data\n\t\tiii. Type_of_EnergyPlus_Simulation_Set and if categorical, Number_of_Simulations_Per_Category\n\tc. Weather file .epw\n\td. Pricing data .csv\n\te. run_TEMPLATE.py\n\tf. findkeys.txt\n\tg. replacekeys.txt')
print('\nWhen the above steps are complete, enter Y to run setup, S to skip this step, or E to exit.')
# Handle multiple response options
response = ''
while True:
	response = input(">> ").lower()
	if 'y' in response:
		#run ep2ucef_fmu_setup.py
		# Use different run method depending on whether user wants to see output of the ep2ucef code or not
		print('View output?')
		if 'y' in input("[Y or N?]: ").lower():
			#This method shows output as it is being run
			ep2ucefproc = subprocess.Popen('ep2ucef_fmu_setup.py', shell=True)
			ep2ucefproc.wait() #must include this otherwise it gets stuck for some reason.
		else:
			print('Running EP -> UCEF FMU & IDF Setup, please wait...')
			ep2ucefproc = subprocess.run('ep2ucef_fmu_setup.py', capture_output=True, shell=True, text=True)
			print('\n***** EP -> UCEF FMU & IDF Setup Complete! *****\n')
		break
	elif 's' in response:
		print('Skipping setup.')
		break
	elif 'e' in response:
		print('Exiting program')
		exit()
	else:
		print('Complete the tasks above, then enter \'Y\' to run, \'S\' to skip, or \'E\' to exit the program.')


print('\n===================> 2. Run the EnergyPlus Simulations <===================')
print('Launch all EnergyPlus simulations such that they can all connect to UCEF (epautoparallel.py)\n')
# Pre-run check - instructions for user to do before starting to launch simulations
print('INSTRUCTIONS:\n1. In UCEF VM:\n\ta. Copy all files in the copy2UCEF folder (config_####.txt and setNumSims.txt) to EP_Control_deployment. Replace existing if needed. \n\tb. Open config.txt. Paste the list_of_simulations.txt contents below building_names\n\tc. in EP_Control_deployment folder, run: bash run-default.sh ../EP_Control_generated\n2. Wait until Supercontroller has launched and says \"Waiting for ___ to join\"\n\nWhen the above steps are complete, enter Y to run EnergyPlus simulations, S to skip this step, or E to exit.')

response = ''
while True:
	response = input(">> ").lower()
	if 'y' in response:
		#run epautorun.py
		print('View output?')
		if 'y' in input("[Y or N?]: ").lower():
			# Use Popen to allow parallel processes
			epautoproc = subprocess.Popen('epautoparallel.py', shell=True)
			epautoproc.wait()
		else:
			print('Running EP Simulations Auto Runner. This typically takes 5 mins per simulated day + 30 seconds per EP model, so take a break and be patient...')
			epautoproc = subprocess.run('epautoparallel.py', capture_output=True, shell=True)
			print('\n***** EP Autorun Complete! *****\n')
			#print(epautoproc.stdout) #only shows output after entire run is completed
		break
	elif 's' in response:
		print('Skipping running the EnergyPlus simulations.')
		break
	elif 'e' in response:
		print('Exiting program')
		exit()
	else:
		print('Complete the tasks above, then enter \'Y\' to run, \'S\' to skip, or \'E\' to exit the program.')


#Run post-processing code
print('\n===================> 3. Post Processing <===================')
print('Run Postprocessing code to obtain electricity costs (epautopostprocess.py and epcombineresults.py)\n\nEnter Y to run, S to skip this step, or E to exit.')

response = ''
while True:
	response = input(">> ").lower()
	if 'y' in response:
		print('View output?')
		if 'y' in input("[Y or N?]: ").lower():
			postprocproc = subprocess.run('epautopostprocess.py', shell=True)
			postpcombine = subprocess.run('epcombineresults.py', shell=True)
		else:
			print('Running postprocess code, please wait...')
			postprocproc = subprocess.run('epautopostprocess.py', capture_output=True, shell=True)
			postpcombine = subprocess.run('epcombineresults.py', capture_output=True, shell=True)
			print('\n***** Simulation Postprocessing Complete! *****\n')
		break
	elif 's' in response:
		print('Skipping postprocessing.')
		break
	elif 'e' in response:
		print('Exiting program')
		exit()
	else:
		print('Unrecognized input. Enter \'Y\' to run, \'S\' to skip, or \'E\' to exit the program.')

# Remove the setup files
print('\n===================> 4. Cleanup <===================')
print('Remove leftover files and codes for launching the simulations? (Copy2UCEF, Launchcodes, FMU files, and unused EP output files are removed. All results and original files are kept. This will run cleanup_simfiles.py)\n\nEnter Y to remove the files, N to keep the files.')
response = ''
while True:
	response = input(">> ").lower()
	if 'y' in response:
		cleanupproc = subprocess.run('cleanup_simfiles.py', shell=True)
		print('\n***** Cleanup complete! *****\n')
		break
	elif 'n' in response or 's' in response:
		print('All files have been kept')
		break
	elif 'e' in response:
		print('Exiting program')
		exit()
	else:
		print('Unrecognized input. Enter \'Y\' to remove the files, \'N\' to keep the files, or \'E\' to exit the program.')


# Simulation runtime
endtime = int(round(time.time()))
duration = endtime - starttime
print("\nComplete AutoSim Runtime = ", duration, " seconds = ", duration/60, " minutes")

print('\n<======= EnergyPlus + UCEF Auto Co-Simulation Complete! =======>\n')
