"""

A test script for iteratively running a HEC-RAS controller model X number of times.


By: Lockwood, Andrews, and Newnam
Alexander Govea

for more information contact: AGovea@lan-inc.com


"""

# Package Imports
import os
import time
import subprocess
from random import uniform
from subprocess import CalledProcessError
from datetime import datetime
import traceback
import pandas as pd

errorlog =r'C:\wpt\scratch\Cursor.txt'




#  File Management
def splitProperty(lineStr, splitCh="="):
    """splits  a line by a defined hec-ras/controlfiledelimiter for certain propoerties."""
    strVals = str(lineStr).split(splitCh)
    prop = strVals.pop(0)
    return prop, ''.join(map(str,strVals))

def MakeDir(SourceDir):
    """It Creates directories."""
    if os.path.exists(SourceDir) == False:
        os.makedirs(SourceDir)

def get_python_path():
    # def getMXDVersion(mxdFile):
    #     matchPattern = re.compile ("9.2|9.3|10.0|10.1|10.2|10.3|10.4")
    #     with open (mxdFile , 'rb') as mxd:
    #         fileContents = mxd.read ().decode ('latin1')[ 1000:4500 ]
    #         removedChars = [ x for x in fileContents if x not in [ u'\xff' , u'\x00' , u'\x01' , u'\t' ] ]
    #         joinedChars = ''.join (removedChars)
    #         regexMatch = re.findall (matchPattern , joinedChars)
    #         if len (regexMatch) > 0:
    #             version = regexMatch[ 0 ]
    #             return version
    #         else:
    #             return 'version could not be determined'
    # mxd = arcpy.mapping.MapDocument("CURRENT")
    # mxd_file = mxd.filePath
    # del mxd
    # version = getMXDVersion(mxd_file)
    # def_dir = 'C:\\Python27\\ArcGIS{0}\\python.exe'.format(version).replace('\\','/')
    # if os.path.exists(def_dir):
    #     return def_dir
    # else:
        return 'C\:\\Python27\\ArcGIS10.3\\python.exe'.replace('\\','/')

def read_txt_file(flow_file):
    """ returns a list of all lines withn a text file.
     Input Variables:
        [0] flow_file- (string) path to a desired text, geometry, flow, or plan file.
    Output Variables / Results:
        [0] lines - (list) a list of all lines within the file.
    """
    with open(flow_file, "r") as read:
        lines = read.readlines()
    return lines

def write_txt_file(fi, lns, append):
    """ returns a list of all lines withn a text file.
         Input Variables:
            [0] flow_file- (string) path to a desired text, geometry, flow, or plan file.
            [1] lines - (list, str, or dict) lines to be written to text file
        Output Variables / Results:
            [0] lines - writes lines within the file.
    """
    try:
        lines = ''
        evt_time =  datetime.now ().strftime ("%I:%M:%S")
        if os.path.exists(os.path.dirname(fi)) == False:
            MakeDir (os.path.dirname (fi))
        if type(lns) is list:
            l2 = []
            l2.append('\t\t\t\t\tTime: {0}\n'.format(evt_time))
            l2 += lns
            lines = l2
        elif type(lns) is str:
            lines = ['Time: {0}\n'.format(evt_time), lns]
        elif type(lns) is dict:
            l2 = []
            for key in lns:
                msg = '\t\tkey: {0},\tvalue: {1}\n'.format(key, lns[key])
                l2.append(msg)
            lines = ['Time: {0}\n'.format(evt_time)]
            lines += l2
        if append == True:
            if os.path.exists(fi):
                with open (fi , 'a') as outlines:
                    outlines.writelines (lines)
            else:
                with open (fi , 'w') as outlines:
                    outlines.writelines (lines)
        else:
            os.remove(fi)
            with open(fi, 'w') as outlines:
                outlines.writelines(lines)
    except:
        lines = ['{0}'.format(traceback.format_exc())]
        fi = 'C:/wpt/scratch/HCFCDLog.txt'
        with open(fi, 'w+') as hcfdlog:
            hcfdlog.writelines(lines)

# SUBPROCESS MANAGEMENT
def get_active_process(scratch_fldr, crash):
    evt = datetime.now ().strftime ("%I_%M_%S_%f")
    ofi = ''
    if crash == False:
        ofi = os.path.join (scratch_fldr , 'wpt_process_{0}.csv'.format (evt))
    else:
        ofi = os.path.join(scratch_fldr, 'wpt_ex_process_{0}.csv'.format(evt))
    if os.path.exists (ofi): os.remove (ofi)
    tlproc = subprocess.Popen ('tasklist.exe /FO CSV', shell=False , stdout=subprocess.PIPE)
    x = str(tlproc.communicate ()[ 0 ])
    x = x.split ('\r\n')
    image_names , pids , session_names , session_nos , mem_usage = [ ] , [ ] , [ ] , [ ] , [ ]
    for i , pro in enumerate (x):
        rx = pro.replace ('"' , '').split (',')
        if i > 0 and len (rx) > 1:
            zen = pro.split('","')
            mem = zen[4].replace('"','')
            if len(rx) >= 5:
                image_names.append (rx[ 0 ])
                # print '{0} = {1}'.format(rx[0], len(rx))
                pids.append (rx[ 1 ])
                session_names.append (rx[ 2 ])
                session_nos.append (rx[ 3 ])
                mem_usage.append (mem)
    pro_dict = {'Process': image_names , 'PID': pids , 'SessionName': session_names ,
                'Session#': session_nos , 'MemoryUsage': mem_usage}
    df = pd.DataFrame (data=pro_dict , columns=[ 'Process' , 'MemoryUsage' , 'SessionName' , 'Session#' ])
    df.to_csv (ofi)

