"""

Generates Tributary XS at Intervals of a given Tributary Shape File, Then associates Vertices to LiDAR values.


By: Alex Govea


Requirements: Requires 3D Analyst to Execute Tool.

STARMap folder - L:\GIS-DataLibrary\Reference\COG\HGAC\STARMap_Feb2017

"""
import arcpy
import os
from math import sin, cos, degrees
import time
import bisect
import traceback
import gc
from Geom import *
from ArcGeom import generate_xy_stations, get_vertices, getSpatialReferencefactoryCode
from datetime import datetime, timedelta


def define_XS_Spacing(bankfull_depth, bed_slope, default_spacing=300):
    """
    source https://hecrasmodel.blogspot.com/2008/12/samuels-equation-for-cross-section.html
    :param bankful_depth: avg channel depth (avg bank elev to chan invert ) in ft.
    :param bed_slope: slope of channel.
    :return:
    """
    try:
        spacing = int(round(0.07*bankfull_depth / float(bed_slope)))
    except:
        spacing = default_spacing
    if spacing < default_spacing:
        spacing = default_spacing
    return spacing

def creat_xs_fc(outpath, outname, spatial_ref, is_shp=True):
    """Creates the 2D XS Poly Feature Class utilizing the initial tributary FC spatial reference"""
    shp = None
    if not is_shp:
        shp = os.path.join (outpath , '{0}.shp'.format (outname))
        if arcpy.Exists(shp):
            arcpy.Delete_management(shp)
        arcpy.CreateFeatureclass_management (outpath , '{0}.shp'.format (outname) , geometry_type="POLYLINE" ,
                                             has_m="DISABLED" ,
                                             has_z="DISABLED" , spatial_reference=spatial_ref)
    else:
        shp = os.path.join (outpath , '{0}'.format (outname))
        if arcpy.Exists(shp):
            arcpy.Delete_management(shp)
        arcpy.CreateFeatureclass_management (outpath , '{0}'.format (outname) , geometry_type="POLYLINE" ,
                                             has_m="DISABLED" ,
                                             has_z="DISABLED" , spatial_reference=spatial_ref)

    arcpy.AddField_management (shp , field_name="Tributary" , field_alias="Tributary" , field_type="TEXT" ,
                               field_length=25 , )

    arcpy.AddField_management (shp , field_name="Station" , field_alias="Station" , field_type="TEXT" ,
                               field_length=25 , )

    return shp

#Get a Set of Unique Trib Names in Shape File. Trib_id_key_field
def get_unique_trib_names(fc, trib_id_key_field):
    """returns a list of unique values based on values populated in the trib_id_key_field specified."""
    og_trib_list = []
    with arcpy.da.SearchCursor(fc, [trib_id_key_field]) as tribIDCursor:
        for row in tribIDCursor:
            og_trib_list.append(str(row[0]))
    return list(set(og_trib_list))

def build_trib_exp(trib_identifier, trib_key_field):
    """Establishes a SQL query expresion associating a given tributary id"""
    return '"{0}"'.format(trib_key_field) + " LIKE '%{0}%'".format(trib_identifier)


def create_xs_for_trib_fc(fc, sta_seg_length,
                          xs_interval, xs_shp, trib, trib_exp, xs_length=500.0):
    """"""

    def produce_xs_for_trib(xy_stas , trib, des_xs_length=100.0, xs_interval = 1.0):
        no_xs = len (xy_stas[ "OID" ])
        half_des_length = des_xs_length / 2.0
        xs_list = []
        for i in range (no_xs):
            xs_dict = {'Station':None,'X':[],'Y':[]}
            if i != 0:
                #Establisehes XS Station
                station = xy_stas['Stations'][i]
                xs_dict['Station'] = station
                pt1X, pt1Y = xy_stas['X'][i-1], xy_stas['Y'][i-1]
                pt2X , pt2Y = xy_stas[ 'X' ][ i ] , xy_stas[ 'Y' ][ i ]
                theta_p = np.arctan2(float(pt2Y - pt1Y), float(pt2X-pt1X))
                theta_p += pi/2.0
                if theta_p < 0:
                    theta_p += 2*pi
                #Handles differnet angles
                theta_p_deg = int(round(degrees(theta_p),0))
                if (theta_p_deg == 0) or (theta_p_deg == 180):
                    #X first, horizontal.
                    if theta_p_deg == 90:
                        theta_p -= pi
                elif (theta_p_deg == 90) or (theta_p_deg == 270):
                    #Y first, vertical.
                    if theta_p_deg == 90:
                        theta_p -= pi
                # elif (theta_p_deg > 90) and (theta_p_deg < 180):
                #     #Y first, Quardrant 2 move to Quadrant 4 add pi
                #     theta_p += pi
                # elif (theta_p_deg > 180) and (theta_p_deg < 270):
                #     #Quadrant 3 move to Quadrant 1
                #     theta_p -= pi
                # elif (theta_p_deg > 0) and (theta_p_deg < 90):
                #     # Moves Quadrant 1 to Quadrant 3
                #     pass
                # elif (theta_p_deg > 270) and (theta_p_deg < 360):
                #     #Quadrant 3 move to Quadrant 1
                #     pass


                xdist = half_des_length * cos (theta_p)
                ydist = half_des_length * sin (theta_p)
                xstart = pt2X + xdist
                ystart = pt2Y + ydist
                xdist_total =  des_xs_length* cos (theta_p)
                ydist_total = half_des_length * sin (theta_p)
                xend = xstart + xdist_total
                yend = ystart + ydist_total
                # print('\t\t\t|-Station: {0}'.format(station))
                # print('\t\t|-Center Point: ({0}, {1})\n\t\t|-XS Start: ({2}, {3})'.format(pt2X, pt2Y, xstart, ystart))
                # print('\t\t|-XS End: ({0}, {1})'.format(xend, yend))
                # print('\t\t|-Theta: {0}*\n\n'.format(theta_p_deg))
                x_int_d = abs(xs_interval * cos (theta_p))
                xp = None
                yp = None
                xi = None
                yi = None
                xs_run_length = 0.0
                xs_dict[ 'X' ].append(xstart)
                xs_dict[ 'Y' ].append(ystart)
                #"Iterates between all intervals "
                count = 0
                while xs_run_length <= des_xs_length - xs_interval:
                    xdist = -1 * xs_interval * cos (theta_p)
                    ydist = -1 * xs_interval * sin (theta_p)

                    if count == 0:
                        xi = xstart + xdist
                        yi = ystart + ydist
                        a , b = get_legs (xstart, ystart, xi, yi)
                    else:
                        xi = xp + xdist
                        yi = yp + ydist
                        a , b = get_legs (xp , yp , xi , yi)
                    xs_run_length += abs(getHypot(a, b))
                    xs_dict[ 'X' ].append (xi)
                    xs_dict[ 'Y' ].append (yi)
                    xp = xi
                    yp = yi
                    count += 1
                xs_list.append(xs_dict)
        return xs_list

    vertices, total_length = get_vertices(fc, trib_exp)
    xy_stas = generate_xy_stations(vertices,total_length, sta_seg_length)
    xs_list = produce_xs_for_trib(xy_stas,trib,des_xs_length=xs_length,  xs_interval=xs_interval)
    gc.collect()
    with arcpy.da.InsertCursor (xs_shp , [ "Tributary" , "Station" , "SHAPE@" ]) as XSinsertcursor:
        for j in range (len (xs_list)):
            station = xs_list[j]['Station']
            no_pts = len(xs_list[j]['X'])
            pnts = [ ]
            for k in range (no_pts):
                pnt  = arcpy.Point(float (xs_list[j][ 'X' ][k ]) ,
                                   float (xs_list[j][ 'Y' ][ k ]))
                pnts.append(pnt)
            ar = arcpy.Array(tuple(pnts))
            pline = arcpy.Polyline (ar)
            XSinsertcursor.insertRow ((trib , station , pline ,))

