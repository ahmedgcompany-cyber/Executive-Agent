$localVbs  = 'C:\Users\AHMED\Desktop\Executive Agent\Launch MegaV.vbs'
$localIcon = 'C:\Users\AHMED\Desktop\Executive Agent\executive-agent-app\src\assets\icon.ico'
$localWdir = 'C:\Users\AHMED\Desktop\Executive Agent'
$shell = New-Object -ComObject WScript.Shell

function Make-Shortcut($path, $vbs, $wdir) {
    $lnk = $shell.CreateShortcut($path)
    $lnk.TargetPath       = 'wscript.exe'
    $lnk.Arguments        = "`"$vbs`""
    $lnk.WorkingDirectory = $wdir
    $lnk.Description      = 'MegaV v2.7 - Local AI Operator'
    if (Test-Path $localIcon) { $lnk.IconLocation = $localIcon }
    $lnk.Save()
    Write-Host "Updated: $path -> $vbs"
}

# All shortcuts point to the LOCAL Desktop path (not OneDrive)
Make-Shortcut 'C:\Users\AHMED\OneDrive\Desktop\MegaV.lnk' $localVbs $localWdir
Make-Shortcut 'C:\Users\AHMED\Desktop\MegaV.lnk' $localVbs $localWdir
Make-Shortcut 'C:\Users\AHMED\Desktop\Executive Agent\Launch MegaV.lnk' $localVbs $localWdir

# Remove duplicate "Executive Agent" shortcut if it exists
if (Test-Path 'C:\Users\AHMED\OneDrive\Desktop\Executive Agent.lnk') {
    Remove-Item 'C:\Users\AHMED\OneDrive\Desktop\Executive Agent.lnk' -Force
    Write-Host "Removed duplicate: Executive Agent.lnk"
}

Write-Host "All shortcuts updated to LOCAL Desktop path."