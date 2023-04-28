# epcombineresults.py
# Author(s):    Brian Woo-Shem
# Version:      2.01
# Last Updated: 2023-04-26.
# Project: EnergyPlus + UCEF Superscalable Simulation v8.00
# Info:
# - part of the ucef_ep_autosim system
# - Must be run AFTER epautopostprocess.py
# - Needs Post_Process_Config.ini
# - Customized to combine house data by income levels for the Electricity Fairness by Income Level 2023 research
# - can be adapted to combine houses by other metrics as needed. 

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

'''
occExp corresponds to index = round(prob * 100 - 1)
occExp is array where:
 element 0 = comfort range expansion at probability of occupancy = 0.01
 element 1 = comfort range expansion at probability of occupancy = 0.02
 element 98 = comfort range expansion at probability of occupancy = 0.99
This is used beccause Java lacks a nice norm.ppf type function as in Python
These constant values were taken from a Python script running a loop of all probabilities by 1% 
'''
occExp = [10.141,9.159,8.544,8.086,7.716,7.405,7.133,6.892,6.675,6.476,6.292,6.121,5.961,5.81,5.667,5.532,5.402,5.279,5.16,5.045,4.935,4.829,4.726,4.626,4.529,4.435,4.343,4.253,4.166,4.08,3.997,3.915,3.835,3.757,3.679,3.604,3.529,3.456,3.384,3.313,3.244,3.175,3.107,3.04,2.974,2.909,2.844,2.781,2.718,2.655,2.594,2.533,2.472,2.413,2.353,2.295,2.236,2.179,2.121,2.065,2.008,1.952,1.897,1.841,1.786,1.732,1.678,1.624,1.57,1.517,1.464,1.411,1.359,1.307,1.254,1.203,1.151,1.1,1.048,0.997,0.947,0.896,0.845,0.795,0.745,0.694,0.644,0.594,0.545,0.495,0.445,0.395,0.346,0.296,0.247,0.197,0.148,0.099,0.049]

# Timesteps Per Hour
tshr = 12

# Multiply Joules by this number to get kWh
j_to_kwh = 2.77778e-7

# Folder delimiter
folderDelim = '/'

'''
simulation_list_file = 'list_of_simulations.txt'
simlistfile = open(simulation_list_file, "r")
simlist = simlistfile.readlines()
'''
# Get settings
cp = ConfigParser()
cp.read('autosim_settings.ini')
try:
	sectionName = cp.get('Basic_Info', 'Simulation_Name')
	print("Simulation Name = ", sectionName)
	pn = int(cp.get('Basic_Info', 'Starting_Port_Number'))
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
	CAT_OUT_LIST = cp.get(sectionName, 'Income_Brackets')
	CAT_OUT_LIST = CAT_OUT_LIST.split(',')
	MODELIST = cp.get(sectionName, 'List_of_HVAC_control_modes')
	MODELIST = MODELIST.split(',')
	MODELIST = ['Fixed','Adaptive','Occupancy']
	summaryInFilename = cp.get(sectionName, 'Summary_Filename')
except (NameError, ValueError):
	print("Fatal Error: Could not get config settings. Check autosim_settings.ini \n\nx x\n >\n ⁔\n")
	exit()


sd = pd.read_csv(summaryInFilename)
print(sd.head())

rl = pd.read_csv('Row_Labels.csv')
print(rl.head())

sd = pd.concat([sd,rl], axis=1, join='inner')
print(sd.head())

print(sd.columns.tolist())

priceHeaders.append('Fixed_Cost')
priceHeaders.append('Tiered_Cost')
priceHeaders.append('Total_Electricity')
priceHeaders.append('NaturalGas[kWh]')
priceHeaders.append('NaturalGas[Therm]')
priceHeaders.append('NG_Fixed_Cost')
priceHeaders.append('NG_Tiered_Cost')

print('Price headers:')
print(priceHeaders)

cols = ['Income_Level','Control_Method']
#cols = cols.append(priceHeaders[:])
#cols = cols.append(priceHeaders)
cols = cols + priceHeaders
print('cols')
print(cols)

a = pd.DataFrame(columns = cols)

# sd = summary data, i = income, c = control
for cm in MODELIST:
	sdc = sd[sd['Control_Method'] == cm]
	print(sdc.head())
	
	for il in CAT_OUT_LIST:
		print('il = ',il)
		sdic = sdc['Income_Level']
		sdic = sdc[sdc['Income_Level'] == il]
		
		#a['Income_Level'] = il
		#a['Control_Method'] = cm
		
		#row = pd.Series([il,cm])
		row = [str(il),str(cm)]
		print(row)
		
		for p in priceHeaders:
			me = sdic[p].mean()
			print('mean = ',me)
			#a[p] = sdic[p].mean()
			#row = row.append(str(sdic[p].mean()))
			row = row + [sdic[p].mean()]
		
		rs = pd.Series(row,index=a.columns)
		a = a.append(rs,ignore_index=True)

print(a.head())

a.to_csv(sectionName + '_supersummary.csv')

