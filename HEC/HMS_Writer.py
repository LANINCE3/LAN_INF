import os
import datetime
from datetime import timedelta
import bisect
import pandas as pd
import traceback
import math
import numpy as np
import arcpy
from collections import OrderedDict


def write_lines(file_path, lines,append=True):
    if append:
        with open(file_path, 'a') as fi:
            fi.writelines(lines)
    else:
        if os.path.exists(file_path):
            os.remove(file_path)
        with open(file_path, 'w+') as fi:
            fi.writelines(lines)

class HMS_Model(object):

    def __init__(self, mainstem_unit_number, hms_filename, subcatchment_fc, subreach_fc,
                 start_date, out_put_folder, subcatchment_name_field = "UnitNumber",
                 subreach_name_field="SubReach_ID" , sr_drains_to_field="DrainsTo_Subreach",
                 control_name="Event", time_step = 15, hydrologic_region=1, duration=24, isAtlas14=True,
                 isLevel1=False):
        """

        :param mainstem_unit_number:  The mainstem tributary hcfcd unit number for the watershed.
        :param hms_filename: Name of output HMS File
        :param subcatchment_fc: the (Watershed Master Plan) WMP/WPT formatted sub-catchment feature class
        :param subreach_fc:  the WMP/WPT formatted sub-catchment feature class.
                            Verify that all  sub-reaches are uni-directional vectors pointing to it's downstream subreach
        :param start_date: a start date datetime formatted
        :param out_put_folder: a output folder
        :param subcatchment_name_field: the field identifying the subcatchment field
        :param subreach_name_field: the field identifying the subcatchment field
        :param subreach_drains_to_field: the donwstream drains to field.
        :param control_name:
        :param time_step:
        :param hydrologic_region:
        :param duration:
        :param isAtlas14:
        """

        __hydro_region_dirct__ = {1:"Region_1", 2:"Region_2", 3:"Region_3"}

        self.storm_event_dict = {10:'10-Yr', 25:'25-Yr', 50:'50-Yr',
                                   100:'100-Yr', 500:'500-Yr'}

        self.annual_exceedance = {10:'10%', 25:'4%', 50:'2%',
                                   100:'1%', 500:'0.2%'}

        self.folder_path = out_put_folder #str, path
        self.project_folder = os.path.join(out_put_folder, "PROJECT")
        print('Creating project directories:\n\t|-{0}'.format (self.project_folder))
        self.shp_folder =os.path.join(self.folder_path,'SHP')

        if os.path.exists(self.project_folder):
            os.remove(self.project_folder)
            os.makedirs(self.project_folder)
        else:
            os.makedirs(self.project_folder)

        if os.path.exists(self.shp_folder):
            os.remove(self.shp_folder)
            os.makedirs(self.shp_folder)
        else:
            os.makedirs(self.shp_folder)
        self.isLevel1  = isLevel1
        self.subcatchment_fc = subcatchment_fc
        self.subreach_fc = subreach_fc
        self.subcatchment_name_field = subcatchment_name_field
        self.drains_to_field = sr_drains_to_field
        self.subreach_name_field = subreach_name_field
        self.unitNumber_field = "UnitNumber"
        self.hms_filename = hms_filename #str
        self.trib = mainstem_unit_number #str
        self.isAtlas = isAtlas14
        self.watershed = self.trib[ 0:5 ]
        self.project_folder = os.path.join(self.folder_path,self.watershed)
        self.basin_title = "{0} Baseline".format(self.watershed)
        self.storm_events = [10,25,50,100,500]
        self.region = __hydro_region_dirct__[hydrologic_region] #str (Region_1, Region_2, Region_3)
        self.time_step = time_step #int in minutes [tbd] default = 15mins
        self.start_datetime =start_date
        self.end_datetime = start_date + timedelta(hours=duration)   #end date-time, deault 24:00?
        self.duration = duration
        self.met_titles = {}
        self.control_title = control_name
        # Begins Creating Geometries
        print('Creating Geometr Data:')
        self.run_hms_gis_model_prep(self.subcatchment_fc, self.subreach_fc)


    def add_unitnumber_field(self):
        print("\t|-Creaiting Unit Number fields")
        unit_name_field = self.unitNumber_field
        sr_fields = [ fld.name for fld in arcpy.ListFields (self.subreach_fc) ]
        sc_fields = [ fld.name for fld in arcpy.ListFields (self.subcatchment_fc ) ]
        if unit_name_field not in sr_fields:
            arcpy.AddField_management (self.subreach_fc , unit_name_field , "TEXT" , field_length=30)

        if unit_name_field not in sc_fields:
            arcpy.AddField_management (self.subcatchment_fc , unit_name_field , "TEXT" , field_length=30)

        with arcpy.da.UpdateCursor(self.subreach_fc , (self.subreach_name_field,unit_name_field))as srUC:
            for row in srUC:
                unitNumber = str(row[0])[:10]
                srUC.updateRow((row[0], unitNumber))

        with arcpy.da.UpdateCursor(self.subcatchment_fc , (self.subcatchment_name_field,unit_name_field))as scUC:
            for row in scUC:
                unitNumber = str(row[0])[:10]
                scUC.updateRow((row[0], unitNumber))

    def run_hms_gis_model_prep(self, subcatchment_fc, subreach_fc):


        def dissove_catchments_on_reaches(shp_folder, subcatchment_fc, dissolve_field="HMSBasin"):
            """Unifies subcatchment fc's on unit number or other tributary name field."""
            dissolved_fc = os.path.join(shp_folder, '{0}_Dissolve.shp'.format(os.path.basename(subcatchment_fc)))
            disolved_catchments = arcpy.Dissolve_management(subcatchment_fc,
                                                            dissolved_fc,
                                                            dissolve_field,
                                                            multi_part="MULTI_PART")
            return disolved_catchments

        def create_circle(x , y , radius):
            pnts = [ ]
            for theta in np.arange (0 , 2 * math.pi , 0.1):
                xx = x + radius * math.cos (theta)
                yy = y + radius * math.sin (theta)
                pnts.append (arcpy.Point (xx , yy))
            return arcpy.Polygon (arcpy.Array (pnts))

        def create_junctions(shp_folder, spatial_reference, subreach_fc, dissolved_reach_fc, intersection_fc,
                                      subreach_field_name="SubReach_ID", unit_number_field = "UnitNumber"):

            bounding_sub_reach_points = {}
            bounding_points_buffers =[]
            total_points = 0
            filtered_points = 0
            overlaping_points = 0
            short_tribs = []

            # Accquires all unit numbers of dissolved feature class
            with arcpy.da.SearchCursor (dissolved_reach_fc , (unit_number_field )) as dissC:
                for drow in dissC:
                    unitNumber = str (drow[ 0 ])
                    if isLevel1:
                        short_tribs.append (unitNumber[ :4 ])
                    else:
                        short_tribs.append(unitNumber[:7])

            with arcpy.da.SearchCursor (intersection_fc , ('SHAPE@' )) as dissC:
                for drow in dissC:
                    total_points += 1

            # Ordred list of unit number from the dissolved feature class
            uniqueTribs = list(sorted(list(set(short_tribs)), reverse=False))
            if isLevel1:
                mainstem = uniqueTribs[0]+"-00-00"
            else:
                mainstem = uniqueTribs[ 0 ] + "-00"
            print('\t\t|-Mainstem: {0}'.format(mainstem))
            pnt_index = 0
            sr_dict = {}
            chk_point = None
            mainstem_line = None
            mainstem_length = None
            for uniTrib in uniqueTribs:
                unitNumber = uniTrib + "-00"
                q_exp = "\"{0}\" LIKE '{1}'".format (unit_number_field , unitNumber)
                print("\t\t|-UnitNumber: {0}".format(unitNumber))
                #Searches through all dissolved tributaries in alpha_numeric order starting with the mainstem.
                with arcpy.da.SearchCursor(dissolved_reach_fc, (unit_number_field, "SHAPE@"), q_exp) as dissC:
                    for drow in dissC:
                        pline = drow[1]
                        total_length = pline.length
                        if str(drow[0]) == mainstem:
                            bounding_point = pline.firstPoint
                            chk_point = pline.firstPoint
                            mainstem_line = pline
                            mainstem_length = total_length
                            if isLevel1:
                                name = "{0}_{1:.0f}J".format (unitNumber[ :4 ] , round(total_length))
                            else:
                                name = "{0}_{1:.0f}J".format (unitNumber[ :7 ] , round (total_length))
                            filtered_points += 1
                            circ = create_circle (bounding_point.X , bounding_point.Y , 200.0)
                            bounding_points_buffers.append (circ)
                            bounding_sub_reach_points[ pnt_index ] = {}
                            bounding_sub_reach_points[ pnt_index ][ 'Point' ] = bounding_point
                            bounding_sub_reach_points[ pnt_index ][ 'UnitNumber' ] = unitNumber
                            bounding_sub_reach_points[ pnt_index ][ 'SubReach' ] = None
                            bounding_sub_reach_points[ pnt_index ][ 'JunctionName' ] = name
                            bounding_sub_reach_points[ pnt_index ][ 'ReachDistance' ] = round(total_length)
                            pnt_index += 1
                        # Searches Intersection Point FC  and  identifies those pointes found between those points
                        with arcpy.da.SearchCursor(subreach_fc, (subreach_field_name, "SHAPE@"), q_exp) as srC:
                            for srow in srC:
                                subReach = str(srow[0])
                                sr_line = srow[1]
                                sr_buffer = sr_line.buffer(2)
                                sr_start_point = sr_line.firstPoint
                                sr_last_point = sr_line.lastPoint
                                dist_to_start = round (total_length - pline.measureOnLine (sr_start_point, False) )
                                dist_to_end = round (total_length - pline.measureOnLine (sr_last_point, False) )
                                sr_dict[subReach] = {'Upper':dist_to_start, "Lower":dist_to_end}
                                sr_dict['TotalLength'] = round(total_length)
                                adj_end = dist_to_end +200
                                # print("\t\t\t\t|-Start Dist.: {0} ft.-|".format (dist_to_start))
                                # print("\t\t\t\t|-End Dist.: {0} ft.-|".format (dist_to_end))
                                # Searches Intersection Point FC  and  identifies those pointes found between those points
                                with arcpy.da.SearchCursor (intersection_fc , ("SHAPE@"), q_exp) as intPC:
                                    for irow in intPC:
                                        pnt = irow[ 0 ].firstPoint
                                        dit_to_pnt = round (total_length - pline.measureOnLine (pnt, False) )
                                        srl_pnt = sr_line.measureOnLine (pnt , False)
                                        intersects_subreach = pnt.within(sr_buffer,)
                                        # Checks if the point if  observed is within the bounds of the subreach fc.
                                        if (dit_to_pnt <= sr_last_point) and  (dit_to_pnt >= adj_end ) and intersects_subreach:
                                            if len(bounding_points_buffers) == 0:
                                                bounding_point = sr_start_point
                                                if isLevel1:
                                                    name = "{0}_{1:.0f}J".format (unitNumber[ :4 ] , dist_to_start)
                                                else:
                                                    name = "{0}_{1:.0f}J".format (unitNumber[:7] , dist_to_start)
                                                filtered_points += 1
                                                circ = create_circle (sr_start_point.X , sr_start_point.Y , 200.0)
                                                bounding_points_buffers.append(circ)
                                                bounding_sub_reach_points[ pnt_index ] = {}
                                                bounding_sub_reach_points[pnt_index]['Point'] = bounding_point
                                                bounding_sub_reach_points[ pnt_index ][ 'UnitNumber' ] = unitNumber
                                                bounding_sub_reach_points[ pnt_index ][ 'SubReach' ] = subReach
                                                bounding_sub_reach_points[ pnt_index ][ 'JunctionName' ] = name
                                                bounding_sub_reach_points[ pnt_index ][
                                                    'ReachDistance' ] = dist_to_start
                                                pnt_index += 1
                                                # print("\t\t\t\t\t|-Chk.Dist: {0}-|".format (dit_to_pnt))
                                            else:
                                                point_exists = None
                                                # Checks all existin point to see if point already exists in system
                                                exist_list = []
                                                for buf in bounding_points_buffers:
                                                    exist_list.append(sr_start_point.within(buf))
                                                if True in exist_list:
                                                    point_exists = True
                                                else:
                                                    point_exists = False
                                                # Updates Bounding Points list
                                                if not point_exists:
                                                    bounding_point = sr_start_point
                                                    if isLevel1:
                                                        name = "{0}_{1:.0f}J".format (unitNumber[ :4 ] , dist_to_start)
                                                    else:
                                                        name = "{0}_{1:.0f}J".format (unitNumber[:7], dist_to_start)
                                                    filtered_points += 1
                                                    circ = create_circle (sr_start_point.X , sr_start_point.Y , 200.0)
                                                    bounding_points_buffers.append (circ)
                                                    bounding_sub_reach_points[ pnt_index ] = {}
                                                    bounding_sub_reach_points[ pnt_index ][ 'Point' ] = bounding_point
                                                    bounding_sub_reach_points[ pnt_index ][ 'UnitNumber' ] = unitNumber
                                                    bounding_sub_reach_points[ pnt_index ][ 'SubReach' ] = subReach
                                                    bounding_sub_reach_points[ pnt_index ][ 'JunctionName' ] = name
                                                    bounding_sub_reach_points[ pnt_index ][ 'ReachDistance' ] = dist_to_start
                                                    pnt_index += 1
                                                    # print("\t\t\t\t\t|-Chk.Dist: {0}-|".format (dit_to_pnt))
                                                else:
                                                    overlaping_points += 1

            # Creates Junction FC
            junction_fc_name = '{0}_HMSJunctions'.format (os.path.splitext(os.path.basename (subreach_fc))[0])
            junction_fc = os.path.join (shp_folder , '{0}.shp'.format (junction_fc_name))
            if arcpy.Exists (junction_fc):
                arcpy.Delete_management (junction_fc)
            arcpy.CreateFeatureclass_management (shp_folder , junction_fc_name , 'POINT' , spatial_reference=spatial_reference)
            arcpy.AddField_management (junction_fc , 'JUNCID' , 'LONG')
            arcpy.AddField_management (junction_fc , 'Name' , 'TEXT' , field_length=40)
            arcpy.AddField_management (junction_fc , 'UnitNumber' , 'TEXT' , field_length=15)
            arcpy.AddField_management (junction_fc , 'SubReachID' , 'TEXT' , field_length=20)
            arcpy.AddField_management(junction_fc, 'Station','DOUBLE')
            arcpy.AddField_management (junction_fc , 'inHMSModel' , 'TEXT' , field_length=5)

            # Updates junction feature class with points
            jfc_fields = ('JUNCID', 'Name', 'UnitNumber', 'SubReachID', 'Station', 'inHMSModel', 'SHAPE@')
            with arcpy.da.InsertCursor (junction_fc , jfc_fields) as juncIC:
                for pnt_index in list(bounding_sub_reach_points.keys()):
                    junctionName = bounding_sub_reach_points[ pnt_index ][ 'JunctionName' ]
                    unitNumber = bounding_sub_reach_points[pnt_index]['UnitNumber']
                    subReach = bounding_sub_reach_points[ pnt_index ][ 'SubReach' ]

                    if subReach is None:
                        print('\t\t\t\tSubReach:{0}'.format(subReach))
                        sr_fields =(subreach_field_name, "SHAPE@")
                        query_exp = "\"{0}\" LIKE '{1}'".format (unit_number_field , mainstem)
                        with arcpy.da.SearchCursor(subreach_fc, sr_fields, query_exp) as srCursor:
                            for srow in srCursor:
                                sr = str(srow[0])
                                first_point = srow[ 1 ].firstPoint
                                last_point = srow[1].lastPoint
                                dist_to_end = round(mainstem_length-mainstem_line.measureOnLine(last_point,False))
                                if (round(first_point.X,2)== round(chk_point.X,2)) or (round(first_point.Y,2) == round(chk_point.Y,2)):
                                    subReach = sr
                                    sr_dict[ subReach ] = {'Upper': sr_dict['TotalLength'] , "Lower": dist_to_end}
                                    print('\t\t\t\t|-{0}-|'.format (sr))
                                    print('True')
                    station = bounding_sub_reach_points[ pnt_index ][ 'ReachDistance' ]
                    point = bounding_sub_reach_points[ pnt_index ][ 'Point' ]
                    inHMSModel = "TRUE" if unitNumber == mainstem else "FALSE"
                    row = (pnt_index , junctionName , unitNumber , subReach , station, inHMSModel, point ,)
                    juncIC.insertRow (row)
            print('::Cluster Report::\n\t|-Total Tributary Intersections: {0}'.format(total_points))
            print('\t|-Total Filtered Intersections Identified: {0}'.format(filtered_points))
            print('\t|-Total Overlapping Points Identified: {0}'.format(overlaping_points))
            arcpy.Delete_management(intersection_fc)
            return junction_fc, sr_dict

        def create_basins(shp_folder, subcatchment_fc, junction_fc, subreach_fc, sr_dict,
                          sub_catchment_field, subreach_name_field,
                                     unitNumber_field, drains_to_field,
                          isLevel1 = True):
            root_trib = None
            print("\t\t|-Creating Basins")
            with arcpy.da.SearchCursor(subreach_fc, (subreach_name_field)) as scCursor:
                unis = []
                tis = []
                for row in scCursor:
                    unitNumber = str(row[0])[:10]
                    if isLevel1:
                        tribIdentifier = str(row[0])[:4]
                    else:
                        tribIdentifier = str (row[ 0 ])[ :7 ]
                    unis.append(unitNumber)
                    tis.append(tribIdentifier)
            unitNumbers = list(sorted(list(set(unis)),reverse=False))
            tribIdentifiers= list (sorted (list (set (tis)) , reverse=False))

            root_trib = unitNumbers[0][:4]
            main_unitNumber = unitNumbers[0]
            if isLevel1:
                print(main_unitNumber)
            print(main_unitNumber)
            def get_basin_name(basin_cnt, root_trib=root_trib):
                alphabet = [ ch for ch in 'ABCEDEFGHIJKLMNOPQRSTUVWXYZ' ]
                val , rem = divmod (basin_cnt , len (alphabet))
                if val == 0:
                    basin = "{0}-{1}".format (root_trib , alphabet[ basin_cnt ])
                else:
                    basin = "{0}-{1}{2}".format (root_trib , alphabet[ val - 1 ] , alphabet[ rem ])
                basin_cnt += 1
                return basin, basin_cnt

            query_exp = "\"{0}\" LIKE '{1}'".format (unitNumber_field , main_unitNumber)
            stations = []
            junc_fields = ( unitNumber_field, 'SubReachID', 'Station', "Name")
            # Identifies Bounding Stations
            with arcpy.da.SearchCursor(junction_fc,junc_fields, query_exp) as juncCursor:
                for jrow in juncCursor:
                    stations.append(jrow[2])
            stations = list(sorted(stations, reverse=True))
            sta_pairs = {}
            for i, sta in enumerate(stations):
                if i <= len(stations) -2:
                    sta_pairs[sta] = (sta,stations[i+1])

            juncs = {}
            # Fields and stuff
            sr_fields = ("FID", unitNumber_field, subreach_name_field, drains_to_field, "SHAPE@")
            cnt = 0

            for k, sta in enumerate(stations):
                query_exp = "\"{0}\" LIKE '{1}' AND \"{2}\" = {3}".format (unitNumber_field ,
                                                                           main_unitNumber,
                                                                           "Station",
                                                                           sta)
                if k < len(stations) - 1:
                    upper_bound = sta_pairs[sta][0]
                    lower_bound = sta_pairs[sta][1]
                else:
                    upper_bound = sta
                    lower_bound = 0.0
                basin, cnt = get_basin_name(cnt)
                scnt = 0
                juncs[basin] = {'SubReaches':[], 'Junction':None}
                with arcpy.da.SearchCursor(junction_fc, junc_fields, query_exp) as juncCursor:
                    for jrow in juncCursor:
                        unitNumber = str(jrow[0])
                        juncName  = str(jrow[3])
                        drns_to_exp = "\"{0}\" LIKE '{1}'".format (unitNumber_field , main_unitNumber)
                        with arcpy.da.SearchCursor(sub_reach_fc,sr_fields, drns_to_exp) as srCursor:
                            # First identifies break of tributaires on unitnumber
                            for sr_row in srCursor:
                                sub_reach = sr_row[2]
                                st_point = sr_dict[sub_reach]['Upper']  - 20.0
                                if st_point <= upper_bound and st_point >= lower_bound:
                                    juncs[ basin ]['SubReaches'].append(sub_reach)
                                    juncs[ basin ]['Junction'] = juncName




            tribIdentifiers.pop(0)
            for k, trib in enumerate(tribIdentifiers):
                sr_fields = ("FID" , unitNumber_field , subreach_name_field , drains_to_field , "SHAPE@")
                trib_exp = "\"{0}\" LIKE '{1}%' AND \"{2}\" LIKE '{3}%'".format (drains_to_field ,
                                                                                 main_unitNumber[:7],
                                                                                 unitNumber_field,
                                                                                 trib)
                sub_reaches = []
                drains_to_reach = None
                with arcpy.da.SearchCursor (sub_reach_fc , sr_fields , trib_exp) as srCursor:
                    for srRow in srCursor:
                        sub_reach = str (srRow[  2  ])
                        drains_to_sr = str(srRow[3])
                        drains_to_trib = drains_to_sr[ :7 ]

                        sub_reaches.append(sub_reach)
                        if drains_to_trib == main_unitNumber[:7]:
                            drains_to_reach = drains_to_sr

                if drains_to_reach is not None:
                    junc_fields = ("FID" , unitNumber_field , 'SubReachID' , "Name")
                    query_exp = "\"{0}\" LIKE '{1}'".format (unitNumber_field , main_unitNumber)

                    with arcpy.da.SearchCursor (junction_fc , junc_fields , query_exp) as juncCursor:
                        for jrow in juncCursor:
                            juncName = str (jrow[ 3 ])
                            jSubReach = str(jrow[2])
                            if jSubReach is not None and jSubReach == drains_to_reach:
                                basin, cnt = get_basin_name(cnt)
                                juncs[ basin ] = {'SubReaches': [ ] , 'Junction': None}
                                juncs[ basin ][ 'SubReaches' ] = sub_reaches
                                juncs[ basin ][ 'Junction' ] = juncName

            basin_dict = {}
            #Adds HEC-HMS Basin Field
            try:
                arcpy.AddField_management (subcatchment_fc , 'HMSBasin' ,
                                           'TEXT' , field_alias="HMS Basin",
                                           field_length=30)

                arcpy.AddField_management (subcatchment_fc , 'HMSJunct' ,
                                           'TEXT' , field_alias="HMS Junction" ,
                                           field_length=30)

            except:
                pass


            #Establish HEC-HMS Basin
            with arcpy.da.UpdateCursor(subcatchment_fc,(sub_catchment_field, 'HMSBasin', 'HMSJunct')) as scUCursor:
                for row in scUCursor:
                    subreach = row[0]
                    trib = subreach[:10]
                    for basin in juncs.keys():
                        if subreach in juncs[basin]['SubReaches']:
                            junction = juncs[ basin ][ 'Junction' ]
                            basin_dict[basin] = trib
                            scUCursor.updateRow((row[0], basin, junction))


            out_path = os.path.join(shp_folder, "{0}HMSBasins.shp".format(root_trib))
            dc_fc = arcpy.Dissolve_management(subcatchment_fc,
                                              out_feature_class=out_path,
                                              dissolve_field="HMSBasin", multi_part="SINGLE_PART")
            #identifies all unnamed basins
            with arcpy.da.SearchCursor(out_path,("FID","HMSBasin")) as searchBasins:
                unnamed_fids = []
                for row in searchBasins:
                    if len(str(row[1])) > 2 :
                        pass
                    else:
                        unnamed_fids.append (row[ 0 ])




            #Names unnamed Basins
            basin_cnt = 0
            for fid in unnamed_fids:
                basin, basin_cnt = get_basin_name(cnt)

                dexp = "\"FID\" = {0}".format (fid)
                with arcpy.da.UpdateCursor(out_path,("HMSBasin",  "SHAPE@"),dexp) as updateBasin:
                    for row in updateBasin:
                        row[0] = basin
                        pgon = row[1]
                        buffgon = pgon.buffer(50)
                        with arcpy.da.SearchCursor (subreach_fc , (subreach_name_field, 'SHAPE@')) as scCursor:
                            for rowp in scCursor:
                                trib = str(rowp[0])[:10]
                                pline = rowp[1]
                                if buffgon.contains(pline):
                                    basin_dict[ basin ] = trib
                                    break
                        updateBasin.updateRow(row)

            arcpy.AddField_management (out_path , unitNumber_field , "TEXT" , field_length=30)
            arcpy.AddField_management (out_path , 'BDF' , 'DOUBLE')
            arcpy.AddField_management (out_path , 'Tc_Hr' , 'DOUBLE')
            arcpy.AddField_management (out_path , 'R_Hr' , 'DOUBLE')
            arcpy.AddField_management (out_path , 'Area_SqMi' , 'DOUBLE')
            arcpy.AddField_management (out_path , 'DnJunc' , 'TEXT' , field_length=30)
            arcpy.AddField_management (out_path , 'UpJunc' , 'TEXT' , field_length=30)

            #Verifies and Corrects Unit Numbers to each HMS Basin
            with arcpy.da.UpdateCursor (out_path , ("HMSBasin" , unitNumber_field, "SHAPE@") ) as updateBasin:
                for row in updateBasin:
                    basin = row[ 0 ]
                    pgon = row[ 2 ]
                    buffgon = pgon.buffer (20)
                    with arcpy.da.SearchCursor (subreach_fc , (subreach_name_field , 'SHAPE@')) as scCursor:
                        for rowp in scCursor:
                            subreach = str(rowp[0])
                            trib = subreach[:4] + "-00-00"
                            pline= rowp[ 1 ]
                            if buffgon.contains (pline):
                                row[1] = trib
                                break
                    updateBasin.updateRow (row)

            #Makes first attempt at identifying bounding junctions /nodes
            flds = ('HMSBasin', unitNumber_field, 'Area_SqMi','DnJunc', 'UpJunc','SHAPE@')
            all_stas_dict = {}
            with arcpy.da.UpdateCursor(out_path, flds) as outC:
                for row  in outC:
                    basin = str(row[0])
                    pgon = row[5]
                    buffgon = pgon.buffer(400)
                    if basin != ' ':
                        junc_fields = ("FID" , unitNumber_field , 'Station' , "Name", "SHAPE@")
                        qry_exp = "\"inHMSModel\" LIKE 'TRUE'"
                        bj_dict = {}
                        dn_junc = 'None'
                        up_junc  = 'None'
                        with arcpy.da.SearchCursor (junction_fc , junc_fields , qry_exp) as juncCursor:
                            for jrow in juncCursor:
                                pnt = jrow[4]
                                if pnt.within(buffgon) or pnt.touches(buffgon) :
                                    station = int (jrow[ 2 ])
                                    junc_name = str (jrow[ 3 ])
                                    trib = junc_name[:7]
                                    all_stas_dict[ station ] = junc_name
                                    if trib == mainstem[:7]:
                                        bj_dict[ station ] = junc_name
                        stations = [sta for sta in bj_dict.keys()]
                        stations = list(sorted(stations,reverse=False))
                        for i, sta in enumerate(stations):
                            if i == 0:
                                dn_junc = bj_dict[sta]
                            else:
                                up_junc = bj_dict[sta]
                        area_sqft = pgon.area
                        area_sqmi = area_sqft / 43560.0 / 640.0  # converts area to be area in Sq Mi
                        row[ 4 ] = up_junc
                        row[ 3 ]= dn_junc
                        row[ 2 ] = area_sqmi
                        outC.updateRow(row)

            #Corrects and adjusts those Upstream Junctions defined as None
            upjunc_exp = "\"UpJunc\" LIKE 'None' AND \"{0}\" LIKE {1}".format(unitNumber_field, mainstem)
            all_stas = [sta for sta in all_stas_dict.keys()]
            all_stas_sorted = list(sorted(all_stas, reverse=False))
            min_sta_junc = all_stas_dict[all_stas_sorted[0]]
            max_sta_junc = all_stas_dict[all_stas_sorted[len(all_stas_sorted)-1]]
            flds = ('HMSBasin' , unitNumber_field , 'Area_SqMi' , 'DnJunc' , 'UpJunc', 'FID', "SHAPE@")
            missnamed_basins = {}
            passed_basins = []
            delete_fids = []
            with arcpy.da.UpdateCursor (out_path , flds) as updateBasin1:
                for row in updateBasin1:
                    basin = row[0]
                    unitNumber = row[1]
                    dn_junc= str(row[3])
                    up_junc = str(row[ 4 ])
                    if up_junc == "None" and unitNumber == mainstem and "_" in dn_junc:
                        rc = str(dn_junc).replace('J',"").split('_')
                        dn_sta = int(str(rc[1]))
                        print('\t\t\t\-Basin:{0}::Juncs:({1},{2})'.format (basin , dn_junc , up_junc))
                        if dn_junc == max_sta_junc:
                            new_up_junct = max_sta_junc
                            new_dn_junct =  all_stas_dict[all_stas_sorted[bisect.bisect_left(all_stas_sorted, dn_sta , lo=0) - 1]]
                            fid = row[5]
                            mxexp = "\"DnJunc\" LIKE '{0}'".format(new_dn_junct)
                            with arcpy.da.SearchCursor (out_path , flds, mxexp) as searchBasin1:
                                for xow in searchBasin1:
                                    if xow[5] != fid and xow[1]==unitNumber:
                                        row[0] = xow[0]
                                        rpg = row[6] #most upstream basin polygon
                                        xpg = xow[6] #next most upstream basin polygon
                                        new_pg = rpg.union(xpg)
                                        row[6] = new_pg
                                        delete_fids.append(xow[5])
                            row[3] = new_dn_junct
                            row[4] = new_up_junct
                        elif dn_junc == min_sta_junc:
                            new_up_junct = dn_junc
                            new_dn_junct = "Outfall"
                            row[3] = new_dn_junct
                            row[4] = new_up_junct
                        else:
                            if basin not in list(missnamed_basins.keys()):
                                missnamed_basins[basin] = [int(row[5])]
                            else:
                                missnamed_basins[basin].append(int(row[5]))
                    elif unitNumber != mainstem and basin in passed_basins:
                        basin , basin_cnt = get_basin_name (basin_cnt)
                        row[0] = basin
                        row[ 3 ] = dn_junc
                        row[ 4 ] = "None"
                        print('\t\t\t\-Basin:{0}::Juncs:({1},{2})'.format (basin , dn_junc , up_junc))
                    elif unitNumber != mainstem and basin not in passed_basins:
                        row[0] = basin
                        row[ 3 ] = dn_junc
                        row[ 4 ] = "None"
                    elif unitNumber == mainstem and basin in passed_basins:
                        basin , basin_cnt = get_basin_name (basin_cnt)
                        row[ 0 ] = basin
                        row[ 3 ] = dn_junc
                        row[ 4 ] = up_junc
                    else:
                        pass
                    passed_basins.append (basin)

                    updateBasin1.updateRow (row)
            #Adjusts last of the misnammed basins on the mainstem
            flds = ('HMSBasin' , unitNumber_field , 'Area_SqMi' , 'DnJunc' , 'UpJunc' , 'FID', 'SHAPE@')
            for basin in list(missnamed_basins.keys()):
                update_fids = []
                if len(missnamed_basins[basin]) == 2:
                    bquery = "\"FID\" IN ({0})".format(", ".join(map(str,missnamed_basins[basin])))
                    pgs = {}
                    fids = []
                    with arcpy.da.SearchCursor (out_path , flds, bquery) as updateBasin2:
                        for row in updateBasin2:
                            fid = int(row[5])
                            pgon = row[6]
                            pgs[ fid ]  = {}
                            pgs[fid]['pg'] = pgon
                            pgs[ fid ][ 'dnJ' ] = str(row[3])
                            fids.append(fid)
                    fid = fids[0]
                    next_fid = fids[1]
                    opg = pgs[fid]['pg']
                    buffopg  = opg.buffer(200)
                    odnjnc = pgs[fid]['dnJ']
                    npg = pgs[next_fid]['pg']
                    ndnjunc = pgs[next_fid]['dnJ']
                    overlaps = buffopg.overlaps(npg)
                    if overlaps:
                        delete_fids.append(next_fid)
                        unionpg = opg.union(npg) # union of polygons
                        og_sta  = int(str (odnjnc).replace ('J' , "").split ('_')[ 1 ])
                        dn_sta = int(str (ndnjunc).replace ('J' , "").split ('_')[ 1 ])
                        if og_sta > dn_sta:
                            dn_junc = ndnjunc
                            up_junc = odnjnc

                            update_fids += [next_fid, fid]
                        else:
                            dn_junc = odnjnc
                            up_junc = ndnjunc
                            update_fids += [ next_fid , fid ]
                        bquery = "\"FID\" = {0}".format (fid)
                        with arcpy.da.UpdateCursor (out_path , flds,bquery) as updateBasin2:
                            for row in updateBasin2:
                                rfid = int (row[ 5 ])
                                if rfid == fid:
                                    row[3] = dn_junc
                                    row[4] = up_junc
                                    row[6] = unionpg
                                updateBasin2.updateRow(row)

            #Deletes duplicate / overlapping baisns:
            if len(delete_fids) >= 1:
                delquery = "\"FID\" IN ({0})".format (", ".join (map (str , delete_fids)))
                print(delquery)
                with arcpy.da.UpdateCursor (out_path ,flds, delquery) as delBasin1:
                    for row in delBasin1:
                        print('\t\t\t|-Deleting Duplicate Data: {0}'.format(row[0]))
                        delBasin1.deleteRow()

            #Adjusts areas for merged features
            #  flds = ('HMSBasin' , unitNumber_field , 'Area_SqMi' , 'DnJunc' , 'UpJunc' , 'FID', 'SHAPE@')
            with arcpy.da.UpdateCursor (out_path ,flds) as updateAreas:
                for row in updateAreas:
                    row[2] = row[6].area / 43560.0 / 640.0
                    print('\t\t\t|-Identified HMS Sub-Basin:{0}'.format (row[0]))
                    updateAreas.updateRow(row)

            #Identify all downstream junctions with three or more

            return out_path

        def create_reach_segment(upstream_point , downstream_point , polyline , subreach_fc, subreach_name_field="SubReach_ID",
                                 identifier="HA", junctionID=0 , isEnd=False):
            """Returns a polyline based on two bounding vertices found on the line. """
            part = polyline.getPart (0)
            total_length = polyline.length
            lineArray = arcpy.Array ()
            # Identifies bounding vertices and associated distance along the line.
            if isEnd:
                last_point = polyline.lastPoint
                upstream_point_dist = round (total_length - polyline.measureOnLine (downstream_point , False) , 2)
                downstream_point_dist = round (total_length - polyline.measureOnLine (last_point , False) , 2)
            else:
                upstream_point_dist = round (total_length - polyline.measureOnLine (upstream_point , False) , 2)
                downstream_point_dist = round (total_length - polyline.measureOnLine (downstream_point , False) , 2)
            # Retrieves all vertices between bounding vertices of a polyline.
            for pnt in part:
                pnt_dist = round (total_length - polyline.measureOnLine (pnt , False) , 2)
                if pnt_dist <= upstream_point_dist and pnt_dist >= downstream_point_dist:
                    if lineArray.count == 0:
                        lineArray.add (upstream_point)
                        lineArray.add (pnt)
                    else:
                        lineArray.add (pnt)
            # Makes ending downstream point is added to array
            if lineArray[ lineArray.count - 1 ].X != downstream_point.X and lineArray[
                lineArray.count - 1 ].Y != downstream_point.Y:
                lineArray.add (downstream_point)

            # Creates a new polyline from point array
            new_polyline = arcpy.Polyline (lineArray)
            identifier = str (identifier)
            junc = identifier
            if identifier.upper ().find ('J') == len (identifier) - 1:
                identifier = identifier.upper ()[ 0:len (identifier) - 1 ] + 'R'
            else:
                identifier = identifier.upper () + 'R'
            return {'name': identifier , 'polyline': new_polyline , 'DJunc': junc , 'JuncID': junctionID}


        def process_hms_basin(basin_fc, unitNumberField):
            fields = ('HMSBasin' , unitNumberField , 'Area_SqMi' , 'DnJunc' , 'UpJunc' , 'FID' )
            mainstem = None
            unitNumbers = []
            downstream_basin= None
            upstream_mainstem_basin = None
            non_mainstem_basins = []
            ordered_basins = []
            basin_ref = {}
            junc_pairs = {}
            #Identify Tribs:
            with arcpy.da.SearchCursor (basin_fc , fields) as basinCursor:
                for row in basinCursor:
                    unitNumber = row[1]
                    unitNumbers.append(unitNumber)
                    dnJunc = row[3]
                    upJunc = row[4]
                    basin =  row[0]
                    fid = row[5]
                    if dnJunc != "Outfall" and dnJunc != 'None':
                        dnSta = int(dnJunc.replace("J","").split("_")[1])
                    else:
                        dnSta = 0
                    basin_ref[basin] = {"unitNumber":unitNumber, 'FID':fid,
                                        'DnJunc':dnJunc,'UpJunc':upJunc,
                                        'DnSta':dnSta}
                    if dnJunc == 'Outfall':
                        ordered_basins.append(basin)
                    else:
                        pass
                    if dnJunc in list(junc_pairs.keys()):
                        junc_pairs[ dnJunc ].append(basin)
                    else:
                        junc_pairs[dnJunc] = [basin]

            unitNumbers = list(sorted(list(set(unitNumbers)), reverse=False))
            mainstem = unitNumbers[0]
            mainstem_dnstas = {}
            mainstem_dnstaL = []
            for basin in list(basin_ref.keys()):
                unitNumber = basin_ref[basin]['unitNumber']
                dnJunc =  basin_ref[basin]['DnJunc']
                dnsta = int(basin_ref[basin]['DnSta'])
                if unitNumber == mainstem:
                    mainstem_dnstas[dnsta] = dnJunc
                    mainstem_dnstaL.append(dnsta)
            ordered_dnsta =  list(sorted(list(set(mainstem_dnstaL)),reverse=True))
            hms_order = {}
            for dnSta in ordered_dnsta:
                dnJunc = mainstem_dnstas[dnSta]
                basins = junc_pairs[dnJunc]
                hms_order[dnJunc] = []
                for basin in basins:
                    unitNumber = basin_ref[basin]['unitNumber']
                    if unitNumber == mainstem:
                        if len(hms_order[dnJunc]) == 0:
                            hms_order[ dnJunc ].append(basin)
                        else:
                            old_basins = hms_order[ dnJunc ]
                            hms_order[ dnJunc ] = [basin] + old_basins
                    else:
                        hms_order[ dnJunc ].append (basin)
            print('\n\nHMS Flow Schematic:\n')
            cnt= 0
            od = OrderedDict()
            od2 = OrderedDict()
            final_Model = {'OrderedSta':ordered_dnsta,'J&B':od,'Sta|Junc':mainstem_dnstas, 'dnJuncPair':od2}
            previous_dnJunc = None
            for dnSta in ordered_dnsta:
                dnJunc = mainstem_dnstas[ dnSta ]
                juncBasins = hms_order[dnJunc]
                intermed_junc = None
                intermed_junc = None
                intermed_junc_next = None
                previous_interJunc = None
                if cnt == 0:
                    if len(juncBasins) == 2 or  len(juncBasins) == 1  :
                        if len(juncBasins) == 2 :
                            for basin in juncBasins:
                                final_Model[ "dnJuncPair" ][ basin ] = dnJunc
                        else:
                            final_Model[ "dnJuncPair" ][ juncBasins[0] ] = dnJunc
                        final_Model["J&B"][dnJunc] = juncBasins
                        print(juncBasins)

                    elif len(juncBasins) > 2 and len(juncBasins) %2 == 1:
                        # Handles Odd number of adjoing basins at most upstream junction
                        num_interim_juncs = len(juncBasins)
                        for i in range(0,num_interim_juncs):
                            dif_ = num_interim_juncs - i - 1
                            ji = dif_ - 1
                            intermed_junc =  "{0}I{1}".format(dnJunc,ji)
                            if i == 0 :
                                basin_2 = juncBasins[dif_]
                                basin_1 = juncBasins[ ji ]
                                final_Model[ "J&B" ][ intermed_junc ] = [basin_1, basin_2]
                                final_Model[ "dnJuncPair" ][ basin_2 ] = intermed_junc
                                final_Model[ "dnJuncPair" ][ basin_1 ] = intermed_junc
                                previous_interJunc = intermed_junc
                            elif i > 0 and i < num_interim_juncs - 1 :
                                basin_1 = juncBasins[ (ji) ]
                                final_Model[ "J&B" ][ intermed_junc ] = [ basin_1 , previous_interJunc]
                                final_Model[ "dnJuncPair" ][ basin_1 ] = intermed_junc
                                final_Model[ "dnJuncPair" ][ previous_interJunc ] = intermed_junc
                                previous_interJunc = intermed_junc
                            elif ji==0:
                                basin_1 = juncBasins[ (ji) ]
                                final_Model[ "J&B" ][ dnJunc ] = [ previous_dnJunc, basin_1 ]
                                final_Model[ "dnJuncPair" ][ basin_1 ] = dnJunc
                                final_Model[ "dnJuncPair" ][ previous_dnJunc ] = dnJunc
                                previous_interJunc = None
                    elif len(juncBasins) > 2 and len(juncBasins) %2 ==0:
                        # Handles Even number of adjoining Basins at most upstream junction
                        num_interim_juncs = len(juncBasins)
                        for i in range(0,num_interim_juncs):
                            dif_ = num_interim_juncs - i - 1
                            ji = dif_ - 1
                            if i == 0 :
                                intermed_junc =  "{0}I{1}".format(dnJunc,ji)
                                basin_2 = juncBasins[dif_]
                                basin_1 = juncBasins[ dif_-1]
                                final_Model[ "J&B" ][ intermed_junc ] = [basin_1, basin_2]
                                final_Model[ "dnJuncPair" ][ basin_1 ] = intermed_junc
                                final_Model[ "dnJuncPair" ][ basin_2 ] = intermed_junc
                                previous_interJunc = intermed_junc
                            elif i > 0 and i < num_interim_juncs - 1 :
                                intermed_junc = "{0}I{1}".format (dnJunc , ji)
                                basin_2 = juncBasins[dif_-1]
                                final_Model[ "J&B" ][ intermed_junc ] = [ basin_2 , previous_interJunc]
                                final_Model[ "dnJuncPair" ][ basin_2 ] = intermed_junc
                                final_Model[ "dnJuncPair" ][ previous_interJunc ] = intermed_junc
                                previous_interJunc = intermed_junc
                            elif ji==0:
                                basin_2 = juncBasins[ dif_ - 1 ]
                                final_Model[ "J&B" ][ dnJunc ] = [ basin_2 , previous_dnJunc]
                                final_Model[ "dnJuncPair" ][ basin_2 ] = dnJunc
                                final_Model[ "dnJuncPair" ][ previous_dnJunc ] = dnJunc
                                previous_interJunc = None
                else:
                    if len(juncBasins) == 2:
                        final_Model[ "J&B" ][ dnJunc+"I1" ] = juncBasins
                        final_Model[ "J&B" ][ dnJunc ] = [previous_dnJunc, dnJunc + "I1"]
                        final_Model[ "dnJuncPair" ][ juncBasins[0]] = dnJunc+"I1"
                        final_Model[ "dnJuncPair" ][ juncBasins[1] ] = dnJunc+"I1"
                        final_Model[ "dnJuncPair" ][ dnJunc + "I1" ] = dnJunc
                        final_Model[ "dnJuncPair" ][ previous_dnJunc ] = dnJunc
                    elif len(juncBasins) == 3:
                        final_Model[ "J&B" ][ dnJunc+"I2" ] = [juncBasins[1],juncBasins[2]]
                        final_Model[ "J&B" ][ dnJunc + "I1" ] = [ juncBasins[0 ] , dnJunc + "I2"]
                        final_Model[ "J&B" ][ dnJunc ] = [previous_dnJunc, dnJunc + "I1"]
                        final_Model[ "dnJuncPair" ][ juncBasins[2]] = dnJunc+"I2"
                        final_Model[ "dnJuncPair" ][ juncBasins[1] ] = dnJunc+"I2"
                        final_Model[ "dnJuncPair" ][ juncBasins[0 ]  ] =  dnJunc + "I1"
                        final_Model[ "dnJuncPair" ][ dnJunc+"I2" ] = dnJunc + "I1"
                        final_Model[ "dnJuncPair" ][ dnJunc + "I1" ] = dnJunc
                        final_Model[ "dnJuncPair" ][ previous_dnJunc ] = dnJunc
                    elif len(juncBasins) > 1 and len(juncBasins) %2 == 1:
                        num_interim_juncs = len(juncBasins)
                        for i in range(0,num_interim_juncs):
                            dif_ = num_interim_juncs - i - 1
                            ji = dif_ - 1
                            intermed_junc =  "{0}I{1}".format(dnJunc,dif_)
                            if i == 0 :
                                basin_2 = juncBasins[dif_]
                                basin_1 = juncBasins[ ji ]
                                final_Model[ "J&B" ][ intermed_junc ] = [basin_1, basin_2]
                                final_Model[ "dnJuncPair" ][ basin_2 ] = intermed_junc
                                final_Model[ "dnJuncPair" ][ basin_1 ] = intermed_junc
                                previous_interJunc = intermed_junc
                            elif i > 0 and i < num_interim_juncs - 1 :
                                basin_1 = juncBasins[ (ji) ]
                                final_Model[ "J&B" ][ intermed_junc ] = [ basin_1 , previous_interJunc]
                                final_Model[ "dnJuncPair" ][ basin_1 ] = intermed_junc
                                final_Model[ "dnJuncPair" ][ previous_interJunc ] = intermed_junc
                                previous_interJunc = intermed_junc
                            elif ji==0:
                                basin_1 = juncBasins[ (ji) ]
                                final_Model[ "J&B" ][ intermed_junc ] = [  basin_1, previous_interJunc ]
                                final_Model[ "J&B" ][ dnJunc ] = [ previous_dnJunc , intermed_junc ]
                                final_Model[ "dnJuncPair" ][ basin_1 ] = intermed_junc
                                final_Model[ "dnJuncPair" ][ previous_interJunc ] = intermed_junc
                                final_Model[ "dnJuncPair" ][ intermed_junc ] = dnJunc
                                final_Model[ "dnJuncPair" ][ previous_dnJunc ] = dnJunc
                                previous_interJunc = None
                    elif len(juncBasins) > 1 and len(juncBasins) %2 ==0:
                        num_interim_juncs = len (juncBasins)
                        for i in range(0,num_interim_juncs):
                            dif_ = num_interim_juncs - i - 1
                            ji = dif_ -1
                            if i == 0 :
                                intermed_junc =  "{0}I{1}".format(dnJunc,dif_)
                                basin_2 = juncBasins[dif_]
                                basin_1 = juncBasins[ ji]
                                final_Model[ "J&B" ][ intermed_junc ] = [basin_1, basin_2]
                                final_Model[ "dnJuncPair" ][ basin_1 ] = intermed_junc
                                final_Model[ "dnJuncPair" ][ basin_2 ] = intermed_junc
                                previous_interJunc = intermed_junc
                            elif i > 0 and i < num_interim_juncs - 1 :
                                intermed_junc = "{0}I{1}".format (dnJunc , dif_)
                                basin_2 = juncBasins[ji]
                                final_Model[ "J&B" ][ intermed_junc ] = [ basin_2 , previous_interJunc]
                                final_Model[ "dnJuncPair" ][ basin_2 ] = intermed_junc
                                final_Model[ "dnJuncPair" ][ previous_interJunc ] = intermed_junc
                                previous_interJunc = intermed_junc
                            elif ji==0:
                                intermed_junc = "{0}I{1}".format (dnJunc , dif_)
                                basin_2 = juncBasins[ ji]
                                final_Model[ "J&B" ][ intermed_junc ] = [ basin_2 , previous_interJunc]
                                final_Model[ "dnJuncPair" ][ basin_2 ] = intermed_junc
                                final_Model[ "dnJuncPair" ][ previous_interJunc ] = intermed_junc
                                final_Model[ "dnJuncPair" ][ intermed_junc ] = dnJunc
                                final_Model[ "dnJuncPair" ][ previous_dnJunc ] = dnJunc
                                previous_interJunc = None
                cnt +=1
                previous_dnJunc = dnJunc
                rn = len(juncBasins)
                tbs = [' __________/']*rn
                tbs[0] = '|__/'
                print('|\t/-{0}'.format ('\t/-'.join (map (str , juncBasins))))
                print('{0}'.format(''.join(map(str,tbs))))
                print('|-{0}'.format (dnJunc))
                print('|')
                print('|')
            print('Sub Basin Junction Divides')
            print(''.join(map(str,['%']*200)))
            tbs = ['\t']
            tb_cnt = 1
            for jp in (final_Model['J&B'].keys()):
                juncBasins = final_Model['J&B'][jp]
                tbs = [' __________/']*2
                tbs[0] = '|__/'
                print('| \t/-{0}'.format ('\t/-'.join (map (str , juncBasins))))
                if 'J' in juncBasins[0]:
                    tbs[1] = '   ________________/'
                else:
                    pass
                print('{0}'.format (''.join (map (str , tbs))))
                print('|-{0}'.format (jp))
                print('\n\n')

            return final_Model





        def break_subreach_fc_into_hms_features(shp_folder , subreach_fc ,
                                                sub_reach_id_field,
                                                subcatchment_name_field='On_SubReach_ID',
                                                unitnumber_field="UnitNumber",
                                                drains_to_field='Drains_To_SubReach'):
            """Creates two sets of GIS feature classes reflecting HEC-HMS required attribute data."""
            sr = arcpy.Describe (subreach_fc).spatialReference #Spatial reference of input subreach fc

            # Dissolves reaches on tributary on Unit Number
            disolved_reaches = arcpy.Dissolve_management (in_features=subreach_fc ,
                                                          dissolve_field=unitnumber_field ,
                                                          multi_part="MULTI_PART")

            intersection_fc = os.path.join (shp_folder ,
                                            '{0}_Intersections.shp'.format (os.path.splitext(os.path.basename (subreach_fc))[0]))
            if arcpy.Exists(intersection_fc):
                arcpy.Delete_management(intersection_fc)

            arcpy.Intersect_analysis (disolved_reaches , out_feature_class=intersection_fc ,
                                      cluster_tolerance=5 , join_attributes='ALL' , output_type='POINT')

            junc_fc , sr_dict = create_junctions(shp_folder,sr, subreach_fc, disolved_reaches,
                                                            intersection_fc,
                                                            subreach_field_name=sub_reach_id_field,
                                                            unit_number_field = unitnumber_field)

            basin_fc = create_basins (shp_folder , subcatchment_fc , junc_fc , sub_reach_fc , sr_dict,
                                           sub_catchment_field=subcatchment_name_field ,
                                           subreach_name_field=sub_reach_id_field ,
                                           unitNumber_field=unitnumber_field ,
                                           drains_to_field=drains_to_field,
                                      isLevel1=self.isLevel1)

            process_hms_basin(basin_fc,unitnumber_field)



        def get_feature_extents(subcatchment_fc):
            """Returns Max and Min Coordinate Extents, returns a cross section."""
            description = arcpy.Describe(subcatchment_fc)
            ex_North = float(description.extent.YMax)+500.00
            ex_South = float(description.extent.YMin)-500.00
            ex_West = float(description.extent.XMin)-500.00
            ex_East = float(description.extent.XMax)+500.00
            return {"North":ex_North, "South":ex_South, "East":ex_East, "West":ex_West}

        self.add_unitnumber_field ()

        break_subreach_fc_into_hms_features(self.shp_folder, self.subreach_fc,
                                            drains_to_field=self.drains_to_field,
                                            subcatchment_name_field=self.subcatchment_name_field,
                                            sub_reach_id_field=self.subreach_name_field,
                                            unitnumber_field=self.unitNumber_field)

    def run_model_creation(self):
        print('Creating HEC-HMS Model: {0}'.format(self.hms_filename))
        print('\t|-Creating Control file:\n\t\t|-{0}'.format (self.control_title))
        self.write_control()
        print('\t|-Creating baseline condition basin file:\n\t\t|-{0}'.format (self.basin_title))
        # sub_basins = self.write_basin_files(subcatchment_fc, subreach_fc, subcatchment_name_field,
        #                          subreach_name_field, subreach_drains_to_field)
        print('\t|-Creating Meteorologic files:')
        # self.write_meteorolgical_files(sub_basins)
        # print('\t|-Creating Run files:'
        # self.write_runs()

    def write_control(self, description=""):
        duration = self.duration #in Hrs
        time_interval = self.time_step  # in Mins
        start_date = self.start_datetime
        fn = os.path.join (self.folder_path , "{0}.control".format (self.control_title))
        now = datetime.datetime.now ()
        end_date = start_date+ timedelta (hours=duration)
        start_line = "Run: {0}\n".format (self.control_title)
        l1 = "\t Description: {0}\n".format (description)
        l2 = "\t Last Modified Date: {0}\n".format (now.strftime("%d %B %Y"))  # DATE 31, Month Full Name, Year
        l3 = "\t Last Modified Time: {0}\n".format (now.strftime("%H:%M:%S"))  # XX:XX Military Time
        l4 = "\t Start Date: {0}\n".format (start_date.strftime("%d %B %Y"))  # DATE 31, Month Full Name, Year
        l5 = "\t Start Time: 00:00\n"  # XX:XX Military Time
        l6 = "\t End Date: {0}\n".format (end_date.strftime("%d %B %Y"))  # DATE 31, Month Full Name, Year
        l7 = "\t End Time: {0}\n".format (end_date.strftime("%H:%M:%S"))  # XX:XX Military Time
        l8 = "\t Time Interval: {0}\n".format (time_interval)  # Int in minutes.
        end_line = "End:\n\n"
        lines = [ start_line , l1 , l2 , l3 , l4 , l5 , l6 , l7 , l8 , end_line ]
        write_lines (fn , lines , False)

    def write_basin_files(self):

        #Local Variables
        fn = os.path.join (self.folder_path , "{0}.basin".format (self.hms_filename))

        def write_subbasin(basin, x, y, area, downstream, tc, r, adjoining_junction):
            start = "Subbasin: {0}\n".format (basin)
            l2 = "\t Canvas X: {0:.2f}\n".format(x)
            l3= "\t Canvas Y: {0:.2f}\n".format(y)
            l4 = "\t Label X: -14.0\n".format()
            l5 = "\t Label Y: -14.0\n".format()
            l6 = "\t Area: {0:.5f}\n".format (area) # in square miles
            l7 = "\t Downstream: {0}\n\n".format (adjoining_junction)
            l8 = "\t Canopy: None\n\n"
            l9 = "\t Surface: None\n\n"
            l10 = "\t Transform: Clark\n\n"
            l11 = "\t Time of Concentration: {0:.2f}\n".format(tc) # in hours
            l12 = "\t Storage Coefficient: {0:.2f}\n\n".format (r) # in hours
            l13 = "\t Baseflow: None\n\n"
            end = "End:\n\n"
            basin_lines = [start, l2, l3, l4, l5, l6, l7, l8, l9, l10, l11,l12, l13, end]
            pass

        def write_junction(junc, x, y, description, adjoining_ds_feature):
            start = "Junction: {0}\n".format(junc)
            l2 = "\t Description: {0}\n".format(description)
            l3 = "\t Canvas X: {0:.2f}\n".format(x)
            l4 = "\t Canvas Y: {0:.2f}\n".format(y)
            l5 = "\t Label X: 14.0\n"
            l6 = "\t Label Y: 14.0\n"
            l7 = "\t Downstream: {0}\n".format(adjoining_ds_feature)
            end = "End:\n\n"
            junction_lines = [start, l2, l3, l4, l5, l6,l7, end]
            write_lines(fn, junction_lines, True)

        def write_basin(version=3.4):
            """
            """
            now = datetime.datetime.now()
            start = "Basin: {0}".format(self.watershed)
            l1 = "\t Last Modified Date: {0:%d} {0:%B} {0:%Y}\n".format(now)
            l2 = "\t Last Modified Time: {0:%H}:{0:%M}:{0:%S}\n".format(now)
            l3 = "\t Version: {0:.1f}\n".format(version)
            l4 = "\t Unit System: English\n"
            l5 = "\t Missing Flow To Zero: No\n"
            l6 = "\t Enable Flow Ratio: No\n"
            l7 = "\t Allow Blending: No\n"
            l8 = "\t Compute Local Flow At Junctions: No\n\n"
            l9="\t Enable Sediment Routing: No\n\n"
            l10="\t Enable Quality Routing: No" \
                "n"
            end="End:\n\n"
            basin_lines = [ start, l1, l2, l3, l4, l5 , l6, l7, l8, l9, l10, end]
            write_lines(fn, basin_lines, True)

        def write_basin_schematic(ex_North, ex_South, ex_West, ex_East, ):
            """
            "Basin Schematic Properties:\n"
             "\t Last View N:  {0:.16E}\n".format(Decimal(ex_North)).replace("+","")
             "\t Last View S:  {0:.16f}\n".format(Decimal(ex_South)).replace("+","")
             "\t Last View W:  {0:.16f}\n".format(Decimal(ex_West)).replace("+","")
             "\t Last View E:  {0:.16f}\n".format(Decimal(ex_East)).replace("+","")
             "\t Maximum View N:  {0:.16E}\n".format(Decimal(ex_North)).replace("+","")
             "\t Maximum View S:  {0:.16f}\n".format(Decimal(ex_South)).replace("+","")
             "\t Maximum View W:  {0:.16f}\n".format(Decimal(ex_West)).replace("+","")
             "\t Maximum View E:  {0:.16f}\n".format(Decimal(ex_East)).replace("+","")
             "\t Extent Method: Elements"
             "\t Buffer: 0"
             "\t Draw Icons: Yes"
             "\t Draw Icon Labels: Yes"
             "\t Draw Map Objects: No"
             "\t Draw Gridlines: Yes"
             "\t Draw Flow Direction: No"
             "\t Fix Element Locations: No"
            "\t End:\n\n"
            """

        if os.path.exists(fn):
            os.remove(fn)

        write_basin()

    def write_meteorolgical_files(self, sub_basins):
        """Creates Meteorolgoical files """

        def write_met_description(fn, storm, basin_title, version=3.4):
            now = datetime.datetime.now()
            met_title = "{0} ({1})".format(self.annual_exceedance[storm],  self.storm_event_dict[storm])
            start_line = "Meteorology:: {0} \n".format(met_title)
            l1 = '\t Description: {0} Frequency Storm Event. HCFCD meteorological {1}\n'.format(met_title,
                                                                                               self.region)
            l2 = '\t Last Modified Date: {0}'.format(now.strftime("%d %B %Y"))
            l3 = '\t Last Modified Time: {0}\n'.format(now.strftime("%H:%M:%S"))
            l4 = '\t Version: {0}\n'.format (version)
            l5 = '\t Precipitation Method: Frequency Based Hypothetical\n'
            l6 = '\t Radiation Method: None\n'
            l7 = '\t Snowmelt Method: None\n'
            l8 = '\t Evapotranspiration Method: No Evapotranspiration'
            l9 = '\t Evapotranspiration Method: No Evapotranspiration'
            l10 = '\t Use Basin Model: {0}'.format(basin_title)
            end = "End:\n\n"
            lines = [start_line, l1, l2, l3, l4, l5, l6, l7, l8, l9, l10, end]
            write_lines (fn , lines , False)
            return met_title

        def write_met(fn, storm, depths, time_step=self.time_step):
            """ Applies Base Meteorolgical Infomratinn. """
            ex_freq = {10:10, 25:4, 50:2, 100:1, 500:0.2}
            start_line = "\t Precip Method Parameters: Frequency Based Hypothetical\n"
            l1 = '\t Exceedence Frequency: {0}\n'.format(ex_freq[storm])
            l2 = '\t Single Hypothetical Storm Size: Yes'
            l3 = '\t Convert From Annual Series: {0}\n'.format('Yes' if storm not in range(2,1000) else 'No')
            l4 = '\t Convert to Annual Series: {0}\n'.format ('Yes' if storm in range (2 , 1000) else 'No')
            l5 = '\t Storm Size: 0.01\n'
            l6 = '\t Total Duration: 1440\n'
            l7 = '\t Time Interval: {0}\n'.format(time_step)
            lines = [start_line, l1, l2, l3, l4, l5, l6, l7]
            for i in range (0,11):
                if i <= 6 :
                    if i == 0:
                        depth = "\t Depth: 0.0\n"#in inches
                        lines.append(depth)
                        depth = "\t Depth: {0}\n".format(depths[i]) #in inches
                        lines.append(depth)
                    else:
                        depth = "\t Depth: {0}\n".format(depths[i]) #in inches
                        lines.append(depth)
                else:
                    lines.append("\t Depth: 0.0\n".format(depths[i]))
            end = "End:\n\n"
            lines.append(end)
            write_lines(fn, lines, True)

        def add_subbasins(list_of_basin_names, fn):
            """Adds all subbasins."""
            for basin in list_of_basin_names:
                sb = "Subbasin: {0}".format(basin)
                eb = "End:\n\n"
                write_lines(fn, [sb,eb], True)

        ref_csv = None
        df = None

        if self.isAtlas:
            ref_csv = ".{0}_AtlasP.csv".format (self.region)
            df = pd.read_csv (ref_csv)
        else:
            ref_csv = ".{0}_Precip.csv".format (self.region)
            df = pd.read_csv (ref_csv)

        for storm in self.storm_events:
            met_name = "{0}_{1}YR".format (self.annual_exceedance[ storm ] ,
                                           self.storm_event_dict[ storm ])  # Define Met name base on storm event
            omet_name = met_name.replace("%","_").replace("-","_").replace(" ","_")
            fn = os.path.join (self.folder_path , "{0}.met".format (omet_name))
            depths = df[self.storm_events[storm]].tolist()
            met_title = write_met_description(fn, storm, self.basin_title)
            self.met_titles[storm] = met_title
            write_met(fn, storm, depths)
            add_subbasins(sub_basins, fn)
            print("\t\t|-{0} Created!".format (met_title))

    def write_runs(self, run_file_path):
        fn = os.path.join (run_file_path , "{0}.run".format (self.watershed))
        now = datetime.datetime.now()
        control_title = self.control_title
        basin_title = self.basin_title
        def write_run(run_file_name,  precip_title,
                      description, isfirst = False):
            start_line = "Run: {0}\n".format(precip_title)
            l1 = "\t Default Description: Yes\n"
            l2 = "\t Log File: {0}.log\n".format(precip_title.replace("%","_").replace(" ","_").replace("-","_").replace(".","_"))
            l3 = "\t DSS File: {0}.dss\n".format(run_file_name)
            l4 = "\t Basin: {0}\n".format(basin_title)
            l5 = "\t Precip: {0}\n".format(precip_title)
            l6 = "\t Control: {0}\n".format(control_title)
            l7 = "\t Precip Last Execution Date: {0}\n".format(now.strftime("%d %B %Y"))
            l8 = "\t Precip Last Execution Time:: {0}\n".format(now.strftime("%H:%M:%S"))
            l9 = "\t Basin Last Execution Date: {0}\n".format(now.strftime("%d %B %Y"))
            l10 = "\t Basin Last Execution Time: {0}\n".format(now.strftime("%H:%M:%S"))
            end_line = "End:\n\n"
            lines = [start_line, l1, l2, l3, l4, l5, l6, l7, l8, l9, l10, end_line]
            if isfirst:
                write_lines(fn,lines,append=False)
            else:
                write_lines(fn, lines,append=True)

        for i, storm in enumerate(self.storm_events):
            met_title = self.met_titles[storm]
            if i == 0:
                write_run(run_file_path, met_title, description='', isfirst=True)
            else:
                write_run (run_file_path , met_title, description='')
            print('\t\t|-{0} Created!'.format(met_title))


if __name__ == "__main__":
    mainstem = 'W100-00-00'
    hms_filename = 'HAlls Ahead?'
    # sub_catchment_fc = r'C:\Projects\HMS_Test_Shp\P118_Drainage_Areas.shp'
    # sub_reach_fc  = r'C:\Projects\HMS_Test_Shp\P118_Sub_Reaches.shp'
    sub_catchment_fc = r'C:\Projects\HMS_Test_Shp\W100DA.shp'
    sub_reach_fc  = r'C:\Projects\HMS_Test_Shp\W100_Sub_Reaches.shp'
    sub_reach_id_field = "Sub_Reach_"
    sub_catchment_field = "On_Sub_Rea"
    drains_to_field_ = "Drains_To_"
    start_date = datetime.date(year=2019, month=9, day=9)
    out_put_folder = 'C:\\Users\\AGovea\\Documents\\SHP\\W100'
    isLevel1 = False

    thing = HMS_Model(mainstem, hms_filename, sub_catchment_fc,sub_reach_fc,start_date,
                      out_put_folder,
                      subcatchment_name_field=sub_catchment_field,
                      subreach_name_field=sub_reach_id_field,
                      sr_drains_to_field=drains_to_field_,
                      isLevel1=isLevel1)

