import os
import arcpy
import traceback
from Geom import get_legs, pi, getTheta, get_segment_length
from math import sin, cos, hypot
import bisect
from gc import collect

def buffer_inlets_and_roadside(line_feature, point_feature, output_feature, buff_distance):
    buf_point_fc = os.path.join(os.path.dirname(output_feature), "{0}_buf".format(os.path.basename(point_feature)))
    buf_line_fc = os.path.join(os.path.dirname(output_feature), "{0}_buf".format(os.path.basename(line_feature)))
    pass

def disolve_subcatchment_on_area(polygon_fc, field_name, out_folder):
    out_fc_path = os.path.join(out_folder, "{0}_SB".format(os.path.basename(polygon_fc)))
    arcpy.Dissolve_management(in_features=polygon_fc,out_feature_class=out_fc_path, dissolve_field=field_name,
                              multi_part="SINGLE_PART", statistics_fields="LAST")


def get_single_poly_centroid(fc, id_field):
    with arcpy.da.SearchCursor (fc , [ "OID@" , id_field, "SHAPE@" ]) as cursor:
        pg = cursor[0][2]
        cenX, cenY = pg.centroid.X, pg.centroid.Y
    return cenX, cenY

def get_polygon_centroids(fc, id_field, exp=""):
    with arcpy.da.SearchCursor (fc , [ "OID@" , id_field, "SHAPE@" ] , exp) as cursor:
        for row in cursor:
            pg = row[2]
            if pg.isMultiPart:
                pass
            else:
                cenX, cenY = pg.centroid.X, pg.centroid.Y
    return cenX, cenY

# def buffer_polylines(fc, id_field, exp, buffer_distance):
#     with arcpy.da.SearchCursor (fc , [ "OID@" , id_field, "SHAPE@" ] , exp) as cursor:
#         for row in cursor:
#             pline = row[2]
#             pline.buffer()


def create_fishnet(boundry_fc, boundry_fc_id_field, point_fc, output_gdb, cell_size=370, cell_size_units="Feet"):
    sr = getSpatialReferencefactoryCode(boundry_fc)
    #Buffers FC
    buffer_distance = 3*cell_size
    buf_str = "{0} {1}".format(int(buffer_distance), cell_size_units)
    cenX, cenY = get_single_poly_centroid(boundry_fc,boundry_fc_id_field)
    buffer_fc = os.path.join(output_gdb,'{0}_buff'.format(os.path.basename(point_fc)))
    buffered_points = arcpy.Buffer_analysis(point_fc,buffer_fc,line_side="FULL",method="PLANAR",)


def getSpatialReferencefactoryCode(fc):
    spatial_ref = arcpy.Describe(fc).spatialReference
    return spatial_ref.factoryCode

def get_intersection(l1, l2):
    """
    :param l1:
    :param l2:
    :return:
    """
    pass

def get_vertices(fc, exp):
    """Returns points of a point feature class
        :param fc:
        :param exp:
        :return:
    """
    try:
        coordinate_array = []
        total_lenght = 0.0
        with arcpy.da.SearchCursor(fc, ["OID@", "SHAPE@"], exp) as cursor:
            for row in cursor:
                part_array = []
                total_lenght += row[1].length
                for part in row[1]:
                    for pnt in part:
                        if pnt:
                            part_array.append([round(float(pnt.X), 7), round(float(pnt.Y), 7)])
                    coordinate_array.append(part_array)
        return coordinate_array, total_lenght
    except:
        print('{0}'.format(traceback.format_exc()))


