# installer_tache_planifiee.ps1
# ================================
# Enregistre une tache planifiee Windows qui execute le rafraichissement
# quotidien du pipeline ETL NG Travel (pipeline_orchestrator/tache_quotidienne.py)
# tous les jours a 08h00, sur CETTE machine (PC allume + session ouverte).
#
# A executer UNE SEULE FOIS, dans PowerShell, depuis la racine du projet :
#     powershell -ExecutionPolicy Bypass -File pipeline_orchestrator\installer_tache_planifiee.ps1
#
# Verifier ensuite :
#     Get-ScheduledTask -TaskName "NG Travel - Rafraichissement quotidien"
#
# Pour desinstaller la tache :
#     Unregister-ScheduledTask -TaskName "NG Travel - Rafraichissement quotidien" -Confirm:$false

$ErrorActionPreference = "Stop"

$racine = (Get-Item $PSScriptRoot).Parent.FullName
$python = Join-Path $racine "venv\Scripts\python.exe"
$nomTache = "NG Travel - Rafraichissement quotidien"

if (-not (Test-Path $python)) {
    Write-Error "Python introuvable dans '$python'. Adapte la variable `$python dans ce script si ton environnement virtuel se trouve ailleurs."
    exit 1
}

$action = New-ScheduledTaskAction -Execute $python `
    -Argument "-m pipeline_orchestrator.tache_quotidienne" `
    -WorkingDirectory $racine

$trigger = New-ScheduledTaskTrigger -Daily -At 08:00

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $nomTache `
    -Action $action -Trigger $trigger -Settings $settings `
    -Description ("Rafraichit le Data Warehouse NG Travel tous les jours a 8h " + `
                   "(etl/transformation + etl/load), publie data/, et journalise " + `
                   "le resultat dans log/historique_orchestration.log.") `
    -Force | Out-Null

Write-Host "Tache planifiee installee : '$nomTache' (tous les jours a 08:00)." -ForegroundColor Green
Write-Host "Cette tache ne s'execute que si cette machine est allumee a 8h (StartWhenAvailable : elle se rattrape au demarrage si le PC etait eteint)."
Write-Host ""
Write-Host "Verification : Get-ScheduledTask -TaskName '$nomTache'"
Write-Host "Test manuel immediat : Start-ScheduledTask -TaskName '$nomTache'"
Write-Host "Desinstallation : Unregister-ScheduledTask -TaskName '$nomTache' -Confirm:`$false"
