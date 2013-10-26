#For use with Capital Bikeshare trip history data.
#Available at http://www.capitalbikeshare.com/trip-history-data.
#The relevent file is imported into Python as a pandas DataFrame using the read_csv method.

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import re as re
import datetime as dt
import random

def duration_timedelta(d):
#Input 'Duration' column in default format ('[0-9*]h [0-9*]m [0-9*]s').
#Returns each duration as Python datetime.timedelta. 
	durations = d.apply(lambda x: re.split('[a-z]',x))
	return durations.apply(lambda x: dt.timedelta(hours=int(x[0]),minutes=int(x[1]),seconds=int(x[2])))

def duration_in_seconds(d):
#Input 'Duration' column in default format ('[0-9*]h [0-9*]m [0-9*]s').
#Returns each duration in number of seconds as an int. 
	durations = d.apply(lambda x: re.split('[a-z ]*',x))
	return durations.apply(lambda x: int(x[0])*3600 + int(x[1])*60 +int(x[2]))

def split_date_time(t):
#Input 'Start date' or 'End date' column in default format ('[0-9*]/[0-9*]/[0-9*] [0-9]*:[0-9*]').
#Returns each date as Python date and each time as Python time.
	t = t.apply(lambda x: re.split('[/: ]',x))
	dates = t.apply(lambda x: dt.date(month=int(x[0]),day=int(x[1]),year=int(x[2])))
	times = t.apply(lambda x: dt.time(hour=int(x[3]),minute=int(x[4])))
	return dates, times

def format_date(t):
#Input 'Start date' or 'End date' column in default format ('[0-9*]/[0-9*]/[0-9*] [0-9]*:[0-9*]').
#Returns each date/time as Python datetime object.
	t = t.apply(lambda x: re.split('[/: ]',x))
	datetimes = t.apply(lambda x: dt.datetime(month=int(x[0]),day=int(x[1]),year=int(x[2]),hour=int(x[3]),minute=int(x[4])))
	return datetimes

def replace_columns(df):
#Input DataFrame.
#Returns DataFrame with columns replaced by those returned from duration_timedelta() and split_date_time().
	durations = duration_timedelta(df['Duration'])
	start_dates, start_times = split_date_time(df['Start date'])
	start_times.name = 'Start time'
	end_dates, end_times = split_date_time(df['End date'])
	end_times.name = 'End time'
	return pd.concat([durations, start_dates, start_times, df['Start terminal'], end_dates, end_times, df['End terminal'], df['Subscription Type']], axis=1)

def format_columns(df):
#Input DataFrame.
#Returns DataFrame with columns replaced by those returned from duration_timedelta and format_date methods.
	durations = duration_timedelta(df['Duration'])
	start_dates = format_date(df['Start date'])
	end_dates = format_date(df['End date'])
	return pd.concat([durations, start_dates, df['Start terminal'], end_dates, df['End terminal'], df['Subscription Type']], axis=1)

def stations_dict(df, station_col='Start Station', terminal_col='Start terminal'):
#Input DataFrame and, optionally, the column names of the starting stations and terminal numbers.
#Returns a dict with the terminal numbers as keys and the stations names as values.
	df = df.drop_duplicates([station_col, terminal_col])
	return dict(zip(df[terminal_col],df[station_col]))

def terminals_dict(df, station_col='Start Station', terminal_col='Start terminal'):
#Input DataFrame and, optionally, the column names of the starting stations and terminal numbers.
#Returns a dict with the station names as keys and the terminal numbers as values.
	df = df.drop_duplicates([station_col, terminal_col])
	return dict(zip(df[station_col],df[terminal_col]))
		
def net_bikes(df):
#Input DataFrame.
#Returns a DataFrame of the difference between the number of trips started from, and ended at, each station.
	starts = df['Start terminal'].value_counts()
	ends = df['End terminal'].value_counts()
	start_mismatches = pd.Series(starts.index).apply(lambda x: x not in ends.index)
	if sum(start_mismatches) > 0:
		print "The following start terminals were removed because there was no matching end terminal:"
		print starts.index[start_mismatches]
		starts = starts[[not s for s in start_mismatches]]
	end_mismatches = pd.Series(ends.index).apply(lambda x: x not in starts.index)
	if sum(end_mismatches) > 0:
		print "The following end terminals were removed because there was no matching start terminal:"
		print ends.index[end_mismatches]
		ends = ends[[not e for e in end_mismatches]]
	starts = starts.sort_index()
	ends = ends.sort_index()	
	netbikes = starts - ends
	stations = stations_dict(df)
	netbikes.index = pd.Series(netbikes.index).apply(lambda x: stations[x])
	return netbikes

def change_in_bikes(df):
#Input DataFrame.
#Returns a DataFrame that keeps track of how many bikes have been added or lost from each station over time.
	df = format_columns(df)
	starts = pd.concat([df['Start date'], df['Start terminal'], pd.Series([-1]*len(df.index))],axis=1)
	ends = pd.concat([df['End date'], df['End terminal'], pd.Series([1]*len(df.index))],axis=1)
	bike_counts = pd.concat([starts, ends])
	bike_counts.columns = ['Time','Terminal','Bikes']
	bike_counts = bike_counts[bike_counts['Terminal'].apply(lambda x: not np.isnan(x))]
	bike_counts = bike_counts.sort(columns='Time')
	bike_counts.index = range(len(bike_counts.index))
	terminals = {t:0 for t in bike_counts['Terminal']}
	for i in range(len(bike_counts.index)):
		terminals[bike_counts['Terminal'][i]] += bike_counts['Bikes'][i]
		bike_counts['Bikes'][i] = terminals[bike_counts['Terminal'][i]]
	return bike_counts

def plot_change(df, terminal, line_color='b', legend_name=''):
#Input a DataFrame in the format returned by the change_in_bikes(), a terminal number to plot, and optional plotting criteria.
#Plots the net change between trips started from that station and ended at that station over time, and returns that data as a Series.
	terminal_rows = df[df['Terminal']==terminal]
	data_to_plot = pd.Series(list(terminal_rows['Bikes']), index=list(terminal_rows['Time']))
	data_to_plot.plot(color=line_color, label=legend_name)
	return data_to_plot

def plot_top_terminals(df, n, legend=False, stations={}):
#Input a DataFrame in the format returned by the change_in_bikes(), the number of terminals to plot, and optional plotting criteria.
#For the n most active stations, plots the net change between trips_started from that station and ended at that station over time.
	terminals = list(df['Terminal'].value_counts()[:n].index)
	#To show a legend with station names, set stations to be a dict mapping terminal numbers to station names
	#The dict may be obtained by calling stations_dict() on the original, raw data set.
	if len(stations) > 0:
		labels = [stations[t] for t in terminals]
	else:
		labels = terminals
	colors = zip([x/float(n) for x in range(n)], [y%n/float(n) for y in range(n/3,n+n/3)],[z%n/float(n) for z in range(n*2/3,n+n*2/3)])
	for i in range(len(terminals)):
		plot_change(df,terminals[i],colors[i],labels[i])
	#Set legend to True to display a legend on the plot.
	if legend:
		plt.legend()

