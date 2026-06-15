$ErrorActionPreference = "Stop"

$repoName = "adab-bot"
$currentAuth = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "GitHub CLI is not logged in. Run this first:"
    Write-Host "gh auth login --hostname github.com --git-protocol https --web"
    exit 1
}

$repoExists = gh repo view $repoName 2>$null
if ($LASTEXITCODE -ne 0) {
    gh repo create $repoName --private --source . --remote origin --push
} else {
    $owner = gh api user --jq .login
    $remoteUrl = "https://github.com/$owner/$repoName.git"
    git remote remove origin 2>$null
    git remote add origin $remoteUrl
    git push -u origin master
}

Write-Host "Repository is ready:"
gh repo view $repoName --web
