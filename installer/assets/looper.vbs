' Looper launcher — no console window; graceful error if setup incomplete
Set fso = CreateObject("Scripting.FileSystemObject")
Set wsh = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName) & "\"
pythonw   = scriptDir & ".venv\Scripts\pythonw.exe"
launcher  = scriptDir & "launcher.pyw"

If Not fso.FileExists(pythonw) Then
    logPath = scriptDir & "post_install.log"
    detail  = ""
    If fso.FileExists(logPath) Then
        detail = vbCrLf & "Check the setup log for details:" & vbCrLf & logPath
    End If
    MsgBox "Looper setup did not complete successfully." & vbCrLf & vbCrLf & _
           "The Python environment was not found at:" & vbCrLf & _
           pythonw & vbCrLf & vbCrLf & _
           "Please re-run the Looper installer to finish setup." & detail, _
           vbExclamation, "Looper"
    WScript.Quit 1
End If

wsh.Run """" & pythonw & """ """ & launcher & """", 0, False
