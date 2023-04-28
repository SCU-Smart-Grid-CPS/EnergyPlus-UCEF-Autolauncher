# epautopostprocess.py
# Author(s):    Brian Woo-Shem
# Version:      6.00
# Last Updated: 2023-04-26
# Project: EnergyPlus + UCEF Superscalable Simulation v8.00
# Info:
# - Combined epautopostprocess3 & ep_appliance_postprocess_ucef codes
# - part of the ucef_ep_autosim system
# - 100% refactoring of eppp.py and epPostProcess.py v4.0
# - pricing component working
# - comfort not yet implemented
# - Needs Post_Process_Config.ini
# - This code is highly customized for the study done for the Income Level Fairness 2023 paper. Users will need to adapt it for other purposes as needed.

import time
import pandas as pd
import numpy as np
import sys
from scipy.stats import norm
from configparser import ConfigParser
from ipypublish import nb_setup
import matplotlib.pyplot as plt
import csv
from scipy.stats import norm

# Suppress annoying warning
pd.set_option('mode.chained_assignment', None)

#Add specified file extension if it is not already present to a string representing the output file name
def addExt(c, ext):
	if c[len(c)-len(ext): len(c)] != ext: c = c + ext
	return c

#Remove specified file extension if it is present from a string representing the output file name
def remExt(c, ext):
	if c[len(c)-len(ext): len(c)] == ext: c = c[:len(c)-len(ext)]
	return c

# Functions for searching a single column of a dataframe for a keystring, and returning the associated index
# Returns index of first instance of key, or -1 if not present
def pdSearchFirstIndex(key, data):
	loc = -1
	for i in range(len(data)):
		if key in data.iloc[[i]].to_string():
			loc = i
			break
	return loc

# Returns index of each instance of key in the form of a list, or empty list if not present
def pdSearchAllIndex(key, data):
	loc = []
	for i in range(len(data)):
		if key in data.iloc[[i]].to_string():
			#if str(data.iloc[[i]]).contains(key, case=False):
			loc.append(i)
	return loc

# Returns index of last instance of key, or -1 if not present
def pdSearchLastIndex(key, data):
	loc = []
	for i in range(len(data)):
		if key in data.iloc[[i]].to_string():
			loc.append(i)
	if len(loc) < 1: return -1
	return loc[len(loc)-1]

# Occupancy setbacks in degrees Celsius
# for computing comfort based on occupancy probability - this feature is not yet implemented
'''
occExp corresponds to index = round(prob * 100 - 1)
occExp is array where:
 element 0 = comfort range expansion at probability of occupancy = 0.01
 element 1 = comfort range expansion at probability of occupancy = 0.02
 element 98 = comfort range expansion at probability of occupancy = 0.99
This is used to avoid using the norm.ppf function
These constant values were taken from a Python script running a loop of all probabilities by 1% 
'''
occExp = [10.141,9.159,8.544,8.086,7.716,7.405,7.133,6.892,6.675,6.476,6.292,6.121,5.961,5.81,5.667,5.532,5.402,5.279,5.16,5.045,4.935,4.829,4.726,4.626,4.529,4.435,4.343,4.253,4.166,4.08,3.997,3.915,3.835,3.757,3.679,3.604,3.529,3.456,3.384,3.313,3.244,3.175,3.107,3.04,2.974,2.909,2.844,2.781,2.718,2.655,2.594,2.533,2.472,2.413,2.353,2.295,2.236,2.179,2.121,2.065,2.008,1.952,1.897,1.841,1.786,1.732,1.678,1.624,1.57,1.517,1.464,1.411,1.359,1.307,1.254,1.203,1.151,1.1,1.048,0.997,0.947,0.896,0.845,0.795,0.745,0.694,0.644,0.594,0.545,0.495,0.445,0.395,0.346,0.296,0.247,0.197,0.148,0.099,0.049]

# Timesteps Per Hour
tshr = 12

# Multiply Joules by this number to get kWh
j_to_kwh = 2.77778e-7

# Folder delimiter
folderDelim = '/'

