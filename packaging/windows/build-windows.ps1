param(
  [string]$Configuration = "Release",
  [string]$Version = "",
  [switch]$SkipTests,
  [string]$AppInstallerUri = "https://github.com/ZASENJC/mediatree/releases/latest/download/",
  [string]$SigningPfxPath = "",
  [string]$SigningPfxPassword = "",
  [switch]$SkipSigning
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root

function Invoke-Native {
  if ($args.Count -lt 1) {
    throw "Invoke-Native requires a command."
  }
  $FilePath = [string]$args[0]
  $Arguments = @()
  if ($args.Count -gt 1) {
    $Arguments = @($args[1..($args.Count - 1)])
  }

  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "$FilePath failed with exit code $LASTEXITCODE"
  }
}

function Resolve-MSBuild {
  $programFilesX86 = ${env:ProgramFiles(x86)}
  if (-not $programFilesX86) {
    throw "ProgramFiles(x86) is not available."
  }

  $vswhere = Join-Path $programFilesX86 "Microsoft Visual Studio\Installer\vswhere.exe"
  if (Test-Path $vswhere) {
    $installationPath = & $vswhere -latest -products * -requires Microsoft.Component.MSBuild -property installationPath
    if ($LASTEXITCODE -eq 0 -and $installationPath) {
      $candidate = Join-Path $installationPath "MSBuild\Current\Bin\MSBuild.exe"
      if (Test-Path $candidate) {
        return $candidate
      }
    }
  }

  $fallback = Join-Path $programFilesX86 "Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe"
  if (Test-Path $fallback) {
    return $fallback
  }

  throw "MSBuild.exe was not found. Install Visual Studio 2022 Build Tools with MSBuild and Windows SDK components."
}

function Resolve-WindowsKitTool {
  param([string]$ToolName)

  $programFilesX86 = ${env:ProgramFiles(x86)}
  if (-not $programFilesX86) {
    throw "ProgramFiles(x86) is not available."
  }

  $kitsRoot = Join-Path $programFilesX86 "Windows Kits\10\bin"
  if (-not (Test-Path $kitsRoot)) {
    throw "Windows Kits bin directory was not found. Install the Windows 10 SDK."
  }

  $candidate = Get-ChildItem -Path $kitsRoot -Recurse -Filter $ToolName -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -like "*\x64\*" } |
    Sort-Object FullName -Descending |
    Select-Object -First 1
  if (-not $candidate) {
    $candidate = Get-ChildItem -Path $kitsRoot -Recurse -Filter $ToolName -ErrorAction SilentlyContinue |
      Sort-Object FullName -Descending |
      Select-Object -First 1
  }
  if (-not $candidate) {
    throw "$ToolName was not found under $kitsRoot."
  }

  return $candidate.FullName
}

function New-ExpandedAppxManifest {
  param(
    [string]$SourceManifest,
    [string]$OutputManifest,
    [string]$PackageVersion
  )

  [xml]$package = Get-Content $SourceManifest
  $package.Package.Identity.Version = $PackageVersion
  $package.Package.Identity.SetAttribute("ProcessorArchitecture", "x64")

  $application = $package.Package.Applications.Application
  $application.Executable = "MediaTree.Windows.exe"
  $application.EntryPoint = "Windows.FullTrustApplication"

  $package.Save($OutputManifest)
}

function New-AppInstallerFile {
  param(
    [string]$OutputPath,
    [string]$PackageVersion,
    [string]$PackageName,
    [string]$Publisher,
    [string]$PackageUri,
    [string]$InstallerUri
  )

  $content = @"
<?xml version="1.0" encoding="utf-8"?>
<AppInstaller
  xmlns="http://schemas.microsoft.com/appx/appinstaller/2018"
  Version="$PackageVersion"
  Uri="$InstallerUri">
  <MainPackage
    Name="$PackageName"
    Publisher="$Publisher"
    Version="$PackageVersion"
    ProcessorArchitecture="x64"
    Uri="$PackageUri" />
  <UpdateSettings>
    <OnLaunch HoursBetweenUpdateChecks="24" ShowPrompt="true" UpdateBlocksActivation="false" />
  </UpdateSettings>
</AppInstaller>
"@
  Set-Content -Path $OutputPath -Value $content -Encoding UTF8
}

