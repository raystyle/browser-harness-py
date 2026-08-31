# Start the agent's own Chrome (isolated profile) + the X monitor.
# IMPORTANT: this must NOT touch the user's Profile 3 Chrome.

$ErrorActionPreference = "Stop"
$chrome = "C:\Program Files\Google\Chrome Dev\Application\chrome.exe"
$profile = "D:\browser-harness\agent-chrome-profile"
$port = 9223

# 1. Ensure the dedicated agent Chrome is running (isolated user-data-dir).
$running = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" |
    Where-Object { $_.CommandLine -match [regex]::Escape($profile) -and $_.CommandLine -notmatch '--type=' }
if (-not $running) {
    $flags = "--user-data-dir=$profile --remote-debugging-port=$port --disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows --disable-features=IntensiveWakeUpThrottling,CalculateNativeWinOcclusion"
    Start-Process -FilePath $chrome -ArgumentList $flags
    Start-Sleep -Seconds 5
}

# 2. Start the supervisor against the dedicated Chrome only.
$env:BU_CDP_URL = "http://127.0.0.1:$port"
uv run python -m browser_harness.run x-monitor
