param([ValidateSet("quit", "restart")][string]$Action)

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Log = Join-Path $Root "outputs\system_control.log"

function Log([string]$msg) {
    Add-Content -Path $Log -Value ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg) -Encoding UTF8
}

function Stop-Ports {
    $pids = @(Get-NetTCPConnection -LocalPort 9890,3000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
    Log ("pids=" + ($pids -join ","))
    foreach ($p in $pids) {
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
        Log ("killed " + $p)
    }
}

Log ("action=" + $Action)
Start-Sleep -Seconds 1
Stop-Ports

if ($Action -eq "restart") {
    Start-Sleep -Seconds 2
    & (Join-Path $Root "start.bat")
}
