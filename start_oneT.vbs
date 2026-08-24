' oneT silent launcher (no console window)
' VBS itself opens no console, and we explicitly run pythonw.exe
' (console-less interpreter) to bypass the wrong .pyw file association.
'
' Usage: double-click this file. A desktop shortcut can point here too.

Option Explicit

Dim fso, shell, projectDir, pywFile

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

' Project root = directory of this script
projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
pywFile = fso.BuildPath(projectDir, "main.pyw")

' Probe pythonw.exe locations (same dir as current python.exe first)
Dim candidates(2)
candidates(0) = "D:\Program Files\minconda\pythonw.exe"
candidates(1) = fso.BuildPath(shell.Environment("Process")("LOCALAPPDATA"), _
    "Programs\Python\pythonw.exe")

Dim i, found
found = ""
For i = 0 To UBound(candidates)
    If fso.FileExists(candidates(i)) Then
        found = candidates(i)
        Exit For
    End If
Next

If found = "" Then
    MsgBox "pythonw.exe not found. Please edit this script to set the Python path.", _
        vbCritical, "oneT"
    WScript.Quit 1
End If

If Not fso.FileExists(pywFile) Then
    MsgBox "main.pyw not found: " & pywFile, vbCritical, "oneT"
    WScript.Quit 1
End If

' Set working dir to project root so relative resource loading works; run detached
shell.CurrentDirectory = projectDir
shell.Run """" & found & """ """ & pywFile & """", 0, False
