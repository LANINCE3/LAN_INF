"""

Performs some basic geometric computations and conversions

"""
import numpy as np
from math import pi, hypot, floor

def rounddn(x, val=50.0):
    return int(floor(x / val)) * int(val)


def stationing_to_float(station):
    num = str(station).replace("+", "").replace(",", "")
    if "." in list(num):
        val = round(float(num), 2)
    else:
        val = round(float(num), 0)
    return val


def float_to_station(station_as_number):
    station = str(int(station_as_number))
    if len(list(station)) > 2:
        station = str('{0}+'.format(station[:-2])) + station[-2:]
    elif len(list(station)) <= 2 and len(list(station)) > 1:
        station = "00+{0}".format(station)
    else:
        station = "00+0{0}".format(station)
    return station

def getHypot(a, b):
    "Returns a rouned value for the hypotenuse of two legs 'a' and 'b' of a right triangle."
    return round(hypot(a, b), 2)


def getTheta(opp, adjacent):
    """:returns angle (in radians) between traingle legs "a" and "b". """

    return round(np.arctan2(float(opp), float(adjacent)), 8)


def get_legs(x1, y1, x2, y2):
    ":returns 'legs' magnitude and distance of two legs in the 'x' and 'y' of  two coordinate points."
    return x2 - x1, y2 - y1


def get_segment_length(x1, y1, x2, y2):
    """Returns the distance between two points."""
    a, b = get_legs(x1, y1, x2, y2)
    return getHypot(a, b)


def adjust_y( m, x1, y1, x2):
    """Reorients Theta to exist wihtin Quadrant 1 and Quadrant 4 of a polar graph"""
    y2 = m * (x2-x1) + y1
    return y2