def generate_xy_stations(coordinate_array, toatl_length, sta_dist=50, start_station_float=0.0):
    try:
        oids, stations, x_coords, y_coords, = [], [], [], []
        running_length_total = None
        if int(sta_dist)==0:
            sta_dist = 50
        station_bins = list(range(0, 999999995, sta_dist))
        start_station = None
        previous_station = None
        x1, y1 = None, None
        prevpart_x, prevpart_y = None, None
        j = 0
        if start_station_float != 0.0:
            running_length_total = float(start_station_float)
        else:
            running_length_total = 0.0
        part_arrrays_to_revisit = []
        for k in range(len(coordinate_array)):
            part_array = coordinate_array[k]
            if k == 0:
                for i in range(len(part_array)):
                    if i < len(part_array) - 1:
                        pnt_1 = part_array[i]
                        pnt_2 = part_array[i + 1]
                        # a is length in x direction, b is length in y direction
                        a, b = get_legs(pnt_1[0], pnt_1[1], pnt_2[0], pnt_2[1])
                        x1, y1, = pnt_1[0], pnt_1[1]
                        x2, y2 = pnt_2[0], pnt_2[1]
                        if b == 0.0:
                            theta = 0
                        elif a == 0.0:
                            theta = pi / 2.0
                        else:
                            theta = getTheta(b, a)
                        length = abs(get_segment_length(pnt_1[0], pnt_1[1], pnt_2[0], pnt_2[1]))
                        if i == 0:
                            oids.append(j)
                            start_station = '{:.02f}'.format(round(toatl_length - running_length_total,2))
                            previous_station = running_length_total
                            stations.append(start_station)
                            x_coords.append(x1)
                            y_coords.append(y1)
                            # print('index: {0} station: {1}\n\t|-x: {2}\ty: {3}'.format(i, start_station, x1, y1))
                        next_station_float = station_bins[
                            bisect.bisect_right(station_bins, running_length_total)]
                        # Begins creating station-ing points
                        if running_length_total + length <= next_station_float:
                            pass
                        else:
                            while running_length_total + length > next_station_float:
                                station = '{:.02f}'.format (round (toatl_length - next_station_float , 2))
                                dif = next_station_float - previous_station
                                if theta > 0 and theta < pi / 2.0:
                                    # print('\t#Quadrant 1, theta:{0}'.format(degrees(theta)))
                                    x1 += round(float(dif * cos(theta)), 8)
                                    y1 += round(float(dif * sin(theta)), 8)
                                elif (theta > pi / 2.0) and (theta < pi):
                                    # print('\t#Quadrant 2')
                                    x1 += round(float(dif * cos(theta)), 8)
                                    y1 += round(float(dif * sin(theta)), 8)
                                elif theta > pi and (theta < 3 * pi / 2.0):
                                    # print('\t#Quadrant 3')
                                    x1 += round(float(dif * cos(theta)), 8)
                                    y1 += round(float(dif * sin(theta)), 8)
                                elif theta > 3 * pi / 2.0 and (theta < 2.0 * pi):
                                    # print('\t#Quadrant 4')
                                    x1 += round(float(dif * cos(theta)), 8)
                                    y1 += round(float(dif * sin(theta)), 8)
                                elif theta < 0 and (theta > - pi / 2.0):
                                    # print('\t#Quadrant 4, theta:{0}'.format(degrees(theta)))
                                    x1 += round(float(dif * cos(theta)), 8)
                                    y1 += round(float(dif * sin(theta)), 8)
                                elif (theta < - pi / 2.0) and (theta > - pi):
                                    # print('\tQuandrant 3')
                                    x1 += round(float(dif * cos(theta)), 8)
                                    y1 += round(float(dif * sin(theta)), 8)
                                elif (theta < - pi) and (theta > - 3 * pi / 2.0):
                                    # print('\tQuandrant 2')
                                    x1 += round(float(dif * cos(theta)), 8)
                                    y1 += round(float(dif * sin(theta)), 8)
                                elif (theta == 0) or (theta == 2 * pi):
                                    # X Axis
                                    x1 += dif
                                elif (theta == pi / 2.0) or (theta == pi / -2.0):
                                    # Y Axis
                                    y1 += dif
                                elif (theta > pi * 2.0) or (theta < - pi * 2.0):
                                    print('\n\n!!!!ARGGGGG!!!!!\n\n')
                                else:
                                    x1 += round(float(dif * cos(theta)), 8)
                                    y1 += round(float(dif * sin(theta)), 8)
                                j += 1
                                oids.append(j)
                                stations.append(station)
                                x_coords.append(x1)
                                y_coords.append(y1)
                                previous_station = next_station_float
                                next_station_float += sta_dist
                        running_length_total += length
                        previous_station = running_length_total
                    else:
                        pnt_1 = part_array[i]
                        prevpart_x, prevpart_y, = pnt_1[0], pnt_1[1]
            else:
                xi, yi = part_array[0][0], part_array[0][1]
                xf, yf = part_array[len(part_array) - 1][0], part_array[len(part_array) - 1][1]
                if (round(prevpart_x, 2) == round(xi, 2)) and (round(prevpart_y, 2) == round(yi, 2)):
                    for i in range(len(part_array)):
                        if i < len(part_array) - 1:
                            pnt_1 = part_array[i]
                            pnt_2 = part_array[i + 1]
                            # a is length in x direction, b is length in y direction
                            a, b = get_legs(pnt_1[0], pnt_1[1], pnt_2[0], pnt_2[1])
                            x1, y1, = pnt_1[0], pnt_1[1]
                            x2, y2 = pnt_2[0], pnt_2[1]
                            if b == 0.0:
                                theta = 0
                            elif a == 0.0:
                                theta = pi / 2.0
                            else:
                                theta = getTheta(b, a)
                            length = abs(get_segment_length(pnt_1[0], pnt_1[1], pnt_2[0], pnt_2[1]))
                            next_station_float = station_bins[
                                bisect.bisect_right(station_bins, running_length_total)]
                            # Begins creating station-ing points
                            if running_length_total + length <= next_station_float:
                                pass
                            else:
                                while running_length_total + length > next_station_float:
                                    station = '{:.02f}'.format (round (toatl_length - next_station_float , 2))
                                    dif = next_station_float - previous_station
                                    if theta > 0 and theta < pi / 2.0:
                                        # print('\t#Quadrant 1, theta:{0}'.format(degrees(theta)))
                                        x1 += round(float(dif * cos(theta)), 8)
                                        y1 += round(float(dif * sin(theta)), 8)
                                    elif (theta > pi / 2.0) and (theta < pi):
                                        # print('\t#Quadrant 2')
                                        x1 += round(float(dif * cos(theta)), 8)
                                        y1 += round(float(dif * sin(theta)), 8)
                                    elif theta > pi and (theta < 3 * pi / 2.0):
                                        # print('\t#Quadrant 3')
                                        x1 += round(float(dif * cos(theta)), 8)
                                        y1 += round(float(dif * sin(theta)), 8)
                                    elif theta > 3 * pi / 2.0 and (theta < 2.0 * pi):
                                        # print('\t#Quadrant 4')
                                        x1 += round(float(dif * cos(theta)), 8)
                                        y1 += round(float(dif * sin(theta)), 8)
                                    elif theta < 0 and (theta > - pi / 2.0):
                                        # print('\t#Quadrant 4, theta:{0}'.format(degrees(theta)))
                                        x1 += round(float(dif * cos(theta)), 8)
                                        y1 += round(float(dif * sin(theta)), 8)
                                    elif (theta < - pi / 2.0) and (theta > - pi):
                                        # print('\tQuandrant 3')
                                        x1 += round(float(dif * cos(theta)), 8)
                                        y1 += round(float(dif * sin(theta)), 8)
                                    elif (theta < - pi) and (theta > - 3 * pi / 2.0):
                                        # print('\tQuandrant 2')
                                        x1 += round(float(dif * cos(theta)), 8)
                                        y1 += round(float(dif * sin(theta)), 8)
                                    elif (theta == 0) or (theta == 2 * pi):
                                        # X Axis
                                        x1 += dif
                                    elif (theta == pi / 2.0) or (theta == pi / -2.0):
                                        # Y Axis
                                        y1 += dif
                                    elif (theta > pi * 2.0) or (theta < - pi * 2.0):
                                        print('\n\n!!!!ARGGGGG!!!!!\n\n')
                                    else:
                                        x1 += round(float(dif * cos(theta)), 8)
                                        y1 += round(float(dif * sin(theta)), 8)
                                    j += 1
                                    oids.append(j)
                                    stations.append(station)
                                    x_coords.append(x1)
                                    y_coords.append(y1)
                                    previous_station = next_station_float
                                    next_station_float += sta_dist
                            running_length_total += length
                            previous_station = running_length_total
                        else:
                            pnt_1 = part_array[i]
                            prevpart_x, prevpart_y, = pnt_1[0], pnt_1[1]
                elif (round(prevpart_x, 2) == round(xf, 2)) and (round(prevpart_y, 2) == round(yf, 2)):
                    part_array = part_array.reverse()
                    for i in range(len(part_array)):
                        if i < len(part_array) - 1:
                            pnt_1 = part_array[i]
                            pnt_2 = part_array[i + 1]
                            # a is length in x direction, b is length in y direction
                            a, b = get_legs(pnt_1[0], pnt_1[1], pnt_2[0], pnt_2[1])
                            x1, y1, = pnt_1[0], pnt_1[1]
                            x2, y2 = pnt_2[0], pnt_2[1]
                            if b == 0.0:
                                theta = 0
                            elif a == 0.0:
                                theta = pi / 2.0
                            else:
                                theta = getTheta(b, a)
                            length = abs(get_segment_length(pnt_1[0], pnt_1[1], pnt_2[0], pnt_2[1]))
                            next_station_float = station_bins[
                                bisect.bisect_right(station_bins, running_length_total)]
                            # Begins creating station-ing points
                            if running_length_total + length <= next_station_float:
                                pass
                            else:
                                while running_length_total + length > next_station_float:
                                    station = '{:.02f}'.format (round (toatl_length - next_station_float , 2))
                                    dif = next_station_float - previous_station
                                    if theta > 0 and theta < pi / 2.0:
                                        # print('\t#Quadrant 1, theta:{0}'.format(degrees(theta)))
                                        x1 += round(float(dif * cos(theta)), 8)
                                        y1 += round(float(dif * sin(theta)), 8)
                                    elif (theta > pi / 2.0) and (theta < pi):
                                        # print('\t#Quadrant 2')
                                        x1 += round(float(dif * cos(theta)), 8)
                                        y1 += round(float(dif * sin(theta)), 8)
                                    elif theta > pi and (theta < 3 * pi / 2.0):
                                        # print('\t#Quadrant 3')
                                        x1 += round(float(dif * cos(theta)), 8)
                                        y1 += round(float(dif * sin(theta)), 8)
                                    elif theta > 3 * pi / 2.0 and (theta < 2.0 * pi):
                                        # print('\t#Quadrant 4')
                                        x1 += round(float(dif * cos(theta)), 8)
                                        y1 += round(float(dif * sin(theta)), 8)
                                    elif theta < 0 and (theta > - pi / 2.0):
                                        # print('\t#Quadrant 4, theta:{0}'.format(degrees(theta)))
                                        x1 += round(float(dif * cos(theta)), 8)
                                        y1 += round(float(dif * sin(theta)), 8)
                                    elif (theta < - pi / 2.0) and (theta > - pi):
                                        # print('\tQuandrant 3')
                                        x1 += round(float(dif * cos(theta)), 8)
                                        y1 += round(float(dif * sin(theta)), 8)
                                    elif (theta < - pi) and (theta > - 3 * pi / 2.0):
                                        # print('\tQuandrant 2')
                                        x1 += round(float(dif * cos(theta)), 8)
                                        y1 += round(float(dif * sin(theta)), 8)
                                    elif (theta == 0) or (theta == 2 * pi):
                                        # X Axis
                                        x1 += dif
                                    elif (theta == pi / 2.0) or (theta == pi / -2.0):
                                        # Y Axis
                                        y1 += dif
                                    elif (theta > pi * 2.0) or (theta < - pi * 2.0):
                                        print('\n\n!!!!ARGGGGG!!!!!\n\n')
                                    else:
                                        x1 += round(float(dif * cos(theta)), 8)
                                        y1 += round(float(dif * sin(theta)), 8)
                                    j += 1
                                    oids.append(j)
                                    stations.append(station)
                                    x_coords.append(x1)
                                    y_coords.append(y1)
                                    previous_station = next_station_float
                                    next_station_float += sta_dist
                            running_length_total += length
                            previous_station = running_length_total
                        else:
                            pnt_1 = part_array[i]
                            prevpart_x, prevpart_y, = pnt_1[0], pnt_1[1]
                else:
                    part_arrrays_to_revisit.append(part_array)
        out_dict = {"OID": oids, "Stations": stations, "X": x_coords, "Y": y_coords}
        return out_dict
    except:
        print('{0}'.format(traceback.format_exc()))

