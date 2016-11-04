#!/usr/bin/env python

from __future__ import print_function

import glob
import os
import subprocess
import sys
from datetime import datetime

from numpy import sqrt

import pygrib

TMPDIR = 'tmp/'
DATADIR = 'data/'

# bounds to create sliced versions for:
BOUNDS = {
    # label: [sw_corner, ne_corner] in (lng, lat)-order
    'nl': [[3.071, 50.748], [7.252, 53.761]],
    'ijmwad': [[4.363, 52.294], [5.903, 53.411]],
    'zeeland': [[2.6, 51.2], [5.0, 52.0]]
}

# discover ggrib location
GGRIB_BIN = None
for location in ('/usr/local/bin/ggrib', './ggrib'):
    if os.path.isfile(location) and os.access(location, os.X_OK):
        GGRIB_BIN = location

if __name__ == '__main__':
    files = sorted(glob.glob(os.path.join(TMPDIR, '*_GB')))

    if len(files) != 49:
        print('Verkeerd aantal GRIB-bestanden in {}, exiting'.format(TMPDIR))
        sys.exit(1)

    gribout = open(TMPDIR+'temp.grb', 'wb')
    gribout_wind = open(TMPDIR+'temp_wind.grb', 'wb')

    def writeGribMessage(message, wind=False):
        message['generatingProcessIdentifier'] = 96
        message['centre'] = 'kwbc'

        gribout.write(message.tostring())
        if wind:
            gribout_wind.write(message.tostring())

    for filename in files:
        grbs = pygrib.open(filename)

        # Mean sea level pressure
        msg_mslp = grbs.select(indicatorOfParameter=1)[0]
        msg_mslp.indicatorOfParameter = 2
        msg_mslp.indicatorOfTypeOfLevel = 'sfc'
        msg_mslp.typeOfLevel = 'meanSea'
        writeGribMessage(msg_mslp)

        # Relative humidity
        msg_rh = grbs.select(indicatorOfParameter=52)[0]
        msg_rh.values = msg_rh.values * 100
        writeGribMessage(msg_rh)

        # Temperature 2m
        msg_t = grbs.select(indicatorOfParameter=11)[0]
        writeGribMessage(msg_t)

        # U-wind
        msg_u = grbs.select(indicatorOfParameter=33)[0]
        writeGribMessage(msg_u, wind=True)

        # V-wind
        msg_v = grbs.select(indicatorOfParameter=34)[0]
        writeGribMessage(msg_v, wind=True)

        # Precipication Intensity
        msg_ip = grbs.select(indicatorOfParameter=61, level=456)[0]
        msg_ip.typeOfLevel = 'surface'
        msg_ip.level = 0
        msg_ip.values = msg_ip.values * 3600  # mm/s => mm/h
        writeGribMessage(msg_ip)

        # Wind gusts
        msg_ug = grbs.select(indicatorOfParameter=162)[0]
        msg_vg = grbs.select(indicatorOfParameter=163)[0]
        msg_ug.values = sqrt(msg_ug.values ** 2 + msg_vg.values ** 2)
        msg_ug.indicatorOfParameter = 180
        msg_ug.typeOfLevel = 'surface'
        msg_ug.level = 0
        writeGribMessage(msg_ug, wind=True)

        os.remove(filename)

    run_time = datetime.strptime(files[0][-17:-7], '%Y%m%d%H').strftime('%Y-%m-%d_%H')

    filename = DATADIR + '{0}/harmonie_zy_{0}.grb'.format(run_time)
    filename_fmt = DATADIR + '{0}/harmonie_zy_{0}_{{}}.grb'.format(run_time)
    if not os.path.isdir(DATADIR + run_time):
        os.mkdir(DATADIR + run_time)

    # delete old files
    for file in glob.glob('harm36_v1_*.grb.bz2'):
        os.remove(file)

    def compress_rename(src, dst):
        subprocess.call(['bzip2', src])
        os.rename(src + '.bz2', dst)

    def bounded_slice(src, name, bounds):
        dst = filename_fmt.format(name)
        print('Writing {} to {}'.format(name, dst))

        tmp_filename = 'temp_bounds.grb'
        cmd = [GGRIB_BIN, src, tmp_filename]
        cmd.extend(map(str, [bounds[0][0], bounds[0][1], bounds[1][0], bounds[1][1]]))
        subprocess.call(cmd)

        compress_rename(tmp_filename, dst)

    if GGRIB_BIN is None:
        print('ggrib binary not found, please install by typing `make ggrib`')
    else:
        DEVNULL = open(os.devnull, 'wb')

        for name, bounds in BOUNDS.items():
            bounded_slice(TMPDIR+'temp.grb', name, bounds)
            bounded_slice(TMPDIR+'temp_wind.grb', 'wind_' + name, bounds)

    compress_rename(TMPDIR+'temp.grb', filename)
    compress_rename(TMPDIR+'temp_wind.grb', filename_fmt.format('wind'))