def create_trib_sdf_file(thePath, trib_fc_path, trip_exp, xs_path_, expXS, river):
    """
    based on Robert Henry's Script "writeRAS_GIS.py", the script generates HEC-RAS importable SDF files.
    """
    buildResCursor = arcpy.da.SearchCursor (trib_fc_path , ("SHAPE@") , trip_exp)
    # rowcount = len(list(i for i in buildResCursor))
    # print "Rows: " + str(rowcount)
    SurfaceLineList = [ ]
    newFile = os.path.join (thePath , river + ".sdf")
    f = open (newFile , 'w')
    print ("\t\t9|-SDF Processing Reach {0}:".format (river))  # Prints the reach
    for row2 in buildResCursor:
        partnum = 0  # Prints the current multipont's ID
        reach = river
        XSCursor = arcpy.da.SearchCursor (xs_path_ , ("SHAPE@" ) , expXS)
        rowcount = len (list (i for i in XSCursor))
        del XSCursor
        f.write ('#This file is generated by HEC-GeoRAS Beta 1 for ArcGIS' + '\n')
        f.write ('BEGIN HEADER:' + '\n')
        f.write ('DTM TYPE: TIN' + '\n')
        f.write ('DTM: \\' + '\n')
        f.write ('STREAM LAYER: \River' + '\n')
        f.write ('NUMBER OF REACHES: 1' + '\n')
        f.write ('CROSS-SECTION LAYER: \XSCutLines' + '\n')
        f.write ('NUMBER OF CROSS-SECTIONS: ' + str (rowcount) + '\n')
        f.write ('MAP PROJECTION: ' + '\n')
        f.write ('PROJECTION ZONE: ' + '\n')
        f.write ('DATUM: ' + '\n')
        f.write ('VERTICAL DATUM: ' + '\n')
        f.write ('BEGIN SPATIAL EXTENT:' + '\n')
        f.write ('XMIN: ' + '\n')
        f.write ('YMIN: ' + '\n')
        f.write ('XMAX: ' + '\n')
        f.write ('YMAX: ' + '\n')
        f.write ('END SPATIAL EXTENT:' + '\n')
        f.write ('UNITS: ' + '\n')
        f.write ('END HEADER:' + '\n')
        f.write ('\n')
        f.write ('\n')
        f.write ('BEGIN STREAM NETWORK:' + '\n')
        f.write ('ENDPOINT: , , , ' + '\n')
        f.write ('\n')
        f.write ('REACH:' + '\n')
        f.write ('STREAM ID: ' + river + '\n')
        f.write ('REACH ID: ' + reach + '\n')
        f.write ('FROM POINT: ' + '\n')
        f.write ('TO POINT: ' + '\n')
        f.write ('CENTERLINE:' + '\n')

        for part in row2[ 0 ]:
            for vertex in part:
                coords = '\t' + ("{0}, {1}, ,".format (vertex.X , vertex.Y))
                f.write (coords + '\n')
            partnum += 1

        f.write ('END:' + '\n')
        f.write ('\n')
        f.write ('END STREAM NETWORK:' + '\n')
        f.write ('\n')
        f.write ('\n')
    f.write ('BEGIN CROSS-SECTIONS:' + '\n')
    f.write ('\n')
    XSCursor = arcpy.da.SearchCursor (xs_path_ , ("SHAPE@" , 'Station', 'LOB', 'ROB') , expXS)
    xs_cursor_list = list(r for r in XSCursor)
    xs_shape = len(xs_cursor_list)
    for i, row in enumerate(xs_cursor_list):
        print('\t\t\t|-Reach Station: {0}'.format(row[1]))
        SurfaceLineList = [ ]
        pn = 0  # Prints the current multipont's ID
        # print pn
        station = str(row[ 1 ])
        if i == xs_shape - 1:
            dnst_reach_length = round(0.00,2)
        else:
            dnst_reach_length =round(float(row[ 1 ])-float(xs_cursor_list[i+1][1]),2)
        lob, rob = round(row[2], 5), round(row[3], 5)
        if rob < lob:
            lob = round(row[3], 5)
            rob = round(row[2], 5)
        f.write ('CROSS-SECTION:' + '\n')
        f.write ('STREAM ID: ' + river + '\n')
        f.write ('REACH ID: ' + river + '\n')
        f.write ('STATION: ' + str (station) + '\n')
        f.write ('NODE NAME:' + '\n')
        f.write ('BANK POSITIONS: {0},{1}'.format(lob, rob) + '\n')
        f.write ('REACH LENGTHS: {0},{1},{2}'.format(dnst_reach_length, dnst_reach_length,dnst_reach_length) + '\n')
        f.write ('NVALUES:' + '\n')
        f.write ('LEVEE POSITIONS:' + '\n')
        f.write ('INEFFECTIVE POSITIONS:' + '\n')
        f.write ('BLOCKED POSITIONS:' + '\n')
        f.write ('CUT LINE:' + '\n')

        for p in row[ 0 ]:
            # print ("Part {0}:".format(pn)) # Prints the part number

            for v in p:
                coordsXS = '\t' + ("{0}, {1}, {2}".format (round(v.X,2),
                                                           round(v.Y,2) ,
                                                           round(v.Z,2)))
                SurfaceLineList.append (coordsXS)

                f.write (coordsXS + '\n')
        pn += 1

        f.write ('SURFACE LINE:' + '\n')
        for sl in SurfaceLineList:
            f.write (sl + '\n')
        f.write ('END:' + '\n')
        f.write ('\n')

    f.write ('END CROSS-SECTIONS:' + '\n')
    f.write ('\n')

    f.close ()


