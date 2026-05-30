Set WshShell = CreateObject("WScript.Shell")
Set Fso = CreateObject("Scripting.FileSystemObject")
BaseDir = Fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = BaseDir
WshShell.Run Chr(34) & BaseDir & "\run_jarvis.bat" & Chr(34) & " --mini --silent", 0, False
