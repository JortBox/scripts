#!/usr/bin/python
# initial calibration of the calibrator, sol flag + effects separation

skymodel = '/home/fdg/scripts/model/3C196-allfield.skymodel' # tooth LBA
parset_dir = '/home/fdg/scripts/autocal/1RXSJ0603_LBA/parset_cal' # tooth LBA
#skymodel = '/home/fdg/scripts/model/3C295-allfield.skymodel' # virgo LBA
#parset_dir = '/home/fdg/scripts/autocal/VirA_LBA/parset_cal' # virgo LBA
#skymodel = '/home/fdg/scripts/model/3C295-allfield.skymodel' # virgo HBA
#parset_dir = '/home/fdg/scripts/autocal/VirA_HBA/parset_cal' # virgo HBA
#skymodel = '/home/fdg/scripts/scripts/model/3C196-allfield.skymodel' # perseus LBA
#parset_dir = '/home/fdg/scripts/autocal/PerA_LBA/parset_cal' # perseus LBA
#skymodel = '/home/fdg/scripts/scripts/model/3C295-allfield.skymodel' # mode-test LBA
#parset_dir = '/home/fdg/scripts/autocal/LBAmode/parset_cal' # mode-test LBA

###################################################

import sys, os, glob, re
import numpy as np
import pyrap.tables as pt
from lib_pipeline import *

set_logger()
check_rm('logs')
s = Scheduler(dry=False)
mss = sorted(glob.glob('*MS'))

##############################################
# Initial processing (2/2013->2/2014)
logging.warning('Fix beam table')
for ms in mss:
    s.add('/home/fdg/scripts/fixinfo/fixbeaminfo '+ms, log=ms+'_fixbeam.log')
s.run(check=False)

##############################################
# Avg data DATA -> SMOOTHED_DATA (BL-based smoothing)
# NOTE: the WEIGHTED_COLUMN is now smoothed in this dataset, a backup is in WEIGHTED_COLUMN_ORIG
logging.info('BL-averaging')
for ms in mss:
    s.add('BLavg.py -r -w -i DATA -o SMOOTHED_DATA '+ms, log=ms+'_avg.log')
s.run(check=False)

############################################
# If only clock is tarnsferred we need to prepare a parmdb
logging.info('Creating fake parmdb...')
for ms in mss:
    s.add('calibrate-stand-alone -f --parmdb-name instrument_fake '+ms+' '+parset_dir+'/bbs-fakeparmdb.parset '+skymodel, log=ms+'_fakeparmdb.log', cmd_type='BBS')
s.run(check=True)

###############################################
# Initial calibrator
# Solve cal_SB.MS:SMOOTHED_DATA (only solve)
logging.info('Calibrating with skymodel: '+skymodel)
for ms in mss:
    s.add('calibrate-stand-alone -f '+ms+' '+parset_dir+'/bbs-cal.parset '+skymodel, log=ms+'_cal.log', cmd_type='BBS')
s.run(check=True)

##############################################
# Clock/TEC check and flagging
check_rm('globaldb*')
os.system('mkdir globaldb')
if only_clock: os.system('mkdir globaldb-clockonly')

logging.info('Running LoSoTo...')
for i, ms in enumerate(mss):
    num = re.findall(r'\d+', ms)[-1]

    logging.debug('Copy instrument of '+ms+' into globaldb/instrument-'+str(num))
    os.system('cp -r '+ms+'/instrument globaldb/instrument-'+str(num))
    if i == 0: os.system('cp -r '+ms+'/ANTENNA '+ms+'/FIELD '+ms+'/sky globaldb/')
    
    # We export clock, need to create a new parmdb
    logging.debug('Copy instrument_fake of '+ms+' into globaldb-clockonly/instrument-'+str(num))
    os.system('cp -r '+ms+'/instrument_fake globaldb-clockonly/instrument-'+str(num))
    if i == 0: os.system('cp -r '+ms+'/ANTENNA '+ms+'/FIELD '+ms+'/sky globaldb-clockonly/')

check_rm('plots')
os.makedirs('plots')
check_rm('cal.h5')
s.add('H5parm_importer.py -v cal.h5 globaldb', log='losoto.log', cmd_type='python')
s.run(check=False)
s.add('losoto -v cal.h5 '+parset_dir+'/losoto.parset', log='losoto.log', log_append=True, cmd_type='python', processors='max')
s.run(check=False)
s.add('H5parm_exporter.py -v cal.h5 globaldb-clockonly', log='losoto.log', log_append=True, cmd_type='python')
s.run(check=True)

logging.info("Done.")
