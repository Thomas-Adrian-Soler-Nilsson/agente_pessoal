$ErrorActionPreference = "Stop"
$key = "HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.agente_pessoal.browser"
if (Test-Path -LiteralPath $key) { Remove-Item -LiteralPath $key -Recurse -Force }
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dist = Join-Path $repo ".browser-host-dist"
if (Test-Path -LiteralPath $dist) { Remove-Item -LiteralPath $dist -Recurse -Force }
Write-Output "Registro e binário do Agente Pessoal removidos. A extensão carregada pode ser removida em chrome://extensions."
