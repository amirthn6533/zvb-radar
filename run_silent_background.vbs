Set WshShell = CreateObject("WScript.Shell")
' Run daily_digest.py silently in background without showing a black command prompt window
WshShell.Run "python """ & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\telegram_bot_service.py""", 0, False
