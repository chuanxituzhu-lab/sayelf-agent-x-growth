$ErrorActionPreference='Stop'
$taskName='Sayelf X Growth Daily local'
if ((Get-TimeZone).Id -ne 'Tokyo Standard Time') { throw 'This installer requires Tokyo local time' }
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { throw 'Task already exists; inspect it before changing it' }
$pythonPath=(Get-Command python -ErrorAction Stop).Source
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+(Join-Path $PSScriptRoot 'daily.ps1')+'" -PythonPath "'+$pythonPath+'"') -WorkingDirectory $PSScriptRoot
$trigger=New-ScheduledTaskTrigger -Daily -At '08:00'
$principal=New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings
