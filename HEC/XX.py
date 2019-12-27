import arcpy
import os
from bisect import  bisect_left

def get_intersect_clusters(intersection_points,subcatchment_name_field ):
    """Identifies intersection of dissolved tributaries and attributes upstream and downstream segments"""
    pts = {'pts': [ ] , 'Xs': [ ] , 'Ys': [ ] , 'FID': [ ]}

    with arcpy.da.SearchCursor (intersection_points, ("OBJECTID" , subcatchment_name_field , "SHAPE@")) as oC:
        cnt = 0
        clusters = {}
        for row in oC:
            pnt = row[ 2 ].firstPoint
            unit = str (row[ 1 ])
            fid = row[ 0 ]
            if cnt == 0:
                pts[ 'pts' ].append (pnt)
                pts[ 'FID' ].append (fid)
                pts[ 'Xs' ].append (round(pnt.X,2))
                pts[ 'Ys' ].append (round(pnt.Y,2))
                clusters[ fid ] = {'pnt': pnt , 'downstream': unit , 'upstream': [ ] , 'count': 0}
            else:
                if round(pnt.X,2) in pts[ 'Xs' ] and round(pnt.Y in pts[ 'Ys' ],2):
                    fid = pts[ 'FID' ][ pts[ 'Ys' ].index (pnt.Y) ]
                    id_unit = clusters[ fid ]['downstream']
                    if id_unit != unit:
                        clusters[ fid ][ 'upstream' ].append (unit)
                        clusters[ fid ][ 'count' ] += 1
                else:
                    pts[ 'pts' ].append (pnt)
                    pts[ 'Xs' ].append (round(pnt.X,2))
                    pts[ 'Ys' ].append (round(pnt.Y,2))
                    pts[ 'FID' ].append (fid)
                    clusters[ fid ] = {'pnt': pnt , 'downstream': unit , 'upstream': [ ] , 'count': 0}
            cnt += 1
    return clusters

def create_reach_segment(upstream_point, downstream_point, polyline, identifier="HA",
                         junctionID=0, isEnd=False):
    """Returns a polyline based on two bounding vertices found on the line. """
    part = polyline.getPart (0)
    total_length = polyline.length
    lineArray = arcpy.Array ()
    #Identifies bounding vertices and associated distance along the line.
    if isEnd:
        last_point= polyline.lastPoint
        upstream_point_dist = round (total_length - polyline.measureOnLine (downstream_point , False) , 2)
        downstream_point_dist = round(total_length -  polyline.measureOnLine (last_point , False), 2)
    else:
        upstream_point_dist = round (total_length - polyline.measureOnLine (upstream_point , False) , 2)
        downstream_point_dist = round(total_length -  polyline.measureOnLine (downstream_point , False), 2)
    #Retrieves all vertices between bounding vertices of a polyline.
    for pnt in part:
        pnt_dist = round(total_length -  polyline.measureOnLine (pnt , False), 2)
        if pnt_dist <= upstream_point_dist and pnt_dist>=downstream_point_dist:
            if lineArray.count == 0:
                lineArray.add(upstream_point)
                lineArray.add (pnt)
            else:
                lineArray.add (pnt)
    #Makes ending downstream point is added to array
    if lineArray[lineArray.count -1].X != downstream_point.X and lineArray[lineArray.count -1].Y != downstream_point.Y:
        lineArray.add(downstream_point)

    #Creates a new polyline from point array
    new_polyline = arcpy.Polyline(lineArray)
    identifier = str(identifier)
    junc = identifier
    if identifier.upper().find('J') == len(identifier)-1:
        identifier =identifier.upper()[0:len(identifier)-1] + 'R'
    else:
        identifier = identifier.upper() + 'R'
    return {'name':identifier,'polyline':new_polyline, 'DJunc':junc, 'JuncID':junctionID}