function New-TestSigningCertificate {
  param(
    [string]$SigningDir,
    [string]$PublicCertPath
  )

  New-Item -ItemType Directory -Force -Path $SigningDir | Out-Null
  $plainPassword = [Guid]::NewGuid().ToString("N")
  $securePassword = ConvertTo-SecureString -String $plainPassword -Force -AsPlainText
  $cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject "CN=MediaTree" `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -KeyExportPolicy Exportable `
    -KeyUsage DigitalSignature `
    -KeyLength 2048 `
    -HashAlgorithm SHA256
  $pfxPath = Join-Path $SigningDir "MediaTree-Windows.test.pfx"
  Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $securePassword | Out-Null
  Export-Certificate -Cert $cert -FilePath $PublicCertPath | Out-Null

  return [PSCustomObject]@{
    PfxPath = $pfxPath
    Password = $plainPassword
    Thumbprint = $cert.Thumbprint
  }
}

function Sign-MsixPackage {
  param(
    [string]$MsixPath,
    [string]$PfxPath,
    [string]$PfxPassword
  )

  $signtool = Resolve-WindowsKitTool "signtool.exe"
  Invoke-Native $signtool sign /fd SHA256 /f $PfxPath /p $PfxPassword $MsixPath
}

if (-not $Version) {
  $Version = (Get-Content VERSION -TotalCount 1).Trim()
}
if (-not $Version) {
  throw "VERSION is empty."
}

Write-Host "Building MediaTree Windows $Version"

$MsixVersion = $Version
if (($MsixVersion.Split(".")).Count -eq 3) {
  $MsixVersion = "$MsixVersion.0"
}
if (-not ($MsixVersion -match '^\d+\.\d+\.\d+\.\d+$')) {
  throw "MSIX version must be numeric four-part version. Got: $MsixVersion"
}

Invoke-Native python -m pip install --upgrade pip
Invoke-Native python -m pip install -r backend/requirements.txt -c backend/constraints.txt
Invoke-Native python -m pip install pyinstaller

if (-not $SkipTests) {
  Push-Location backend
  try {
    $env:PYTHONPATH = "."
    Invoke-Native python -m unittest discover -s tests -p "test_*.py"
  } finally {
    Pop-Location
  }
  Invoke-Native python -m compileall -q backend/app
}

Push-Location frontend
try {
  Invoke-Native npm.cmd ci --legacy-peer-deps
  Invoke-Native npm.cmd run build
} finally {
  Pop-Location
}

Invoke-Native pyinstaller --noconfirm --distpath dist/windows/server --workpath build/windows packaging/windows/mediatree-server.spec