# Get settings
cp = ConfigParser()
cp.read('autosim_settings.ini')
try:
	sectionName = cp.get('Basic_Info', 'Simulation_Name')
	print("Simulation Name = ", sectionName)
	pn = int(cp.get('Basic_Info', 'Starting_Port_Number'))
	pn1 = pn #temporary workaround for older ucef file system
	#n_sims = int(cp.get(sectionName, 'Number_of_Simulations_Per_Category'))
	firstTimestep = cp.get(sectionName, 'First_Timestep_Keystring_in_EP_CSV')
	print('warmup key = ')
	print(firstTimestep)
	fixedPrice = float(cp.get(sectionName, 'Fixed_Price'))
	tierPricesStr = cp.get(sectionName, 'Tier_Prices')
	tierPrices = [float(j) for j in tierPricesStr.split(',')]
	tierCutoffStr = cp.get(sectionName, 'Tier_Cutoffs')
	tierCutoffs = [float(j) for j in tierCutoffStr.split(',')]
	priceFilename = cp.get(sectionName, 'Electricity_Pricing_Filename')
	priceHeadersStr = cp.get(sectionName, 'Electricity_Pricing_Headers')
	priceHeaders = priceHeadersStr.split(',')
	ngFixedPrice = float(cp.get(sectionName, 'Natural_Gas_Fixed_Price'))
	ngFlatPrice = float(cp.get(sectionName, 'Natural_Gas_Flat_Fee'))
	ngTierPricesStr = cp.get(sectionName, 'Natural_Gas_Tier_Prices')
	ngTierPrices = [float(j) for j in ngTierPricesStr.split(',')]
	ngTierCutoffStr = cp.get(sectionName, 'Natural_Gas_Tier_Cutoffs')
	ngTierCutoffs = [float(j) for j in ngTierCutoffStr.split(',')]
	#Extra outputs for meter and appliances
	mtrHeadersStr = cp.get(sectionName, 'Meter_Headers')
	mtrHeaders = mtrHeadersStr.split(',')
	catList = cp.get(sectionName, 'Output_Category_List')
	catList = catList.split(',')
	applianceList = cp.get(sectionName, 'Appliance_List')
	applianceList = applianceList.split(',')
except (NameError, ValueError):
	print("Fatal Error: Could not get config settings. Check autosim_settings.ini \n\nx x\n >\n ⁔\n")
	exit()

#Number of simulations
try:
	setnumsimsfile = open("copy2UCEF"+folderDelim+"setNumSims.txt", "r")
except (FileNotFoundError):
	setnumsimsfile = open("setNumSims.txt", "r")
n_sims = int(setnumsimsfile.read())
print("Number of Simulations = ", n_sims)

# For summary file
hstr = 'SimNum,Number_of_Data_Rows,Total_Electricity,'
for i in range(len(priceHeaders)):
	hstr = hstr  + priceHeaders[i].replace('/kWh','') + ','

hstr = hstr + 'Fixed_Cost,Tiered_Cost,NaturalGas[kWh],NaturalGas[Therm],NG_Fixed_Cost,NG_Tiered_Cost'
print('Output Headers')
print(hstr)

# Open CSV and write header
summary = open(addExt(sectionName+'_summary','.csv'), "a") #a = "append" mode
summary.truncate(0) #clears out any existing contents
summary.write(hstr + '\n') #Write header

# Moving price data here - we only need to get price data once!
#Add .csv extension if needed
priceFilename = addExt(priceFilename,'.csv')
print('Getting prices from: ',priceFilename)
elecprices = pd.read_csv(priceFilename)
print('Original price data')
print('length = ', len(elecprices))
#print(elecprices.head(5))

#Method for identifying the start of each new day in the meter files
#The code runs much faster if you set to True, but this only works for runperiod = 1 year and timestep = 5min
# otherwise, use False and it will be slower but works for any run period and timestep
# If unsure, it is safest to use False.
dayshortcut = True

t5m = pd.read_csv('TimeOfDay5min.csv')
print(t5m.head())

aggdfs = []
for mtrHead in mtrHeaders:
	aggdfs.append(t5m.copy(deep=True))

aggdfs_s = []
for mtrHead in mtrHeaders:
	aggdfs_s.append(t5m.copy(deep=True))

#Energy consumption dataframe
#econs = t5m.copy(deep=True)
econs = pd.DataFrame()

