param([string]$PythonPath='python')
$ErrorActionPreference='Stop'
$agentRoot=$PSScriptRoot
$opsRoot=Join-Path (Split-Path $agentRoot -Parent) 'sayelf-agent-ops'
$env:PYTHONPATH=$agentRoot+[IO.Path]::PathSeparator+$opsRoot
& $PythonPath -m sayelf_x_growth.daily --database (Join-Path $agentRoot 'local-data\x-growth.sqlite3') --region Tokyo
if ($LASTEXITCODE -ne 0) { throw 'Daily preparation failed' }
