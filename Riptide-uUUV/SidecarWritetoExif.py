import exif
from exif import Image
import os
import pandas as pd
from GPSPhoto import gpsphoto

img_path = "E:/2022.12.13_NOAA1_CameraEval/Camera"

#img_path = pq
#proj_dir, jpeg_name = os.path.split(img_path)
base_dir, img_folder = os.path.split(img_path)
#print("proj_dir: " + str(proj_dir))
print("base_dir: " + str(base_dir))
#print("jpeg_name: " + str(jpeg_name))

#proj_name = str(jpeg_name.rsplit('_', 1)[0])
#print("proj_name: " + str(proj_name))

#export_folder = proj_name
#agisoft_files = "Agisoft_Project_Data_Exports"
#export_path = os.path.join(base_dir, agisoft_files, export_folder)
#print("export_path: " + str(export_path))

print("image_path: " + img_path)
#imgs = os.path.join(proj_dir, jpeg_name)
print(os.path.exists(img_path))
##Define photos list
photoslist = [os.path.join(img_path, photo)
          for photo in os.listdir(img_path)
          if photo.endswith('.tif')]

#for p in photoslist:
p = 1
photopath = photoslist[p]
print("photo path: "+ photopath)
path, photo = os.path.split(photopath)
print("Photo: "+ photo)

photoname = str(photo.rsplit('.', 1)[0])
sidecar = photoname + ".csv"
sidecarpath = os.path.join(path,sidecar)
print(sidecarpath)

df = pd.read_csv(sidecarpath, header=None)
print(df)

date = df.iat[0,0]
time = df.iat[0,1]
lat = df.iat[0,2]
long = df.iat[0,3]
depth = df.iat[0,4]
altitude = df.iat[0,5]
pitch = df.iat[0,6]
roll = df.iat[0,7]
heading = df.iat[0,8]
lightmode = df.iat[0,9]
exposure = df.iat[0,10]
gain = df.iat[0,11]/1E6
focallength = df.iat[0,12]
aperture = df.iat[0,13]

print("Latitude: "+str(lat)+" Longitude: "+str(long))
print("Photopath = " + photopath)
outimage = os.path.join(path,photoname+"-NewExif.tif")
print("Out Image = " + outimage)


#Add GPS to Photo
# img = gpsphoto.GPSPhoto(photopath)
# info = gpsphoto.GPSInfo((lat, long), \
#                         alt = int(depth))
# img.modGPSData(info, outimage)


import rasterio

with rasterio.open(photopath, 'r') as src_ds:
    tags = src_ds.tags()
    with rasterio.open(outimage, 'w', **src_ds.meta) as dst_ds:
        tags['TIFFTAG_ARTIST'] = 'Mike Bollinger'
        tags['TIFFTAG_MAKE'] = 'Artic Rays'
        tags['TIFFTAG_MODEL'] = 'Swordfish'
        tags['TIFFTAG_EXIFIFD'] = focallength
        dst_ds.update_tags(**tags)
        dst_ds.write(src_ds.read())






# from PIL import Image
# from PIL.TiffTags import TAGS
# import piexif
# print(TAGS)
#
# im = Image.open(photopath)
# exif_dict = piexif.load(im.info["TAGS"])
# w,h = im.size
# exif_dict["0th"][piexif.ImageIFD.XResolution] = (w,1)
# exif_dict["0th"][piexif.ImageIFD.YResolution] = (y,1)
# exif_bytes = piexif.dump(exif_dict)
# im.save(outimage, "jpeg", exif= exif_bytes)





#
# import exiftool as et
# from exiftool import ExifToolHelper
# exiftoolpath = os.path.join("C:\Users\Mike.Bollinger\Documents\Python\exiftool(-k).exe")
# #exiftool.ExifTool(executable = <"C:\Users\Mike.Bollinger\Documents\Python\exiftool(-k).exe">)
#
# et.ExifTool.executable(exiftoolpath)

# with ExifToolHelper() as et:
#     for d in et.get_metadata(photopath):
#         for k, v in d.items():
#             print(f"Dict: {k} = {v}")

# import io
# from PIL import Image
# import piexif
# Image.MAX_IMAGE_PIXELS = 10000000000
# o = io.BytesIO()
#
# img = Image.open(photopath)
# exif_dict = piexif.load(photopath)
#
# altitudes = exif_dict['Exif'][piexif.ImageIFD.]
# print(altitudes)

# zeroth_ifd = {
#     piexif.ImageIFD.Artist: u"Mike Bollinger",
#     piexif.ImageIFD.Software: u"piexif",
#     piexif.ImageIFD.CameraSerialNumber: u"NOAA1",
#     piexif.ImageIFD.Make: u"Arctic Rays",
#     piexif.ImageIFD.Model: u"Swordfish"
#     }
# exif_ifd = {
#     piexif.ExifIFD.FocalLength: focallength,
#     piexif.ExifIFD.WaterDepth: depth
#     }
# exif_dict = {"0th": zeroth_ifd, "Exif": exif_ifd}
# print(exif_dict)
# exif_bytes = piexif.dump(exif_dict)
# print(piexif.dump(exif_dict))
# # jpgimg1 = Image.new("RGB", (64, 64))
# tifimg1 = Image.new("RGB")
# # jpgimg1.save(outimage, exif=exif_bytes)
# tifimg1.save(outimage, format = "tif", exif = exif_dict)
# # jpgimg2 = Image.open(outimage)
# tifimg2 = Image.open(outimage)
# tifimg2._getexif()









# Using PIL Alone
# from PIL import Image
# from PIL.TiffTags import TAGS
#
# img = Image.open(photopath)
# meta_dict = {TAGS[key] : img.tag[key] for key in img.tag_v2}
#
# print(meta_dict)
# sourceimg = Image.open(photopath)
# targetimg = Image.open(photopath)
# # Get the TIFF tags from the source image
# tiffinfo = sourceimg.tag_v2
#
# # Add or modify any tags you want (using the tag number as key)
# # Tag number 270 is the ImageDescription tag
# tiffinfo[271] = "Arctic Rays"
# tiffinfo[272] = "Swordfish"
# print(img)
# # Save the target image with the correct tags
# targetimg.save(photo, tiffinfo=tiffinfo)
#
# print(targetimg.tag_v2)



# with open(photopath, 'rb') as image_file:
#     img = Image(image_file)
# img.list_all()
# print(img.has_exif)


# my_image.get_all()
#
# my_image.set('gps_latitude_ref', "N")
# my_image.set('gps_latitude', lat)
# my_image.set('gps_longitude_ref', "E")
# my_image.set('gps_longitude', long)

# my_image.gps_latitude
# my_image.gps_latitude_ref

# with open('modified_image2.jpg', 'wb') as new_image_file:
#     new_image_file.write(my_image.get_file())

 ####ED
#I had an image list that was looking into a folder with JPGs
# with open(image_list[0], 'rb') as image_file:
#     my_image = Image(image_file)
# my_image.get_all()
#
# my_image.set('gps_latitude_ref', "N")
# my_image.set('gps_latitude', lat)
# my_image.set('gps_longitude_ref', "E")
# my_image.set('gps_longitude', long)
#
# my_image.gps_latitude
# my_image.gps_latitude_ref
#
# with open('modified_image2.jpg', 'wb') as new_image_file:
#     new_image_file.write(my_image.get_file())