MainFolder<-"E:\\OR-24-01_VoyisSeaTrial"  #Change path according to your set up
DiveNum <- "DIVE015" #Change Dive ID for each run

#RootFolder<-paste0(MainFolder,"\\VEH_NAV")

NavFile=paste0(MainFolder,"\\",DiveNum ,"\\Vehicle_Data\\", DiveNum ,"_Veh_Data.txt")

AllData<-read.table(NavFile, sep = ",",header = TRUE, stringsAsFactors = FALSE, skip = 1)
  
colnames(AllData)<-c("Time", "Date","LonLat","Altitude","Bathymetry","Depth_vehicle","Heading","Headingrate", "NeilBrownSoundSpeed","Pitch","Pitchrate","Roll","Rollrate","Velocity","x")
  
#AllData<-AllData[,c("Time", "Date","LonLat","Altitude","Depth_vehicle","Heading","Headingrate")]
  
AllData$Time<-trimws(AllData$Time)
  
AllData$Date_mod<-as.Date(AllData$Date,"%m/%d/%Y")
  
AllData$time_mod<-ifelse(nchar(AllData$Time)==11, paste0("0",AllData$Time),AllData$Time)
  
AllData$Tmstamp<-paste(AllData$Date_mod, AllData$time_mod, sep=" ")
  
AllData$Tmstamp2<-as.POSIXct(AllData$Tmstamp, format="%Y-%m-%d %H:%M:%OS", tz="")
  
AllData<-AllData[order(AllData$Tmstamp2),]
  
  #AllData$MissionTime<- as.numeric(AllData$Tmstamp2)
  
  #AllData$MissionTime<-AllData$MissionTime-(4*60*60) #Changes time to s from 1970 For splitting SAS
  
AllData$Latitude<-sapply(strsplit(as.character(AllData$LonLat), " "), "[[", 2)
  
AllData$Longitude<-sapply(strsplit(as.character(AllData$LonLat), " "), "[[", 4)
  
AllData$Latitude_dd<-as.numeric(sapply(strsplit(as.character(AllData$Latitude), "N"), "[[", 1)) + as.numeric(sapply(strsplit(as.character(AllData$Latitude), "N"), "[[", 2))/60
  
AllData$Longitude_dd<-(as.numeric(sapply(strsplit(as.character(AllData$Longitude), "W"), "[[", 1)) + as.numeric(sapply(strsplit(as.character(AllData$Longitude), "W"), "[[", 2))/60)*-1

#AllData<-AllData[,c("MissionTime","Heading","Latitude_dd","Longitude_dd","Depth_vehicle","Headingrate","Altitude")]
AllData<-AllData[,c("Date_mod", "time_mod","Tmstamp2","Latitude_dd", "Longitude_dd",
                    "Altitude","Bathymetry","Depth_vehicle","Heading","Headingrate",
                    "Pitch","Pitchrate","Roll","Rollrate","Velocity")]

  
colnames(AllData)<-c("date","time","timestamp","latitude","longitude",
                     "altitude","bathymetry", "depth","heading","heading_rate",
                     "pitch", "pitchrate","roll", "rollrate", "velocity")
  
AllData$heading_rate<-AllData$heading_rate * -1
  
Destination_Folder <- paste0(MainFolder,"\\NavProducts")
  
if (!file.exists(Destination_Folder)){
  dir.create(Destination_Folder)
  print(paste("Created Directory:",Destination_Folder))
}else{
  print("Directory Exists")}
  
Filename<-paste0(Destination_Folder,"\\",sub('\\.txt$', '', basename(NavFile)),"_Formatted.csv")
  
write.table(AllData,Filename, sep = ",", col.names = TRUE, row.names = FALSE, quote = FALSE)
print(paste("Completed", DiveNum))