pstr = []
s = 0
while s < n_sims:
	
	# EP Output for energy consumption and prices ====================================
	epoutfilename = str(pn) + folderDelim + 'eplusout.csv'
	print('Getting Data From: ',epoutfilename)
	#Get data as dataframe
	epout = pd.read_csv(epoutfilename)

	print('original dataset')
	print('length = ', len(epout))
	#print(epout.head(10))

	# find first index with valid data
	# Now will work regardless of if warmup data includes the first timestep of the actual simulation
	# Trick is to find last instance, since it never runs more than 1 year, that timestep won't be repeated again
	datastart = pdSearchLastIndex(firstTimestep, epout['Date/Time'])
	
	print('datastart = ',datastart)
	
	# Stop and raise error if the start of legit data key is not found
	if datastart == -1:
		print('Fatal Error: Could not find warmup time key! \n\nx x\n >\n ⁔\n')
		exit()
	elif datastart > len(epout):
		print('Fatal Error: Warmup time key index exceeds size of data! \n\nx x\n >\n ⁔\n')
		exit()
	
	epout = epout[datastart:]
	
	print('data after removing warmup')
	#print(epout.head(15))
	numrows = len(epout)
	print('numrows = ', numrows)
	
	elecpriceabr = elecprices[:numrows]
	print('Abridged price data')
	print('length = ', len(elecpriceabr))

	# convert units from [J] to [kWh]
	epout['Net_Elec_kWh'] = epout['Whole Building:Facility Net Purchased Electricity Energy [J](TimeStep)'] * j_to_kwh
	
	#One file with electricity consumption, for Fixed simulations only.
	if pn % 3 == 0:
		econs[str(pn)] = epout['Net_Elec_kWh']

	totalprice = []

	for pricetype in priceHeaders:
		hname = 'ElecCostTimestep_' + pricetype
		
		# this works https://stackoverflow.com/questions/65336725/copy-parts-of-a-dataframe-into-another-dataframe
		epout[pricetype] = elecpriceabr[pricetype].values
		
		epout[hname] = epout[pricetype].mul(epout['Net_Elec_kWh'], axis=0)
		
		totalprice.append(epout[hname].sum())
		
		#print(epout.head(15))

	#total consumption
	totelec = epout['Net_Elec_kWh'].sum()
	print('Total Electricity [kWh] = ', totelec)

	#Fixed price
	fixcost = totelec * fixedPrice

	#Tiered pricing
	remelec = totelec
	tierCost = 0
	i = 0
	done = False
	#tiered pricing
	while i < len(tierCutoffs) and not done:
		#If remaining electricity is less than the next cutoff
		if remelec <= tierCutoffs[i]:
			# add remaining electricity * cost at this tier to the total tiered cost
			tierCost = tierCost + remelec * tierPrices[i]
			remelec = 0 #set remaining electricity to zero
			done = True #flag for loop is done
		else: # remelec > next cutoff
			# add max for this tier at the cost at this tier to the total tiered cost
			tierCost = tierCost + tierCutoffs[i] * tierPrices[i]
			# subtract the electricity accounted for at this tier from remaining electricity
			remelec = remelec - tierCutoffs[i]
		i = i+1
	# If anything is left beyond the last cutoff (the highest tier)
	if remelec > 0:
		# Add the remaining electricity at the highest tier price
		tierCost = tierCost + remelec * tierPrices[i]

	# Summarize total price
	# pstr is a temp var
	pstr = str(pn) + ',' + str(numrows) + ',' + str(totelec) + ','
	for i in range(len(priceHeaders)):
		#print(priceHeaders[i], ' = ', totalprice[i])
		pstr = pstr  + str(totalprice[i])+ ','

	pstr = pstr + str(fixcost) + ',' + str(tierCost)

	print(pstr)
	# add to price summary file # - Moved to after the Meter section to also collect Natural Gas data
	#summary.write(pstr + '\n')
	
	#Create plot of temperature over time, using days as index
	epout['Day'] = epout.index / (tshr * 24)
	plt.plot(epout['Day'],epout['LIVING_UNIT1:Zone Thermostat Cooling Setpoint Temperature [C](TimeStep)'],color='blue')
	plt.plot(epout['Day'],epout['LIVING_UNIT1:Zone Thermostat Heating Setpoint Temperature [C](TimeStep)'],color='red')
	plt.plot(epout['Day'],epout['LIVING_UNIT1:Zone Thermostat Air Temperature [C](TimeStep)'],color='purple')
	plt.xlabel('Day of Simulation')
	plt.ylabel('Temperature [°C]')
	plt.grid()
	#plt.show() #savefig won't work if this is enabled
	# Export a .png file
	plt.savefig(addExt(str(pn) + str(folderDelim) + sectionName + "_" + str(pn) + "_plot_indoor_temp", '.png'))

	#Output cleaned results from this simulation to its folder
	outputfilename = addExt(str(pn) + str(folderDelim) + sectionName + "_" + str(pn) + "_autoprocessed", '.csv')
	print('Exporting sim ', pn, ' results as: ', outputfilename)
	outputdata = epout.to_csv(outputfilename, index = False)
	
	
	# Meters =========================================================================================
	epmtrfilename = str(pn) + folderDelim + 'eplusout.csv'
	print('Getting Data From: ',epmtrfilename)
	#Get data as dataframe
	epmtr = pd.read_csv(epmtrfilename)

	#print('original dataset')
	#print('length = ', len(epmtr))
	#print(epmtr.head(10))

	# find first index with valid data
	# Now will work regardless of if warmup data includes the first timestep of the actual simulation
	# Trick is to find last instance, since it never runs more than 1 year, that timestep won't be repeated again
	datastart = pdSearchLastIndex(firstTimestep, epmtr['Date/Time'])
	
	print('datastart = ',datastart)
	
	# Stop and raise error if the start of legit data key is not found
	if datastart == -1:
		print('Fatal Error: Could not find warmup time key! \n\nx x\n >\n ⁔\n')
		exit()
	elif datastart > len(epmtr):
		print('Fatal Error: Warmup time key index exceeds size of data! \n\nx x\n >\n ⁔\n')
		exit()
	
	# remove warmup data
	epmtr = epmtr[datastart:]

	#print('data after removing warmup')
	#print('length = ', len(epmtr))
	#print(epmtr.head(15))

	numrows = len(epmtr)
	print('numrows = ', numrows)
	
	#Split by day
	# This is the correct way to get all the indices for each file, assuming not all files are the same.
	# However, it takes about a minute per simulation for whatever reason
	if not dayshortcut:
		data = epmtr['Date/Time']
		#print(data)
		#print(data.iloc[[576]], '   ', type(data.iloc[[0]]))
		#print(data.iloc[[576]].to_string())
		newdayind = pdSearchAllIndex('00:05:00',epmtr['Date/Time'])
		print('Indices for new days')
		print(newdayind)
		
	else:
		# SHORTCUT if all files have same timestep and runperiod.
		# total run period can be up to one year.
		newdayind = [0, 288, 576, 864, 1152, 1440, 1728, 2016, 2304, 2592, 2880, 3168, 3456, 3744, 4032, 4320, 4608, 4896, 5184, 5472, 5760, 6048, 6336, 6624, 6912, 7200, 7488, 7776, 8064, 8352, 8640, 8928, 9216, 9504, 9792, 10080, 10368, 10656, 10944, 11232, 11520, 11808, 12096, 12384, 12672, 12960, 13248, 13536, 13824, 14112, 14400, 14688, 14976, 15264, 15552, 15840, 16128, 16416, 16704, 16992, 17280, 17568, 17856, 18144, 18432, 18720, 19008, 19296, 19584, 19872, 20160, 20448, 20736, 21024, 21312, 21600, 21888, 22176, 22464, 22752, 23040, 23328, 23616, 23904, 24192, 24480, 24768, 25056, 25344, 25632, 25920, 26208, 26496, 26784, 27072, 27360, 27648, 27936, 28224, 28512, 28800, 29088, 29376, 29664, 29952, 30240, 30528, 30816, 31104, 31392, 31680, 31968, 32256, 32544, 32832, 33120, 33408, 33696, 33984, 34272, 34560, 34848, 35136, 35424, 35712, 36000, 36288, 36576, 36864, 37152, 37440, 37728, 38016, 38304, 38592, 38880, 39168, 39456, 39744, 40032, 40320, 40608, 40896, 41184, 41472, 41760, 42048, 42336, 42624, 42912, 43200, 43488, 43776, 44064, 44352, 44640, 44928, 45216, 45504, 45792, 46080, 46368, 46656, 46944, 47232, 47520, 47808, 48096, 48384, 48672, 48960, 49248, 49536, 49824, 50112, 50400, 50688, 50976, 51264, 51552, 51840, 52128, 52416, 52704, 52992, 53280, 53568, 53856, 54144, 54432, 54720, 55008, 55296, 55584, 55872, 56160, 56448, 56736, 57024, 57312, 57600, 57888, 58176, 58464, 58752, 59040, 59328, 59616, 59904, 60192, 60480, 60768, 61056, 61344, 61632, 61920, 62208, 62496, 62784, 63072, 63360, 63648, 63936, 64224, 64512, 64800, 65088, 65376, 65664, 65952, 66240, 66528, 66816, 67104, 67392, 67680, 67968, 68256, 68544, 68832, 69120, 69408, 69696, 69984, 70272, 70560, 70848, 71136, 71424, 71712, 72000, 72288, 72576, 72864, 73152, 73440, 73728, 74016, 74304, 74592, 74880, 75168, 75456, 75744, 76032, 76320, 76608, 76896, 77184, 77472, 77760, 78048, 78336, 78624, 78912, 79200, 79488, 79776, 80064, 80352, 80640, 80928, 81216, 81504, 81792, 82080, 82368, 82656, 82944, 83232, 83520, 83808, 84096, 84384, 84672, 84960, 85248, 85536, 85824, 86112, 86400, 86688, 86976, 87264, 87552, 87840, 88128, 88416, 88704, 88992, 89280, 89568, 89856, 90144, 90432, 90720, 91008, 91296, 91584, 91872, 92160, 92448, 92736, 93024, 93312, 93600, 93888, 94176, 94464, 94752, 95040, 95328, 95616, 95904, 96192, 96480, 96768, 97056, 97344, 97632, 97920, 98208, 98496, 98784, 99072, 99360, 99648, 99936, 100224, 100512, 100800, 101088, 101376, 101664, 101952, 102240, 102528, 102816, 103104, 103392, 103680, 103968, 104256, 104544, 104832]

	
	#print('Columns: ',epmtr.columns)
	h = 0
	#For each meter column we want
	for mtrhd in mtrHeaders:
		# Each simulation will only have a particular column if it has the corresponding appliance
		# Check if this column exists
		if mtrhd in epmtr.columns:
			#print('Getting: ',mtrhd)
			i = 0
			npcount = np.zeros(24*tshr,dtype=float)
			tempnp = np.array([])
			# For each block of days
			while i < len(newdayind)-1:
				#print('Search range: ',newdayind[i],', ',newdayind[i+1])
				tempdf = pd.DataFrame(epmtr[mtrhd].iloc[newdayind[i]:newdayind[i+1]])
				#epmtr.loc[tempdf > 0,mtrhd+'_tally'] = 1
				#epmtr.loc[tempdf <= 0,mtrhd+'_tally'] = 0
				
				#Dataframes are not behaving
				#convert to numpy because I know how to make it work this way - TODO (low priority): get this to work using Dataframes to be more efficient
				tempnp = epmtr[mtrhd].iloc[newdayind[i]:newdayind[i+1]].values
				'''
				print('tempnp has: ',len(tempnp))
				print('npcount has: ',len(npcount))
				print('i = ',i)
				'''
				j = 0
				# for each timestep
				while j < len(tempnp):
					if tempnp[j] > 0:
						npcount[j] = npcount[j] + 1
					j = j+1
				
				#Get string for category (income level) of each simulated house model
				#Temporary workaround - only works for current income level study where there are 5 categories of 10 houses each
				#*** TODO (mid-priority): Create a unified strategy that works for different number of categories, if different number of sims in each category, etc.
				iname = ''
				if pn < pn1 + n_sims/5:
					iname = catList[0]
				elif pn < pn1 + 2*n_sims/5:
					iname = catList[1]
				elif pn < pn1 + 3*n_sims/5:
					iname = catList[2]
				elif pn < pn1 + 4*n_sims/5:
					iname = catList[3]
				else:
					iname = catList[4]
				
				aggdfs[h][str(pn)] = pd.Series(npcount)
				#print(aggdfs[h].head())
				i = i+1
		else:
			# This simulation does not have this particular appliance
			# print a warning just in case
			print('Warning: ',mtrhd,' not found')
		
		#print('aggdfs dataframe:')
		#print(aggdfs[h].head())
		h = h+1
	
	
	# Table for Natural Gas Consumption ============================================================
	eptblfilename = str(pn) + folderDelim + 'eplustbl.csv'
	print('Getting Table Data From: ',eptblfilename)
	
	with open (eptblfilename) as tf:
		#tblrd = csv.reader(tf)
		tbl_list = list(csv.reader(tf, delimiter=','))
		# In the EP Table, the natural gas consumption data is always on a particular cell, D66.
		# to follow good practices, this code will check the headers on the associated
		# row and column of the table to make sure they match what is expected
		# Print statements are optional, for manual verification
		#print(len(tbl_list))
		# Check header on D50 [3][49]
		#print('D50 = ',tbl_list[49][3])
		#B66
		#print('B66 = ',tbl_list[65][1])
		#Natural Gas consumption is D66
		#print('D66 = ',tbl_list[65][3])
		# Check that headers are correct, and if so, get the natural gas consumption
		if tbl_list[49][3] == 'Natural Gas [kWh]' and tbl_list[65][1] == 'Total End Uses':
			ng = float(tbl_list[65][3])
			# convert from [J] to [BTU]
			ngbtu = ng * 3412.141633
			# Convert from [J] to [Therms]
			ngthm = ng * 0.0340951064
		else:
			print('Warning: No Natural Gas consumption found!')
			# Flag values so it has something to write, but it is obvious that something is wrong with the data
			ng = -99999999999999
			ngbtu = -99999999999999999
			ngthm = -99999999999
	
	#Fixed pricing, natural gas
	ngFixedCost = ngthm * ngFixedPrice + ngFlatPrice
	
	#Tiered pricing for natural gas
	remNG = ngthm
	ngTierCost = ngFlatPrice
	i = 0
	done = False
	while i < len(ngTierCutoffs) and not done:
		#If remaining natural gas is less than the next cutoff
		if remelec <= ngTierCutoffs[i]:
			# add remaining ng * cost at this tier to the total tiered cost
			ngTierCost = ngTierCost + remNG * ngTierPrices[i]
			remNG = 0 #set remaining natural gas to zero
			done = True #flag for loop is done
		else: # remelec > next cutoff
			# add max for this tier at the cost at this tier to the total tiered cost
			ngTierCost = ngTierCost + ngTierCutoffs[i] * ngTierPrices[i]
			# subtract the natural gas accounted for at this tier from remaining
			remNG = remNG - ngTierCutoffs[i]
		i = i+1
	# If anything is left beyond the last cutoff (the highest tier)
	if remNG > 0:
		# Add the remaining ng at the highest tier price
		ngTierCost = ngTierCost + remNG * ngTierPrices[i]
	
	pstr = pstr + ',' + str(ng) + ',' + str(ngthm) + ',' + str(ngFixedCost) + ',' + str(ngTierCost)
	#print(pstr)
	# add row for this simulation to price summary file
	summary.write(pstr + '\n')
	
	# Increment for next
	s = s+1
	pn = pn+1

