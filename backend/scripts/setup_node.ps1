$zipPath = "$env:TEMP\node.zip"
$targetDir = "$env:LOCALAPPDATA\Programs\nodejs"

Write-Host "Downloading Node.js..."
Invoke-WebRequest -Uri "https://nodejs.org/dist/v20.18.0/node-v20.18.0-win-x64.zip" -OutFile $zipPath

Write-Host "Extracting Node.js..."
$extractDir = "$env:TEMP\node_extracted"
Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
Copy-Item -Path "$extractDir\node-v20.18.0-win-x64\*" -Destination $targetDir -Recurse -Force

# Add to user PATH permanently
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$targetDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$targetDir;$userPath", "User")
}

Write-Host "Node.js installed:"
& "$targetDir\node.exe" -v
& "$targetDir\npm.cmd" -v
