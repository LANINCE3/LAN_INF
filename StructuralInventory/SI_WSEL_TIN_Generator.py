"""
UTF-8

This script is generated to develop dedicated polygon for bounding tributaries

By Alex Govea
Date 11-13-2019
Updated:12-2-2019
"""


import arcpy
import os
import numpy as np
import pandas as pd
import traceback
import time
from datetime import datetime, timedelta

#Utility Funcitons
def getRequiredExtensions():
    # Checks if extenion is available and Checks out the 3D Analyst extension
    if arcpy.CheckExtension ("3D") == "Available":
        arcpy.CheckOutExtension ("3D")
        print('\t|-Checking-Out Extension: {0}'.format ('3D'))
    else:
        print('\t|-Meet Extension Requirement: {0}'.format ('3D'))

    # Checks if extenion is available and Checks out the Spatial Analyst extension
    if arcpy.CheckExtension ("Spatial") == "Available":
        arcpy.CheckOutExtension ("Spatial")
        print('\t|-Checking-Out Extension: {0} Analyst'.format ('Spatial'))
    else:
        print('\t|-Meet Extension Requirement: {0}'.format ('Spatial'))


def attribute_XS(xsFeatureClass, xsWSELExceltabel, txtStationField="STREAM_STN", unitNumber = "E101-00-00", hasTailWater=False, tailwaterWSELs = None):
    """ Add's Fields to Xs Feature-class Converts Text Station field to float and attributes each Xs with WSEL """
    if os.path.exists (xsWSELExceltabel) and arcpy.Exists (xsFeatureClass):
        arcpy.AddField_management (xsFeatureClass , field_name='Station' , field_type='DOUBLE')
        arcpy.AddField_management (xsFeatureClass , field_name='UnitNumber' , field_type='TEXT', field_length=15)
        arcpy.AddField_management(xsFeatureClass, field_name='WSEL10yr', field_type='DOUBLE')
        arcpy.AddField_management (xsFeatureClass , field_name='WSEL50yr' , field_type='DOUBLE')
        arcpy.AddField_management (xsFeatureClass , field_name='WSEL100yr' , field_type='DOUBLE')
        arcpy.AddField_management (xsFeatureClass , field_name='WSEL500yr' , field_type='DOUBLE')
        arcpy.AddField_management(xsFeatureClass, field_name='WSEL10yrA', field_type='DOUBLE')
        arcpy.AddField_management (xsFeatureClass , field_name='WSEL50yrA' , field_type='DOUBLE')
        arcpy.AddField_management (xsFeatureClass , field_name='WSEL100yrA' , field_type='DOUBLE')
        arcpy.AddField_management (xsFeatureClass , field_name='WSEL500yrA' , field_type='DOUBLE')
    # Imports XsWSELEXCEL Table as datafarme
    df = pd.DataFrame.from_csv(xsWSELExceltabel)
    # DF headers "UnitNumber", "Station", "Profile", "WSEL"
    # Storms
    # DEFINING CURSOR VARIABLES< FIELDS AND EXPRESSIONS
    profiles = {10:"10PCT_10yr", 50:"2PCT_50yr", 100:"1PCT_100yr", 500:"0.2PCT_500yr"}
    fields = (txtStationField, "Station", "WSEL10yr", "WSEL50yr", "WSEL100yr", "WSEL500yr", "UnitNumber")
    # Updates eac cross section
    with arcpy.da.UpdateCursor(xsFeatureClass, fields) as uC:
        for row in uC:
            stationfloat = round(float(row[0]),2)
            df_Check = True if df.loc[df["Station"]==stationfloat].shape[0] == 4 else False
            if df_Check:
                wsel10 = df.loc[(df["Station"]==stationfloat) & (df["Profile"]==profiles[10])]["WSEL"].values[0]
                wsel50 = df.loc[(df["Station"]==stationfloat) & (df["Profile"]==profiles[50])]["WSEL"].values[0]
                wsel100 = df.loc[(df["Station"]==stationfloat) & (df["Profile"]==profiles[100])]["WSEL"].values[0]
                wsel500 = df.loc[(df["Station"]==stationfloat) & (df["Profile"]==profiles[500])]["WSEL"].values[0]
                if hasTailWater and tailwaterWSELs is not None:
                    wsel10 = wsel10 if wsel10 > tailwaterWSELs["WSEL10yr"] else tailwaterWSELs["WSEL10yr"]
                    wsel50 = wsel50 if wsel50 > tailwaterWSELs[ "WSEL10yr" ] else tailwaterWSELs[ "WSEL50yr" ]
                    wsel100 = wsel100 if wsel100 > tailwaterWSELs[ "WSEL100yr" ] else tailwaterWSELs[ "WSEL100yr" ]
                    wsel500 = wsel500 if wsel500 > tailwaterWSELs[ "WSEL500yr" ] else tailwaterWSELs[ "WSEL500yr" ]
                uC.updateRow((row[0], stationfloat, wsel10, wsel50, wsel100, wsel500, unitNumber))
            else:
                uC.updateRow ((row[ 0 ], stationfloat , -9999 , -9999, -9999, -9999, unitNumber))

