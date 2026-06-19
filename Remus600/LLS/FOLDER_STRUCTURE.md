# Expected Folder Structure — `quick_look_convert_data_2_geo.py`

All paths are relative to `BASE_DIR` (configured at the top of the script).
Default example: `E:\EN2501_LLS\DIVE033_Stokey`

```
BASE_DIR/                          ← e.g. E:\EN2501_LLS\DIVE033_Stokey
│
├── lls_raw/                       ← INPUT: raw LLS point cloud files
│   ├── scan_001.xyz
│   ├── scan_002.xyz
│   └── ...                        ← any number of *.xyz files
│
├── vehicle_raw/                   ← INPUT: raw PHINS navigation binary
│   └── phinsdata_YYYYMMDD.bin     
│
└── geo/                           ← OUTPUT: georeferenced point clouds (auto-created)
    ├── geo_scan_001.xyz
    ├── geo_scan_002.xyz
    └── ...
```