def run_produce_xs(trib_fc, output_folder, outname, trib, trib_exp,
                   sta_seg_length=100, xs_interval=5.0, xs_length=500.0,isOptimized=False ):

    if out_3D_xs_path.lower().find('.gdb') != -1:
        isShp = False
    else:
        isShp = True
    if not isOptimized :
        print('\t\t0|-Producing 2D XS')
    else:
        print('\t\t5|-Producing 2D XS')

    spref = getSpatialReferencefactoryCode(trib_fc)
    nam = outname+"_{0}".format(str(trib).replace(' ','').replace('-','_'))
    shp = creat_xs_fc(output_folder, nam, spref, is_shp=isShp)
    create_xs_for_trib_fc(trib_fc, sta_seg_length, xs_interval, xs_shp=shp,
                          trib=trib,trib_exp= trib_exp, xs_length=xs_length)
    return shp


def first_past_3D_XS( out_3D_xs_path,  xs_exp, search_top_width=100.0,
                      vertices_spacing=5.0, channel_length = 1000.00, sta_spacing = 100):

    search_rad = search_top_width / 2.0
    overbank_data = []
    print('\t\t3|-Identifying Relative Overbanks per XS')
    up_invert = None
    dn_invert = None
    avg_avg_depth = 0
    feature_count = 0

    with arcpy.da.SearchCursor(out_3D_xs_path, ['OBJECTID'], xs_exp) as countCursor:
        for row in countCursor:
            feature_count += 1

    #Iterates over all XS for a given Tributary
    with arcpy.da.SearchCursor(out_3D_xs_path, ['SHAPE@', 'OBJECTID'], xs_exp) as xs3Dcursor:
        k = 1
        for i, row in enumerate(xs3Dcursor):
            length = row[0].length
            seg_leg = list(np.arange(0,length+vertices_spacing,vertices_spacing))
            cen_index = int(len(seg_leg)/2)-1
            left_index = bisect.bisect_left(seg_leg, length/2 - search_rad)
            right_index = bisect.bisect_right(seg_leg, length/2 + search_rad)
            first_point  = row[0].firstPoint
            xs_vertices_dict_left= {'Xs':[], 'Ys':[], 'Zs':[]}
            xs_vertices_dict_right = { 'Xs': [ ] , 'Ys': [ ] , 'Zs': [ ]}
            all_vertices = { 'Xs': [ ] , 'Ys': [ ] , 'Zs': [ ]}
            for part in row[0]:
                count = 0
                for vertex in part:
                    x = vertex.X
                    y = vertex.Y
                    z = vertex.Z
                    if count>= left_index and count <= cen_index:
                        xs_vertices_dict_left[ 'Xs' ].append (x)
                        xs_vertices_dict_left[ 'Ys' ].append (y)
                        xs_vertices_dict_left[ 'Zs' ].append (z)
                    elif count > cen_index and count  <= right_index:
                        xs_vertices_dict_right[ 'Xs' ].append (x)
                        xs_vertices_dict_right[ 'Ys' ].append (y)
                        xs_vertices_dict_right[ 'Zs' ].append (z)
                    else:
                        pass
                    if (i == 0) or (i == feature_count -1) :
                        all_vertices['Xs'].append(x)
                        all_vertices['Ys'].append(y)
                        all_vertices['Zs'].append(z)

                    count += 1
            #identifies local max overbanks on left and right side
            #Left Side
            left_min_invert = min(xs_vertices_dict_left['Zs'])
            left_max_invert = max(xs_vertices_dict_left['Zs'])
            left_max_index = xs_vertices_dict_left['Zs'].index(left_max_invert)

            left_x = xs_vertices_dict_left[ 'Xs' ][left_max_index]
            left_y = xs_vertices_dict_left[ 'Ys' ][left_max_index]
            a_left , b_left = get_legs (first_point.X , first_point.Y , left_x , left_y)
            left_length = abs (hypot (a_left , b_left))
            rel_left_length = round(left_length / float(length),5)


            #Right Side
            right_min_invert = min(xs_vertices_dict_left['Zs'])
            right_max_invert = max(xs_vertices_dict_right['Zs'])
            right_max_index = xs_vertices_dict_right[ 'Zs' ].index (right_max_invert)
            right_x = xs_vertices_dict_right[ 'Xs' ][right_max_index]
            right_y = xs_vertices_dict_right[ 'Ys' ][right_max_index]
            a_right , b_right = get_legs (first_point.X , first_point.Y , right_x , right_y)
            right_length = abs(hypot(a_right, b_right))


            left_depth = left_max_invert - left_min_invert
            right_depth = right_max_invert - right_min_invert
            avg_depth = 0.5 * (left_depth + right_depth)
            avg_avg_depth += avg_depth
            rel_right_length = round(right_length / float(length),5)

            if (i == 0) or (i == feature_count - 1):
                if i == 0:
                    up_invert = 0.5*(left_min_invert+right_min_invert)
                else:
                    dn_invert = 0.5*(left_min_invert+right_min_invert)



            xs_props = {"OBJECTID":row[1], "LOB":rel_left_length, "ROB":rel_right_length,
                        "AvgDepth_ft":avg_depth}

            overbank_data.append(xs_props)

            k += 1
    avg_avg_depth = avg_avg_depth / k
    stream_invert_drop = abs(up_invert - dn_invert)
    slope = stream_invert_drop / channel_length
    new_channel_spacing = int(define_XS_Spacing(avg_avg_depth,slope) )# in ft.
    if divmod(float(channel_length), float(new_channel_spacing))[0] <= 4:
        new_channel_spacing = rounddn(channel_length  / 3.0)
    print('\t\t4|-Optimized XS Spacing: {0} ft.'.format(new_channel_spacing))
    #Deletes Firt Pass XS
    if arcpy.Exists(out_3D_xs_path):
        arcpy.Delete_management(out_3D_xs_path)

    return int(new_channel_spacing)