# Method for Identifying WSEL at Each Confluence of a Modeled tributary to it's Receiving Stream's WSEL.
# def getConfluentPoints(watershed_WMP_Subreaches):
#     disolved_reaches = arcpy.Dissolve_management (in_features=subreach_fc ,
#                                                   dissolve_field=unitnumber_field ,
#                                                   multi_part="MULTI_PART")
#     pass


def getSpatialReferencefactoryCode(fc):
    """Identifies the spatial reference of the input feature class"""
    spatial_ref = arcpy.Describe(fc).spatialReference
    return spatial_ref.factoryCode

def get_vertices(arcpyPolyline, reverse = False):
    """Returns points of a polyline feature class as orded list of points
        :param arcpyPolyline:
        :return: list of points
    """
    try:
        points = []
        for part in arcpyPolyline:
            for pnt in part:
                if pnt:
                    points.append(pnt)
        if not reverse:
            return points
        else:
            rev_points = []
            for i, point in enumerate(points):
                rev_points.append(points[len(points) - i - 1])
            return rev_points

    except:
        print('{0}'.format(traceback.format_exc()))

def orderStations(xsFeatureClass, stationField = "", unitNumberField=""):
    unitNumberStations = {}
    unitNumbers = []
    # Acquires all stations on a per Unit Number Basis.
    with arcpy.da.SearchCursor (xsFeatureClass , [ unitNumberField ]) as cursor:
        for row in cursor:
            unitNumbers.append(str(row[0]))
    # Generates a set of unique unit numbers only. Performs an ordered search on a Per Unit numner basis
    unitNumbers = list(sorted(list(set(unitNumbers)),reverse=False))
    fields = (unitNumberField, stationField)
    for unitNumber in unitNumbers:
        # Query expression to reduce search cursor time.
        unitQuery = "\"{0}\" LIKE '{1}'".format(unitNumberField, unitNumber)
        unitNumberStations[unitNumber] = {"Stations":[],'Sorted_Stations':None, 'SortedStationPairs':None}
        with arcpy.da.SearchCursor (xsFeatureClass , fields, unitQuery) as cursor:
            for row in cursor:
                station = float(row[1])
                unitNumberStations[ unitNumber ]['Stations'].append(round(float(station),2))
        # Then sorts all stations in the observed unit number list of stations.
        sorted_stations = list(sorted(unitNumberStations[ unitNumber ]['Stations'], reverse=False))
        unitNumberStations[ unitNumber ][ 'Sorted_Stations' ] = sorted_stations
        len_stations = len(sorted_stations)
        # Generates Station Pairs on a per Unit Number basis.
        pairs = []
        for i, sta in enumerate(sorted_stations):
            if i < len_stations - 1:
                dnStation = sta # Down stream Station
                upStation = sorted_stations[i+1] # Upstream Station
                pair = [dnStation, upStation]
                pairs.append(pair)
        unitNumberStations[ unitNumber ][ 'SortedStationPairs' ] = pairs
    return unitNumberStations

