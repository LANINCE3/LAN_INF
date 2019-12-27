# -*- coding: utf-8 -*-
"""
Created on August 08 08:44:25 2018
@author: Alexander Govea

This script is a part of the Watershed Planning Tool development project,
 which is developed by Lockwood Andrews & Newnam Inc (LAN) for Harris
 County Flood Control District (HCFCD).

 The VB_Mgmt.py Files functions as a method for communicating with the WPT_NET executable for calling
 a particular hec ras model running a computaiton and retreiving select data from the executable by means of accessing the executables output csv files.


the UpdateGDBs script developed to tie in tool results into a GIS geodatabase (GDB) .
"""

import os, sys
import subprocess
import pandas as pd
from json import loads
from random import uniform
from subprocess import CalledProcessError
import traceback
import time
from UtiltyMgmt import on_error, get_active_process, kras, ksub, clean_active_process_files, write_txt_file
from Config import WPTConfig

WPTConfig.init()
sys.path.append(os.path.dirname(__file__))

def vb_function_exit(fi, scratch_fldr):
    kras()
    ksub()
    clean_active_process_files(scratch_fldr)
    try:
        if os.path.exists(fi):
            os.remove(fi)
        else:
            pass
    except:
        pass

def check_if_file_locked(filepath, scratch_fldr):
    """Check's if file in file path is locked. If the file is locked an IO Error is thrown attempted to be force deleted.
    Then checking if the file is locked and or present after.
    Inputs:
        [0] filepath - (str) file path to locked file
    Ouptus:
        [0] result - (Boolean) or (None) """
    result = None
    count = 0
    while (result is None or result == True) and (count <= 4):
        if os.path.exists(filepath):
            try:
                name, ext = os.path.splitext(os.path.basename(os.path.abspath(filepath)))
                temp_name = 'test_rename'
                dirnam = os.path.dirname(os.path.abspath(filepath))
                os.rename(os.path.join(filepath), os.path.join(dirnam, temp_name+ext))
                os.rename( os.path.join(dirnam, temp_name+ext), os.path.join(filepath))
                result = False
            except IOError:
                msg =  "\tFile {0} locked! Attempting to Remove File.\n"
                time.sleep(0.1)
                x = subprocess.Popen('FORCEDEL /Q "{0}"'.format(filepath), shell=False).wait()
                result = True
                count +=1
            except:
                lines = '{0}\n'.format (traceback.format_exc ())
                on_error(WPTConfig.Options_NetworkFile, scratch_fldr, lines)
                result = None
                count += 1
        else:
            result = False
    return result


