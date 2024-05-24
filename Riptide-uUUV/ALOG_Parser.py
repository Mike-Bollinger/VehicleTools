import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Read the in file from the path
file = r"D:\AUV\MIR\MIR-23-01_20230427_DIVE010_NOAA1\MOOSLog_27_4_2023_____16_54_48\MOOSLog_27_4_2023_____16_54_48.alog"
outfolder = r"D:\AUV\MIR\MIR-23-01_20230427_DIVE010_NOAA1"
# Create pandas dataframe
data = pd.read_csv(file,
                   delim_whitespace=True,
                   skiprows=(0, 1, 2, 3, 4),
                   on_bad_lines='warn',
                   header=None,
                   usecols=[0, 1, 3])

# Column names
data.columns = ['Time', 'Variable', 'Data']

# cleanup data and remove non-time values from Time Column
data['Time'] = pd.to_numeric(data['Time'], errors='coerce')
data = data.dropna(subset=['Time'])

# All unique variable names
variables = data['Variable'].unique()
print(f"Number of Unique Variables: {len(variables)}")

# Example: All of NAV_X, NAV_Y, NAV_DEPTH rows
#Nav
nav_x = data[data['Variable'] == 'NAV_X']
nav_y = data[data['Variable'] == 'NAV_Y']
nav_z = data[data['Variable'] == 'NAV_DEPTH']
lat = data[data['Variable'] == 'NAV_LAT']
long = data[data['Variable'] == 'NAV_LONG']


#GPS Data
year = data[data['Variable'] == 'GPS_YEAR']
month = data[data['Variable'] == 'GPS_MONTH']
day = data[data['Variable'] == 'GPS_DAY']
hour = data[data['Variable'] == 'GPS_HOUR']
minute = data[data['Variable'] == 'GPS_MINUTE']
second = data[data['Variable'] == 'GPS_SECOND']
gps_fix = data[data['Variable'] == 'GPS_FIX']
#print(year)

year.set_index('Time',inplace=True)
month.set_index('Time',inplace=True)
day.set_index('Time',inplace=True)
hour.set_index('Time',inplace=True)
minute.set_index('Time',inplace=True)
second.set_index('Time',inplace=True)
lat.set_index('Time',inplace=True)
long.set_index('Time',inplace=True)
gps_fix.set_index('Time',inplace=True)

#Make a csv export db
db = pd.concat([year,month,day,hour,minute,second,lat,long,gps_fix],axis=1,sort=True).reset_index()
# db = pd.concat([year.reset_index(drop=True),
#                 month.reset_index(drop=True),
#                 day.reset_index(drop=True),
#                 hour.reset_index(drop=True),
#                 minute.reset_index(drop=True),
#                 second.reset_index(drop=True),
#                 #lat,long,
#                 gps_fix.reset_index(drop=True)],axis=1,sort=True).reset_index()


# db.rename(columns = {db.columns[0]:'Time', db.columns[1]:'Var1',
#                           db.columns[2]:'Year', db.columns[3]:'Var2',
#                           db.columns[4]:'Month', db.columns[5]:'Var3',
#                           db.columns[6]:'Day', db.columns[7]:'Var4',
#                           db.columns[8]:'Hour', db.columns[9]:'Var5',
#                           db.columns[10]:'Minute',db.columns[11]:'Var6',
#                           db.columns[12]:'Second'})
db.columns.values[0]= 'Time'
db.columns.values[1]= 'Var1'
db.columns.values[2]='Year'
db.columns.values[3]='Var2'
db.columns.values[4]='Month'
db.columns.values[5]='Var3'
db.columns.values[6]='Day'
db.columns.values[7]='Var4'
db.columns.values[8]='Hour'
db.columns.values[9]='Var5'
db.columns.values[10]='Minute'
db.columns.values[11]='Var6'
db.columns.values[12]='Second'
db.columns.values[13]='Var7'
db.columns.values[14]='Latitude'
db.columns.values[15]='Var8'
db.columns.values[16]='Longitude'
db.columns.values[17]='Var9'
db.columns.values[18]='GPS_Fix'

db = db.drop(columns = ['Var1','Var2','Var3','Var4','Var5','Var6','Var7','Var8','Var9'
                        ], axis=1)
print(db.columns)

#fill gaps with the previous cell from the top
db = db.fillna(method='ffill')

print(db)
db.to_csv(outfolder + r'\MOOS_Nav.csv')

# #Jordan's Plotting code######
# # Get just the X and Y of these rows, every N
# every_N = 50
# x = nav_x['Data'].values[::every_N].astype(float)
# y = nav_y['Data'].values[::every_N].astype(float)
# z = nav_z['Data'].values[::every_N].astype(float)
#
# # Stretch the values of z to match the length of x and y
# z_stretched = np.repeat(z, len(x) // len(z) + 1)[:len(x)]
# min_bar = np.min(z_stretched)
# max_bar = np.max(z_stretched)
#
# # Create scatter plot
# plt.figure()
# plt.title("Movements in XY direction; Z interpolated")
# plt.scatter(x, y, c=z_stretched, cmap='jet', vmin=min_bar, vmax=max_bar)
# plt.colorbar()
# # Blue is beginning, Red is end
# plt.scatter(x[0], y[0], c='blue', s=10, marker="*")
# plt.scatter(x[-1], y[-1], c='red', s=10, marker="*")
# print(nav_x)
# print(nav_y)
#
# #Try to make a plot with other vars
# nav_x = data[data['Variable'] == 'TIME']
# nav_y = data[data['Variable'] == 'IMU_ROLL']
# nav_z = data[data['Variable'] == 'NAV_DEPTH']
# y2 = data[data['Variable'] == 'IMU_PITCH']
#
# # Get just the X and Y of these rows, every N
# every_N = 50
# x = nav_x['Data'].values[::every_N].astype(float)
# y = nav_y['Data'].values[::every_N].astype(float)
# z = nav_z['Data'].values[::every_N].astype(float)
# y2 = y2['Data'].values[::every_N].astype(float)
#
# fig, axs = plt.subplots(2)
# fig.suptitle('Attitude Data')
# axs[0].plot(x,y)
# axs[1].plot(x,y2)
# plt.show()