def createExportPolyFc(xsFeatureClass, outFolder, outName,has_z=False):
    #Identifies Spatiral Reference coordinate system of paraent
    sr = getSpatialReferencefactoryCode(xsFeatureClass)
    #identifies if copy of Creation FC already Exists and removes it to start from scratch
    if outFolder.lower().find('.gdb') != -1:
        if outName.lower()[-3:] != "shp":
            outName = outName + ".shp"
    elif outFolder.lower().find('.gdb') > -1 and outName.lower().find(".shp") > -1:
        outName = outName[:-3]
    print("Creating XS: {0}".format(os.path.join(outFolder, outName)))
    if arcpy.Exists(os.path.join(outFolder, outName)):
        print("Adios Old File!")
        arcpy.Delete_management(os.path.join(outFolder, outName))
    hasz = "ENABLE" if has_z else ""
    #Creates a blank feature class with the Features Expected
    arcpy.CreateFeatureclass_management(out_path=outFolder, out_name=outName,geometry_type="POLYGON",has_z=hasz,
                                        spatial_reference=sr)
    newFC = os.path.join(outFolder, outName)

    # Creates Three New Fields for Clasifying the new POlygon Feature Class
    print("\t|-t Creatins XS Fields!")
    if arcpy.Exists(newFC):
        arcpy.AddField_management(newFC,field_name='DS_Station',field_type="DOUBLE")
        arcpy.AddField_management (newFC , field_name='US_Station' , field_type="DOUBLE")
        arcpy.AddField_management (newFC , field_name='UnitNumber' , field_type="TEXT", field_length=20)

    return newFC

def createPolygonFeatures(xsFeatureclass, emptyPGFC, stationField="Station", unitNumberField="UnitNumber",
                          downStationField="DS_Station", upStationField="US_Station"):
    # 1 Identifies all stations and sorts them in order & sorts the stations into ordered pairs.
    oStations = orderStations(xsFeatureclass,stationField="Station", unitNumberField=unitNumberField)
    # 3 iterates through orders pairs and querys XS by Station Field to get two XS Pairs
    # 4 Uses XS Pair vertices to generate a polygon
    xsfields = (stationField , "SHAPE@")
    pgfields = (downStationField , upStationField , unitNumberField , "SHAPE@")
    for unitNumber in list(oStations.keys()):
        print("\t\t|-Creating {0} Bounding XS Polygons".format(unitNumber))
        orderedStatoins = oStations[unitNumber]["SortedStationPairs"]
        for i, pair in enumerate(orderedStatoins):
            print("\t\t Bounding XS: lower:{0},  upper:{1}".format(pair[0], pair[1]))
            query_exp = "\"{0}\" LIKE '{1}' AND \"{2}\" = {3} OR \"{2}\"  = {4}".format(unitNumberField, unitNumber,
                                                                                      stationField, pair[0], pair[1])
            vertices = []
            if i % 100 == 0:
                print("\t\t\t\t|- EXP: {0}".format(query_exp))
            matchCnt = 0
            with arcpy.da.SearchCursor(xsFeatureclass, xsfields, query_exp) as sC:
                for row in sC:
                    matchCnt += 1
            # Verifies that there is a binary match
            if matchCnt ==2:
                print("\t\t|-Station Match Identified!!")
                matchCnt = 0
                with arcpy.da.SearchCursor (xsFeatureclass , xsfields , query_exp) as sC:
                    for row in sC:
                        polyline = row[1]
                        if round(float(row[0]),2) == round(float(pair[0]),2):
                            vertices += get_vertices(polyline)
                        else:
                            vertices += get_vertices(polyline, reverse=True)
                if len(vertices) > 0:
                    print("\t\t\t|-Polygon Vertices Created!")
                    # Creates Polygon Feature And appends feature to XS FC`
                    boundingPolygon = arcpy.Polygon(arcpy.Array(vertices))
                    with arcpy.da.InsertCursor(emptyPGFC,pgfields) as iC:
                        iC.insertRow((pair[0], pair[1], unitNumber, boundingPolygon,))

