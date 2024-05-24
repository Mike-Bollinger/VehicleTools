# ---------------------------------
# BAE Systems, Inc. - Riptide
# Vehicle Mission Post Processor
# ---------------------------------

# native imports
import os
import math
import tkinter as tk
import time
from pathlib import Path
from tkinter import filedialog, simpledialog, messagebox
from tkinter import *
from tkinter.ttk import *
# dependency imports
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
from mpl_toolkits.mplot3d import Axes3D
from PIL import ImageTk, Image

BAE_LOGO = Path(__file__).parent / 'images\\BAE.png'
RAS_LOGO = Path(__file__).parent / 'images\\riptide.jpg'
dirName = "None"
filename = "D:\AUV\MIR\MIR-23-01_20230502_DIVE015_NOAA1\MOOSLog_2_5_2023_____17_39_42\MOOSLog_2_5_2023_____17_39_42.alog"
foldername = "None"
varSelectBox = "empty"
data = "empty"
legendList = []
pidLoaded = False
bounds = False

data = pd.read_csv(filename, delim_whitespace=True, skiprows=(0, 1, 2, 3, 4), on_bad_lines='warn', header=None,
                   usecols=[0, 1, 3])
data.columns = ['Time', 'Variable', 'Data']

# cleanup data and remove non-time values from Time Column
data['Time'] = pd.to_numeric(data['Time'], errors='coerce')  # coerce errors to change to NAN
data = data.dropna(subset=['Time'])  # drop NAN values

varList = list(dict.fromkeys(list(data['Variable'])))
varList.sort()

# parses the data file and extracts only the data
# that corresponds to the 'var' parameter
#
# var - type (string), name of the MOOSVariable
#       that will be extracted from the file
def fileToVar(var):
    global data
    filtered = data.loc[data['Variable'] == var]
    dataOut = filtered[['Time','Data']]
    dataOut.columns = ['Time',var]
    dataOut = dataOut.astype(float)
    dataOut['Time'] = dataOut['Time'] - dataOut.iloc[0,0]
    return(dataOut)

desiredSpeed = fileToVar('DESIRED_SPEED')
speed = fileToVar('NAV_SPEED')
GPSs = fileToVar('GPS_SECOND')

print(GPSs)

'''

def update():
    time.sleep(.01)


# set directory that log files are located in for ease of navigation
def setDirClick():
    global dirName
    dirName = filedialog.askdirectory(initialdir=os.getcwd())

    if dirSetBtn['text'] == 'Set Working Directory':
        dirSetBtn['text'] = 'Change Working Directory'


# displays file name once it has been loaded into the program
def dispOpenFile():
    openfilelbl = Label(window, text="File Selected: " + filename)
    openfilelbl.grid(column=0, row=30, columnspan=5)




# select desired ALOG file for post processing
def openALOGClick():
    global filename
    if dirName != 'None':
        filename = filedialog.askopenfilename(initialdir=dirName, title="Select file",
                                              filetypes=(("alog files", "*.alog"), ("all files", "*.*")))
    else:
        filename = filedialog.askopenfilename(initialdir=os.getcwd(), title="Select file",
                                              filetypes=(("alog files", "*.alog"), ("all files", "*.*")))
    if filename != '':
        dispOpenFile()
        alogParseClick()


# reads in the chosen ALOG file, establishes the
# list of MOOSVariables published by the vehicle
def alogParseClick():
    global legendList, varSelectBox, data, missionEnd
    data = pd.read_csv(filename, delim_whitespace=True, skiprows=(0, 1, 2, 3, 4), on_bad_lines='warn', header=None,
                       usecols=[0, 1, 3])
    data.columns = ['Time', 'Variable', 'Data']

    # cleanup data and remove non-time values from Time Column
    data['Time'] = pd.to_numeric(data['Time'], errors='coerce')  # coerce errors to change to NAN
    data = data.dropna(subset=['Time'])  # drop NAN values

    varList = list(dict.fromkeys(list(data['Variable'])))
    varList.sort()
    varList.insert(0, "Select Variable")

    varSelectBox = Combobox(window)
    varSelectBox['values'] = varList
    varSelectBox.current(0)  # set the selected item
    varSelectBox.grid(column=1, row=1, padx=10, pady=5)

    legendList = []

    dispPlotBtn()

dispOpenFile()
'''