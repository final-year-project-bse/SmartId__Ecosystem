# Create GitHub repo "Smartid_Ecosystem" under the account final-year-project-bse and push.
# Run this script AFTER creating a Personal Access Token at https://github.com/settings/tokens
# (scope: repo). Then either:
#   $env:GITHUB_TOKEN = "your_token_here"
#   .\create_repo_and_push.ps1
# Or run: .\create_repo_and_push.ps1 -Token "your_token_here"

param([string]$Token = $env:GITHUB_TOKEN)

$ErrorActionPreference = "Stop"
$repoName = "Smartid_Ecosystem"
$apiUrl = "https://api.github.com/user/repos"

if (-not $Token) {
    Write-Host "Usage: Set GITHUB_TOKEN or run: .\create_repo_and_push.ps1 -Token YOUR_GITHUB_TOKEN"
    Write-Host "Create a token at: https://github.com/settings/tokens (scope: repo)"
    exit 1
}

$body = @{ name = $repoName; description = "SmartID Ecosystem - Django attendance, timetable, reports"; private = $false } | ConvertTo-Json
$headers = @{
    Authorization = "token $Token"
    Accept = "application/vnd.github.v3+json"
}

Write-Host "Creating repo $repoName..."
try {
    Invoke-RestMethod -Uri $apiUrl -Method Post -Body $body -Headers $headers -ContentType "application/json"
    Write-Host "Repo created. Pushing..."
} catch {
    if ($_.Exception.Response.StatusCode -eq 422) {
        Write-Host "Repo may already exist. Pushing..."
    } else { throw }
}

Set-Location $PSScriptRoot
git push -u origin main
Write-Host "Done: https://github.com/final-year-project-bse/Smartid_Ecosystem"