def create_reach_segments(clusters, intersection_points, dissolve_fc, subcatchment_name_field='UnitNumber'):
    receiving_units = list(sorted(list (set ([ clusters[ cl ][ 'downstream' ] for cl in clusters ])), reverse=False))
    reaches = {}
    basins = {}
    junctions = {}
    #Iterates over all dissolved Reaches to begin estimating each reach length
    for k, unit_no in enumerate(receiving_units):
        un_exp = "{0} LIKE '{1}'".format(subcatchment_name_field,unit_no)
        junctions[unit_no] = {'segmentLengths':[], 'segment_ids':[],
                              'names':[], 'end':[], 'upstream':[]}
        pl = None
        start_point = None
        last_point = None
        total_length = None
        pl  = None
        reaches[unit_no] = {}
        approved_cluster_ids = list(clusters.keys())
        with arcpy.da.SearchCursor (dissolve_fc , (subcatchment_name_field , "SHAPE@"), un_exp) as plC:
            for row in plC:
                un = str (row[ 0 ])
                pl = row[ 1 ]
                total_length = pl.length
                start_point = pl.firstPoint
                last_point = pl.lastPoint
                #Identifies junctions of upstream tributary systems on the observed stream name
                with arcpy.da.SearchCursor (intersection_points , ("OBJECTID" , subcatchment_name_field, "SHAPE@") ,
                                    where_clause="{0} LIKE '{1}'".format (subcatchment_name_field,un)) as pntC:
                    for pnt in pntC:
                        oid = pnt[0]
                        if oid in approved_cluster_ids:
                            upstream = clusters[oid]['upstream']
                            str_us_list = ', '.join(map(str,upstream))
                            reach_dist = round(total_length - pl.measureOnLine (pnt[ 2].firstPoint , False),2)
                            end_point = pnt[2].firstPoint
                            if reach_dist > 5.0:
                                name = "{0}_{1:.0f}J".format(un, reach_dist)
                                junctions[ unit_no ]['segmentLengths'].append(round(reach_dist,0))
                                junctions[ unit_no ][ 'segment_ids' ].append (oid)
                                junctions[ unit_no ][ 'names' ].append (name)
                                junctions[ unit_no ][ 'end' ].append (end_point)
                                junctions[ unit_no ][ 'upstream' ].append (upstream)
        sorted_segment_lengths = list(sorted(junctions[unit_no]['segmentLengths'], reverse=True))
        #Sorts Points by Tributary River Statoining form Upstream
        sorted_segment_ids = []
        sorted_names = []
        sorted_up_names = ['{0}_{1:.0f}J'.format(unit_no,total_length)]
        sorted_ends = []
        upstream_points = [start_point]
        sorted_upstream_length = [total_length]
        junctions[ unit_no ]['length_to_start']  =   sorted_upstream_length
        upstream_point_id = []

        for seg in sorted_segment_lengths:
            seg_index = junctions[unit_no]['segmentLengths'].index(seg)
            sorted_segment_ids.append(junctions[unit_no]['segment_ids'][seg_index])
            sorted_names.append (junctions[ unit_no ][ 'names' ][ seg_index ])
            sorted_ends.append (junctions[ unit_no ][ 'end' ][ seg_index ])
            upstream_points.append (junctions[ unit_no ][ 'end' ][ seg_index ])
        junctions[ unit_no ]['up_names'] =  sorted_up_names
        junctions[ unit_no ][ 'length_to_end' ] = sorted_segment_lengths
        junctions[ unit_no ][ 'end_id' ] = sorted_segment_ids
        junctions[ unit_no ][ 'names' ] = sorted_names
        junctions[ unit_no ][ 'up_point' ] = upstream_points
        junctions[ unit_no ][ 'end_point' ] = sorted_ends

        #Adds end point of polyline to list of junctions
        junctions[ unit_no ][ 'length_to_end' ].append(0.0)
        junctions[ unit_no ][ 'end_id' ].append(9999)
        junctions[ unit_no ][ 'names' ].append("{0}_0000J".format(unit_no))
        junctions[ unit_no ][ 'end_point' ].append(last_point)
        junctions[ unit_no ]['length_to_start'] +=   junctions[ unit_no ][ 'length_to_end' ]
        junctions[ unit_no ]['up_names'] += junctions[ unit_no ][ 'names' ]
        for i, end_point in enumerate(junctions[ unit_no ][ 'end_point' ]):
            if i != 0 :
                r = create_reach_segment(junctions[ unit_no ][ 'up_point' ][i],
                                         end_point,
                                         pl,
                                         identifier=junctions[ unit_no ][ 'names' ][i-1],
                                         junctionID=junctions[ unit_no ][ 'end_id' ][i-1] ,
                                         isEnd=False)
                reach = r['name']
                reaches[ unit_no ][reach] = r
            elif i == 0:
                name =   "{0}_{1:.0f}J".format(junctions[ unit_no ][ 'names' ][i].split('_')[0], total_length)
                r = create_reach_segment(junctions[ unit_no ][ 'up_point' ][i],
                                         end_point,
                                         pl,
                                         identifier=name,
                                         junctionID=9999 ,
                                         isEnd=False)
                reach = r['name']
                reaches[ unit_no ][reach] = r

    return reaches, junctions