def createWSELtins(xsFeatureclass, emptyPGFC, unitNumber="E1010000"):
    # Checks out necessary GIS Extensions to execute the Interpolation of WSEL Elevations
    getRequiredExtensions()
    sr = getSpatialReferencefactoryCode(xsFeatureclass)

    # Base Variables
    stormProfiles = {10:"WSEL10yr",
                     50:'WSEL50yr',
                     100:'WSEL100yr',
                     500:'WSEL500yr'}
    arcpy.env.workspace = outFolder
    for storm in list(stormProfiles.keys()):
        print("\t\t|-Creating Storm Tin {0}".format(stormProfiles[storm]))
        outTin = "{0}{1}".format(unitNumber, stormProfiles[storm])
        xsFCexp = [xsFeatureclass, stormProfiles[storm], "hardline"]
        # "{0} {1} softline".format(xsFeatureclass, stormProfiles[storm])
        pgFCexp = [emptyPGFC, "<None>", "softclip"]
        # "{0} <None> softclip".format(emptyPGFC)
        exp = [xsFCexp, pgFCexp]
        arcpy.CreateTin_3d(outTin, in_features=exp, spatial_reference=sr)

def createStationTIN(xsFeatureclass, emptyPGFC, statoinField="Station",unitNumber="E1010000"):
    # Checks out necessary GIS Extensions to execute the Interpolation of WSEL Elevations
    getRequiredExtensions()
    sr = getSpatialReferencefactoryCode(xsFeatureclass)
    arcpy.env.workspace = outFolder
    print("\t\t|-Creating Station Tin {0}".format(statoinField))
    outTin = "{0}{1}".format(unitNumber, statoinField)
    xsFCexp = [xsFeatureclass, statoinField, "hardline"]
    # "{0} {1} softline".format(xsFeatureclass, stormProfiles[storm])
    pgFCexp = [emptyPGFC, "<None>", "softclip"]
    # "{0} <None> softclip".format(emptyPGFC)
    exp = [xsFCexp, pgFCexp]
    arcpy.CreateTin_3d(outTin, in_features=exp, spatial_reference=sr)

def manageWMPChannels():
    # Dissolves al subreaches on single channel lines.
    # Seperates Main stem for tributaries
    # uses original source data to idetntify stream ordering
    pass

def autogenerateXS(streamCenterLine, buffer=4.0):
    pass