def optimized_3D_XS_spacing(trib_fc_path, out_3D_xs_path, sdf_output_folder, trib_exp,
                     xs_exp, river, search_top_width=400.0, vertices_spacing=5.0, row_width = 30):
    search_rad = search_top_width / 2.0
    sref = getSpatialReferencefactoryCode(trib_fc_path)
    overbank_data = [ ]
    print('\t\t7|-Optimizing 3D XS')
    avg_avg_depth = 0
    with arcpy.da.SearchCursor (out_3D_xs_path , [ 'SHAPE@' , 'OBJECTID'] , xs_exp) as xs3Dcursor:
        k = 0
        new_polyline = None
        save_row = None
        for i , row in enumerate (xs3Dcursor):
            length = row[ 0 ].length
            oid = row[1]
            seg_leg = list (np.arange (0 , length + vertices_spacing , vertices_spacing))
            cen_index = int (len (seg_leg) / 2) - 1
            left_index = bisect.bisect_left (seg_leg , length / 2 - search_rad)
            right_index = bisect.bisect_right (seg_leg , length / 2 + search_rad)
            xs_vertices_dict_left = {'Xs': [ ] , 'Ys': [ ] , 'Zs': [ ]}
            xs_vertices_dict_right = {'Xs': [ ] , 'Ys': [ ] , 'Zs': [ ]}
            all_points = {'Xs': [ ] , 'Ys': [ ] , 'Zs': [ ]}
            polyline_points = []
            saved_polyline = row[0]
            for part in row[ 0 ]:
                count = 0
                for vertex in part:
                    x = vertex.X
                    y = vertex.Y
                    z = vertex.Z
                    polyline_points.append(vertex)
                    if count >= left_index and count <= cen_index:
                        xs_vertices_dict_left[ 'Xs' ].append (x)
                        xs_vertices_dict_left[ 'Ys' ].append (y)
                        xs_vertices_dict_left[ 'Zs' ].append (z)
                    elif count > cen_index and count <= right_index:
                        xs_vertices_dict_right[ 'Xs' ].append (x)
                        xs_vertices_dict_right[ 'Ys' ].append (y)
                        xs_vertices_dict_right[ 'Zs' ].append (z)
                    else:
                        pass
                    count += 1
                    all_points['Xs'].append(x)
                    all_points['Ys'].append(y)
                    all_points['Zs'].append(z)
            # Updates Polyline through ROW
            # Left Side!

            left_max_invert = max (xs_vertices_dict_left[ 'Zs' ])
            left_max_index = xs_vertices_dict_left[ 'Zs' ].index (left_max_invert)
            left_check_index = left_max_index + 5
            left_check_index = len (xs_vertices_dict_left[ 'Zs' ]) - 1 if left_check_index > len (
                xs_vertices_dict_left[ 'Zs' ]) - 1 else left_check_index
            left_check_invert = xs_vertices_dict_left[ 'Zs' ][left_check_index]
            original_left_index = left_max_index
            original_lcheck_index = left_check_index
            l_depth_check = left_max_invert - left_check_invert
            ldepth_val = 2.0
            while l_depth_check < ldepth_val:
                left_max_index += 2
                left_check_index += 2
                left_check_index = len(xs_vertices_dict_left[ 'Zs' ]) -1 if left_check_index >len(xs_vertices_dict_left[ 'Zs' ]) -1  else left_check_index
                left_max_index = len (xs_vertices_dict_left[ 'Zs' ]) - 1 if left_max_index >= len (
                    xs_vertices_dict_left[ 'Zs' ]) - 1 else left_max_index
                if left_max_index == left_check_index:
                    ldepth_val -= 0.25
                    left_max_index = original_left_index
                    left_check_index= original_lcheck_index
                left_max_invert = xs_vertices_dict_left[ 'Zs' ][left_max_index]
                left_check_invert = xs_vertices_dict_left[ 'Zs' ][left_check_index]
                l_depth_check = left_max_invert - left_check_invert
                if int (ldepth_val) < 1.0:
                    left_max_index = original_left_index
                    left_max_invert = xs_vertices_dict_left[ 'Zs' ][ left_max_index ]
                    l_depth_check = 12
            left_row_index = left_max_index - int(round(row_width+10/vertices_spacing,0))
            left_row_index = 0 if left_row_index < 0 else left_row_index
            start__index = left_row_index + left_index
            start__index = 0 if start__index < 0 else start__index

            # Right Side!
            right_max_invert = max (xs_vertices_dict_right[ 'Zs' ])
            right_max_index = xs_vertices_dict_right[ 'Zs' ].index (right_max_invert)
            right_check_index = right_max_index - 5
            right_check_index = 0 if right_check_index < 0 else right_check_index
            right_check_invert = xs_vertices_dict_right[ 'Zs' ][right_check_index]
            original_right_max_index = right_max_index
            original_rcheck_index = right_check_index
            r_depth_check = right_max_invert - right_check_invert
            rdepth_val = 2.0
            while r_depth_check  < rdepth_val:
                right_max_index -= 1
                right_check_index -= 1
                right_check_index = 0 if right_check_index < 0 else right_check_index
                right_max_index = 0 if right_max_index < 0 else right_max_index
                if right_check_index == right_max_index:
                    rdepth_val -= 0.25
                    right_max_index = original_right_max_index
                    right_check_index = original_rcheck_index
                right_max_invert = xs_vertices_dict_right[ 'Zs' ][right_max_index]
                right_check_invert = xs_vertices_dict_right[ 'Zs' ][right_check_index]
                r_depth_check = right_max_invert - right_check_invert
                if int (rdepth_val) < 1.0:
                    right_max_index = original_right_max_index
                    r_depth_check = 12


            right_row_index = right_max_index + int(round(row_width+10/vertices_spacing,0))
            right_row_index = 0 if right_row_index < 0 else right_row_index
            right_row_index = right_row_index if right_row_index <= len( xs_vertices_dict_right[ 'Zs' ]) -1  else len( xs_vertices_dict_right[ 'Zs' ]) -1
            end_index = right_row_index + cen_index - 1
            #Creates New Polyline extending the widths of the ROW
            if end_index >= len(polyline_points)-1:
                new_polyline = arcpy.Polyline(arcpy.Array(tuple(polyline_points[start__index:])), sref, True)
            elif end_index < len(polyline_points)-1:
                new_polyline = arcpy.Polyline(arcpy.Array(tuple(polyline_points[start__index:end_index+1])), sref, True)
            else:
                new_polyline = saved_polyline
            #Adjusts ROW Computation
            pline_length = new_polyline.length
            first_point = new_polyline.firstPoint
            seg_leg = list (np.arange (0 , pline_length + vertices_spacing , vertices_spacing))
            cen_index = int (len (seg_leg) / 2) - 1
            left_index = bisect.bisect_left (seg_leg , pline_length / 2 - search_rad)
            right_index = bisect.bisect_right (seg_leg , pline_length / 2 + search_rad)
            xs_vertices_dict_left = {'Xs': [ ] , 'Ys': [ ] , 'Zs': [ ]}
            xs_vertices_dict_right = {'Xs': [ ] , 'Ys': [ ] , 'Zs': [ ]}
            # print('\t\t\t7.1.{0}|-XS Sized. Identifying Bank Stations'.format(i))
            #Identifies Stationing.
            for part in new_polyline:
                count = 0
                for vertex in part:
                    x = vertex.X
                    y = vertex.Y
                    z = vertex.Z
                    if count >= left_index and count <= cen_index:
                        xs_vertices_dict_left['Xs'].append(x)
                        xs_vertices_dict_left['Ys'].append(y)
                        xs_vertices_dict_left['Zs'].append(z)
                    elif count > cen_index and count <= right_index:
                        xs_vertices_dict_right['Xs'].append(x)
                        xs_vertices_dict_right['Ys'].append(y)
                        xs_vertices_dict_right['Zs'].append(z)
                    else:
                        pass
                    count += 1
            # identifies local max overbanks on left and right side
            # Identifies Left Bank station  and Average Depth
            flag = None
            left_max_invert = max(xs_vertices_dict_left['Zs'])
            left_max_index = xs_vertices_dict_left['Zs'].index(left_max_invert) + 2
            left_max_index = len(xs_vertices_dict_left['Zs'])-1 if left_max_index >= len(xs_vertices_dict_left['Zs']) -1 else left_max_index
            left_check_index = left_max_index + 5
            left_check_index = len (xs_vertices_dict_left[ 'Zs' ]) - 1 if left_check_index > len (
                xs_vertices_dict_left[ 'Zs' ]) - 1 else left_check_index
            left_check_invert = xs_vertices_dict_left[ 'Zs' ][left_check_index]
            original_left_index = left_max_index
            original_lcheck_index = left_check_index
            l_depth_check = left_max_invert - left_check_invert
            ldepth_val = 2.0
            while l_depth_check < ldepth_val:
                left_max_index += 1
                left_check_index += 1
                left_check_index = len(xs_vertices_dict_left[ 'Zs' ]) -1 if left_check_index >len(xs_vertices_dict_left[ 'Zs' ]) -1  else left_check_index
                left_max_index = len (xs_vertices_dict_left[ 'Zs' ]) - 1 if left_max_index >= len (
                    xs_vertices_dict_left[ 'Zs' ]) - 1 else left_max_index
                if left_max_index == left_check_index:
                    ldepth_val -= 0.25
                    left_max_index = original_left_index
                    left_check_index= original_lcheck_index
                left_max_invert = xs_vertices_dict_left[ 'Zs' ][left_max_index]
                left_check_invert = xs_vertices_dict_left[ 'Zs' ][left_check_index]
                l_depth_check = left_max_invert - left_check_invert
                if int (ldepth_val) <= 1.0:
                    left_max_index = original_left_index
                    left_max_invert = xs_vertices_dict_left[ 'Zs' ][ left_max_index ]
                    l_depth_check = 12
                    flag = 'Flag L Bank'
            left_x = xs_vertices_dict_left['Xs'][left_max_index]
            left_y = xs_vertices_dict_left['Ys'][left_max_index]
            a_left, b_left = get_legs(first_point.X, first_point.Y, left_x, left_y)
            left_length = abs(hypot(a_left, b_left))
            rel_left_length = round(left_length / float(pline_length), 5)

            # Identifies Right Bank station  and Average Depth
            right_max_invert = max(xs_vertices_dict_right['Zs'])
            right_max_index = xs_vertices_dict_right['Zs'].index(right_max_invert) -2
            right_max_index = 0 if right_max_index <= 0 else right_max_index
            right_check_index = right_max_index - 5
            right_check_index = 0 if right_check_index < 0 else right_check_index
            original_right_max_index = right_max_index
            original_rcheck_index = right_check_index
            right_check_invert = xs_vertices_dict_right[ 'Zs' ][right_check_index]
            r_depth_check = right_max_invert - right_check_invert
            rdepth_val = 2.0
            while r_depth_check  < rdepth_val:
                right_max_index -= 1
                right_check_index -= 1
                right_check_index = 0 if right_check_index < 0 else right_check_index
                right_max_index = 0 if right_max_index < 0 else right_max_index
                if right_check_index == right_max_index:
                    # print("\t\t\t\t\tCheck Depth Decreased to: {0}".format (ldepth_val))
                    rdepth_val -= 0.25
                    #Resets to RIGHT High point in XS
                    right_max_index = original_right_max_index
                    right_check_index = original_rcheck_index
                right_max_invert = xs_vertices_dict_right[ 'Zs' ][right_max_index]
                right_check_invert = xs_vertices_dict_right[ 'Zs' ][right_check_index]
                # print('\t\t\t\t{0}|{1}|{2}'.format(right_max_index, right_check_index, len(xs_vertices_dict_right['Zs'])-1))
                r_depth_check = right_max_invert - right_check_invert
                if int (rdepth_val) <= 1.0:
                    right_max_index = original_right_max_index
                    right_max_invert = xs_vertices_dict_right[ 'Zs' ][ right_max_index ]
                    r_depth_check = 12
                    if flag is not None:
                        flag = 'Flag LR Banks'
                    else:
                        flag = 'Flag R Bank'
            right_x = xs_vertices_dict_right['Xs'][right_max_index]
            right_y = xs_vertices_dict_right['Ys'][right_max_index]
            a_right, b_right = get_legs(first_point.X, first_point.Y, right_x, right_y)
            right_length = abs(hypot(a_right, b_right))
            left_min_invert = min(xs_vertices_dict_left['Zs'])
            left_depth = left_max_invert - left_min_invert
            right_min_invert = min(xs_vertices_dict_left['Zs'])
            right_depth = right_max_invert - right_min_invert
            avg_depth = 0.5 * (left_depth + right_depth)
            avg_avg_depth += avg_depth
            rel_right_length = round(right_length / float(pline_length), 5)
            xs_props = {"OBJECTID": oid, "LOB": rel_left_length, "ROB": rel_right_length,
                        "AvgDepth_ft": avg_depth, 'Polyline': new_polyline, 'Flag':flag}

            overbank_data.append(xs_props)


    #Updates Optimizes each ROW XS
    with arcpy.da.UpdateCursor(out_3D_xs_path, ['OBJECTID', 'LOB', 'ROB', 'AvgDepth_ft', 'FCL', 'Flag', 'SHAPE@'], xs_exp) as uC:
        for i, row in enumerate(uC):
            oid = overbank_data[i]['OBJECTID']
            if int(row[0]) == int(oid):
                uC.updateRow((row[0],overbank_data[i]['LOB'], overbank_data[i]['ROB'],
                              overbank_data[i]['AvgDepth_ft'], 0, overbank_data[i]['Flag'],
                              overbank_data[i]['Polyline'],))

    print("\t\t8|-Converting Tributary and XS's GIS elements to SDF file.")
    create_trib_sdf_file(thePath=sdf_output_folder, trib_fc_path=trib_fc_path, trip_exp=trib_exp,
                         xs_path_=out_3D_xs_path,expXS=xs_exp, river=river)