def processExists(processname):
    """Identifies a named process is active in the task manager e.g. "ras.exe" """
    tlcall = 'TASKLIST', '/FI', 'imagename eq %s.exe' % processname
    # shell=True hides the shell window, stdout to PIPE enables
    # communicate() to get the tasklist command result
    tlproc = subprocess.Popen(tlcall, shell=False, stdout=subprocess.PIPE)
    # trimming it to the actual lines with information
    tlout = tlproc.communicate()[0].strip().split('\r\n')
    # if TASKLIST returns single line without processname: it's not running
    if len(tlout) > 1 and processname in tlout[-1]:
        # print('process "%s" is running!' % processname)
        # print "ProcessFound"
        return True
    else:
        # print(tlout[0])
        # print('process "%s" is NOT running!' % processname)
        # print "process not present"
        return False

def kill_process(process):
    """Kills a named process running within a PC's processor. (e.g. terminates ras.exe process)
   nput Variables:
        [0] process - (string) anamed process
    Output Variables / Results:
        [0] No return. Kills a named process runnning on a computer.
    """
    try:
        subprocess.call ("TASKKILL /F /IM " + str (process) + ".exe")
        time.sleep(0.3)
    except:
        lines = [ "{0}\n".format (traceback.format_exc ()) ]
        write_txt_file (errorlog , lines , True)

def kras():
    """TERMINATES A RUNNING RAS PROCESS"""
    try:
        ras = 'ras'
        if processExists (ras):
            time.sleep(0.3)
            kill_process (ras)
    except:
        lines = [ "{0}\n".format (traceback.format_exc ()) ]
        write_txt_file (errorlog , lines , True)

def ksub():
    """TERMINATES THE WPT HEC-RAS CONTROLLER SUBROUTINE"""
    try:
        process = 'WPT_NET'
        if processExists (process):
            time.sleep(0.7)
            kill_process (process)
    except:
        pass

def clean_active_process_files(scratch_fldr):
    if os.path.exists(scratch_fldr):
        try:
            for fi in os.listdir(scratch_fldr):
                if os.path.exists(os.path.join(scratch_fldr, fi)):
                    fname, ext = os.path.splitext(fi)
                    ext = ext.lower()
                    fname = fname.lower()
                    if 'wpt' in fname and 'process' in fname and 'csv' in ext:
                        os.remove(os.path.join(scratch_fldr,fi))
        except:
            lines = ['{0}\n'.format(traceback.format_exc())]
            write_txt_file (errorlog , lines , True)


# .Net Execution Functions and End Functions
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
                write_txt_file (errorlog , lines , True)
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
                clean_active_process_files(scratch_fldr)
                time.sleep(uniform(0.4,2.4))
                get_active_process(scratch_fldr, False)
                subprocess.check_output('"{0}" "{1}" "{2}" "{3}" "{4}"'.format(exe, prjfile, plantitle, sfldr, out_data), shell=False)
                time.sleep(5.0)
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
                    return True
            except CalledProcessError as e:
                lines = [ '{0}\n'.format (traceback.format_exc ()) ]
                lines.append("Called Process Error!")
                for line in lines:
                    print (line)
                vb_function_exit(os.path.join(scratch_fldr,result+'.txt'), scratch_fldr)
                return False
            except:
                lines = ['{0}\n'.format (traceback.format_exc ())]
                for line in lines:
                    print (line)
                vb_function_exit (os.path.join(scratch_fldr,'{0}.txt'.format(result)) , scratch_fldr)
                return False
            count+=1





def runRASModelIndeffinetley():
    """runs a given ras prj file a users specifiied number of iterations! """
    controlFile = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Control.txt')
    lines = read_txt_file(controlFile)
    prjPath = None
    planTitle = None
    outFolder = None
    computeCount = None
    waitTime = None
    # Control File input Parameter Processing
    for i, line in enumerate(lines):
        prop, strVal = splitProperty(line)
        if prop.find("HEC-RAS Prj Path") != -1:
            prjPath= strVal.replace("\n","").replace ('\\' , '/')
        elif prop.find("HEC-RAS Plan Title") != -1:
            planTitle= strVal.replace("\n","")
        elif prop.find("Output Folder") != -1:
            outFolder= strVal.replace("\n","").replace ('\\' , '/')
        elif prop.find("Number of Computations") != -1:
            computeCount= float(strVal.replace("\n",""))
        elif prop.find("Computation Wait Interval") != -1:
            waitTime= float(strVal.replace("\n",""))
    compCounts = 0
    if os.path.exists(prjPath):
            outFolder = os.path.dirname(prjPath)
            print("Beelining iterative running of HEC-RAS via HEC-RAS Controller!")
            print("\t|-Testing RAS PRJ: {0}".format(prjPath))
            print("\t|-Testing RAS Plan File: {0}".format(planTitle))
            print("\t|-Goal Number of Iterations: {0}".format(computeCount))
            print("\t|-Wait Time Between Iterations: {0}".format(waitTime))
            print ("\t|-Beginning Processing: ".format (waitTime))
            for i in range (int(computeCount)):
                evt_time = datetime.now ().strftime ("%H:%M:%S")
                if fetch_controller_data(prjPath, planTitle, outFolder, out_data="compute"):
                    compCounts += 1
                    print("\t\t|-RAS Analysis: Succeeded \tCount: {0:,.1f}\tCompleted @ {1}".format(compCounts, evt_time))
                else:
                    print ("\t\t|-RAS Analysis: !Failed!\tAttempt: {0:,.1f}\t@{1}".format (i, evt_time))
                time.sleep(waitTime)
            print("\t|-Completed!")
    else:
        print("Input PRJ path  {0} in Control.txt file does not exist or was not input correctly.".format(prjPath))

if __name__ == "__main__":
    runRASModelIndeffinetley()

