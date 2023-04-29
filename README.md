# EnergyPlus + UCEF Superscalable Co-Simulation Autolauncher

Santa Clara University,
School of Engineering,
Department of Mechanical Engineering,
Smart Grid & Residential Energy Simulation Team  

__Author__: [Brian Woo-Shem](www.brianwooshem.com)  
__Version__: 8.00 Stable     
__Updated__: 2023-04-28  

## Purpose & Capabilities

Command-line user interface to automatically:

1. Convert regular EnergyPlus simulations to work with UCEF
2. Launch simulations in parallel
3. Postprocessing for energy consumption and utility bills
4. Cleans out temporary files to save disk space - new!

### List of Features

- Co-simulation allows us to implement more advanced building energy controls into EnergyPlus simulations. 
- Scalability for many building models running in parallel (Greater than 100 EnergyPlus simulations can be run in parallel. Up to 150 were tested.)
    - Enables complex interactions (such as Transactive Energy) between buildings at the timestep level. 
    - Reduces researcher time spent per model: Less than 1 minute of human working time is required to launch each simulation (not counting initial .idf generation or data analysis). It currently takes 10 minutes of human time per batch of simulations, and current batch size is 150 models.
    - The number of buildings can be easily adjusted.
- Implemented in Python
- Launches large numbers of EnergyPlus simulations in parallel
- Detects when EnergyPlus crashes and has error handling capability to prevent a single error from causing all simulations to fail. 
- Before running a batch of simulations, a script parses through the EnergyPlus model files and edits the contents to be compatible with the FMU and UCEF. Bulk IDF editing via find and replace automation replaces time-consuming manual editing in the IDF Editor.
- Post-processing to gather total energy consumption for each house model and compute utility bills for time-variable pricing is automated
- Results can be computed for individual houses or groups of houses in a particular category.


### Background

Prior to this, there was no publicly available software to launch multiple EnergyPlus simulations in parallel. Previously, we used EP Launch and opened one instance per simulation, and manually ran them in order. This was time consuming; > 1 minute per house model, which made it impractical for more than a few houses. 


## Usage

### Prerequisites

#### Base Computer requirements

At least 4 CPU cores, more is better.

8 GB RAM + 0.25 GB per EnergyPlus model you want to run in parallel.

The SCU team uses a workstation computer with 40 CPU cores and 128 GB of RAM. In testing, we have run a handful of simulations (< 10) with a laptop with 8 CPU cores and 16 GB RAM.

\> 64 GB of disk space: > 50 GB for VMs, and > 10 GB for simulations. Running 50 EnergyPlus simulations for 1 year duration used 6.1 GB.

#### Virtualbox

Version 6.0 or above.