def fetch_controller_data(prjfile, plantitle, scratch_fldr, out_data):
    """This function is used to work in unison with the "WPT_NET" Executable to operate as a go between with the HEC_RAS
     Controller. The current scope of the vb executable is used to generate the output data used within the WPT code.
    Args:
        [0] prj file - (str) the file path to a hec-ras project file
        [1] plantitle - (str) the exact title name of a hec-ras plan file
        [2] scratch_fldr - (str) the file path to a folder to deposit generated output files. often linked
                            to the ras-scratch file.
        [3] out_data - (str) the requested output data for the tool (i.e 'los_df', 'nodes', 'ws_df',
                                                                'vel_df', 'channel_info', 'inverts', or 'computes')
    Outputs:
        [0] - Depending on the out_data variable a csv file or nothing is generated. If a csv file is generated, the
         funciton will interprete and return the csv as a dataframe. Otherwise nothing is passed (i.e. 'computes').
     """
    # the out_data varialble will be used to establish what type of output data is expected to be returned from the executable
    sfldr = "Scratch={0}".format(scratch_fldr)
    result = None
    count = 0
    while result is None and count <=5:
        flocked = check_if_file_locked(os.path.join(scratch_fldr,"{0}.csv".format(out_data)),scratch_fldr)
        lines = ['Inputs: {0}, {1}, {2}\n'.format(prjfile,plantitle,out_data), '\t\tfile locked: {0}\n'.format(flocked)]
        if os.path.exists(scratch_fldr) and flocked is False:
            try:
                exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'WPT_NET.exe')
                if os.path.exists(exe):
                    exe = exe.replace('\\','/')
                kras()
                # write_txt_file (os.path.join (scratch_fldr , 'VB_Inputs.txt') ,
                #                 lines , True)
                clean_active_process_files(scratch_fldr)
                time.sleep(uniform(0.4,2.4))
                get_active_process(scratch_fldr, False)
                subprocess.check_output('"{0}" "{1}" "{2}" "{3}" "{4}"'.format(exe, prjfile, plantitle, sfldr, out_data), shell=False)
                time.sleep(4.0)
                get_active_process(scratch_fldr, False)
                time.sleep (0.3)
                if out_data == 'los_df':
                    # multi-dim array
                    fl = os.path.join(scratch_fldr, '{0}.csv'.format(out_data))
                    if os.path.exists(fl):
                        result = pd.DataFrame.from_csv(fl, index_col=False)
                        vb_function_exit (fl , scratch_fldr)
                        return result
                    else:
                        pass
                        # print('File {0} DNE\n'.format(fl))
                elif out_data == "nodes":
                    # list
                    fl = os.path.join(scratch_fldr,  '{0}.csv'.format(out_data))
                    if os.path.exists(fl):
                        result = pd.DataFrame.from_csv(fl, index_col=False)
                        # prep and convert to list
                        result = [round(sta,4) for sta in result['Riv_Sta'].tolist()]
                        result.sort(reverse=True)
                        vb_function_exit (fl , scratch_fldr)
                        return result
                    else:
                        pass
                        # print('File {0} DNE\n'.format(fl))
                elif out_data == "ws_df":
                    # multi-dim array
                    fl = os.path.join(scratch_fldr,  '{0}.csv'.format(out_data))
                    if os.path.exists(fl):
                        result = pd.DataFrame.from_csv(fl, index_col=False)
                        vb_function_exit (fl , scratch_fldr)
                        return result
                    else:
                        pass
                        # print('File {0} DNE\n'.format(fl))
                elif out_data == "vel_df":
                    # multi-dim array
                    fl = os.path.join(scratch_fldr, '{0}.csv'.format(out_data))
                    if os.path.exists(fl):
                        result = pd.DataFrame.from_csv(fl, index_col=False)
                        vb_function_exit (fl , scratch_fldr)
                        return result
                    else:
                        pass
                        # print('File {0} DNE\n'.format(fl))
                elif out_data == "channel_info":
                    fl = os.path.join(scratch_fldr, '{0}.csv'.format(out_data))
                    if os.path.exists(fl):
                        result = pd.DataFrame.from_csv(fl, index_col=False)
                        vb_function_exit (fl , scratch_fldr)
                        return result
                    else:
                        pass
                        # print('File {0} DNE\n'.format(fl))
                elif out_data == "inverts":
                    # multi-dim array
                    fl = os.path.join(scratch_fldr, '{0}.csv'.format(out_data))
                    if os.path.exists(fl):
                        result = pd.DataFrame.from_csv(fl, index_col=None)
                        vb_function_exit (fl , scratch_fldr)
                        return result
                    else:
                        pass
                        # print('File {0} DNE\n'.format(fl))
                elif out_data == 'flow_df':
                    fl = os.path.join(scratch_fldr, '{0}.csv'.format(out_data))
                    if os.path.exists(fl):
                        result = pd.DataFrame.from_csv(fl, index_col=False)
                        vb_function_exit (fl , scratch_fldr)
                        return result
                    else:
                        pass
                        # print('File {0} DNE\n'.format(fl))
                elif out_data == "compute":
                    result='computed'
                    vb_function_exit(os.path.join(scratch_fldr,result+'.txt'), scratch_fldr)
            except CalledProcessError as e:
                error = loads(e.output[7:])
                lines.append("\tError Code: {0}\n".format (error['code']) )
                lines.append ("\tError Message: \n\t\t{0}\n".format (error[ 'message' ]))
                lines = ['{0}\n'.format (traceback.format_exc ())]
                on_error(WPTConfig.Options_NetworkFile, WPTConfig.Options_ScratchDir , lines)
                vb_function_exit(os.path.join(scratch_fldr,result+'.txt'), scratch_fldr)
            except:
                lines = ['{0}\n'.format (traceback.format_exc ())]
                on_error (WPTConfig.Options_NetworkFile , WPTConfig.Options_ScratchDir , lines)
                vb_function_exit (os.path.join(scratch_fldr,result+'.txt') , scratch_fldr)
            count+=1
            time.sleep(0.2)