def break_subreach_fc_into_hms_features(export_gdb, subreach_fc, subcatchment_fc,
                                        subcatchment_name_field='UnitNumber',
                                        subreach_name_field="Sub_Reach_ID", ):
    """Creates two sets of GIS feature classes reflecting HEC-HMS required attribute data."""
    sr = arcpy.Describe (subreach_fc).spatialReference
    #Dissolves reaches on tributare
    disolved_reaches = arcpy.Dissolve_management (in_features=subreach_fc,
                                                  dissolve_field=subcatchment_name_field,
                                                  multi_part="MULTI_PART")

    intersection_fc = os.path.join(export_gdb,'{0}_Intersections'.format(os.path.basename(subreach_fc)))

    arcpy.Intersect_analysis(disolved_reaches,out_feature_class=intersection_fc,
                             cluster_tolerance=2,join_attributes='ALL',output_type='POINT')

    clusters = get_intersect_clusters(intersection_fc, subcatchment_name_field)

    reaches, junctions = create_reach_segments(clusters, intersection_fc, disolved_reaches)

    #Creates Junction FC and Required Fields to Attribute for each Reach
    junc_fc_name = '{0}_HMSJunctions'.format(os.path.basename(subreach_fc))
    junc_fc = os.path.join(export_gdb, '{0}'.format(junc_fc_name))
    if arcpy.Exists(junc_fc):
        arcpy.Delete_management(junc_fc)

    if arcpy.Exists(intersection_fc):
        arcpy.Delete_management(intersection_fc)

    arcpy.CreateFeatureclass_management(export_gdb,junc_fc_name,'POINT', spatial_reference=sr)
    arcpy.AddField_management(junc_fc,subcatchment_name_field,'TEXT',field_length=14)
    arcpy.AddField_management(junc_fc,'Junction','TEXT',field_length=30)
    arcpy.AddField_management (junc_fc , 'JuncID' , 'SHORT' )
    arcpy.AddField_management (junc_fc , 'StaDist' , 'DOUBLE')

    #Creates junction features
    with arcpy.da.InsertCursor (junc_fc , (subcatchment_name_field , 'Junction' , 'JuncID', 'StaDist','SHAPE@')) as jIC:
        for unitNumber in junctions:
            print('CREATING:  {0}'.format(unitNumber))
            for j, junc in enumerate(junctions[ unitNumber ][ 'names' ]):
                if j == 0:
                    nam = junctions[ unitNumber ]['up_names']  [j]
                    print('\t{0}:{1}'.format(j,nam))
                    point = junctions[ unitNumber ][ 'up_point' ][j]
                    ul = junctions[ unitNumber ][ 'length_to_start' ][j]
                    urow = (unitNumber,nam, 9999, ul, point)
                    jIC.insertRow(urow)
                    print('\t{0}:{1}'.format(j,junc))
                    juncID = junctions[ unitNumber ][ 'end_id' ][j]
                    point = junctions[ unitNumber ][ 'end_point' ][j]
                    el = junctions[ unitNumber ][ 'length_to_end' ][j]
                    row = (unitNumber,junc, juncID, el, point)
                    jIC.insertRow(row)
                else:
                    print('\t{0}:{1}'.format(j,junc))
                    juncID = junctions[ unitNumber ][ 'end_id' ][j]
                    point = junctions[ unitNumber ][ 'end_point' ][j]
                    el = junctions[ unitNumber ][ 'length_to_end' ][ j ]
                    row = (unitNumber , junc , juncID , el , point)
                    jIC.insertRow(row)


    updated_reaches = os.path.join(export_gdb,'{0}_Identified_Reaches'.format(os.path.basename(subreach_fc)))

    if arcpy.Exists(updated_reaches):
        arcpy.Delete_management(updated_reaches)
    #Creats Feature Class
    arcpy.CopyFeatures_management(subreach_fc,updated_reaches)
    arcpy.AddField_management(updated_reaches,'Up_Junction','TEXT',field_length=30)
    arcpy.AddField_management(updated_reaches,'Dn_Junction','TEXT',field_length=30)
    # arcpy.AddField_management(updated_reaches,'Up_Station','DOUBLE', field_precision=0)
    # arcpy.AddField_management (updated_reaches , 'Dn_Station' , 'DOUBLE' , field_precision=0)
    for unitNumber in junctions:
        exp = '"{0}"'.format(subcatchment_name_field) +" LIKE '{0}'".format( unitNumber)
        flds = (subreach_name_field, 'Up_Junction', 'Dn_Junction')
        print('::{0}::'.format(unitNumber))
        with arcpy.da.UpdateCursor(updated_reaches, flds, exp) as urUC:
            for row in urUC:
                up_sta = str(row[0])[-4:] + "00"
                up_sta_flt = float(int(up_sta))
                n = bisect_left(a=list(sorted(junctions[ unitNumber ][ 'length_to_start' ])), x=up_sta_flt)
                up_junc_length_index = len(junctions[ unitNumber ][ 'length_to_start' ]) - 1 -n
                if up_junc_length_index < 0:
                    up_junc_length_index += 1
                dn_junc_length_index = up_junc_length_index + 1
                print('\t|-search: {0}, {1} '.format(up_sta_flt, row[0]))
                print('\t\t|-{0}\n\t\t|-bounding juncs: ({1}, {2})'.format(list(sorted(junctions[ unitNumber ][ 'length_to_start' ])),
                                                                      up_junc_length_index,
                                                                      dn_junc_length_index))
                up_junc = junctions[ unitNumber ][ 'up_names' ] [up_junc_length_index]
                dn_junc = junctions[ unitNumber ][ 'up_names' ] [dn_junc_length_index]
                urUC.updateRow((row[0],up_junc,dn_junc))




    # #Creates Reach FC and Required Fields to Attribute for each Reach
    # reach_fc_name = '{0}_HMSReaches'.format(os.path.basename(subreach_fc))
    # reach_fc = os.path.join(shp_folder, '{0}.shp'.format(reach_fc_name))
    # if arcpy.Exists(reach_fc):
    #     arcpy.Delete_management(reach_fc)
    #
    # arcpy.CreateFeatureclass_management(shp_folder,reach_fc_name,'POLYLINE', spatial_reference=sr)
    # arcpy.AddField_management(reach_fc,subcatchment_name_field,'TEXT',field_length=14)
    # arcpy.AddField_management(reach_fc,'Reach','TEXT',field_length=30)
    # arcpy.AddField_management (reach_fc , 'Junction' , 'TEXT' , field_length=30)
    # arcpy.AddField_management (reach_fc , 'JuncID' , 'SHORT' )
    #
    # #Populates Feature Classes with Reach Segments created
    # with arcpy.da.InsertCursor(reach_fc,(subcatchment_name_field, 'Reach', 'Junction', 'JuncID','SHAPE@')) as rIC:
    #     for unitNumber in reaches:
    #         for reach in reaches[unitNumber]:
    #             polyline = reaches[unitNumber][reach]['polyline']
    #             djunc = reaches[unitNumber][reach]['DJunc']
    #             juncID = reaches[unitNumber][reach]['JuncID']
    #             row = (unitNumber,reach,djunc, juncID, polyline,)
    #             rIC.insertRow(row)





    # sr_join_fc_name = '{0}_SRSJ'.format(os.path.basename(subreach_fc))
    # srt_fc = os.path.join (shp_folder , '{0}.shp'.format (sr_join_fc_name))
    # if arcpy.Exists(srt_fc):
    #     arcpy.Delete_management(srt_fc)
    # arcpy.SpatialJoin_analysis(subreach_fc,reach_fc,srt_fc,"JOIN_ONE_TO_MANY","KEEP_ALL",match_option="CLOSEST")
    #relates spatialy the drainage areas contributing to each unique reach.
    # catchment_join_fc_name = '{0}_HMS_SubBasins'.format(os.path.basename(subcatchment_fc))
    # catchment_fc = os.path.join (shp_folder , '{0}.shp'.format (catchment_join_fc_name))
    # if arcpy.Exists(catchment_fc):
    #     arcpy.Delete_management(catchment_fc)
    # arcpy.SpatialJoin_analysis(subcatchment_fc,srt_fc,catchment_fc,"JOIN_ONE_TO_MANY","KEEP_ALL",
    #                            match_option="WITHIN_A_DISTANCE",search_radius=0)