#Done with all simulations

summary.close() #saves file


# Output aggregate appliance data from meters ============================================

probdfs = []
a = 0
# For all appliance types
for app in applianceList:
	print('Checking : ', app)
	#Create new "sheet" or list item in the probability dataframe
	#probdfs.append(pd.DataFrame())
	probdfs.append(t5m.copy(deep=True))
	
	#Solve problem where some appliances appear in multiple headers
	h = 0
	for mh in mtrHeaders:
		if app in mh:
			print('Found in ',mtrHeaders[h])
			
			tempdf2 = aggdfs[h]
			# For each income level
			for il in catList:
				#Get correct columns from this sheet
				incCols = [c for c in tempdf2.columns if il in c]
				print(incCols)
				# Sum along rows that contain the correct income level
				#Account for if this column is already created, then add to the col
				if il in probdfs[a].columns:
					probdfs[a][il] = probdfs[a][il] + tempdf2[incCols].sum(axis=1)
				else: #otherwise create new col
					probdfs[a][il] = tempdf2[incCols].sum(axis=1)
			
		h = h+1
	a = a+1


#Export total number of times each appliance was running during each time block for each house
toxls = pd.ExcelWriter("ApplianceScheduleTotals_ByHouse.xlsx")
s = 0
#Exports sheets one at a time to the .xlsx file
for sheet in aggdfs:
	# Clean up header strings to remove extra text that doesn't add useful info
	mtrHeaders[s] = mtrHeaders[s].replace(':','')
	mtrHeaders[s] = mtrHeaders[s].replace('(TimeStep)','')
	mtrHeaders[s] = mtrHeaders[s].replace(' ','')
	mtrHeaders[s] = mtrHeaders[s].replace('[J]','')
	mtrHeaders[s] = mtrHeaders[s].replace('InteriorEquipment','')
	print('Sheet: ',mtrHeaders[s])
	# export sheet
	sheet.to_excel(toxls, sheet_name = mtrHeaders[s])
	s = s+1

