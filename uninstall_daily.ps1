$ErrorActionPreference='Stop'
$taskName='Sayelf X Growth Daily local'
$task=Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
$expectedScript=Join-Path $PSScriptRoot 'daily.ps1'
if (-not ($task.Actions.Arguments -like ('*"'+$expectedScript+'"*'))) { throw 'Task belongs to a different checkout' }
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
