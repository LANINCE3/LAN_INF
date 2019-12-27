import subprocess
import win32gui
import win32con
import time
import win32api
import os
import traceback

# HEC RAS Management

def MakeDir(SourceDir):
    """It Creates directories."""
    if os.path.exists (SourceDir) == False:
        os.makedirs (SourceDir)

# Screen and Proccess Management
def processExists(processname):
    'Identifies a named active process e.g. "ras.exe" '
    tlcall = 'TASKLIST' , '/FI' , 'imagename eq %s.exe' % processname
    # shell=True hides the shell window, stdout to PIPE enables
    # communicate() to get the tasklist command result
    tlproc = subprocess.Popen (tlcall , shell=False , stdout=subprocess.PIPE)
    # trimming it to the actual lines with information
    tlout = tlproc.communicate ()[ 0 ].strip ().split ('\r\n')
    # if TASKLIST returns single line without processname: it's not running
    if len (tlout) > 1 and processname in tlout[ -1 ]:
        # print('process "%s" is running!' % processname)
        # print "ProcessFound"
        return True
    else:
        # print(tlout[0])
        # print('process "%s" is NOT running!' % processname)
        # print "process not present"
        return False

def windowEnumerationHandler(hwnd , top_windows):
    """Identifies top active windows in windows system.
    Input Variables:
        [0] hwnd - (object) windows handler
        [1] top_windows - (list) of top windows
    Output Variables / Results:
        [0] a validator for identifying what window is on top"""
    top_windows.append ((hwnd , win32gui.GetWindowText (hwnd)))

def window_to_top(appName, setForeground=True):
    """Positions Application as Top window on Screen"""
    topWindows = [ ]
    win32gui.EnumWindows (windowEnumerationHandler , topWindows)
    for i in topWindows:
        hwnd = i[ 0 ]
        window_title = i[ 1 ].lower ()
        if window_title.lower ().find (appName.lower ()) != -1:
            win32gui.ShowWindow (hwnd , win32con.SW_SHOWNORMAL)
            if setForeground:
                win32gui.SetForegroundWindow (hwnd)

def kill_process(process):
    """Kills a named process running within a PC's processor. (e.g. terminates ras.exe process)
   nput Variables:
        [0] process - (string) anamed process
    Output Variables / Results:
        [0] No return. Kills a named process runnning on a computer.
    """
    try:
        subprocess.call ("TASKKILL /F /IM " + str (process) + ".exe")
        time.sleep (0.14)
    except:
        lines =  "{0}\n".format (traceback.format_exc ())
        print(lines)
        raise Exception

def kras():
    """Terminates the HEC-RAS Executable"""
    try:
        ras = 'ras'
        if processExists (ras):
            time.sleep (0.25)
            kill_process (ras)
    except:
        lines = "{0}\n".format (traceback.format_exc ())
        print(lines)
        raise Exception

def launch_hec_ras(RAS_WINDOWTITLE_HECRAS):
    "Launches HEC-RAS from a subprocess by directly calling the executable "
    kras ()
    x = subprocess.Popen ('"C:/Program Files (x86)/HEC/HEC-RAS/5.0.5/ras.exe"')
    window_to_top (RAS_WINDOWTITLE_HECRAS)

