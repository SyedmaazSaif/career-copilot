' career-copilot launcher for Windows.
'
' Double-click this file (or the desktop shortcut that setup creates) and the
' app window is the only thing that appears -- no console, no PowerShell, and
' nothing to keep out of the way while you work.
'
' How: Windows runs a .vbs through wscript.exe, which has no console of its
' own, and the Run call below uses window style 0 (hidden) with wait = False
' (do not block). scripts\start.js then starts Vite and Electron directly and
' sends all their output to:
'
'     %USERPROFILE%\.career-copilot\logs\app.log
'
' To stop the app, close its window.

Option Explicit

Dim fso, sh, appDir, nodeExe, startScript

Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")

appDir = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
sh.CurrentDirectory = appDir
startScript = fso.BuildPath(appDir, "scripts\start.js")

If Not fso.FileExists(startScript) Then
  MsgBox "career-copilot is missing scripts\start.js." & vbCrLf & vbCrLf & _
         "Download the app again, or run ""Setup on Windows.bat"" next to this file.", _
         vbExclamation, "career-copilot"
  WScript.Quit 1
End If

nodeExe = FindNode()
If nodeExe = "" Then
  MsgBox "career-copilot could not find Node.js on this PC." & vbCrLf & vbCrLf & _
         "Run ""Setup on Windows.bat"" next to this file once -- it installs " & _
         "everything the app needs -- then start the app again.", vbExclamation, "career-copilot"
  WScript.Quit 1
End If

' 0 = hidden window, False = do not wait for it to finish.
sh.Run """" & nodeExe & """ """ & startScript & """", 0, False


' Look for node.exe without shelling out: WshShell.Exec would open the very
' console window this launcher exists to avoid, so the search is done here.
Function FindNode()
  Dim candidates, candidate, pathDirs, dir, i

  candidates = Array( _
    sh.ExpandEnvironmentStrings("%ProgramFiles%\nodejs\node.exe"), _
    sh.ExpandEnvironmentStrings("%ProgramFiles(x86)%\nodejs\node.exe"), _
    sh.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\nodejs\node.exe"), _
    sh.ExpandEnvironmentStrings("%APPDATA%\nvm\node.exe") _
  )

  For i = 0 To UBound(candidates)
    candidate = candidates(i)
    If InStr(candidate, "%") = 0 Then
      If fso.FileExists(candidate) Then
        FindNode = candidate
        Exit Function
      End If
    End If
  Next

  ' Anything else on PATH -- a Node installed by nvm, volta, or by hand.
  pathDirs = Split(sh.ExpandEnvironmentStrings("%PATH%"), ";")
  For i = 0 To UBound(pathDirs)
    dir = Trim(pathDirs(i))
    If dir <> "" Then
      candidate = fso.BuildPath(dir, "node.exe")
      If fso.FileExists(candidate) Then
        FindNode = candidate
        Exit Function
      End If
    End If
  Next

  FindNode = ""
End Function
