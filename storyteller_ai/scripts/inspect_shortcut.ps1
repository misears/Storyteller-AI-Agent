$p = 'C:\Users\misea\Desktop\Storyteller AI.lnk'
if (-not (Test-Path $p)) { Write-Output 'Shortcut not found'; exit 2 }
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($p)
Write-Output "Path: $p"
Write-Output "TargetPath: $($s.TargetPath)"
Write-Output "WorkingDirectory: $($s.WorkingDirectory)"
Write-Output "Arguments: $($s.Arguments)"
Write-Output "Description: $($s.Description)"
Write-Output "IconLocation: $($s.IconLocation)"
Write-Output "WindowStyle: $($s.WindowStyle)"
Write-Output "Hotkey: $($s.Hotkey)"
