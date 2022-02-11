#!/bin/env python3

import os
import sys
import argparse
import time
import json
import glob
import itertools as it
import re
import pandas as pd
import numpy as np
from string import Formatter
import parse
import pwd
import shutil
import subprocess
from datetime import datetime

scriptDir = os.path.dirname(os.path.realpath(__file__))
defaultConfigPath = os.path.join(scriptDir,'config.json')
defaultPapayaPath = os.path.join(scriptDir,'papaya_template')

# ARGUMENT PARSER
ap = argparse.ArgumentParser(description='Perform visual quality checks on a dataset using Papaya')

ap.add_argument('-d','--data-dir',required=True,help='base path of data directory')
ap.add_argument('-c','--check',required=True,help='specify which check to perform. This must match a key in config.json.')
ap.add_argument('-n','--n-batch',type=int,default=50,help='specify how many images to include in a batch [DEFAULT = 50]')
ap.add_argument('--filter',nargs='+',action='append',help='argument pairs for search filter. First argument must be a field in config formatted string, subsequent arguments denote possible values')
ap.add_argument('--browser-cmd',default='firefox',help='specify browser command [DEFAULT = "firefox"]')
ap.add_argument('--config',default=defaultConfigPath,help=f'specify config file [DEFAULT = {defaultConfigPath}]')
ap.add_argument('--papaya-template-dir',default=defaultPapayaPath,help=f'specify papaya template folder [DEFAULT = {defaultPapayaPath}]')

modes = ap.add_mutually_exclusive_group()
modes.add_argument('--fail',action='store_true',default=False,help='search through images that have been failed within current query')
modes.add_argument('--flag',action='store_true',default=False,help='search through images that have been flagged within current query.')
modes.add_argument('--unlock',action='store_true',default=False,help='remove lock files for current query')
modes.add_argument('--summary',action='store_true',default=False,help='output summary text for current query')


args = vars(ap.parse_args())

def get_format_fields(formatstr):
    return [ x for _,x,_,_ in Formatter().parse(formatstr) if x ]

def query_files(formatstr,formats):
    '''
    reads format string and arguments from parser, constructs glob searches and
    returns found files
    '''
    argList = [ dict(zip(formats.keys(),x)) for x in it.product(*formats.values()) ]
    files = []
    for x in argList:
        print(f'glob: {formatstr.format(**x)}')
        files.extend(glob.glob(formatstr.format(**x)))
    return files

def get_config(config):
    '''
    reads in then validates the config file. There cannot be any format strings
    in "overlay" or "qcDir" fields not present in "image"
    '''
    with open(config,'r') as x:
        config = json.load(x)
    # image and qc can not have any fields not in overlay
    for k,v in config.items():
        overlay_fields = get_format_fields(v['overlay'])
        image_fields = get_format_fields(v['image'])
        qc_fields = get_format_fields(v['qcDir'])
        if not(all(x in overlay_fields for x in image_fields)):
            raise ValueError(
                f'''One or more format strings for {k}["image"] is not present
                in {k}["overlay"].'''.replace('\n',''))
        if not(all(x in overlay_fields for x in qc_fields)):
            raise ValueError(
                f'''One or more format strings for {k}["qc"] is not present
                in {k}["overlay"].'''.replace('\n',''))
    return config

def write_lock_file(filename):
    '''
    write current user ID and timestamp to specified filename
    '''
    user = pwd.getpwuid(os.getuid())[0]
    timestamp = time.strftime("%Y-%M-%d_%H-%M-%S")
    with open(filename,'w') as x:
        x.write(user)
        x.write(timestamp)


# read in config file
config = get_config(args['config'])

# verify check is valid
if args['check'] not in config.keys():
    raise ValueError(
        f'''{args["check"]} is not a valid check type. Must be one of
        {config.keys()} or must be added to config'''.replace('\n',''))

