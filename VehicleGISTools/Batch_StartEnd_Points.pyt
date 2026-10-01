"""
================================================================================
BATCH START-END POINTS - ARCGIS PRO PYTHON TOOLBOX
================================================================================

Author:         Mike Bollinger
Last Updated:   February 11, 2026

FUNCTION:
    Creates a single output point feature class containing the start and end
    positions extracted from each selected point or polyline layer.

USAGE:
    Load this .pyt in ArcGIS Pro's Geoprocessing pane (Toolboxes > Add Toolbox),
    then run the "Create Start and End Points" tool.

INPUTS:
    - Input Point or Polyline Layers (multi-value, required): one or more
      point or polyline feature layers to extract start/end positions from.
    - Point Order Field Name (optional): field used to determine point order
      within point layers (defaults to the OID field if not supplied).
    - Output Start-End Features (required): path/name of the output feature
      class or shapefile.

OUTPUTS:
    A single point feature class (or .shp) with fields SOURCE, POINT_TYPE
    (Start/End), ORDER_BY, and ORDER_VAL, containing two points per valid
    input layer.
================================================================================
"""

import datetime
import os

import arcpy


class Toolbox:
    def __init__(self):
        self.label = "Batch Start-End Points"
        self.alias = "BatchStartEndPoints"
        self.tools = [CreateStartEndPoints]


