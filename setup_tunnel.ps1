# PowerShell Script to Setup Cloudflare Tunnel locally
$ErrorActionPreference = "Stop"

$url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
$output = "cloudflared.exe"
$target = "http://10.93.36.6:80"

if (-not (Test-Path $output)) {
    Write-Host "Downloading cloudflared..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $url -OutFile $output
    Write-Host "Download complete." -ForegroundColor Green
} else {
    Write-Host "cloudflared.exe already exists." -ForegroundColor Yellow
}

Write-Host "Starting Tunnel to $target using HTTP2..." -ForegroundColor Cyan
Write-Host "Look for the URL ending in .trycloudflare.com below:" -ForegroundColor Magenta

# Start process and redirect output to see the URL
# Using --protocol http2 to avoid QUIC issues
& .\cloudflared.exe tunnel --url $target --protocol http2