$ServerSource = Join-Path $Root "dist/windows/server/mediatree-server"
$ShellServer = Join-Path $Root "windows/MediaTree.Windows/server"
if (Test-Path $ShellServer) {
  Remove-Item $ShellServer -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $ShellServer | Out-Null
Copy-Item (Join-Path $ServerSource "*") $ShellServer -Recurse -Force

$Assets = Join-Path $Root "windows/MediaTree.Windows/Assets"
New-Item -ItemType Directory -Force -Path $Assets | Out-Null
$Logo = Join-Path $Root "docs/assets/logo.png"
if (-not (Test-Path $Logo)) {
  throw "Missing logo asset: $Logo"
}
Copy-Item $Logo (Join-Path $Assets "StoreLogo.png") -Force
Copy-Item $Logo (Join-Path $Assets "Square44x44Logo.png") -Force
Copy-Item $Logo (Join-Path $Assets "Square150x150Logo.png") -Force
Copy-Item $Logo (Join-Path $Assets "Square310x310Logo.png") -Force
Copy-Item $Logo (Join-Path $Assets "Wide310x150Logo.png") -Force

$ManifestPath = Join-Path $Root "windows/MediaTree.Windows/Package.appxmanifest"
$OriginalManifest = Get-Content $ManifestPath -Raw
[xml]$Manifest = Get-Content $ManifestPath
$Manifest.Package.Identity.Version = $MsixVersion
$Manifest.Save($ManifestPath)

try {
  $MsBuild = Resolve-MSBuild
  Invoke-Native $MsBuild windows/MediaTree.Windows/MediaTree.Windows.csproj `
    /restore `
    /p:Configuration=$Configuration `
    /p:Platform=x64 `
    /p:RuntimeIdentifier=win-x64 `
    /p:GenerateAppxPackageOnBuild=true `
    /p:AppxPackageDir="$Root\dist\windows\msix\" `
    /p:AppxBundle=Never `
    /p:AppxIntermediateExtension=.intermediate `
    /p:UapAppxPackageBuildMode=SideloadOnly `
    /p:AppxPackageSigningEnabled=false

  $ShellOutput = Join-Path $Root "windows/MediaTree.Windows/bin/x64/$Configuration/net8.0-windows10.0.19041.0/win-x64"
  if (-not (Test-Path (Join-Path $ShellOutput "MediaTree.Windows.exe"))) {
    throw "WinUI output is missing MediaTree.Windows.exe: $ShellOutput"
  }
  if (-not (Test-Path (Join-Path $ShellOutput "server/mediatree-server.exe"))) {
    throw "WinUI output is missing bundled backend server: $ShellOutput"
  }
  if (-not (Test-Path (Join-Path $ShellOutput "resources.pri"))) {
    throw "WinUI output is missing resources.pri: $ShellOutput"
  }

  $MsixOutDir = Join-Path $Root "dist/windows/msix"
  $PackageLayout = Join-Path $Root "build/windows/msix-layout"
  if (Test-Path $MsixOutDir) {
    Remove-Item $MsixOutDir -Recurse -Force
  }
  if (Test-Path $PackageLayout) {
    Remove-Item $PackageLayout -Recurse -Force
  }
  New-Item -ItemType Directory -Force -Path $MsixOutDir | Out-Null
  New-Item -ItemType Directory -Force -Path $PackageLayout | Out-Null

  Copy-Item (Join-Path $ShellOutput "*") $PackageLayout -Recurse -Force
  New-ExpandedAppxManifest `
    -SourceManifest $ManifestPath `
    -OutputManifest (Join-Path $PackageLayout "AppxManifest.xml") `
    -PackageVersion $MsixVersion

  $MsixPath = Join-Path $MsixOutDir "MediaTree-Windows-$Version.msix"
  $AppInstallerPath = Join-Path $MsixOutDir "MediaTree-Windows-$Version.appinstaller"
  $PublicCertPath = Join-Path $MsixOutDir "MediaTree-Windows-$Version.cer"
  $MakeAppx = Resolve-WindowsKitTool "makeappx.exe"
  Invoke-Native $MakeAppx pack /d $PackageLayout /p $MsixPath /overwrite

  $GeneratedCert = $null
  if (-not $SkipSigning) {
    $EffectivePfxPath = $SigningPfxPath
    if (-not $EffectivePfxPath -and $env:WINDOWS_SIGNING_PFX) {
      $EffectivePfxPath = $env:WINDOWS_SIGNING_PFX
    }
    $EffectivePfxPassword = $SigningPfxPassword
    if (-not $EffectivePfxPassword -and $env:WINDOWS_SIGNING_PASSWORD) {
      $EffectivePfxPassword = $env:WINDOWS_SIGNING_PASSWORD
    }

    if ($EffectivePfxPath) {
      if (-not (Test-Path $EffectivePfxPath)) {
        throw "Signing PFX was not found: $EffectivePfxPath"
      }
      if (-not $EffectivePfxPassword) {
        throw "Signing PFX password is required when SigningPfxPath is provided."
      }
      Sign-MsixPackage -MsixPath $MsixPath -PfxPath $EffectivePfxPath -PfxPassword $EffectivePfxPassword
    } else {
      $GeneratedCert = New-TestSigningCertificate `
        -SigningDir (Join-Path $Root "build/windows/signing") `
        -PublicCertPath $PublicCertPath
      Sign-MsixPackage -MsixPath $MsixPath -PfxPath $GeneratedCert.PfxPath -PfxPassword $GeneratedCert.Password
    }
  }

  $BaseDownloadUri = $AppInstallerUri.TrimEnd("/") + "/"
  New-AppInstallerFile `
    -OutputPath $AppInstallerPath `
    -PackageVersion $MsixVersion `
    -PackageName $Manifest.Package.Identity.Name `
    -Publisher $Manifest.Package.Identity.Publisher `
    -PackageUri ($BaseDownloadUri + "MediaTree-Windows-$Version.msix") `
    -InstallerUri ($BaseDownloadUri + "MediaTree-Windows-$Version.appinstaller")

  if (-not (Test-Path $MsixPath)) {
    throw "MSIX package was not generated: $MsixPath"
  }
  if (-not (Test-Path $AppInstallerPath)) {
    throw "App installer file was not generated: $AppInstallerPath"
  }
  if (-not $SkipSigning -and -not $SigningPfxPath -and -not $env:WINDOWS_SIGNING_PFX -and -not (Test-Path $PublicCertPath)) {
    throw "Public signing certificate was not exported: $PublicCertPath"
  }
} finally {
  Set-Content -Path $ManifestPath -Value $OriginalManifest -Encoding UTF8
  if ($GeneratedCert -and $GeneratedCert.Thumbprint) {
    Remove-Item -Path "Cert:\CurrentUser\My\$($GeneratedCert.Thumbprint)" -ErrorAction SilentlyContinue
  }
}

Write-Host "Windows artifacts:"
Get-ChildItem -Path (Join-Path $Root "dist/windows") -Recurse -File |
  Where-Object { $_.Extension -in ".msix", ".appinstaller", ".cer", ".zip", ".exe" } |
  ForEach-Object { Write-Host " - $($_.FullName)" }
