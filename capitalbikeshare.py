#For use with Capital Bikeshare trip history data.
#Available at http://www.capitalbikeshare.com/trip-history-data.
#The relevent file is imported into Python as a pandas DataFrame using the read_csv method.
#This module assumes a DataFrame with the following column names: Duration, Start date, End Date, Start station, End station, Start terminal, End terminal, Bike#, Subscription type.  The rename_columns() method corrects for some variations, such as different capitalization.
#Many methods in this module depend on station terminal numbers, which have only been included in the data since the start of 2012.

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import re as re
import datetime as dt
import copy as cp
import random

def rename_columns(df):
#Input DataFrame.
#Searches for and replaces column names that are inconsistent with the expected column names.
	columns = list(df.columns)
	for c in range(len(columns)):
		columns[c] = re.sub('[Dd]uration','Duration',columns[c])
		columns[c] = re.sub('[Ss]tart [Dd]ate','Start date',columns[c])
		columns[c] = re.sub('[Ee]nd [Dd]ate','End date',columns[c])
		columns[c] = re.sub('[Ss]tart [Ss]tation','Start station',columns[c])
		columns[c] = re.sub('[Ee]nd [Ss]tation','End station',columns[c])
		columns[c] = re.sub('[Ss]tart [Tt]erminal','Start terminal',columns[c])
		columns[c] = re.sub('[Ee]nd [Tt]erminal','End terminal',columns[c])
		columns[c] = re.sub('[Bb]ike.*','Bike#',columns[c])
		columns[c] = re.sub('.*[Tt]ype.*','Subscription type',columns[c])
	df.columns = columns
	return df

def duration_timedelta(d):
#Input 'Duration' column in default format ('[0-9]*h [0-9]*m [0-9]*s').
#Returns each duration as Python datetime.timedelta. 
	durations = d.apply(lambda x: re.split('[^0-9]*',x))
	return durations.apply(lambda x: dt.timedelta(hours=int(x[0]),minutes=int(x[1]),seconds=int(x[2])))

def format_date(t):
#Input 'Start date' or 'End date' column in default format ('[0-9*]/[0-9*]/[0-9*] [0-9]*:[0-9*]').
#Returns each date/time as Python datetime object.
        t = t.apply(lambda x: re.split('[/: ]',x))
        datetimes = t.apply(lambda x: dt.datetime(month=int(x[0]),day=int(x[1]),year=int(x[2]),hour=int(x[3]),minute=int(x[4])))
        return datetimes

def format_columns(df):
#Input DataFrame.
#Returns DataFrame with appropriate columns reformatted as datetimes.
	df = rename_columns(df)
	#Uncomment the line below to format the Duration column as Python datetime.timedelta.
	#df['Duration'] = duration_timedelta(df['Duration'])
	df['Start date'] = format_date(df['Start date'])
	df['End date'] = format_date(df['End date'])
	return df

def stations_dict(df_raw):
#Input DataFrame.
#Returns a dict with the terminal numbers as keys and the stations names as values.
	df = cp.deepcopy(df_raw)
	df = rename_columns(df)
	df = df.drop_duplicates(['Start station', 'Start terminal'])
	return dict(zip(df['Start terminal'],df['Start station']))

def terminals_dict(df_raw):
#Input DataFrame.
#Returns a dict with the station names as keys and the terminal numbers as values.
	df = cp.deepcopy(df_raw)
	df = rename_columns(df)
	df = df.drop_duplicates(['Start station', 'Start terminal'])
	return dict(zip(df['Start station'],df['Start terminal']))
		
def net_bikes(df_raw):
#Input DataFrame.
#Returns a DataFrame of the difference between the number of trips started from, and ended at, each station.
	df = cp.deepcopy(df_raw)
	df = rename_columns(df)
	starts = df['Start terminal'].value_counts()
	ends = df['End terminal'].value_counts()
	start_mismatches = pd.Series(starts.index).apply(lambda x: x not in ends.index)
	if sum(start_mismatches) > 0:
		print("The following start terminals were removed because there was no matching end terminal:")
		print(starts.index[start_mismatches])
		starts = starts[[not s for s in start_mismatches]]
	end_mismatches = pd.Series(ends.index).apply(lambda x: x not in starts.index)
	if sum(end_mismatches) > 0:
		print("The following end terminals were removed because there was no matching start terminal:")
		print(ends.index[end_mismatches])
		ends = ends[[not e for e in end_mismatches]]
	starts = starts.sort_index()
	ends = ends.sort_index()	
	netbikes = starts - ends
	stations = stations_dict(df)
	netbikes.index = pd.Series(netbikes.index).apply(lambda x: stations[x])
	return netbikes

