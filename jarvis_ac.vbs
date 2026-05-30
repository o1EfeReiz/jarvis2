Set WshShell = CreateObject("WScript.Shell")
Set Fso = CreateObject("Scripting.FileSystemObject")
BaseDir = Fso.GetParentFolderName(WScript.ScriptFullName)
Pythonw = BaseDir & "\.venv\Scripts\pythonw.exe"
AppFile = BaseDir & "\jarvis_app.py"

If Fso.FileExists(Pythonw) Then
    WshShell.Run Chr(34) & Pythonw & Chr(34) & " " & Chr(34) & AppFile & Chr(34), 0, False
Else
    WshShell.Run "py -3.12 " & Chr(34) & AppFile & Chr(34), 0, False
End If