# get formats for config format strings
formats = {}
formats['data_dir'] = [args['data_dir']]
fields = get_format_fields(config[args['check']]['overlay'])
if args['filter'] is not None:
    for x in args['filter']:
        if x[0] in fields:
            formats[x[0]] = x[1:]
        else:
            raise ValueError(' '.join(
                f'''filter {x} does not match a format that is present in
                {os.path.basename(args["config"])}'''.split()))
for x in fields:
    if x not in formats.keys():
        formats[x] = ['*'] # if not filtered, generic wildcard

# query images and create dataframe
print(f'[{time.strftime("%H:%M:%S")}]','Searching for images...')
df = pd.DataFrame({'overlay':query_files(config[args['check']]['overlay'],formats)})

if len(df) == 0:
    print('No images matching config formats found. Exiting...')
    sys.exit()

# reverse the format string to get relevant variables (to find image files)
df['vars'] = df['overlay'].apply(
    lambda x: parse.parse(config[args['check']]['overlay'],x).named)

df['overlay'] = df['overlay'].apply(os.path.abspath)
df['image'] = df['vars'].apply(
    lambda x: os.path.abspath(config[args['check']]['image'].format(**x)))
df['qcDir'] = df['vars'].apply(
    lambda x: os.path.abspath(config[args['check']]['qcDir'].format(**x)))
df['doneFile'] = df['qcDir'].apply(
    lambda x: os.path.join(x,f'{args["check"]}.done'))
df['lockFile'] = df['qcDir'].apply(
    lambda x: os.path.join(x,f'{args["check"]}.lock'))

print(f'[{time.strftime("%H:%M:%S")}]','Validating files...')
df['imageExists'] = df['image'].apply(os.path.isfile)
df['isDone'] = df['doneFile'].apply(os.path.isfile)
df['isLocked'] = df['lockFile'].apply(os.path.isfile)

# read in previous quality check information
if not(args['unlock']):
    print(f'[{time.strftime("%H:%M:%S")}]','Reading completed check files...')
    df['currentRating'] = np.nan
    df['currentFlagged'] = np.nan
    df.loc[df['isDone'],'currentRating'] = df[df['isDone']]['doneFile'].apply(
        lambda x: pd.read_csv(x,sep='\t')['Rating'][0])
    df.loc[df['isDone'],'currentFlagged'] = df[df['isDone']]['doneFile'].apply(
        lambda x: pd.read_csv(x,sep='\t')['Flagged'][0])
else:
    df = df[df['isLocked']]
    df['lockFile'].apply(os.remove)
    print(f'[{time.strftime("%H:%M:%S")}]',f'All locks removed.')
    sys.exit()

# if doneFile is older than the overlay file, then we need to remove the doneFile
df['doneTimestamp'] = np.nan
df.loc[df['isDone'],'doneTimestamp'] = df.loc[df['isDone'],'doneFile'].apply(
    lambda x: datetime.fromtimestamp(os.path.getmtime(x)))
df['overlayTimestamp'] = df['overlay'].apply(
    lambda x: datetime.fromtimestamp(os.path.getmtime(x)))

df.loc[df['doneTimestamp'] < df['overlayTimestamp'],'doneFile'].apply(os.remove)
df.loc[df['doneTimestamp'] < df['overlayTimestamp'],'isDone'] = False

if args['summary']:
    print(
    f'''
    ---------------- SUMMARY ---------------
    Number of files in query: {len(df)}
    Number of files checked: {df["isDone"].sum()} ({df["isDone"].mean()*100:.2f}%)
    Number of files failed: {sum(df["currentRating"] == 0)}
    Number of files flagged: {df["currentFlagged"].sum()}
    Number of files currently locked: {df["isLocked"].sum()}
    ----------------------------------------
    ''')
    exit()

# Do data frame filters!
df = df[~df['isLocked']]
if args['fail']:
    df = df[df['currentRating'] == 0]
    df.reset_index(inplace=True)
elif args['flag']:
    df = df[df['currentFlagged'] == 1]
    df.reset_index(inplace=True)
