#!/usr/bin/python
# data preparation for selfcal, apply cal solutions and split SB in time and concatenate in freq
# Input:
# Virgin target MSs and a globaldb of the calibrator
# Output:
# set of group*_TC*.MS file with DATA = calibrator corrected data, beam corrected, flagged

import sys, os, glob, re
import numpy as np
import pyrap.tables as pt
from lib_pipeline import *

parset_dir = '/home/fdg/scripts/autocal/LBAsurvey/parset_timesplit'
initc = 0 # initial tc num (useful for multiple observation of same target) - tooth10==12

if 'tooth' in os.getcwd():
    # tooth
    ngroups = 2 # number of groups (totalSB/SBperFREQgroup)
    datadir = '.' # tooth
    globaldb = 'globaldb'
    do_fixbeamtable = True
else:
    # survey
    ngroups = 1 # number of groups (totalSB/SBperFREQgroup)
    datadir = '/lofar5/stsf309/LBAsurvey/%s/%s' % (os.getcwd().split('/')[-2], os.getcwd().split('/')[-1]) # assumes e.g. ~/data/LBAsurvey/c05-o07/P155+52
    globaldb = '../3c196/globaldb' #TODO: copy form repository
    do_fixbeamtable = False

##################################################################################################

set_logger('pipeline-timesplit.logging')
check_rm('logs')
s = Scheduler(dry=False)
assert os.path.isdir(globaldb)

#################################################
## Clear
logging.info('Cleaning...')

check_rm('*group*')
mss = sorted(glob.glob(datadir+'/*MS'))

##############################################
# Avg to 4 chan and 4 sec
# Remove internationals
nchan = find_nchan(mss[0])
timeint = find_timeint(mss[0])
if nchan % 4 != 0:
    logging.error('Channels should be a multiple of 4.')
    sys.exit(1)
avg_factor_f = nchan / 4 # to 4 ch/SB
if avg_factor_f < 1: avg_factor_f = 1
avg_factor_t = int(np.round(4/timeint))
if avg_factor_t < 1: avg_factor_t = 1 # to 4 sec

if avg_factor_f != 1 or avg_factor_t != 1:
    logging.info('Average in freq (factor of %i) and time (factor of %i)...' % (avg_factor_f, avg_factor_t))
    for ms in mss:
        msout = ms.replace('.MS','-avg.MS').split('/')[-1]
        if os.path.exists(msout): continue
        s.add('NDPPP '+parset_dir+'/NDPPP-avg.parset msin='+ms+' msout='+msout+' msin.datacolumn=DATA avg.timestep='+str(avg_factor_t)+' avg.freqstep='+str(avg_factor_f), \
                    log=msout+'_avg.log', cmd_type='NDPPP')
    s.run(check=True)
    nchan = nchan / avg_factor_f
    timeint = timeint * avg_factor_t
    mss = sorted(glob.glob('*-avg.MS'))

################################################
# Initial processing
if do_fixbeamtable:
    logging.warning('Fix beam table')
    for ms in mss:
        s.add('/home/fdg/scripts/fixinfo/fixbeaminfo '+ms, log=ms+'_fixbeam.log')
    s.run(check=False)

####################################################
# Beam correction DATA -> CORRECTED_DATA (beam corrected)
logging.info('Beam correction...')
for ms in mss:
    s.add('NDPPP '+parset_dir+'/NDPPP-beam.parset msin='+ms, log=ms+'_beam.log', cmd_type='NDPPP')
s.run(check=True)

###################################################################################################
# To circular - SB.MS:CORRECTED_DATA -> SB.MS:CORRECTED_DATA (circular)
logging.info('Convert to circular...')
for ms in mss:
    s.add('/home/fdg/scripts/mslin2circ.py -s -w -i '+ms+':CORRECTED_DATA -o '+ms+':CORRECTED_DATA', log=ms+'_circ2lin.log', cmd_type='python')
s.run(check=True)

##########################################################################################
# Copy instrument tables
for ms in mss:
    num = re.findall(r'\d+', ms)[-1]
    check_rm(ms+'/instrument')
    logging.debug('cp -r '+globaldb+'/sol000_instrument-'+str(num)+' '+ms+'/instrument')
    os.system('cp -r '+globaldb+'/sol000_instrument-'+str(num)+' '+ms+'/instrument')

# Apply cal sol - SB.MS:CORRECTED_DATA -> SB.MS:CORRECTED_DATA (calibrator corrected data, beam corrected, lin)
logging.info('Apply solutions...')
for ms in mss:
    s.add('NDPPP '+parset_dir+'/NDPPP-cor.parset msin='+ms+' cor1.parmdb='+ms+'/instrument'+' cor2.parmdb='+ms+'/instrument', log=ms+'_cor.log', cmd_type='NDPPP')
s.run(check=True)

###################################################################################################
# Create groups
groupnames = []
logging.info('Concatenating in frequency...')
for i, msg in enumerate(np.array_split(mss, ngroups)):
    if ngroups == 1:
        groupname = 'mss'
    else:
        groupname = 'mss%02i' %i
    groupnames.append(groupname)
    check_rm(groupname)
    os.system('mkdir '+groupname)

    # add missing SB with a fake name not to leave frequency holes
    num_init = int(re.findall(r'\d+', msg[0])[-1])
    num_fin = int(re.findall(r'\d+', msg[-1])[-1])
    ms_name_init = msg[0]
    msg = []
    for j in range(num_init, num_fin+1):
        msg.append(ms_name_init.replace('SB%03i' % num_init, 'SB%03i' % j))

    # prepare concatenated time chunks (TC) - SB.MS:CORRECTED_DATA -> group#.MS:DATA (cal corr data, beam corrected, circular)
    s.add('NDPPP '+parset_dir+'/NDPPP-concat.parset msin="['+','.join(msg)+']"  msout='+groupname+'/'+groupname+'.MS', \
                log=groupname+'_NDPPP_concat.log', cmd_type='NDPPP')
s.run(check=True)

# Flagging on concatenated dataset
logging.info('Flagging...')
for groupname in groupnames:
    s.add('NDPPP '+parset_dir+'/NDPPP-flag.parset msin='+groupname+'/'+groupname+'.MS', \
                log=groupname+'_NDPPP_flag.log', cmd_type='NDPPP')
s.run(check=True)

# Create time-chunks
for groupname in groupnames:
    ms = groupname+'/'+groupname+'.MS'
    if not os.path.exists(ms): continue
    t = pt.table(ms, ack=False)
    starttime = t[0]['TIME']
    endtime   = t[t.nrows()-1]['TIME']
    hours = (endtime-starttime)/3600.
    logging.debug(ms+' has length of '+str(hours)+' h.')

    # split this ms into many TCs (#hours, i.e. chunks of 60 min)
    # to re-concat:
    #   t = table(['T0','T1',...])
    #   t.sort('TIME').copy('output.MS', deep = True)
    for tc, timerange in enumerate(np.array_split(t.getcol('TIME'), round(hours))):
        tc += initc
        logging.debug('%02i - Splitting timerange %f %f' % (tc, timerange[0], timerange[-1]))
        t1 = t.query('TIME >= ' + str(timerange[0]) + ' && TIME <= ' + str(timerange[-1]), sortlist='TIME,ANTENNA1,ANTENNA2')
        splitms = groupname+'/TC%02i.MS' % tc
        check_rm(splitms)
        t1.copy(splitms, True)
        t1.close()
    t.close()

    check_rm(ms) # remove not-timesplitted file

logging.info("Done.")
