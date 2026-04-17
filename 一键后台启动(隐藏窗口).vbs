Set WshShell = CreateObject("WScript.Shell") 
' 这里的 0 代表隐藏窗口运行
WshShell.Run "python """ & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\order-helper-backend\app.py""", 0, False
