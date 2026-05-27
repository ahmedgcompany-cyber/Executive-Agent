' ============================================================
' MegaV v2.7 — Simple Launcher
'
' 1. If a MegaV window already exists → bring it to front.
' 2. Otherwise → launch pythonw run.py (silent, no console).
' 3. Wait up to 12 seconds for the window to appear.
' ============================================================
Option Explicit

Dim oShell, fso
Dim strRoot, strApp, strPython, strCmd, strLog

Set oShell = CreateObject("WScript.Shell")
Set fso    = CreateObject("Scripting.FileSystemObject")

strRoot = fso.GetParentFolderName(WScript.ScriptFullName)
strApp  = strRoot & "\executive-agent-app"
strLog  = strApp  & "\logs\launcher.log"

' -- Log helper ------------------------------------------------
Sub WriteLog(msg)
    On Error Resume Next
    Dim logDir : logDir = strApp & "\logs"
    If Not fso.FolderExists(logDir) Then fso.CreateFolder logDir
    Dim f : Set f = fso.OpenTextFile(strLog, 8, True)
    f.WriteLine Now & "  " & msg
    f.Close
    On Error GoTo 0
End Sub

WriteLog "========================================"
WriteLog "MegaV v2.7 launcher started"
WriteLog "Root: " & strRoot

' -- Check app folder ------------------------------------------
If Not fso.FolderExists(strApp) Then
    WriteLog "ERROR: App folder not found: " & strApp
    MsgBox "App folder not found:" & vbCrLf & strApp & vbCrLf & vbCrLf & _
           "Make sure this launcher is inside the 'Executive Agent' folder.", _
           vbExclamation, "MegaV"
    WScript.Quit 1
End If

' -- NOTE: AppActivate substring-matches window titles, so a browser tab
' -- containing "MegaV" would steal the activation (e.g. Chrome jumps to
' -- front instead of launching). Dedup is handled inside run.py via the
' -- Global\MegaV_SingleInstance_v2 mutex + EnumWindows scan, which is
' -- title-exact and process-aware. Always launch — run.py raises the
' -- existing window if one is alive.

' -- Find pythonw.exe ------------------------------------------
On Error Resume Next
Dim oExec : Set oExec = oShell.Exec("cmd /c where pythonw.exe 2>nul")
Dim strWhere : strWhere = ""
If Not oExec Is Nothing Then
    Do While Not oExec.StdOut.AtEndOfStream
        Dim ln : ln = Trim(oExec.StdOut.ReadLine())
        If Len(ln) > 4 And LCase(Right(ln, 11)) = "pythonw.exe" Then
            strWhere = ln : Exit Do
        End If
    Loop
End If
On Error GoTo 0

If Len(strWhere) > 0 And fso.FileExists(strWhere) Then
    strPython = strWhere
    WriteLog "Found pythonw: " & strPython
Else
    ' Fallback: look for pythonw beside python.exe
    On Error Resume Next
    Set oExec = oShell.Exec("cmd /c where python.exe 2>nul")
    Dim strPyDir : strPyDir = ""
    If Not oExec Is Nothing Then
        Do While Not oExec.StdOut.AtEndOfStream
            Dim pyln : pyln = Trim(oExec.StdOut.ReadLine())
            If Len(pyln) > 4 Then strPyDir = fso.GetParentFolderName(pyln) : Exit Do
        Loop
    End If
    On Error GoTo 0

    If Len(strPyDir) > 0 Then
        strPython = strPyDir & "\pythonw.exe"
        If Not fso.FileExists(strPython) Then
            strPython = strPyDir & "\python.exe"
            WriteLog "Fallback to python.exe: " & strPython
        Else
            WriteLog "Found pythonw beside python.exe: " & strPython
        End If
    Else
        strPython = "pythonw.exe"
        WriteLog "Fallback to PATH pythonw.exe"
    End If
End If

' -- Validate Python -------------------------------------------
If InStr(strPython, "\") > 0 And Not fso.FileExists(strPython) Then
    WriteLog "ERROR: Python not found at " & strPython
    MsgBox "Python not found." & vbCrLf & vbCrLf & _
           "Please install Python 3.10+ from python.org" & vbCrLf & _
           "and check 'Add Python to PATH' during install.", _
           vbExclamation, "MegaV"
    WScript.Quit 1
End If

' -- Launch ----------------------------------------------------
oShell.CurrentDirectory = strApp
strCmd = """" & strPython & """ run.py"
WriteLog "Launching: " & strCmd
oShell.Run strCmd, 0, False   ' 0 = no console window, False = don't wait

' -- Wait for window (up to 12 seconds) -----------------------
Dim i, activated
For i = 1 To 12
    WScript.Sleep 1000
    On Error Resume Next
    activated = oShell.AppActivate("MegaV v2.7")
    On Error GoTo 0
    If activated Then
        WriteLog "MegaV window appeared after " & i & "s"
        Exit For
    End If
Next

If Not activated Then
    WriteLog "MegaV still loading (window will appear shortly)"
End If

Set oShell = Nothing
Set fso    = Nothing