def assign_SI_BoundingStation(pg_path, si_path, tin_Path):
    """
    :param pg_path: path to bounding polygon feature class
    :param tin_path: path to tin feature for the observed tribnutary
    :param si_path: path to structural inventory
    :return:
    """
    start = datetime.now()
    print("Processing Start Time: {0}".format(start.strftime("%H:%M:%S")))
    fds = arcpy.ListFields(si_path)
    addFields = ['DS_Station', 'US_Station', 'Station', 'UnitNumber']
    fields = [str(fd.name)for fd in fds]
    for addFN in addFields:
        if addFN not in fields:
            if addFN.find("Station") != -1:
                if addFN.find("DS") != -1:
                    arcpy.AddField_management (si_path , field_name='DS_Station' , field_type="DOUBLE")
                elif addFN.find("US") != -1:
                    arcpy.AddField_management (si_path , field_name='US_Station' , field_type="DOUBLE")
                elif addFN.find("DS") == -1 and addFN.find("US") == -1:
                    arcpy.AddField_management (si_path , field_name='Station' , field_type="DOUBLE")
            elif addFN == "UnitNumber":
                arcpy.AddField_management (si_path , field_name='UnitNumber' , field_type="TEXT" , field_length=20)
            else:
                print("Something Went Hella Wrong!")
    addFields.pop(addFields.index("Station"))
    updateFields = addFields + ["SHAPE@"]
    searchFields = addFields + ["SHAPE@"]
    getRequiredExtensions()
    cnt = 0
    xnt = 0
    with arcpy.da.SearchCursor (pg_path , searchFields) as sCursor:
        for sow in sCursor:
            ds = sow[searchFields.index("DS_Station")]
            us = sow[searchFields.index("US_Station")]
            unit = sow[searchFields.index("UnitNumber")]
            pg = sow[searchFields.index("SHAPE@")]
            with arcpy.da.UpdateCursor(si_path, updateFields) as uCursor:
                for uow in uCursor:
                    pnt = uow[updateFields.index("SHAPE@")]
                    unitN = uow[updateFields.index("UnitNumber")]
                    if (pnt.within(pg)) and ((unitN is None) or (unitN == "")):
                        uow[ updateFields.index ("DS_Station") ] = ds
                        uow[updateFields.index("US_Station")] = us
                        uow[ updateFields.index ("UnitNumber") ] = unit
                        uCursor.updateRow(uow)
                        cnt += 1
                    else:
                        pass
    out_feature = "SI_Station"
    oldwrkspace = arcpy.env.workspace
    arcpy.env.workspace = r'N:\GIS-Proposals\HCFCD_SI\ArcMap Project\SIConceptTest\SIConceptTest.gdb'
    #Applies Station Value as Z-elevation to feature.
    print(out_feature)
    # Applies the  the thing!
    arcpy.InterpolateShape_3d(in_surface=tin_Path, in_feature_class=si_path,out_feature_class=out_feature,
                              method="NEAREST", preserve_features="EXCLUDE",  vertices_only="VERTICES_ONLY")
    arcpy.env.workspace = oldwrkspace
    updateFields = ["Station", "SHAPE@"]
    with arcpy.da.UpdateCursor (out_feature , updateFields) as uCursor:
        for uow in uCursor:
            z = float(uow[1].Z)
            uow[0] = z
            uCursor.updateRow (uow)
    end = datetime.now()
    elapsedTime = end - start
    elapsedTime = list(divmod(elapsedTime.total_seconds(), 60))
    print ("Processing End Time: {0}".format (end.strftime ("%H:%M:%S")))
    print ("Elapsed Run Time: {0} min. {1} seconds.".format (elapsedTime[ 0 ] , elapsedTime[ 1 ]))

if __name__ == "__main__":
    # Inputs, Ideally this will iterate an ordered list set by tributary order on a tributary by tributary basis
    start = datetime.now()
    print("Processing Start Time: {0}".format(start.strftime("%H:%M:%S")))
    xsFC = r"C:\Users\AGovea\Desktop\RJH\Example Effective Model\E115-00-00\Support_Data\Spatial_Data\S_XS.shp"
    WSELcsv = r"C:\Users\AGovea\Desktop\RJH\Example Effective Model\E115-00-00\WSEL.csv"
    unitNumber = "E115-00-00"
    outFolder = r"C:\Users\AGovea\Desktop\RJH\Output"
    # Step 1 Attributes XS with WSEL elevations form Effective Model
    attribute_XS(xsFC,WSELcsv, unitNumber=unitNumber)
    # Step 2 Generates XS Bounding Polygon
    pgFC = createExportPolyFc(xsFC,outFolder, "{0}.shp".format(unitNumber.replace("-","")),)
    createPolygonFeatures(xsFC,pgFC)
    createStationTIN(xsFC, pgFC, unitNumber=unitNumber)
    end = datetime.now()
    elapsedTime = end - start
    elapsedTime = list(divmod(elapsedTime.total_seconds(), 60))
    print("Processing End Time: {0}".format(end.strftime("%H:%M:%S")))
    print("Elapsed Run Time: {0} min. {1} seconds.".format(elapsedTime[0], elapsedTime[1]))
