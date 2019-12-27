import numpy as np
import arcpy
import math
import os
from gc import collect



def create_circle(x , y , radius):
    pnts = [ ]
    for theta in np.arange (0 , 2 * math.pi , 0.1):
        xx = x + radius * math.cos (theta)
        yy = y + radius * math.sin (theta)
        pnts.append (arcpy.Point (xx , yy))
        return arcpy.Polygon (arcpy.Array (pnts))



def create_hcfdcWatersheds(outpath, roads, channels, channel_xs, ch_id_field, *args):
    shp = os.path.join (outpath , '{0}.shp'.format('HCFCDWatersheds'))



    if arcpy.Exists (shp):
        arcpy.Delete_management (shp)

    arcpy.CreateFeatureclass_management (outpath , '{0}.shp'.format ('HCFCDWatersheds') , geometry_type="POLYGON" ,
                                         has_m="DISABLED" ,
                                         has_z="DISABLED")

    avg_channel_widths = {}
    channel_fields = (ch_id_field)
    xs_fields = (ch_id_field, 'SHAPE@')
    print('%%%%Estimating Average Channel Width%%%%')
    with arcpy.da.SearchCursor(channels, channel_fields) as  chSC:
        for row in chSC:
            lengths = []
            unitNumber = row[0]
            print('\t\tObserving: {0}').format(unitNumber)
            query_exp = None
            if channels[ -4: ].lower () == '.shp':
                query_exp = "\"{0}\" LIKE '{1}'".format (ch_id_field , unitNumber)
            else:
                query_exp = "{0} LIKE '{1}'".format (ch_id_field , unitNumber)
            with arcpy.da.SearchCursor(channel_xs, xs_fields, query_exp)  as xsSC:
                for xsrow in  xsSC:
                    if xsrow[0] == unitNumber:
                        length = xsrow[1].length
                        lengths.append(length)

            if len(lengths) > 0:
                avg_length = roundup(sum(lengths) / len(lengths), round_unit=50.0)
            else:
                avg_length = 100
            avg_channel_widths[unitNumber] = avg_length


    for i, watershed in enumerate(args):
        with arcpy.da.InsertCursor (shp , ('FID', 'SHAPE@')) as iCursor:
            if arcpy.Exists(watershed):
                cnt = 0
                watershed_shape = None
                with arcpy.da.SearchCursor(watershed,('SHAPE@')) as sC:
                    for row in sC:
                        if cnt == 0:
                            watershed_shape = row[0]
                        else:
                            watershed_shape.union(row[0])
                        cnt += 1

                arcpy.CreateFeatureclass_management (outpath , '{0}.shp'.format ('HCFCDWatersheds') ,
                                                     geometry_type="POLYGON" ,
                                                     has_m="DISABLED" ,
                                                     has_z="DISABLED")
                # Creates channels and road feature casses for each watershed.
                rd_shp = os.path.join(outpath , '{0}_{1}.shp'.format ('Roads', i))
                if arcpy.Exists (rd_shp):
                    arcpy.Delete_management (rd_shp)

                arcpy.CreateFeatureclass_management (outpath , '{0}_{1}.shp'.format ('Roads', i) ,
                                                     geometry_type="POLYGON" ,
                                                     has_m="DISABLED" ,
                                                     has_z="DISABLED")
                with arcpy.da.InsertCursor (rd_shp , ('FID' , 'SHAPE@')) as irCursor:
                    with arcpy.da.SearchCurosr(roads, ('FID','SHAPE@')) as rCursor:
                        for rowd in rCursor:
                            if rowd[1].within(watershed_shape, 'BOUNDARY'):
                                irCursor.insertRow((rowd[0],rowd[1]))

                #Creates watershed featureclass
                ws_shp = os.path.join(outpath , '{0}_{1}.shp'.format ('Channels', i))

                if arcpy.Exists (ws_shp):
                    arcpy.Delete_management (ws_shp)

                arcpy.CreateFeatureclass_management (outpath , '{0}_{1}.shp'.format ('Channels', i) ,
                                                     geometry_type="POLYGON" ,
                                                     has_m="DISABLED" ,
                                                     has_z="DISABLED")

                with arcpy.da.InsertCursor (ws_shp , ('FID' , 'SHAPE@')) as iwCursor:
                    with arcpy.da.SearchCurosr(channels, ('FID','SHAPE@')) as wCursor:
                        for roww in wCursor:
                            if roww[1].within(watershed_shape, 'BOUNDARY'):
                                iwCursor.insertRow((roww[0],roww[1]))

                iCursor.insertRow ((i , watershed_shape ,))

    print('\t\tCompleted Combining Watersheds!')


def clip_roads(roads, channels):
    pass









