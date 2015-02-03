import win32com.client
import ctypes

# this is simplified from:
# http://www.blog.pythonlibrary.org/2010/10/03/how-to-find-and-list-all-running-processes-with-python/
wmi=win32com.client.GetObject('winmgmts:')
for p in wmi.InstancesOf('win32_process'):
    if p.Name == 'hub4com.exe':
        pid = int(p.Properties_('ProcessId'))
        print(('Found: ',p.Name, 'pid: ',pid, ' Killing.'))

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(1,0,pid)
        kernel32.TerminateProcess(handle,0)
                                      

#and from : docs.python.org/2/faq/windows.html

junk = eval(input("Hit Enter to exit."))


##alternate way to find a process:
#import win32com.client

#def find_process(name):
#    objWMIService = win32com.client.Dispatch("WbemScripting.SWbemLocator")
#    objSWbemServices = objWMIService.ConnectServer(".", "root\cimv2")
#    colItems = objSWbemServices.ExecQuery(
#         "Select * from Win32_Process where Caption = '{0}'".format(name))
#    return len(colItems)

#print find_process("hub4com.exe")
