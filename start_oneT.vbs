' oneT silent launcher (no console window)
' VBS itself opens no console, and we explicitly run pythonw.exe
' (console-less interpreter) to bypass wrong .pyw file associations.
'
' Detection order:
'   1. pythonw.exe on PATH
'   2. Directory of the registered .py/.pyw handler in the registry
'      (works when only python.exe was associated)
'   3. Common per-user / system-wide install locations
'
' Usage: double-click this file. A desktop shortcut can point here too.

Option Explicit

Dim fso, shell, projectDir, pywFile

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
pywFile = fso.BuildPath(projectDir, "main.pyw")

If Not fso.FileExists(pywFile) Then
    MsgBox "main.pyw not found: " & pywFile, vbCritical, "oneT"
    WScript.Quit 1
End If

Dim found
found = FindPythonw()

If found = "" Then
    MsgBox "pythonw.exe not found." & vbCrLf & vbCrLf & _
        "Please install Python 3.10+ (python.org) with the ""py launcher"" option, " & _
        "or edit this script to add your Python path.", _
        vbCritical, "oneT"
    WScript.Quit 1
End If

' Working dir = project root so relative resource loading works; run detached
shell.CurrentDirectory = projectDir
shell.Run """" & found & """ """ & pywFile & """", 0, False


' ─── Helpers ────────────────────────────────────────────────────────────

Function FindPythonw()
    Dim p
    p = FindOnPath()
    If p = "" Then p = FindFromRegistry()
    If p = "" Then p = FindInCommonDirs()
    FindPythonw = p
End Function

' 1) "where pythonw" — relies on CreateProcess PATH search
Function FindOnPath()
    On Error Resume Next
    Dim ex, out, lines, i
    Set ex = shell.Exec("%COMSPEC% /c where pythonw")
    out = Trim(ex.StdOut.ReadAll())
    If Err.Number <> 0 Or out = "" Then Exit Function
    lines = Split(out, vbCrLf)
    For i = 0 To UBound(lines)
        If Len(Trim(lines(i))) > 0 And fso.FileExists(Trim(lines(i))) Then
            FindOnPath = fso.GetAbsolutePathName(Trim(lines(i)))
            Exit Function
        End If
    Next
End Function

' 2) Registry handler dirs: take python.exe path from the registered file
'    association, then look for pythonw.exe next to it
Function FindFromRegistry()
    On Error Resume Next
    Dim keys, k, cmd, exePath, dir, w
    keys = Array( _
        "HKCR\Python.NoConFile\shell\open\command\", _
        "HKCR\py_auto_file\shell\open\command\", _
        "HKCR\Python.CompiledFile\shell\open\command\")
    For Each k In keys
        cmd = ""
        cmd = shell.RegRead(k)
        If Err.Number <> 0 Then
            Err.Clear
        ElseIf Len(cmd) > 0 Then
            exePath = ExtractExePath(cmd)
            If exePath <> "" Then
                dir = fso.GetParentFolderName(exePath)
                w = fso.BuildPath(dir, "pythonw.exe")
                If fso.FileExists(w) Then
                    FindFromRegistry = w
                    Exit Function
                End If
            End If
        End If
    Next
End Function

' Pull the first quoted or bare token that looks like an exe path
Function ExtractExePath(cmd)
    Dim s, first, last
    s = Trim(cmd)
    If Left(s, 1) = """" Then
        last = InStr(2, s, """")
        If last > 0 Then
            s = Mid(s, 2, last - 2)
            If fso.FileExists(s) Then ExtractExePath = s
        End If
    Else
        first = InStr(1, s, " ")
        If first = 0 Then first = Len(s) + 1
        s = Left(s, first - 1)
        If LCase(Right(s, 4)) = ".exe" And fso.FileExists(s) Then ExtractExePath = s
    End If
End Function

' 3) Well-known install locations (per-user first, then system-wide)
Function FindInCommonDirs()
    Dim localAppData, base, bases, suffixes, b, s, candidate, vers, v
    localAppData = shell.Environment("Process")("LOCALAPPDATA")
    vers = Array("313", "312", "311", "310", "")
    suffixes = Array("Programs\Python\Python", "")

    ' Per-user: %LOCALAPPDATA%\Programs\Python\Python3XX\
    For Each v In vers
        candidate = fso.BuildPath(fso.BuildPath(localAppData, _
            "Programs\Python\Python" & v), "pythonw.exe")
        If fso.FileExists(candidate) Then
            FindInCommonDirs = candidate
            Exit Function
        End If
    Next

    ' System-wide: %SystemDrive%\Python3XX\ and Program Files variants
    bases = Array(shell.Environment("Process")("SystemDrive") & "\", _
        shell.Environment("Process")("ProgramFiles") & "\")
    For Each b In bases
        For Each v In vers
            candidate = fso.BuildPath(b, "Python" & v & "\pythonw.exe")
            If fso.FileExists(candidate) Then
                FindInCommonDirs = candidate
                Exit Function
            End If
        Next
    Next
End Function
