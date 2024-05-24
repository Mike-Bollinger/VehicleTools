#---------------------------------
# BAE Systems, Inc. - Riptide 
# Vehicle Mission Post Processor
#---------------------------------

import os
import math
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.backends.backend_tkagg
import tkinter as tk
from scipy import stats
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from mpl_toolkits.mplot3d import Axes3D
from tkinter import filedialog
from tkinter import *
from tkinter.ttk import *
from PIL import ImageTk, Image

dirName = "None"
filename = "None"
foldername = "None"
varSelectBox = "empty"
data = "empty"
legendList = []
pidLoaded = False
bounds = False

def update():
    time.sleep(.01)

# set directory that log files are located in for ease of navigation
def setDirClick():
    global dirName
    dirName= filedialog.askdirectory(initialdir=os.getcwd())
    
    if dirSetBtn['text'] == 'Set Working Directory':
        dirSetBtn['text'] = 'Change Working Directory'
    
# displays file name once it has been loaded into the program
def dispOpenFile():
    openfilelbl = Label(window,text="File Selected: " + filename)
    openfilelbl.grid(column=0,row=30, columnspan= 5)

# displays buttons that can be used to plot vehicle parameters 
def dispPlotBtn():
    global rateSelectBox
    
    addVarBtn = Button(window, text="Add Variable",command=addVarClick)
    addVarBtn.grid(column=1, row=2, padx=10, pady=5)

    clearGraphBtn = Button(window, text="Clear Graph",command=clearGraphClick)
    clearGraphBtn.grid(column=1, row=3, padx=10, pady=5)

    plotNavBtn = Button(window, text="Plot Nav",command=navPlotClick)
    plotNavBtn.grid(column=4, row=1, padx=10, pady=5)

    scaledDepthBox = Checkbutton(window, text='Scale Depth', var=scaledDepth)
    scaledDepthBox.grid(column=4, row=3, padx=10, pady=5)

    nav3DBtn = Button(window, text="Plot 3D Nav",command=navPlot3DClick)
    nav3DBtn.grid(column=4, row=2, padx=10, pady=5)
    
    plotSpeedBtn = Button(window, text="Plot Speed",command=speedTuningClick)
    plotSpeedBtn.grid(column=2, row=1, padx=10, pady=5)

    plotDepthBtn = Button(window, text="Plot Depth",command=depthTuningClick)
    plotDepthBtn.grid(column=2, row=2, padx=10, pady=5)
    
    plotHeadBtn = Button(window, text="Plot Heading",command=headingTuningClick)
    plotHeadBtn.grid(column=2, row=3, padx=10, pady=5)
    
    plotRollBtn = Button(window, text="Plot Roll",command=rollStabilityClick)
    plotRollBtn.grid(column=3, row=1, padx=10, pady=5)
    
    stabRateBtn = Button(window, text="Plot Stability Rate",command=stabilityRateClick)
    stabRateBtn.grid(column=3, row=2, padx=10, pady=5)
    
    rateSelectBox = Combobox(window)
    rateSelectBox['values']= ['Select Parameter','NAV_ROLL','NAV_PITCH','NAV_HEADING']
    rateSelectBox.current(0) #set the selected item
    rateSelectBox.grid(column=3, row=3, padx=10, pady=5)

# parses the data file and extracts only the data 
# that corresponds to the 'var' parameter
#
# var - type (string), name of the MOOSVariable 
#       that will be extracted from the file    
def fileToVar(var):
    filtered = data.loc[data['Variable'] == var]
    dataOut = filtered[['Time','Data']]
    dataOut.columns = ['Time',var]
    dataOut = dataOut.astype(float)
    dataOut['Time'] = dataOut['Time']-dataOut.iloc[0,0]
    return(dataOut)

