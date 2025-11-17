param(
    [ValidateSet('start','seed','clear','backup')][string]$action = 'start'
)

Set-Location -LiteralPath (Join-Path $PSScriptRoot '..')

function Timestamp() { Get-Date -Format yyyyMMdd_HHmmss }

switch ($action) {
    'backup' {
        New-Item -ItemType Directory -Path backups -Force | Out-Null
        if (Test-Path -LiteralPath 'library.db') {
            $dst = Join-Path 'backups' ("library_$(Timestamp).db")
            Copy-Item -LiteralPath 'library.db' -Destination $dst -Force
            Write-Output "Backed up library.db -> $dst"
        } else { Write-Output 'No library.db found to backup.' }
        break
    }
    'clear' {
        Write-Output 'Stopping any running app.py processes...' 
        $p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'app.py' }
        if ($p) { $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force } }
        Write-Output 'Running clear script (this deletes all rows)...'
        python .\scripts\clear_db.py
        break
    }
    'seed' {
        Write-Output 'Seeding demo data (seed_demo.py)...'
        python .\scripts\seed_demo.py
        break
    }
    'start' {
        Write-Output 'Starting Flask dev server (app.py)...'
        Start-Process -FilePath 'python' -ArgumentList '.\app.py' -NoNewWindow
        Write-Output 'Server started in background (check terminal or app.log).'
        break
    }
}