def develop_lateral_structures_cl_from_XS(xs_fc_path, xs_exp, lateral_structure_output_folder ):
    pass

def split_drainage_area_by_lateral_structures():
    pass


def getRequiredExtensions():
    # Checks if extenion is available and Checks out the 3D Analyst extension
    if arcpy.CheckExtension ("3D") == "Available":
        arcpy.CheckOutExtension ("3D")
        print ('\t|-Checking-Out Extension: {0}'.format ('3D'))
    else:
        print ('\t|-Meet Extension Requirement: {0}'.format ('3D'))

    # Checks if extenion is available and Checks out the Spatial Analyst extension
    if arcpy.CheckExtension ("Spatial") == "Available":
        arcpy.CheckOutExtension ("Spatial")
        print ('\t|-Checking-Out Extension: {0} Analyst'.format ('Spatial'))
    else:
        print ('\t|-Meet Extension Requirement: {0}'.format ('Spatial'))

def create_3D_XS(path_2dXS, raster_path, out_path):

    if arcpy.Exists(out_path):
        arcpy.Delete_management(out_path)

    arcpy.InterpolateShape_3d (raster_path , path_2dXS , out_path , method="CONFLATE_ZMIN" ,
                               vertices_only="VERTICES_ONLY")
    arcpy.AddField_management (out_path , field_name="LOB" , field_alias="Left_Overbank" , field_type="FLOAT")

    arcpy.AddField_management (out_path , field_name="ROB" , field_alias="Right_Overbank" ,
                               field_type="FLOAT")

    arcpy.AddField_management (out_path , field_name="AvgDepth_ft" , field_alias="Avg_Depth_ft" ,
                               field_type="FLOAT")

    arcpy.AddField_management (out_path , field_name="FCL" , field_alias="FCL" ,
                               field_type="SHORT")

    arcpy.AddField_management (out_path , field_name="Flag" , field_alias="Flag" , field_type="TEXT" ,
                               field_length=25 , )
    return out_path