# handles converting the plotted figure when 
# switching between viewing ALOG files and PID files
def resetFigure():
    global graph1, graph2, pidLoaded, bounds
    
    if pidLoaded:
        graph1.clear()
        graph1.axis('off')
        graph2.clear()
        graph2.axis('off')
        
        graph1 = fig.add_subplot(111)
        graph1.plot()
        graph1.axis('on')
        
        pidLoaded = False
    else:
        graph1.clear()
        bounds = False

# removes outliers from a dataset that are 3 local 
# standard deviations greater/less than the rolling 
# median of the data.
#
# data - type (DataFrame), output of fileToVar function
# col - type (string), name of the DataFrame column 
#       that outliers will be removed from
def filterOutlier(data,col):    
    data['rolling_med'] = data[col].rolling(window=20).median()
    data['rolling_std'] = data[col].rolling(window=20).std()
    
    data = data.drop(data[(data[col]>data['rolling_med']+3*data['rolling_std'])|(data[col]<data['rolling_med']-3*data['rolling_std'])].index)
    
    del data['rolling_med']
    del data['rolling_std']
    
    return(data)

# select desired ALOG file for post processing
def openALOGClick():
    global filename
    if dirName != 'None':
        filename =  filedialog.askopenfilename(initialdir = dirName,title = "Select file",filetypes = (("alog files","*.alog"),("all files","*.*")))
    else:
        filename =  filedialog.askopenfilename(initialdir = os.getcwd(),title = "Select file",filetypes = (("alog files","*.alog"),("all files","*.*")))
    if filename != '':   
        dispOpenFile()
        alogParseClick()
        
# reads in the chosen ALOG file, establishes the 
# list of MOOSVariables published by the vehicle
def alogParseClick():
    global legendList, varSelectBox, data, missionEnd
    data = pd.read_csv(filename, delim_whitespace=True, skiprows=(0,1,2,3,4), error_bad_lines=False, warn_bad_lines=False, header=None, usecols=[0,1,3])
    data.columns = ['Time', 'Variable', 'Data']
    
    varList = list(dict.fromkeys(list(data['Variable'])))
    varList = [x for x in varList if not any(x1.isdigit() for x1 in x)]
    varList.sort()
    varList.insert(0, "Select Variable")

    varSelectBox = Combobox(window)
    varSelectBox['values']= varList
    varSelectBox.current(0) #set the selected item
    varSelectBox.grid(column=1, row=1, padx=10, pady=5)
    
    legendList = []
    
    dispPlotBtn()

# select desired PID file for post processing
def openPIDClick():
    global filename   
    if dirName != 'None':
        filename =  filedialog.askopenfilename(initialdir = dirName,title = "Select file",filetypes = (("pid files","*.pid"),("all files","*.*")))
    else:
        filename =  filedialog.askopenfilename(initialdir = os.getcwd(),title = "Select file",filetypes = (("pid files","*.pid"),("all files","*.*")))
    if filename != '':        
        dispOpenFile()
        pidParseClick()
        