toxls.save() # save and close
print("Exported as ApplianceScheduleTotals_ByHouse.xlsx")

#Export total number of times each appliance was running during each time block for all houses combined by income level
toxls2 = pd.ExcelWriter("ApplianceAggregateTotals.xlsx")
s = 0
#Exports sheets one at a time to the .xlsx file
for sheet in probdfs:
	print('Sheet: ',applianceList[s])
	sheet.to_excel(toxls2, sheet_name = applianceList[s])
	s = s+1

toxls2.save()
print("Exported as ApplianceAggregateTotals.xlsx")


# Reorganize the appliance data to only log the start time (not the rest of the time it is running)
probdfs_s = []
a = 0
# For all appliance types
for app in applianceList:
	print('Checking : ', app)
	#Create new "sheet" or list item in the probability dataframe
	probdfs_s.append(t5m.copy(deep=True))
	
	#Solve problem where some appliances appear in multiple headers
	h = 0
	for mh in mtrHeaders:
		if app in mh:
			print('Found in ',mtrHeaders[h])
			
			tempdf3 = aggdfs_s[h]
			# For each income level
			for il in catList:
				#Get correct columns from this sheet
				incCols = [c for c in tempdf3.columns if il in c]
				print(incCols)
				# Sum along rows that contain the correct income level
				#Account for if this column is already created, then add to the col
				if il in probdfs_s[a].columns:
					probdfs_s[a][il] = probdfs_s[a][il] + tempdf3[incCols].sum(axis=1)
				else: #otherwise create new col
					probdfs_s[a][il] = tempdf3[incCols].sum(axis=1)
			
		h = h+1
	a = a+1


#Export total number of times each appliance type activates in each house at each tine
toxls3 = pd.ExcelWriter("ApplianceStartTotals_ByHouse.xlsx")
s = 0
for sheet in aggdfs_s:
	sheet.to_excel(toxls3, sheet_name = mtrHeaders[s])
	s = s+1

toxls3.save()
print("Exported ApplianceStartTotals_ByHouse.xlsx")

#Export total number of times each appliance type activates in all houses combined by income level at each tine
toxls4 = pd.ExcelWriter("ApplianceAggregateStart.xlsx")
s = 0
for sheet in probdfs_s:
	print('Sheet: ',applianceList[s])
	sheet.to_excel(toxls4, sheet_name = applianceList[s])
	s = s+1

toxls4.save()
print("Exported ApplianceAggregateStart.xlsx")

# Export Electricity consumption of all houses by time
toxls5 = pd.ExcelWriter("EnergyConsumption.xlsx")
econs.to_excel(toxls5)
toxls5.save()
print("Exported EnergyConsumption.xlsx")

print('Complete! Run latest version of epcombineresults#.py to get aggregate result')