def cutXS(trib_fc, temp_folder, trib_id_key_field, raster_path, output_gdb,
                     sta_seg_length=100, xs_interval=2.5,
                      xs_length=600.0):
    getRequiredExtensions()
    # Front end input Checks
    try:
        if xs_length / xs_interval > 500:
            raise ValueError
    except ValueError as e:
        e.message = "HEC-RAS limits number of vertices to 500 per XS. Increase XS Interval"
        raise

    try:
        if xs_length < 500:
            raise ValueError
    except ValueError as e:
        e.message = "WPT Requires a minimum XS length of 500 ft. " \
                    "Increase XS Length to a value equal to or greater than 500.0"
        raise

    # Disolves Tribfc Subreaches into Single Line Features per Tributary
    if '.shp' in os.path.basename(trib_fc).lower():
        bn = os.path.basename(trib_fc)[:len(os.path.basename(trib_fc))-4]
    else:
        bn = os.path.basename(trib_fc)
    dis_trib_path =os.path.join(os.path.dirname(trib_fc), "{0}_Dissolve".format(bn))

    if '.shp' in os.path.basename(trib_fc).lower():
        dis_trib_path += '.shp'
    print(dis_trib_path)

    print('\t|-Dissolving Tributaries on "{0}".'.format(trib_id_key_field))
    if arcpy.Exists(dis_trib_path):
        arcpy.Delete_management(dis_trib_path)

    trib_fc = arcpy.Dissolve_management(trib_fc, dis_trib_path,
                                        dissolve_field=trib_id_key_field,
                                        multi_part="SINGLE_PART", unsplit_lines='UNSPLIT_LINES')

    unique_tribs = get_unique_trib_names (trib_fc , trib_id_key_field)
    outname = "XS2D_"
    for trib in unique_tribs:
        print('\t%% Analyzing {0} %%'.format(trib))
        adj_trib_nam = str(trib).replace(' ','').replace('-','_')
        trib_exp = build_trib_exp (trib , trib_id_key_field)
        shp = run_produce_xs (trib_fc , temp_folder , outname , trib , trib_exp ,
                              sta_seg_length=sta_seg_length , xs_interval=xs_interval ,
                              xs_length=xs_length)
        print('\t\t1|-Creating 1st Pass 3D-XS')
        xs3d_path = os.path.join(output_gdb, 'iXS3D_{0}'.format(adj_trib_nam))
        create_3D_XS(shp, raster_path, xs3d_path)
        #0 indicates no, 1 indicates yes
        gc.collect ()