def net_tracker(df_raw):
#Input DataFrame.
#Returns a DataFrame that keeps track of the difference between the number of trips started from, and ended at, each terminal over time.
	df = cp.deepcopy(df_raw)
	df = format_columns(df)
	starts = pd.concat([df['Start date'], df['Start terminal'], df['Bike#'], pd.Series([-1]*len(df.index))],axis=1)
	ends = pd.concat([df['End date'], df['End terminal'], df['Bike#'], pd.Series([1]*len(df.index))],axis=1)
	bikes_count = pd.concat([starts, ends])
	bikes_count.columns = ['Date','Terminal','Bike#','Bikes Count']
	bikes_count = bikes_count[bikes_count['Terminal'].apply(lambda x: not np.isnan(x))]
	bikes_count = bikes_count.sort(columns='Date')
	bikes_count.index = range(len(bikes_count.index))
	bikes_count['Bikes Count'] = bikes_count.groupby('Terminal')['Bikes Count'].transform(np.cumsum)
	return bikes_count
        
def estimated_tracker(df_raw):
#Input DataFrame.
#Returns a DataFrame that estimates how many bikes have been added or lost from each terminal over time.
#The data only shows bike movement when riders check out a bike and does not include reapportionment of bikes between terminals, so this method tries to estimate that bike movement.
#This method counts the number of trips started from, and ended at, each terminal over time, but also keeps track of whether a bike that was dropped off at one terminal is later checked out from another terminal.
	df = cp.deepcopy(df_raw)
	df = format_columns(df)
	starts = pd.concat([df['Start date'], df['Start terminal'], df['Bike#'], pd.Series([-1]*len(df.index))],axis=1)
	ends = pd.concat([df['End date'], df['End terminal'], df['Bike#'], pd.Series([1]*len(df.index))],axis=1)
	df2 = pd.concat([starts, ends])
	df2.columns = ['Date','Terminal','Bike#','Gain/Loss']
	df2 = df2[df2['Terminal'].apply(lambda x: not np.isnan(x))]
	df2 = df2.sort(columns='Date')
	df2.index = range(len(df2.index))
	terminals = set(df2['Terminal'])
	counts = {t:0 for t in terminals}
	bikes = {t:set() for t in terminals}
	bikes_dict = {'Date':[], 'Terminal':[], 'Bike#':[], 'Bikes Count':[]}
	def add_row(date, terminal, bike, count):
		bikes_dict['Date'].append(date)
		bikes_dict['Terminal'].append(terminal)
		bikes_dict['Bike#'].append(bike)
		bikes_dict['Bikes Count'].append(count)		
	for i in range(len(df2.index)):
		d = df2['Date'][i]
		t = df2['Terminal'][i]
		b = df2['Bike#'][i]
		if df2['Gain/Loss'][i] == 1:
			if b not in bikes[t]:
				counts[t] += 1
				bikes[t].add(b)
				add_row(d,t,b,counts[t])
			for term in [x for x in terminals if x!=t]:
				if b in bikes[term]:
					counts[term] -= 1
					bikes[term].remove(b)
					add_row(d,term,b,counts[term])
		else:
			if b in bikes[t]:
				counts[t] -= 1
				bikes[t].remove(b)
				add_row(d,t,b,counts[t])
			for term in [x for x in terminals if x!=t]:
				if b in bikes[term]:
					counts[term] -= 1
					bikes[term].remove(b)
					add_row(d,term,b,counts[term])
	bikes_count = pd.DataFrame(bikes_dict)
	return bikes_count

def plot_change(df, terminal, line_color='b', legend_name=''):
#Input a DataFrame in the format returned by net_tracker() or estimated_tracker(), a terminal number to plot, and optional plotting criteria.
#Plots the net change between trips started from that terminal and ended at that terminal over time, and returns that data as a Series.
	terminal_rows = df[df['Terminal']==terminal]
	data_to_plot = pd.Series(list(terminal_rows['Bikes Count']), index=list(terminal_rows['Date']))
	data_to_plot.plot(color=line_color, label=legend_name)
	return data_to_plot

def plot_top_terminals(df, n=5, legend=False, stations={}):
#Input a DataFrame in the format returned by net_tracker() or estimated_tracker.  Optionally, input the number of terminals to plot and other plotting criteria.
#For the n most active terminals, plots the net change between trips_started from that terminal and ended at that terminal over time.
	terminals = list(df['Terminal'].value_counts()[:n].index)
	#To show a legend with station names, set stations to be a dict mapping terminal numbers to station names
	#The dict may be obtained by calling stations_dict() on the original, raw data set.
	if len(stations) > 0:
		labels = [stations[t] for t in terminals]
	else:
		labels = terminals
	colors = list(zip([x/float(n) for x in range(n)], [y%n/float(n) for y in range(n//3,n+n//3)],[z%n/float(n) for z in range(n*2//3,n+n*2//3)]))
	for i in range(n):
		plot_change(df,terminals[i],colors[i],labels[i])
	#Set legend to True to display a legend on the plot.
	if legend:
		plt.legend()

