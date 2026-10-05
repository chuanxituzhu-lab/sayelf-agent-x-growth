param([int]$Port=8765)
$ErrorActionPreference='Stop'
$agentRoot=$PSScriptRoot
$opsRoot=Join-Path (Split-Path $agentRoot -Parent) 'sayelf-agent-ops'
$env:PYTHONPATH=$agentRoot+[IO.Path]::PathSeparator+$opsRoot
python -m sayelf_x_growth.web --port $Port --database (Join-Path $agentRoot 'local-data\x-growth.sqlite3')