def run_produce_3d_xs(trib_fc, temp_folder, trib_id_key_field, raster_path, output_gdb,
                      sdf_output_folder, wmp_subcatchments, sta_seg_length=50, xs_interval=2.5,
                      xs_length=600.0, row_width=30, forWPT=False):
    """A sburoutine dedicated toward developing cross sections based on lidar and channel centerline data.
    The file generates SDF files for import to HEC-RAS. """
    start_time = datetime.now ()
    print("DEVELOPING WATERSHED CROSS SECTIONS:\nSTART TIME {0}".format(start_time.strftime("%I:%M:%S")))

    try:
        if xs_length / xs_interval > 500:
            raise ValueError
    except ValueError as e:
        e.message = "HEC-RAS limits number of vertices to 500 per XS. Increase XS Interval"
        raise

    try:
        if xs_length < 500:
            raise ValueError
    except ValueError as e:
        e.message = "WPT Requires a minimum XS length of 500 ft. " \
                    "Increase XS Length to a value equal to or greater than 500.0"
        raise

    getRequiredExtensions()

    # Disolves Tribfc Subreaches into Single Line Features per Tributary
    if '.shp' in os.path.basename(trib_fc).lower():
        bn = os.path.basename(trib_fc)[:len(os.path.basename(trib_fc))-4]
    else:
        bn = os.path.basename(trib_fc)

    dis_trib_path =os.path.join(os.path.dirname(trib_fc), "{0}_Dissolve".format(bn))

    if '.shp' in os.path.basename(trib_fc).lower():
        dis_trib_path += '.shp'
    print(dis_trib_path)


    print('\t|-Dissolving Tributares on "{0}".'.format(trib_id_key_field))
    if arcpy.Exists(dis_trib_path):
        arcpy.Delete_management(dis_trib_path)

    trib_fc = arcpy.Dissolve_management(trib_fc, dis_trib_path,
                                        dissolve_field=trib_id_key_field,
                                        multi_part="SINGLE_PART", unsplit_lines='UNSPLIT_LINES')

    unique_tribs = get_unique_trib_names (trib_fc , trib_id_key_field)
    outname = "XS2D_"

    search_top_width = None
    fcs = []
    for trib in unique_tribs:
        print('\t%% Analyzing {0} %%'.format(trib))
        adj_trib_nam = str(trib).replace(' ','').replace('-','_')
        if trib[1] =='1':
            if forWPT:
                search_top_width=750
            else:
                if trib[5:7] == '00':
                    search_top_width = 750
                else:
                    #Seconds last segment of thing
                    if trib[-2:]!='00':
                        search_top_width = 300
                    else:
                        search_top_width = 400
        else:
            search_top_width = 750


        trib_exp = build_trib_exp (trib , trib_id_key_field)
        xs_exp = '"Tributary" LIKE ' + "'%" + trib + "%'"
        shp = run_produce_xs (trib_fc , temp_folder , outname , trib, trib_exp,
                              sta_seg_length=sta_seg_length , xs_interval=xs_interval , xs_length=xs_length)

        print('\t\t1|-Creating 1st Pass 3D-XS')
        xs3d_path = os.path.join(output_gdb, 'iXS3D_{0}'.format(adj_trib_nam))
        create_3D_XS(shp, raster_path, xs3d_path)

        #0 indicates no, 1 indicates yes
        print('\t\t2|-Identifying Optimal XS Spacing')
        adjust_sta_length = first_past_3D_XS(out_3D_xs_path=xs3d_path, xs_exp=xs_exp,
                                             search_top_width=search_top_width, vertices_spacing=xs_interval,
                                             sta_spacing=sta_seg_length)
        gc.collect()


        opt_shp =   run_produce_xs(trib_fc , temp_folder,'OXS2D',trib, trib_exp,
                                   sta_seg_length=adjust_sta_length , xs_interval=xs_interval,
                                   xs_length=xs_length, isOptimized=True)
        print('\t\t6|-Defining Optimized 3D-XS')
        oxs3d_path = os.path.join(output_gdb, 'XS_{0}'.format(adj_trib_nam))
        create_3D_XS(opt_shp, raster_path, oxs3d_path)
        optimized_3D_XS_spacing(trib_fc, oxs3d_path, sdf_output_folder, trib_exp,
                                xs_exp, trib, search_top_width=search_top_width,
                                vertices_spacing=xs_interval, row_width = row_width)
        fcs.append(oxs3d_path)
        print('\t\tX|-Tributary Complete. SDF file ready for import into HEC-RAS!')
    sref = getSpatialReferencefactoryCode(fcs[0])
    output_xs = os.path.join(output_gdb, "iReach_Cross_Sections")
    if arcpy.Exists(output_xs):
        arcpy.Delete_management(output_xs)

    arcpy.CreateFeatureclass_management(output_gdb,"iReach_Cross_Sections","POLYLINE",fcs[0],has_z='SAME_AS_TEMPLATE', spatial_reference=sref)

    arcpy.Append_management(fcs, output_xs, "TEST")

    for fc in fcs:
        if arcpy.Exists(fc):
            arcpy.Delete_management(fc)

    final_xs  = os.path.join(output_gdb, "Reach_Cross_Sections")
    if arcpy.Exists (final_xs):
        arcpy.Delete_management (final_xs)
    arcpy.SpatialJoin_analysis(output_xs, wmp_subcatchments, final_xs,"JOIN_ONE_TO_ONE",
                               "KEEP_ALL",
                               match_option="WITHIN_CLEMENTINI")
    end_time = datetime.now ()
    delta_time = end_time - start_time
    print("!!! Task Complete!!!\n\n")
    print('Elapsed Time: {0} minutes'.format(round(delta_time.seconds / 60.0,0)))
    return unique_tribs

