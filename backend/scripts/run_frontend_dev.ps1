$nodeDir = "$env:LOCALAPPDATA\Programs\nodejs"
$env:PATH = "$nodeDir;$env:PATH"
Set-Location frontend
npm run dev -- --host 127.0.0.1 --port 5173

