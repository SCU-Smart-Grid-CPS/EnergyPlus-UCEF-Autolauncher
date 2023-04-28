# cleanup_simfiles.py
# Author(s):    Brian Woo-Shem
# Version:      1.00
# Last Updated: 2023-04-26
# Project: EnergyPlus + UCEF Superscalable Simulation -> Autolaunch v8.00
# Cleans up simulation launching files created by ep2ucef_fmu_setup after simulation is complete
# All files can be restored by rerunning the setup and simulations using ep_ucef_autosim

import os
from configparser import ConfigParser
import glob
import shutil

# Delete folders used to hold the simulation running codes that aren't needed if simulation is done
folders_to_remove = ['launchcodes','copy2UCEF','tmp-fmus']
for fd in folders_to_remove:
	try:
		shutil.rmtree(fd)
	except OSError:
		print('Warning: ', fd, ' could not be deleted')

# Delete fmu packages and unused EP outputs
# Modify the list below if you want to keep/remove different output file types
filetypes_to_remove = ['**/*.fmu','**/*.eso','**/*.mdd','**/*.shd','**/*.audit','**/*.eio','**/*.rdd','**/*.mtd','**/*.mtr','**/*.end','**/*.bnd']
for ext in filetypes_to_remove:
	files_to_remove = glob.glob(ext, recursive=True)

	for f in files_to_remove:
		try:
			os.remove(f)
		except OSError:
			print('Warning: could not remove file\n\t',f)