def create_hec_ras_project_files(parent_watershed, tributary, sdf_file):
    import pyautogui
    from shutil import copyfile
    from Utility import MakeDir, kras, init_ks_, set_hec_ras_default_project_folder

    # msg = "Key stroking will begin soon, do you want to proceed with generating HEC-RAS Project Files? (y/n)"
    # commence_ks = raw_input(msg)
    # if commence_ks.lower() == 'y':
    #     print('%%%CAUTION KEY STROKING WILL COMMENCE SOON%%%')
    #     for trib in tributaries:
    #         print('\t%%%PRODUCING {0} MODEL%%%'.format(trib))
    #         sdf_file = r'C:\Users\AGovea\Desktop\Galveston Bay Local\SDFs\{0}.sdf'.format(trib)
    #         create_hec_ras_project_files(watershed_name,trib,sdf_file=sdf_file)
    #         os.remove(sdf_file)
    #     print"!!! HEC-RAS File Creation Complete!!!\n\n"
    # else:
    #     print("!!! HEC-RAS File Creation Aborted !!!")

    #Creates First Pass of Creating Blank HEC-HSM Files


    #Local Variables
    alt = 'alt'
    RAS_WINDOWTITLE_HECRAS = 'HEC-RAS'
    RAS_WINDOWTITLE_GEOMETRICDATA = 'Geometric'
    RAS_WINDOWTITLE_SFLOWDATA = 'Steady Flow'
    RAS_IMPORT_GEOMETRY  = "Import Geometry Data"
    temp_output_folder = "C:\\HCFCD\\{0}\\{1}".format(parent_watershed,tributary)


    #Creates Temporary Output Directory Folder if it Does not already exist
    for i, ch in enumerate(temp_output_folder.split('\\')):
        if i > 0:
            if i != len(temp_output_folder.split('\\')) - 1:
                MakeDir('\\'.join(map(str,temp_output_folder.split('\\')[:i+1])))
            else:
                MakeDir(temp_output_folder)

    if not os.path.exists(os.path.join(temp_output_folder,os.path.basename(sdf_file))):
        copyfile(sdf_file, os.path.join(temp_output_folder,os.path.basename(sdf_file)))

    def save_as_new_project_file(tributary):
        #Opens Save As Window
        pyautogui.hotkey(alt,'f')
        pyautogui.press(['a'],pause=0.3)
        time.sleep (0.4)
        #tab to default folder
        tabs = ['tab']*4
        pyautogui.press(tabs,pause=0.3)
        pyautogui.press(['space'],pause=0.3)

        #TAB TO TITLE MENU and enters tributary as project file name
        tabs = [ 'tab' ] * 8
        pyautogui.press (tabs , pause=0.3)

        # ENTERS Tributary name as Project Folder
        pyautogui.press([ch for ch in tributary ], pause=0.3)
        time.sleep (0.4)
        # Tabs to Enter Key and selects
        tabs = [ 'tab' ] * 6
        pyautogui.press (tabs , pause=0.3)
        pyautogui.press ([ 'space' ] , pause=0.3)
        time.sleep(0.4)

    def save_project():
        init_ks_ (RAS_WINDOWTITLE_HECRAS , False)
        pyautogui.hotkey(alt,'f')
        pyautogui.press('s',pause=0.3)
        time.sleep(0.5)
        kras()

    def create_baseline_plan_file(tributary,isfirst):
        init_ks_ (RAS_WINDOWTITLE_HECRAS , False)
        fname  = "{0}_BaselineConditions".format(tributary)
        short_ID = "{0}BC".format(tributary)
        pyautogui.hotkey(alt,'r')
        pyautogui.press('s',pause=0.3)
        time.sleep (0.4)
        init_ks_(RAS_WINDOWTITLE_SFLOWDATA, False)
        time.sleep (0.4)
        pyautogui.hotkey(alt,'f')
        pyautogui.press('a',pause=0.3)
        time.sleep (0.5)

        # ENTERS fname as Plan file name
        pyautogui.press(['delete']*50, pause=0.3)
        pyautogui.press([ch for ch in fname ], pause=0.3)
        # Tabs to Enter Key and selects
        tabs = [ 'tab' ] * 5
        pyautogui.press (tabs , pause=0.3)
        pyautogui.press ([ 'space' ] , pause=0.3)
        if isfirst:
            time.sleep (0.4)
            pyautogui.press([ch for ch in short_ID], pause=0.3)
            tabs = [ 'tab' ]
            pyautogui.press (tabs , pause=0.3)
            pyautogui.press ([ 'space' ] , pause=0.3)
            time.sleep (0.4)
            pyautogui.hotkey(alt,'f')
            pyautogui.press('s',pause=0.3)
            time.sleep(0.4)
        else:
            time.sleep (0.4)
            pyautogui.press ([ 'space' ] , pause=0.3)
            pyautogui.press ([ 'delete' ] * 50 , pause=0.3)
            pyautogui.press([ch for ch in short_ID], pause=0.3)
            tabs = [ 'tab' ]
            pyautogui.press (tabs , pause=0.3)
            pyautogui.press ([ 'space' ] , pause=0.3)
            time.sleep (0.4)
            pyautogui.hotkey(alt,'f')
            pyautogui.press('s',pause=0.3)
            time.sleep(0.4)


        pyautogui.hotkey(alt,'f')
        pyautogui.press('x',pause=0.3)
        time.sleep (0.4)

    def import_sdf_to_geometry(tributary):
        #Opens Save As Window
        init_ks_ (RAS_WINDOWTITLE_HECRAS , False)
        pyautogui.hotkey(alt,'e')
        pyautogui.press(['g'],pause=0.3)
        time.sleep(0.6)

        init_ks_ (RAS_WINDOWTITLE_GEOMETRICDATA, True)
        #Iinitializes GIS Import Funciton
        pyautogui.hotkey (alt , 'f')
        pyautogui.press(['i'],pause=0.3)
        pyautogui.press ([ 'enter' ] , pause=0.3)
        time.sleep (0.4)

        #Selects only SDF File in Folder
        pyautogui.press(['tab'],pause=0.3)
        pyautogui.press ([ 'space' ] , pause=0.3)
        pyautogui.press ([ 'enter' ] , pause=0.3)

        time.sleep (1.2)
        init_ks_(RAS_IMPORT_GEOMETRY, False)
        # Presses OK

        #applies import
        pyautogui.press(['tab']*2,pause=0.3)
        pyautogui.press ([ 'space' ] , pause=0.3)

        #Applies File Save As
        pyautogui.hotkey(alt,'f')
        pyautogui.press('a',pause=0.3)
        time.sleep (0.4)

        # ENTERS Tributary name as Project Folder
        pyautogui.press([ch for ch in tributary ], pause=0.3)
        pyautogui.press ([ 'enter' ] , pause=0.3)
        time.sleep(0.4)

        pyautogui.hotkey(alt,'f')
        pyautogui.press('s',pause=0.3)
        time.sleep(0.4)

        pyautogui.hotkey(alt,'f')
        pyautogui.press('x',pause=0.3)
        time.sleep (0.4)

    #Sets Temporary Folder as Default Project Folder in HEC_RAS
    set_hec_ras_default_project_folder('\\'.join(map(str,temp_output_folder.split('\\')[1:])),
                                       RAS_WINDOWTITLE_HECRAS)

    save_as_new_project_file(tributary)
    print('\t\t|-PROJECT FILE CREATED.')

    import_sdf_to_geometry(tributary)
    print('\t\t|-GEOMETRY FILE IMPORTED.')

    create_baseline_plan_file(tributary, isfirst=True)
    print('\t\t|-PLAN FILE GENERATED.')

    save_project()
    kras()




if __name__ == "__main__":
    # Start Time
    start_time = datetime.now ()
    # Input Subreach Layer suggested export a local copy of the WMP subreaches in
    # suggested to export shp from :
    # N:\120\120-12180-000\9-0-Data-GIS-Modeling\9-01-GIS\3-ProjectData\GDB\WMP F - Galveston Bay.mdb\WMP_Level1_Data
    trib_fc = r"C:\Users\AGovea\Desktop\Galveston Bay Local\SHP\UnstudiedTributaries.shp" # a
    # wmp_subcatchments = r"N:\120\120-12180-000\9-0-Data-GIS-Modeling\9-01-GIS\3-ProjectData\SHP\WMP_Drainage_Areas.shp" #Drainage Areas for subreaces exported form WMP
    raster_path = r'N:\120\120-12180-000\9-0-Data-GIS-Modeling\9-01-GIS\3-ProjectData\Raster\GalvestonBayWatershed_2018LiDAR.tif'
    # Output Variables
    temp_folder = r'C:\Users\Agovea\Desktop\Galveston Bay Local\tempSHP'     # Temporary deposit folder for output file
    out_3D_xs_path = r'C:\Users\AGovea\Desktop\Galveston Bay Local\HFCFC_GalvestonBay_Watershed.gdb' #output path for final XS.
    sdf_output_folder = r'C:\Users\AGovea\Desktop\Galveston Bay Local\SDFs' #Output folder  for .sdf files.
    watershed_name = "GalvestonBay"
    # Constant Variables but have potential to vary.
    trib_id_key_field = 'UnitNumber'
    # tributaries = run_produce_3d_xs(trib_fc, temp_folder, trib_id_key_field, raster_path, out_3D_xs_path,
    #                                 sdf_output_folder, wmp_subcatchments, sta_seg_length=25, xs_length=750.0,
    #                                 xs_interval=4, row_width=20, forWPT=True)

    cutXS(trib_fc, temp_folder, trib_id_key_field, raster_path, out_3D_xs_path,
                                    sta_seg_length=25, xs_length=750.0,
                                    xs_interval=4)
    print('SDF Files for tributaries Created!')
    end_time = datetime.now()
    delta_time = end_time - start_time
    print('Absolute Time: {0} minutes'.format(round(delta_time.seconds / 60.0,0)))
