param(
    [switch]$Install
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
Push-Location $PSScriptRoot

try {
    $exeName = "Habit Tracker"

    # Conda keeps Tcl/Tk, libffi, and OpenSSL next to the interpreter in
    # Library\bin instead of the places PyInstaller searches by default.
    $pythonExe = (Get-Command python -ErrorAction Stop).Source
    $pythonHome = Split-Path $pythonExe -Parent
    $dllDirs = @(
        (Join-Path $pythonHome "Library\bin"),
        (Join-Path $pythonHome "DLLs"),
        $pythonHome
    )
    $neededDlls = @(
        "ffi.dll",
        "tcl86t.dll",
        "tk86t.dll",
        "libcrypto-3-x64.dll",
        "libssl-3-x64.dll",
        "liblzma.dll",
        "libbz2.dll"
    )
    $binaryArgs = @()
    foreach ($dll in $neededDlls) {
        foreach ($dir in $dllDirs) {
            $candidate = Join-Path $dir $dll
            if (Test-Path $candidate) {
                $binaryArgs += "--add-binary=$candidate;."
                break
            }
        }
    }

    $pyInstallerArgs = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", $exeName,
        "--icon", "assets\icon.ico",
        "--add-data=assets;assets",
        "--collect-all", "customtkinter",
        "--hidden-import=pystray._win32",
        "--hidden-import=PIL._tkinter_finder",
        "--exclude-module=numpy"
    ) + $binaryArgs + @("main.py")

    Write-Host "Building $exeName.exe with PyInstaller..."
    & $pythonExe @pyInstallerArgs

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }

    $builtExe = Join-Path $PSScriptRoot "dist\$exeName.exe"
    if (-not (Test-Path $builtExe)) {
        throw "Expected build output was not created: $builtExe"
    }
    $sizeMb = [math]::Round((Get-Item $builtExe).Length / 1MB, 1)
    Write-Host "Built $builtExe ($sizeMb MB)"

    if ($Install) {
        $running = Get-Process -Name $exeName -ErrorAction SilentlyContinue
        if ($running) {
            throw "Close Habit Tracker before installing a new build."
        }

        $installDir = Join-Path $env:LOCALAPPDATA "Programs\$exeName"
        New-Item -ItemType Directory -Force -Path $installDir | Out-Null
        $installedExe = Join-Path $installDir "$exeName.exe"
        Copy-Item $builtExe $installedExe -Force

        $desktop = [Environment]::GetFolderPath("Desktop")
        $shortcutPath = Join-Path $desktop "$exeName.lnk"
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $installedExe
        $shortcut.WorkingDirectory = $installDir
        $shortcut.IconLocation = "$installedExe,0"
        $shortcut.Description = "Floating daily habit tracker"
        $shortcut.Save()

        Write-Host "Installed $installedExe"
        Write-Host "Desktop shortcut $shortcutPath"
    }
}
finally {
    Pop-Location
}
