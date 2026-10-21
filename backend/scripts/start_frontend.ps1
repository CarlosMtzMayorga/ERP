$nodeDir = "$env:LOCALAPPDATA\Programs\nodejs"
$env:PATH = "$nodeDir;$env:PATH"
Set-Location frontend
npm run build