def CopyParallelL(plyP,sLength):
    """Copies an arcpy Poly Line Left. Will be commonly applied to upstream XS of a bridge location.
        :param plyP:
        :param sLength:
        :return:
    """
    part=plyP.getPart(0)
    lArray=arcpy.Array()
    for ptX in part:
        dL=plyP.measureOnLine(ptX)
        ptX0=plyP.positionAlongLine (dL-0.01).firstPoint
        ptX1=plyP.positionAlongLine (dL+0.01).firstPoint
        dX=float(ptX1.X)-float(ptX0.X)
        dY=float(ptX1.Y)-float(ptX0.Y)
        lenV=hypot(dX,dY)
        sX=-dY*sLength/lenV;sY=dX*sLength/lenV
        leftP=arcpy.Point(ptX.X+sX,ptX.Y+sY)
        lArray.add(leftP)
    array = arcpy.Array([lArray])
    section=arcpy.Polyline(array)
    return section

def CopyParallelR(plyP,sLength):
    """Copies an arcpy Poly Line Right
        :param plyP:
        :param sLength:
        :return:
    """
    part=plyP.getPart(0)
    rArray=arcpy.Array()
    for ptX in part:
        dL=plyP.measureOnLine(ptX)
        ptX0=plyP.positionAlongLine (dL-0.01).firstPoint
        ptX1=plyP.positionAlongLine (dL+0.01).firstPoint
        dX=float(ptX1.X)-float(ptX0.X)
        dY=float(ptX1.Y)-float(ptX0.Y)
        lenV=hypot(dX,dY)
        sX=-dY*sLength/lenV;sY=dX*sLength/lenV
        rightP=arcpy.Point(ptX.X-sX, ptX.Y-sY)
        rArray.add(rightP)
    array = arcpy.Array([rArray])
    section=arcpy.Polyline(array)
    return section


