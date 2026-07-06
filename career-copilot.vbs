' Double-click to launch career-copilot with NO console window.
' Only the app window appears. Close the app window to stop everything.
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = scriptDir
' The "0" runs the command in a hidden window; "False" = do not wait.
sh.Run "cmd /c npm run dev", 0, False