# reads in the chosen PID file, formats the figure, and plots the PID data
def pidParseClick():
    global graph1, graph2, pidLoaded, filename
    
    if pidLoaded:
        graph1.clear()
        graph2.clear()
    else:
        graph1.clear()
        graph1.axis('off')
        graph1 = fig.add_subplot(211)
        graph1.axis('on')
        graph2 = fig.add_subplot(212, sharex = graph1)
        graph2.axis('on')
    pidLoaded = True
    
    data = pd.read_csv(filename, delim_whitespace=True, skiprows=(0,1,2,3), error_bad_lines=False, warn_bad_lines=False, header=None, usecols=[0,1,2,3,5,7,8,9,10,11])
    data.columns = ['Time','Kp','Kd','Ki','Output','Kp*e','Kd*de/dt','Ki*int(e)','Desired','Actual']
    data['Time'] = data['Time']-data.iloc[0,0]
    data.set_index('Time',drop=True,inplace=True)
       
    data = filterOutlier(data,'Actual')
    data = filterOutlier(data,'Output')
    data = filterOutlier(data,'Kp*e')
    data = filterOutlier(data,'Kd*de/dt')
    data = filterOutlier(data,'Ki*int(e)')
    
    graph1.plot(data.iloc[:,7])
    graph1.plot(data.iloc[:,8])
    graph1.legend(['Desired','Actual'])
    
    graph2.plot(data.iloc[:,4])
    graph2.plot(data.iloc[:,5])
    graph2.plot(data.iloc[:,6])
    graph2.plot(data.iloc[:,3])
    graph2.legend(['Kp*e','Kd*de/dt','Ki*int(e)','Output'])
    
    if filename.find('pitch') != -1:
        loop = 'Pitch'
        ylabel = 'Pitch [rad]'
    elif filename.find('depth') != -1:
        loop = 'Depth'
        ylabel = 'Depth [m]'
    else:
        loop = 'Heading'
        ylabel = 'Heading [deg]'
          
    graph1.set_title('%s Loop: ' %loop + 'Kp = %.2f ' %data.iloc[1,0] + '| Kd = %.2f ' %data.iloc[1,1] + '| Ki = %.2f'%data.iloc[1,2], 
                     fontsize = 16, fontweight = 'bold')
    graph1.set_xlabel('Time [s]')
    graph1.set_ylabel(ylabel)
    graph2.set_xlabel('Time [s]')
    graph2.set_ylabel('Fin Angle Command [rad]')
    fig.canvas.draw_idle()

def ssFlight():
    desiredDepth = fileToVar('DESIRED_DEPTH').iloc[10,1]
    missionStart = fileToVar('NAV_DEPTH')
    missionStart = missionStart.loc[missionStart['NAV_DEPTH']>desiredDepth].iloc[0,0]

    missionEnd = fileToVar('DESIRED_SPEED').iloc[1:]
    missionEnd = missionEnd.loc[missionEnd['DESIRED_SPEED'] == 0].iloc[0,0]
    
    missionTimes = [missionStart, missionEnd]
    return(missionTimes)
    
# plots the selected variable from the drop-down list
def addVarClick():
    global legendList
    variable = varSelectBox.get()
    varData = fileToVar(variable)
    
    if bounds:
        legendList.insert(len(legendList)-2,variable)
    else:
        legendList.append(variable)
    
    graph1.plot(varData.iloc[:,0],varData.iloc[:,1])
    graph1.legend(legendList)
    graph1.set_xlabel('Time [s]')
    fig.canvas.draw_idle()

# clears the figure and associated legend
def clearGraphClick():
    global legendList
    resetFigure()
    legendList = []
    fig.canvas.draw_idle()

# plots the 2D navigation data
def navPlotClick():
    resetFigure()
    navX = fileToVar('NAV_X')
    navX.reset_index(drop=True,inplace=True)
    navY = fileToVar('NAV_Y')
    navY.reset_index(drop=True,inplace=True)
    navData = pd.concat([navX.iloc[:,1],navY.iloc[:,1]], axis=1)
    navData.set_index('NAV_X', drop=True, inplace=True)
    graph1.plot(navData)
    graph1.legend(['Nav Path'])
    fig.canvas.draw_idle()