class CreateStartEndPoints:
    def __init__(self):
        self.label = "Create Start and End Points"
        self.description = (
            "Create one output point shapefile containing the start and end "
            "positions from each selected point or polyline layer."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        input_features = arcpy.Parameter(
            displayName="Input Point or Polyline Layers",
            name="input_features",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
            multiValue=True,
        )
        input_features.filter.list = ["Point", "Polyline"]

        order_field = arcpy.Parameter(
            displayName="Point Order Field Name (optional)",
            name="order_field",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
        )
        order_field.category = "Point Ordering"

        output_features = arcpy.Parameter(
            displayName="Output Start-End Features",
            name="output_features",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output",
        )

        return [input_features, order_field, output_features]

    def isLicensed(self):
        return True

    def updateMessages(self, parameters):
        output_path = parameters[2].valueAsText
        if output_path:
            output_folder, output_name = os.path.split(output_path)
            if output_folder.lower().endswith(".gdb") and output_name.lower().endswith(".shp"):
                parameters[2].setWarningMessage(
                    "The .shp extension will be removed because the output is in a geodatabase."
                )

    def execute(self, parameters, messages):
        inputs = self._parse_multivalue(parameters[0].valueAsText)
        requested_order_field = parameters[1].valueAsText
        output_path = parameters[2].valueAsText

        if not inputs:
            raise arcpy.ExecuteError("Select at least one input layer.")

        output_path, output_folder, output_name = self._normalize_output_path(output_path)
        parameters[2].value = output_path

        first_description = arcpy.Describe(inputs[0])
        output_spatial_reference = first_description.spatialReference

        if arcpy.Exists(output_path):
            if arcpy.env.overwriteOutput:
                arcpy.management.Delete(output_path)
            else:
                raise arcpy.ExecuteError(
                    "Output already exists. Enable Overwrite outputs or choose a new name."
                )

        arcpy.management.CreateFeatureclass(
            output_folder,
            output_name,
            "POINT",
            spatial_reference=output_spatial_reference,
        )
        arcpy.management.AddField(output_path, "SOURCE", "TEXT", field_length=120)
        arcpy.management.AddField(output_path, "POINT_TYPE", "TEXT", field_length=10)
        arcpy.management.AddField(output_path, "ORDER_BY", "TEXT", field_length=40)
        arcpy.management.AddField(output_path, "ORDER_VAL", "TEXT", field_length=80)

        cursor_fields = ["SHAPE@", "SOURCE", "POINT_TYPE", "ORDER_BY", "ORDER_VAL"]
        completed = 0
        with arcpy.da.InsertCursor(output_path, cursor_fields) as insert_cursor:
            for input_layer in inputs:
                try:
                    description = arcpy.Describe(input_layer)
                    source_name = description.name
                    shape_type = description.shapeType

                    if shape_type == "Point":
                        endpoints, order_name = self._point_endpoints(
                            input_layer, requested_order_field
                        )
                    elif shape_type == "Polyline":
                        endpoints = self._polyline_endpoints(input_layer)
                        order_name = description.OIDFieldName
                    else:
                        arcpy.AddWarning(
                            "Skipping {}: geometry type {} is not supported.".format(
                                source_name, shape_type
                            )
                        )
                        continue

                    if not endpoints:
                        arcpy.AddWarning("Skipping {}: it contains no features.".format(source_name))
                        continue

                    input_spatial_reference = description.spatialReference
                    for point_type, geometry, order_value in endpoints:
                        point_geometry = self._as_point_geometry(
                            geometry, input_spatial_reference
                        )
                        point_geometry = self._project_if_needed(
                            point_geometry, output_spatial_reference
                        )
                        insert_cursor.insertRow(
                            [
                                point_geometry,
                                source_name,
                                point_type,
                                order_name,
                                self._format_order_value(order_value),
                            ]
                        )

                    completed += 1
                    arcpy.AddMessage(
                        "{}: wrote Start and End using {}.".format(source_name, order_name)
                    )
                except Exception as error:
                    arcpy.AddWarning("Skipping {}: {}".format(input_layer, error))

        if completed == 0:
            arcpy.management.Delete(output_path)
            raise arcpy.ExecuteError("No start/end points could be created from the inputs.")

        parameters[2].value = output_path
        arcpy.AddMessage(
            "Created {} with {} points from {} input layer(s).".format(
                output_path, completed * 2, completed
            )
        )

    @staticmethod
    def _normalize_output_path(output_path):
        output_folder, output_name = os.path.split(output_path)
        if not output_folder:
            output_folder = arcpy.env.workspace
        if not output_folder:
            raise arcpy.ExecuteError("Choose a folder or geodatabase for the output.")

        is_geodatabase = output_folder.lower().endswith((".gdb", ".sde", ".mdb"))
        base_name, extension = os.path.splitext(output_name)

        if is_geodatabase:
            candidate_name = base_name if extension.lower() == ".shp" else output_name
            output_name = arcpy.ValidateTableName(candidate_name, output_folder)
        else:
            candidate_name = base_name if extension.lower() == ".shp" else output_name
            output_name = arcpy.ValidateTableName(candidate_name, output_folder) + ".shp"

        return os.path.join(output_folder, output_name), output_folder, output_name

    @staticmethod
    def _parse_multivalue(value):
        if not value:
            return []
        return [item.strip().strip("'\"") for item in value.split(";") if item.strip()]

    def _point_endpoints(self, input_layer, requested_field):
        description = arcpy.Describe(input_layer)
        order_field = self._choose_order_field(
            input_layer, requested_field, description.OIDFieldName
        )
        oid_field = description.OIDFieldName
        cursor_fields = ["SHAPE@", oid_field]
        if order_field.lower() != oid_field.lower():
            cursor_fields.append(order_field)

        first_record = None
        last_record = None
        with arcpy.da.SearchCursor(input_layer, cursor_fields) as cursor:
            for row in cursor:
                geometry = row[0]
                oid_value = row[1]
                order_value = row[2] if len(row) == 3 else oid_value
                if geometry is None or order_value is None:
                    continue

                key = (order_value, oid_value)
                record = (key, geometry, order_value)
                if first_record is None or key < first_record[0]:
                    first_record = record
                if last_record is None or key > last_record[0]:
                    last_record = record

        if first_record is None:
            return [], order_field
        return [
            ("Start", first_record[1], first_record[2]),
            ("End", last_record[1], last_record[2]),
        ], order_field

    @staticmethod
    def _choose_order_field(input_layer, requested_field, oid_field):
        fields = arcpy.ListFields(input_layer)
        fields_by_name = {field.name.lower(): field for field in fields}

        if requested_field:
            requested = fields_by_name.get(requested_field.lower())
            if requested:
                return requested.name
            arcpy.AddWarning(
                "Field '{}' was not found in {}; checking for a date field instead.".format(
                    requested_field, arcpy.Describe(input_layer).name
                )
            )

        preferred_names = (
            "timestamp",
            "datetime",
            "date_time",
            "gps_time",
            "gpstime",
            "time",
            "date",
        )
        for preferred_name in preferred_names:
            field = fields_by_name.get(preferred_name)
            if field and field.type not in ("Blob", "Geometry", "Raster"):
                return field.name

        for field in fields:
            if field.type in ("Date", "DateOnly", "TimeOnly", "TimestampOffset"):
                return field.name

        return oid_field

    @staticmethod
    def _polyline_endpoints(input_layer):
        description = arcpy.Describe(input_layer)
        oid_field = description.OIDFieldName
        first_record = None
        last_record = None

        with arcpy.da.SearchCursor(input_layer, ["SHAPE@", oid_field]) as cursor:
            for geometry, oid_value in cursor:
                if geometry is None or geometry.isEmpty:
                    continue
                if first_record is None or oid_value < first_record[0]:
                    first_record = (oid_value, geometry.firstPoint)
                if last_record is None or oid_value > last_record[0]:
                    last_record = (oid_value, geometry.lastPoint)

        if first_record is None:
            return []
        return [
            ("Start", first_record[1], first_record[0]),
            ("End", last_record[1], last_record[0]),
        ]

    @staticmethod
    def _as_point_geometry(geometry, spatial_reference):
        if hasattr(geometry, "firstPoint"):
            return arcpy.PointGeometry(geometry.firstPoint, spatial_reference)
        return arcpy.PointGeometry(geometry, spatial_reference)

    @staticmethod
    def _project_if_needed(geometry, output_spatial_reference):
        input_spatial_reference = geometry.spatialReference
        if (
            input_spatial_reference
            and output_spatial_reference
            and input_spatial_reference.factoryCode != output_spatial_reference.factoryCode
        ):
            return geometry.projectAs(output_spatial_reference)
        return geometry

    @staticmethod
    def _format_order_value(value):
        if isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
            return value.isoformat()
        return str(value)