$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Crie o ambiente .venv e instale requirements.txt antes." }
$extension = Join-Path $repo "browser_extension"
$dist = Join-Path $repo ".browser-host-dist"
$work = Join-Path $env:TEMP "agente-pessoal-browser-host-build"
$buildId = Get-Date -Format "yyyyMMddHHmmssfff"
$hostName = "agente_pessoal_browser_host_$buildId"
$hostPath = Join-Path $dist "$hostName.exe"
$hostManifest = Join-Path $dist "com.agente_pessoal.browser.json"
& $python -m PyInstaller --noconfirm --clean --onefile --name $hostName --paths $repo --distpath $dist --workpath $work --specpath $work (Join-Path $repo "tools\browser_native_host.py")
if ($LASTEXITCODE -ne 0) { throw "Falha ao compilar o Native Messaging host." }
$manifest = @{ name = "com.agente_pessoal.browser"; description = "Agente Pessoal Chrome bridge"; path = $hostPath; type = "stdio"; allowed_origins = @("chrome-extension://kkpfdbnghmplegmilfkkahempcckmefe/") } | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($hostManifest, $manifest, (New-Object System.Text.UTF8Encoding($false)))
$key = "HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.agente_pessoal.browser"
New-Item -Path $key -Force | Out-Null
Set-Item -Path $key -Value $hostManifest
Write-Output "Native host registrado para o usuário atual."
Write-Output "No Chrome, abra chrome://extensions, ative o modo do desenvolvedor e selecione Carregar sem compactação: $extension"
Write-Output "ID esperado da extensão: kkpfdbnghmplegmilfkkahempcckmefe"