# plots the 3D navigation data in a seperate window
def navPlot3DClick():
    navX = fileToVar('NAV_X')
    navX.reset_index(drop=True,inplace=True)
    navY = fileToVar('NAV_Y')
    navY.reset_index(drop=True,inplace=True)
    navDepth = fileToVar('NAV_DEPTH')
    navDepth.reset_index(drop=True,inplace=True)

    navData3D = pd.concat([navX.iloc[:,1],navY.iloc[:,1],navDepth.iloc[:,1]], axis=1)
    navData3D = navData3D.fillna(method='ffill')
    navData3D = navData3D.fillna(method='bfill')

    fig3D = plt.figure()
    ax3D = fig3D.gca(projection='3d')
    ax3D.plot(navData3D['NAV_X'], navData3D['NAV_Y'], navData3D['NAV_DEPTH'], label='Vehicle Path')
    ax3D.legend()

    if scaledDepth.get():
        max_range = np.array([navData3D['NAV_X'].max()-navData3D['NAV_X'].min(), navData3D['NAV_Y'].max()-navData3D['NAV_Y'].min(), navData3D['NAV_DEPTH'].max()-navData3D['NAV_DEPTH'].min()]).max() / 2.0

        mid_x = (navData3D['NAV_X'].max()+navData3D['NAV_X'].min()) * 0.5
        mid_y = (navData3D['NAV_Y'].max()+navData3D['NAV_Y'].min()) * 0.5
        mid_z = (navData3D['NAV_DEPTH'].max()+navData3D['NAV_DEPTH'].min()) * 0.5
        ax3D.set_xlim(mid_x - max_range, mid_x + max_range)
        ax3D.set_ylim(mid_y - max_range, mid_y + max_range)
        ax3D.set_zlim(mid_z - max_range, mid_z + max_range)

    ax3D.invert_zaxis()
    plt.show()

# plots desired and vehicle speed overlayed on the same figure  
def speedTuningClick():
    global legendList
    
    resetFigure()
    desiredSpeed = fileToVar('DESIRED_SPEED')
    speed = fileToVar('NAV_SPEED')
    
    graph1.plot(desiredSpeed.iloc[:,0],desiredSpeed.iloc[:,1])
    graph1.plot(speed.iloc[:,0],speed.iloc[:,1])
    graph1.set_xlabel('Time [s]')
    graph1.set_ylabel('Speed [m/s]')
    
    legendList = ['Desired Speed','Vehicle Speed']
    graph1.legend(legendList)
    fig.canvas.draw_idle()

# plots desired and vehicle depth overlayed on the same figure 
def depthTuningClick():
    global legendList
    
    resetFigure()
    desiredDepth = fileToVar('DESIRED_DEPTH')
    depth = fileToVar('NAV_DEPTH')
    
    graph1.plot(desiredDepth.iloc[:,0],desiredDepth.iloc[:,1])
    graph1.plot(depth.iloc[:,0],depth.iloc[:,1])
    graph1.set_xlabel('Time [s]')
    graph1.set_ylabel('Depth [m]')
    
    legendList = ['Desired Depth','Vehicle Depth']
    graph1.legend(legendList)
    fig.canvas.draw_idle()

# plots desired and vehicle heading overlayed on the same figure 
def headingTuningClick():
    global legendList
    
    resetFigure()
    desiredHeading = fileToVar('DESIRED_HEADING')
    heading = fileToVar('NAV_HEADING')
    heading = filterOutlier(heading,'NAV_HEADING')
    
    graph1.plot(desiredHeading.iloc[:,0],desiredHeading.iloc[:,1])
    graph1.plot(heading.iloc[:,0],heading.iloc[:,1])
    graph1.set_xlabel('Time [s]')
    graph1.set_ylabel('Heading [deg]')
    
    legendList = ['Desired Heading','Vehicle Heading']
    graph1.legend(legendList)
    fig.canvas.draw_idle()

# plots desired and vehicle roll overlayed on the same figure     
def rollStabilityClick():
    global legendList, bounds
    
    resetFigure()
    roll = fileToVar('NAV_ROLL')
    roll = filterOutlier(roll,'NAV_ROLL')
    roll['NAV_ROLL'] = roll['NAV_ROLL']*(180/math.pi)
    
    graph1.hlines(y=0, xmin = roll.iloc[0,0], xmax = roll.iloc[-1,0], linestyles='dashed', colors = 'k')
    graph1.hlines(y=10, xmin = roll.iloc[0,0], xmax = roll.iloc[-1,0], colors = 'k')
    graph1.hlines(y=-10, xmin = roll.iloc[0,0], xmax = roll.iloc[-1,0], colors = 'k')
    graph1.plot(roll.iloc[:,0],roll.iloc[:,1])
    graph1.set_xlabel('Time [s]')
    graph1.set_ylabel('Roll [deg]')
    
    bounds = True
    legendList = ['Vehicle Roll','Desired Roll','Requirement Bounds']
    graph1.legend(legendList)
    fig.canvas.draw_idle()