def create_polygon_centroids(poly_fc,fc_path, new_fc,poly_fields):
    fields = [ str(field) for field in poly_fields]
    print(fields)
    sr = arcpy.Describe (poly_fc).spatialReference
    if arcpy.Exists(os.path.join(fc_path, new_fc)):
        arcpy.Delete_management(os.path.join(fc_path, new_fc))
    arcpy.CreateFeatureclass_management(fc_path,new_fc,'POINT', spatial_reference=sr)
    fds = arcpy.ListFields(poly_fc)
    for fd in fds:
        if str(fd.name) in fields:
            print('\t\t\t{0}: __{1}__'.format(fd.name,fd.type))
            if str(fd.type).find('OID') != -1 or str(fd.type).find('Integer') != -1 :
                arcpy.AddField_management(os.path.join(fc_path, new_fc), str(fd.name), "LONG")
            elif str(fd.type).find('String') != -1:
                arcpy.AddField_management(os.path.join(fc_path, new_fc), str(fd.name), "TEXT", field_length=fd.length)
            elif str(fd.type).find('Double') != -1 or str(fd.type).find('Single') != -1:
                arcpy.AddField_management(os.path.join(fc_path, new_fc), str(fd.name), "FLOAT")
            else:
                pass
    fds = ['SHAPE@']
    fds += fields
    with arcpy.da.SearchCursor(poly_fc, fds) as sCursor:
        with arcpy.da.InsertCursor(os.path.join(fc_path, new_fc), fds) as iCursor:
            for row in sCursor:
                polygon = row[0]
                if polygon is None:
                    collect()
                else:
                    if polygon.isMultipart:
                        pass
                    else:
                        cent = polygon.trueCentroid
                        irow = [cent]
                        irow += [val for val in row[1:]]
                        # print('\t\|{0}: ({1}, {2})'.format(str(row[2]),round(float(cent.X),2), round(float(cent.Y),2)))
                        iCursor.insertRow(irow)