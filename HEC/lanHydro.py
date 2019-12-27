"""


Populates LAN GIS Schema with Hydrualic computations for geometric features
(e.g.subbasins, sub-reaches, cross-section) base on attributed data in each respective featureclass.

"""
import numpy as np



def compute_tc_r(BDF , area , suppress=True):
    """Performs computation of Time of Concentration and Storage Coefficeint based on BDF and Drainage area."""
    def comp_Tc(BDF , area):
        "Computes Time of Concentration based on BDF and Area (in sq.mi.)"
        def comp_Tr(BDF , area):
            tr = 10.0 ** ((-0.05288 * BDF) + (0.4208 * np.log10 (area)) + 0.3926)
            return tr
        tc = comp_Tr (BDF , area) + ((area ** 0.5) / 2)
        return tc

    def comp_R(BDF , area):
        "Computes Storage Coefficient based on BDF and Area"
        r = 8.271 * np.exp (-0.1167 * BDF) * area ** (0.3856)
        return r
    tc = comp_Tc (BDF , area)
    r = comp_R (BDF , area)
    if not suppress:
        print('\n\twhen, BDF={0}, area={1} sq.mi.\n\t\tTc:{2} Hr. R:{3}Hr.'.format (BDF , round (area , 3) ,
                                                                                    round (tc , 2) , round (r , 2)))
    return tc , r