# plots the selected vehicle stability parameter from the drop-down menu 
# and the desired requirement bounds overlayed on the same figure. Data 
# displayed is from the steadystate flight portion of the mission 
def stabilityRateClick():
    global legendList, bounds
    
    resetFigure()
    var = rateSelectBox.get()
    data = fileToVar(var)
    data = filterOutlier(data,var)
    
    tolerance = float(simpledialog.askstring(title="Tolerance Range",
                      prompt="Enter the desired parameter tolerance in deg/s"))
   
    missionTimes = ssFlight()
    
    if var == 'NAV_ROLL':
        data[var] = data[var]*(180/math.pi)
        label = 'Roll'
    elif var == 'NAV_PITCH':
        data[var] = data[var]*(180/math.pi)
        label = 'Pitch'
    else:
        label = 'Yaw'
      
    dataDiff = data[var].diff()
    timeDiff = data['Time'].diff()
    dataRate = dataDiff.divide(timeDiff)
    dataRate = pd.DataFrame(data = {'Time':data['Time'], var: dataRate})
    dataRate = dataRate.loc[dataRate['Time']>missionTimes[0]].loc[dataRate['Time']<missionTimes[1]]

    graph1.hlines(y=tolerance, xmin = dataRate.iloc[0,0], xmax = dataRate.iloc[-1,0], colors = 'k')
    graph1.hlines(y=-tolerance, xmin = dataRate.iloc[0,0], xmax = dataRate.iloc[-1,0], colors = 'k')
    graph1.plot(dataRate.iloc[:,0],dataRate.iloc[:,1])
    graph1.set_xlim([dataRate.iloc[0,0], dataRate.iloc[-1,0]])
    graph1.set_title('Steady State Flight - %s Rate' %label, fontsize=16, fontweight='bold')
    graph1.set_xlabel('Time [s]')
    graph1.set_ylabel('%s Rate [deg/s]' %label)
    
    bounds = True
    legendList = ['Vehicle %s Rate' %label,'Requirement Bounds']
    graph1.legend(legendList)
    fig.canvas.draw_idle()

window = Tk()

scaledDepth = BooleanVar()
scaledDepth.set(False) #set check state
 
window.title("Riptide AS Post Mission Viewer")
window.geometry('1660x975')

welcomelbl = Label(window,text="Welcome to Ripitde Autonomous Solutions Post Mission Data Analyzer. Please download the .alog or .pid file for the desired mission (located at /media/store/data on your vehicle).")
welcomelbl.grid(column=0,row=0, columnspan= 5, padx=30, pady=5)

dirSetBtn = Button(window, text = 'Set Working Directory', command=setDirClick)
dirSetBtn.grid(column=0, row=30)

alogOpenBtn = Button(window, text="Open .ALOG File",command=openALOGClick)
alogOpenBtn.grid(column=0, row=1)

pidOpenBtn = Button(window, text="Open .PID File",command=openPIDClick)
pidOpenBtn.grid(column=0, row=3)

fig = Figure(figsize = [16,7], tight_layout = True)
graph1 = fig.add_subplot(111)
graph1.plot()

canvas = FigureCanvasTkAgg(fig, master=window)
canvas.get_tk_widget().grid(row=6, column=0, rowspan= 12, columnspan=5, padx=30, pady=10)

toolbarFrame = Frame(master=window)
toolbarFrame.grid(row=18,column=0, rowspan= 10, columnspan=5, padx=30, pady=10)
toolbar = NavigationToolbar2Tk(canvas, toolbarFrame)
toolbar.update()

dispOpenFile()

window.mainloop()