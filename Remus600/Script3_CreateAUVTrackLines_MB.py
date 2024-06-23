import arcpy
import pandas as pd #import necessary libraries
import os
arcpy.env.overwriteOutput=1 #Lets you overwrite the shapefile
array = arcpy.Array()#empty array to store points

#### INPUTS ####
dive = "DIVE015" #Specify the dive number here so it can be included as an attribute in the resulting shapefile and also used to name the shapefile
prodDir = r'E:\OR-24-01_VoyisSeaTrial\NavProducts' # where your script2 products are written
coords = dive + "_Veh_Data_Formatted.csv" # double check file output from R


coordDir = os.path.join(prodDir,coords)#This is the csv file created by Script2_CompleteNav.R
print("Coorinate CSV: "+ coordDir)

outFolder = prodDir #os.path.join(prodDir,dive)#path to the folder where the shapefile will be created
print("Output Folder: "+ outFolder)
fc = dive + '.shp' #specify the name of the shapefile
spatRef = arcpy.SpatialReference(4326) #specify the coordinate system; 4326 = WGS84
arcpy.CreateFeatureclass_management(out_path=outFolder, out_name=fc, 
                                   geometry_type='POLYLINE', 
                                   spatial_reference=spatRef)  #create empty shapefile
                                   
shapefile_w_path = outFolder + '\\' + fc

cursor = arcpy.da.InsertCursor(shapefile_w_path,["SHAPE@"])
                                
coordinateList = pd.read_csv(coordDir)  #Read the formatted navigation data
for i in range(len(coordinateList)-1):
            x=float(coordinateList.iloc[i,4]) #Column # reference Longitude
            y=float(coordinateList.iloc[i,3]) #Column # reference Latitude
            point = arcpy.Point(x,y)
            array.add(point)
            x1=float(coordinateList.iloc[i+1,4]) #Column # reference Longitude
            y1=float(coordinateList.iloc[i+1,3]) #Column # reference Latitude
            point1 = arcpy.Point(x1,y1)
            array.add(point1)
            myline = arcpy.Polyline(array,arcpy.SpatialReference(6318))            
            array.removeAll()
            cursor.insertRow([myline])
del cursor
arcpy.management.RepairGeometry(shapefile_w_path, "DELETE_NULL", "ESRI")
print("Shapefile created. Dissolving...")
#shapefile_dissolved
dissolved_shpfile=outFolder + '\\' + 'Dissolved_' + fc
arcpy.management.Dissolve(shapefile_w_path, dissolved_shpfile, "", "", "MULTI_PART", "DISSOLVE_LINES")
arcpy.Delete_management(shapefile_w_path)
arcpy.management.AddField(dissolved_shpfile, "DIVE", "TEXT")
arcpy.management.CalculateField(dissolved_shpfile,"DIVE","'" + dive + "'","PYTHON3", '', "TEXT", "NO_ENFORCE_DOMAINS")
arcpy.management.AddField(dissolved_shpfile, "Length_m", "DOUBLE", 8, "", "", "Length_m",
                          "NULLABLE", "NON_REQUIRED")
arcpy.CalculateGeometryAttributes_management(dissolved_shpfile,[["Length_m","LENGTH_GEODESIC"]],"METERS")
print("Dissolved shapefile created, fuzzball.")