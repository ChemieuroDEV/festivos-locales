# Publica este feed en GitHub por primera vez.
#
# Solo hace falta una vez. A partir de ahi, el propio repositorio se actualiza
# con GitHub Actions y no hay que volver a tocar nada.
#
# Antes de ejecutarlo:
#   1. Instala GitHub CLI si no lo tienes:  winget install GitHub.cli
#   2. Identificate:                        gh auth login
#      (elige GitHub.com, HTTPS, y autentica en el navegador con ChemieuroDEV)
#
# Despues:
#   cd C:\Temp\che\festivos-locales
#   .\publicar.ps1

$ErrorActionPreference = 'Stop'

$repo = 'ChemieuroDEV/festivos-locales'
$descripcion = 'Festivos municipales de Espana, Portugal e Italia en JSON, para que Business Central sepa si una entrega cae en fiesta local'

Write-Host "Comprobando GitHub CLI..." -ForegroundColor Cyan
gh auth status
if ($LASTEXITCODE -ne 0) {
    throw "No estas identificado en GitHub. Ejecuta 'gh auth login' y vuelve a intentarlo."
}

Write-Host "Creando el repositorio $repo (publico)..." -ForegroundColor Cyan
gh repo create $repo --public --description $descripcion --disable-wiki
if ($LASTEXITCODE -ne 0) {
    Write-Host "El repositorio ya existia o no se pudo crear; se intenta subir igualmente." -ForegroundColor Yellow
}

if (-not (Test-Path '.git')) {
    git init
    git branch -M main
}

git add -A
git -c user.name='Chemieuro' -c user.email='davidberna@gmail.com' commit -m 'Festivos locales de Espana, Portugal e Italia: primera publicacion'

git remote remove origin 2>$null
git remote add origin "https://github.com/$repo.git"
git push -u origin main

Write-Host ''
Write-Host 'Publicado.' -ForegroundColor Green
Write-Host "URL base que hay que poner en Business Central, en 'Config. festivos de entrega':" -ForegroundColor Green
Write-Host "  https://raw.githubusercontent.com/$repo/main/data" -ForegroundColor White
Write-Host ''
Write-Host 'Comprueba que responde (deberia salir Pisa con San Ranieri el 17 de junio):' -ForegroundColor Cyan
Write-Host "  curl https://raw.githubusercontent.com/$repo/main/data/IT/2026/56.json" -ForegroundColor White
Write-Host ''
Write-Host 'La actualizacion anual ya queda programada sola en la pestana Actions.' -ForegroundColor Cyan