else:
    df = df[~df['isDone']]
    df.reset_index(inplace=True)

# adjust to batch size
if len(df) > args['n_batch']:
    df = df.iloc[0:args['n_batch'],:].copy()
elif len(df) == 0:
    print('No files available to check. Exiting...')
    sys.exit()

# create lock files
df['qcDir'].apply(lambda x: os.makedirs(x,exist_ok=True))
df['lockFile'].apply(write_lock_files)

#this section wrapped in try so locks are removed if anything is afoot!
try:
    # STEP 2: PREPARE THE PAPAYA
    print(f'[{time.strftime("%H:%M:%S")}]','Configuring Papaya Viewer...')

    user = pwd.getpwuid(os.getuid())[0]
    workDir = os.path.join('tmp',f'{user}_{time.strftime("%Y-%m-%d_%H-%M-%S")}')
    os.mkdir(workDir)

    # copy papaya template files
    for x in os.listdir(args['papaya_template_dir']):
        shutil.copy(os.path.join(args['papaya_template_dir'],x),workDir)

    # write envvars.js papaya file
    with open(os.path.join(workDir,'envvars.js'),'w') as x:
        x.write(f'username="{user}";\n')
        x.write(f'filename="{workDir}/subs.csv";\n')
        x.write(f'checktype="{args["check"]}";\n')
        x.write(f'tempname="{os.path.basename(workDir)}";\n')

    # write images.json papaya file
    images = [ [x,y] for x,y in zip(df['image'],df['overlay']) ]
    images.append(["",""]) # empty final row so they know they're done
    with open(os.path.join(workDir,'images.json'),'w') as x:
        json.dump(images,x)

    # write subs.csv papaya file
    with open(os.path.join(workDir,'subs.csv'),'w') as x:
        for i,row in df.iterrows():
            s = ''
            for k,v in row['vars'].items():
                s += f'{k}={v}, '
            x.write(s[:-1]+'\n')

    # STEP 3: LAUNCH PAPAYA
    print(f'[{time.strftime("%H:%M:%S")}]','Launching Papaya in firefox browser...')
    subprocess.run(['firefox',os.path.join(workDir,"index.html")],stderr=subprocess.DEVNULL)

    #the csv gets saved into the downloads folder with the same name as the temp directory
    outPath = os.path.join(os.path.expanduser('~'),'Downloads',f'{os.path.basename(workDir)}.csv')
    if not(os.path.exists(outPath)):
        raise Exception('firefox was closed before the CSV was saved :(')

    # STEP 4: CLEANUP
    print(f'[{time.strftime("%H:%M:%S")}]','Saving QC data and cleaning up working environment...')
    dfOut = pd.read_csv(outPath,names=['basename','Rating','Flagged','User','check'],skiprows=1)
    df['basename'] = df['overlay'].apply(os.path.basename)
    dfOut = dfOut.merge(df,on='basename',how='left')
    dfOut['Timestamp'] = datetime.fromtimestamp(os.path.getmtime(outPath))

    # write {check}.done files
    for i,row in dfOut.iterrows():
        d = list(row[['Rating','Flagged','User','Timestamp']])
        d = [ str(x) for x in d ]
        print(f'\t{row["doneFile"]} saved')
        with open(row['doneFile'],'w') as x:
            x.write('Rating\tFlagged\tUser\tTimestamp\n')
            x.write('\t'.join(d)+'\n')

    # delete stuff
    df['lockFile'].apply(os.remove)
    shutil.rmtree(workDir)
    os.remove(outPath)

    print(f'[{time.strftime("%H:%M:%S")}]','Batch Completed!')
except:
    if 'df' in locals():
        [ os.remove(x) for x in df['lockFile'] if os.path.isfile(x) ]
    if 'workDir' in locals():
        shutil.rmtree(workDir)
    if 'outPath' in locals():
        if os.path.isfile(outPath):
            os.remove(outPath)
    raise
