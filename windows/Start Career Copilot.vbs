' "Start Career Copilot" launcher for Windows.
'
' Double-click this file (or the desktop shortcut that setup creates) and the
' app window is the only thing that appears -- no console, no PowerShell, and
' nothing to keep out of the way while you work.
'
' Self-healing: if the app was never set up (or its install broke), it runs
' "Setup on Windows.bat" first, which installs what is missing and starts the
' app. A normal start shows nothing but the app's own window.
'
' To stop the app, close its window.

Option Explicit

Dim fso, sh, appDir, nodeExe, startScript, setupBat

Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")

appDir = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
sh.CurrentDirectory = appDir
startScript = fso.BuildPath(appDir, "scripts\start.js")
setupBat = fso.BuildPath(appDir, "windows\Setup on Windows.bat")

If Not fso.FileExists(startScript) Then
  If fso.FileExists(setupBat) Then
    sh.Run """" & setupBat & """", 1, True
  Else
    MsgBox "Career Copilot is incomplete. Download it again from the website.", _
           vbExclamation, "Career Copilot"
  End If
  WScript.Quit 0
End If

nodeExe = FindNode()
If nodeExe = "" Then
  If fso.FileExists(setupBat) Then
    sh.Run """" & setupBat & """", 1, True
  Else
    MsgBox "Career Copilot could not find Node.js. Download the app again.", _
           vbExclamation, "Career Copilot"
  End If
  WScript.Quit 0
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