def init_ks_(appName , maximize, setForeground=True):
    def setBruteWindow__(appName , maximize):
        """tbd
        Input Variables:
            [0]
            [1]
        Output Variables:
            [0]
        """
        try:
            topWindows = [ ]
            win32gui.EnumWindows (windowEnumerationHandler , topWindows)
            hwnd = 0
            arcmap_hwnd = 0
            hec_hwnd = 0
            act_hwnd = win32gui.GetForegroundWindow ()
            act_hwnd_title = win32gui.GetWindowText (act_hwnd)
            if act_hwnd_title.lower ().find (appName.lower ()) != -1:
                return True
            else:
                for i in topWindows:
                    window_title = i[ 1 ].lower ()
                    if window_title.lower ().find (appName.lower ()) != -1:
                        hwnd = i[ 0 ]
                        # print 'Window Title::' + str(window_title)
                        # print 'App Name::' + str(appName)
                        if hwnd != 0:
                            if win32gui.IsWindowVisible (hwnd) != 0 and win32gui.IsWindowEnabled (hwnd) != 0:
                                # win32gui.ShowWindow(hwnd, 5)
                                if maximize == True:
                                    win32gui.ShowWindow (hwnd , win32con.SW_MAXIMIZE)
                                else:
                                    win32gui.ShowWindow (hwnd , 5)
                                win32gui.BringWindowToTop (hwnd)
                                win32gui.EnableWindow (hwnd , True)
                                if setForeground:
                                    win32gui.SetForegroundWindow (hwnd)

                                return True
                            else:
                                # win32gui.ShowWindow(hwnd, 5)
                                if maximize == True:
                                    win32gui.ShowWindow (hwnd , win32con.SW_MAXIMIZE)
                                else:
                                    win32gui.ShowWindow (hwnd , 5)
                                win32gui.BringWindowToTop (hwnd)
                                win32gui.EnableWindow (hwnd , True)
                                if setForeground:
                                    win32gui.SetForegroundWindow (hwnd)
                                return True
                        else:
                            if win32gui.IsWindowVisible (hwnd) != 0 and win32gui.IsWindowEnabled (hwnd) != 0:
                                if maximize == True:
                                    win32gui.ShowWindow (hwnd , win32con.SW_MAXIMIZE)
                                else:
                                    win32gui.ShowWindow (hwnd , 5)
                                win32gui.BringWindowToTop (hwnd)
                                win32gui.EnableWindow (hwnd , True)
                                if setForeground:
                                    win32gui.SetForegroundWindow (hwnd)
                                return True
                            else:
                                # win32gui.ShowWindow(hwnd, 5)
                                if maximize == True:
                                    win32gui.ShowWindow (hwnd , win32con.SW_MAXIMIZE)
                                else:
                                    win32gui.ShowWindow (hwnd , 5)
                                win32gui.BringWindowToTop (hwnd)
                                win32gui.EnableWindow (hwnd , True)
                                if setForeground:
                                    win32gui.SetForegroundWindow (hwnd)
                                return True
                    else:
                        pass
                return True
        except:
            return False

    def ChkForegroundWindow(appName):
        topWindows = [ ]
        win32gui.EnumWindows (windowEnumerationHandler , topWindows)
        act_hwnd = win32gui.GetForegroundWindow ()
        act_hwnd_title = win32gui.GetWindowText (act_hwnd)
        if act_hwnd_title.lower ().find (appName.lower ()) != -1:
            return True
        else:
            return False

    def ChkWindow(appName):
        topWindows = [ ]
        win32gui.EnumWindows (windowEnumerationHandler , topWindows)
        z = False
        arcmap_hwnd = 0
        hec_hwnd = 0
        for i in topWindows:
            hwnd = i[ 0 ]
            window_title = i[ 1 ].lower ()
            if window_title.lower ().find (appName.lower ()) != -1:
                z = True
                break
            else:
                pass
        return z

    try:
        if setBruteWindow__ (appName , maximize) == True:
            x = ChkForegroundWindow (appName)
            if x == True:
                return x
            else:
                y = ChkWindow (appName)
                if y == True:
                    return y
                else:
                    return False
    except:
        lines = 'INIT_KS ERROR:\n\t{0}\n'.format (traceback.format_exc ())
        print(lines)
        raise Exception

def set_hec_ras_default_project_folder(scratch_folder_name, RAS_WINDOWTITLE_HECRAS):
    launch_hec_ras (RAS_WINDOWTITLE_HECRAS)
    init_ks_ (RAS_WINDOWTITLE_HECRAS , False)
    import pyautogui

    # resets to default project folder to C:\
    def open_default_project_window_dialog():
        time.sleep (0.4)
        pyautogui.hotkey ('alt' , 'o')
        pyautogui.press ([ 'right' ] , pause=0.3)
        pyautogui.press ([ 'down' , 'enter' ] , pause=0.3)
        time.sleep (0.4)

    open_default_project_window_dialog ()
    pyautogui.press ([ 'up' ] * 24)
    pyautogui.press ([ 'enter' ] , pause=0.3)
    pyautogui.press ([ 'tab' ] * 3)
    pyautogui.press ('enter')
    # Then sets hec-ras default project folder to scratch_folder_name
    open_default_project_window_dialog ()
    pyautogui.press ([ 'tab' , 'space' ] , pause=0.3)
    time.sleep (0.4)
    pyautogui.press ([ ch for ch in scratch_folder_name ] , pause=0.3)
    pyautogui.press ([ 'tab' , 'enter' ] , pause=0.3)
    time.sleep (0.4)
    pyautogui.press ([ 'enter' ] , pause=0.3)
    pyautogui.press ([ 'tab' , 'tab' , 'enter' ] , pause=0.3)
    kras ()