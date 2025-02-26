#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 - Francesco de Gasperin
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# Usage: updatefits.py -setbeam max min pa -setkeyword name=value fitsfile

import sys,optparse,re
import numpy as np
from astropy.io import fits as pyfits

def isfloat(x):
    try:
        a = float(x)
    except ValueError:
        return False
    else:
        return True

def isint(x):
    try:
        a = float(x)
        b = int(a)
    except ValueError:
        return False
    else:
        return a == b

opt = optparse.OptionParser(usage="%prog [-setbeam max,min,pa] [-setkeyword keyword=value] fitsfile", version="%prog 0.1")
opt.add_option('-b', '--setbeam', help='Set beam minaxis maxaxis and position angle to three comma-separated numbers (arcsec,arcsec,degree) [ex: 123,123,90]')
opt.add_option('-k', '--setkeyword', help='Set a keyword to a specific value (e.g. --k CRPIX1=10)')
opt.add_option('-p', '--setpix', help='Set a pixel value to a new value, -999 is nan (e.g. --p 0=-999')
opt.add_option('-d', '--delkeyword', help='Delete a keyword')
(options, img) = opt.parse_args()
setbeam = options.setbeam
setkeyword = options.setkeyword
setpix = options.setpix
delkeyword = options.delkeyword
sys.stdout.flush()

try:
    hdulist = pyfits.open(img[0], mode='update')
except:
    print("ERROR: problems opening file "+img[0])
    sys.exit(1)

if setkeyword is None and setpix is None and setbeam is None and delkeyword is None:
    for entry, val in hdulist[0].header.items():
        print(entry, val)
    sys.exit(0)

if ( not setkeyword is None ):
    try: keyword, value = setkeyword.split('=')
    except:
        print("ERROR: the format for \"--setkeyword\" is keyword=value")
        sys.exit(1)
    prihdr = hdulist[0].header
    print("Setting",keyword,"=",value)
    if keyword in prihdr:
        print("Type is found to be: ", type(prihdr[keyword]))
        prihdr[keyword] = type(prihdr[keyword])(value)
    else:
        if isint(value) and '.' not in value: # the '.' exclude doubles like 180.0
            prihdr[keyword] = int(value)
        elif isfloat(value):
            prihdr[keyword] = float(value)
        else:
            prihdr[keyword] = str(value)

if ( not setpix is None ):
    try: 
        oldvalue, newvalue = setpix.split('=')
        oldvalue = float(oldvalue)
        newvalue = float(newvalue)
        if newvalue == -999: newvalue = np.nan
    except:
        print("ERROR: the format for \"--setpix\" is oldvalue=newvalue")
        sys.exit(1)
    print("Setting data %f -> %f" % (oldvalue, newvalue))
    hdulist[0].data[(hdulist[0].data == oldvalue)] = newvalue

if ( not delkeyword is None ):
    prihdr = hdulist[0].header
    for keyword in prihdr[:]:
        if re.match(delkeyword, keyword):
            print("Deleting",keyword)
            del prihdr[keyword]

if ( not setbeam is None ):
    try: bmaj,bmin,pa = setbeam.split(',')
    except:
        print("ERROR: the format for \"--setbeam\" is max,min,pa (arcsec,arcsec,deg)")
        sys.exit(1)
    prihdr = hdulist[0].header
    print("Setting beam to ",bmaj,bmin,pa)
    bmaj = float(bmaj)/3600.
    bmin = float(bmin)/3600.
    pa = float(pa)
    prihdr['BMAJ'] = bmaj
    prihdr['BMIN'] = bmin
    prihdr['BPA'] = pa

hdulist.flush()
print("Done!")
