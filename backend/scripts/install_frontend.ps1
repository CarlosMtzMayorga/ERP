$nodeDir = "$env:LOCALAPPDATA\Programs\nodejs"
$env:PATH = "$nodeDir;$env:PATH"

# Set permanently in user environment
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$nodeDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$nodeDir;$userPath", "User")
}

Write-Host "PATH updated with: $nodeDir"
Write-Host "Node version: $(node -v)"
Write-Host "NPM version: $(npm -v)"

Set-Location frontend
npm install
npm run build