Create a [Host-Only Network](https://github.com/SCU-Smart-Grid-CPS/smart-grid-energy-simulation-research/wiki/UCEF---EnergyPlus-Co-Simulation-VirtualBox-Configuration) and a [shared folder](https://oracle-virtualbox.net/faq/15-how-to-use-a-shared-folder-in-virtualbox.html) accessible by both Windows 10 and Linux.

#### Windows computer or VM 

Microsoft Windows: we use Windows 10.

(4 + 0.25 * number_of_energyplus_models) GB of RAM

At least 4 CPU cores available if running more than a few simulations.

EnergyPlus installed, we use v9.4.0

Python 3 or above with the following Python packages installed (most are already included by default)

- configparser
- csv
- ipypublish
- matplotlib
- numpy
- os
- pandas
- scipy
- subprocess
- sys
- time
- zipfile

Download the EP_UCEF_Superscalable_Co-Simulation_Autolauncher package, version 8 or above.

#### UCEF VM

Linux OS, we use Ubuntu 20.04 with Xfce desktop.

2 GB RAM minimum, 4-8 GB recommended

At least 2 CPU cores.

UCEF installed, we use v1.1.0

Download the Supercontroller federation, v0.20 or above.


### Instructions for running a batch of simulations

1. Open Windows 10 and UCEF (Linux) VMs
2. In Windows, make sure all EnergyPlus simulation files (.idf) are in a subdirectory of the shared folder. Open this folder and paste all contents of EP_UCEF_Superscalable_Co-Simulation_Autolauncher.
2. Edit _findkeys.txt_ and _replacekeys.txt_ as needed. Particularly, check the run period and make it match what you intend to run. 
3. Open Command Prompt to the folder with your simulation files by typing `cmd` into the directory list in File Explorer or using the Command Prompt to navigate to that folder.
4. Run `Py ep_ucef_autosim.py`
5. Read the instructions and follow the "wizard". You can choose whether to run or skip each step; generally you run them all. Skipping is useful if you got partway through and you are redoing a step that crashed. View output will show debugging output from the respective step. Debugging outputs are not designed to be easy to interpret except by those who are developing or improving the codes. The general steps it will walk you through are:
    1. Generate port numbers, updated simulation files, and FMU files (ep2ucef_fmu_setup.py)
    2. Launch all EnergyPlus simulations such that they can all connect to UCEF (epautoparallel.py)
    3. Run Postprocessing code to obtain electricity costs (epautopostprocess.py and epcombineresults.py)
    4. Remove leftover files and codes for launching the simulations? Good for reducing disk space of simulations. If unsure, it is safest to skip this step. (Copy2UCEF, Launchcodes, FMU files, and unused EP output files are removed. All results and original files are kept. Note: skip this step if you are experiencing issues or files are disappearing. Runs cleanup_simfiles.py)

There is a video demonstrating these steps here:


## Component Files & Scripts

#### ep_ucef_autosim.py

The main script for launching the co-simulation. Contains a series of print outputs with instructions to the user, user input prompts to choose which components to run, and the ability to launch the other Python scripts. Tracks simulation run time.

#### autosim_settings.ini

The place for predefined and saved settings for different sets of simulations. Used by ep2ucef_fmu_setup, epautoparallel.py, epautopostprocess.py, epcombineresults.py

#### ep2ucef_fmu_setup.py

Code to take regular .idf files for EnergyPlus standalone simulations and do all the necessary preprocessing to make them UCEF-compatible. All outputs are automatically read by subsequent codes.

1. Finds input simulations using 
    a. predefined categories from autosim_settings.ini
    b. the list of simulations from simulation_queue.csv
    c. automatically scans the parent directory and all subfolders and runs all simulations it finds
2. Bulk find and replace to add the FMU connectivity and anything else defined by the user to each .idf
3. Gets fixed setpoints from .idf files to be sent to UCEF
4. Creates necessary config files for UCEF with correct settings for each model.
5. Creates FMU packages using ZipFile
6. Creates a list of all simulations in list_of_simulations.txt
7. Creates the number of simulations in setNumSims.txt
8. Creates the _Copy2UCEF_ folder containing all files that should be copied to UCEF
9. Creates _launchcodes_ folder containing Python codes with names structured as _run\_####.py_ where #### is the port number.
7. Stores each UCEF-ready EP model in a folder whose name is the port number of that simulation.


#### epautoparallel.py

Runs EnergyPlus simulations in parallel. Simulations launch with a delay relative to each other to allow for each to complete initialization and warmup. Assumes simulations follow the file naming convention created by ep2ucef_fmu_setup.py

#### epautopostprocess.py

Automatically gets energy consumption and computes utility bills for each house. Compiles appliance start times and run times across all houses and categories. This code is highly customized for a utility fairness study conducted by this research team in early 2023. Users will need to adapt it for other purposes as needed.

#### epcombineresults.py

Compiles results for each house model into aggregates for each category of simulations.

#### cleanup_simfiles.py

Cleans up simulation launching files created by ep2ucef_fmu_setup after simulation is complete. 

- launchcodes folder
- copy2UCEF folder
- tmp-fmus folder
- fmu files
- EnergyPlus output files we don't use: .eso, .mdd, .shd, .audit, .eio, .rdd, .mtd, .mtr, .end, .bnd

If unsure, it is safest to skip this step. In case of mishap, all files can be restored by rerunning the setup and simulations using ep_ucef_autosim.

#### findkeys.txt

A series of strings that will be found in each .idf for bulk find and replace. Each string is separated by the `@` character. These strings are in the same order as those in _replacekeys.txt_ such that the first string in _findkeys_ will be replaced by the first string in _replacekeys_ and so on. Used to set different run periods, change various other settings, and add the FMU connectivity code. Most of the default included sections can be left alone if you are unsure what they are for.

#### replacekeys.txt

A series of strings that will be replaced in each .idf for bulk find and replace. Each string is separated by the `@` character. These strings are in the same order as those in _replacekeys.txt_ such that the first string in _findkeys_ will be replaced by the first string in _replacekeys_ and so on. Used to set different run periods, change various other settings, and add the FMU connectivity code. Most of the default included sections can be left alone if you are unsure what they are for.

#### run_TEMPLATE.py

A non-runnable Python script that is used as a template by _ep2ucef\_fmu\_setup.py_ to create the _run\_####.py_ in _launchcodes_. Do not modify.

#### config_base.txt

A template config file for UCEF used by _ep2ucef\_fmu\_setup.py_ to create the _config\_####.txt_ files in _copy2UCEF_. Do not modify.

#### binaries

Code used by _ep2ucef\_fmu\_setup.py_ to compile the .fmu files. Do not modify.

#### ipconfig_template.txt

Code used by _ep2ucef\_fmu\_setup.py_ to compile the .fmu files. Do not modify.

#### modelDescription.xml

Code used by _ep2ucef\_fmu\_setup.py_ to compile the .fmu files. Do not modify.

#### TimeOfDay5min.csv

Single column with 1 day worth of 24-hour time in 5 minute intervals. HH:MM:SS format. Used for formatting the output data tables. Do not modify.

#### meterheaders.csv

Just the headers for the meter variables used in _epautopostprocess.py_ for appliance postprocessing. Do not modify unless changing the appliance code.

#### failsafe.idf

A very basic EnergyPlus model that gets launched as a backup if a single EnergyPlus model from the intended set does not run correctly. This allows it to continue running subsequent simulations rather than getting stuck. Do not modify.

#### Various XX\_Pricing\_v#.csv and .xlsx files

These are RTP pricing schedules for locations with codename XX. Used in _epautopostprocess.py_ to compute electricity prices. Use one of these as a template if needed to create pricing schedules for new locations.


### Files generated by ep2ucef_fmu_setup.py

#### launchcodes

A folder containing a bunch of Python codes generated by _ep2ucef\_fmu\_setup.py_. These work in the background and need no user intervention.

#### copy2UCEF

Folder of files that should all be copied to the _EP\_Control\_Deployment_ folder in UCEF. 

#### list_of_simulations.txt

Simple list of all EnergyPlus simulations (models) that will be run by the name of their folders (port numbers in the current implementation). Each entry is separated by a new line. Corresponds to the config_NAME.txt files.  Contents should be pasted into UCEF Supercontroller _config.txt_ under "Building\_Names"
