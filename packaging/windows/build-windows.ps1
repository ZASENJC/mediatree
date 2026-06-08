param(
  [string]$Configuration = "Release",
  [string]$Version = "",
  [switch]$SkipTests,
  [string]$AppInstallerUri = "https://github.com/ZASENJC/mediatree/releases/latest/download/",
  [string]$MpvArchiveUrl = "https://github.com/zhongfly/mpv-winbuild/releases/download/2026-06-07-43b14a4c9f/mpv-x86_64-20260607-git-43b14a4c9f.7z",
  [string]$MpvArchivePath = "",
  [string]$SevenZipUrl = "https://www.7-zip.org/a/7zr.exe",
  [switch]$SkipMpvDownload,
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

function Resolve-7ZipTool {
  $commands = @("7z.exe", "7za.exe", "7zr.exe")
  foreach ($command in $commands) {
    $resolved = Get-Command $command -ErrorAction SilentlyContinue
    if ($resolved) {
      return $resolved.Source
    }
  }

  $candidates = @(
    (Join-Path $env:ProgramFiles "7-Zip\7z.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "7-Zip\7z.exe")
  )
  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path $candidate)) {
      return $candidate
    }
  }

  $toolsDir = Join-Path $Root "build/windows/tools"
  New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
  $downloaded = Join-Path $toolsDir "7zr.exe"
  if (-not (Test-Path $downloaded)) {
    Write-Host "Downloading 7-Zip standalone extractor: $SevenZipUrl"
    Invoke-WebRequest -Uri $SevenZipUrl -OutFile $downloaded
  }
  if (-not (Test-Path $downloaded)) {
    throw "7-Zip extractor was not available."
  }
  return $downloaded
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

function Expand-MpvArchive {
  param(
    [string]$ArchivePath,
    [string]$Destination
  )

  if (Test-Path $Destination) {
    Remove-Item $Destination -Recurse -Force
  }
  New-Item -ItemType Directory -Force -Path $Destination | Out-Null
  $sevenZip = Resolve-7ZipTool
  Invoke-Native $sevenZip x $ArchivePath "-o$Destination" -y
  if (Get-ChildItem -Path $Destination -Recurse -Filter "mpv.exe" -ErrorAction SilentlyContinue | Select-Object -First 1) {
    return
  }

  $extractScript = @"
import sys
from pathlib import Path
import py7zr

archive = Path(sys.argv[1])
destination = Path(sys.argv[2])
with py7zr.SevenZipFile(archive, mode="r") as z:
    z.extractall(destination)
"@
  $extractScriptPath = Join-Path $Root "build/windows/extract-mpv.py"
  Set-Content -Path $extractScriptPath -Value $extractScript -Encoding UTF8
  Invoke-Native python $extractScriptPath $ArchivePath $Destination
}

function Install-BundledMpv {
  param(
    [string]$Destination
  )

  $cacheDir = Join-Path $Root "build/windows/mpv-cache"
  $extractDir = Join-Path $Root "build/windows/mpv-extract"
  New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null
  $archive = $MpvArchivePath
  if (-not $archive) {
    $archive = Join-Path $cacheDir (Split-Path ([Uri]$MpvArchiveUrl).LocalPath -Leaf)
  }

  if (-not (Test-Path $archive)) {
    if ($SkipMpvDownload) {
      throw "Bundled mpv archive is missing and SkipMpvDownload was set: $archive"
    }
    Write-Host "Downloading bundled mpv: $MpvArchiveUrl"
    Invoke-WebRequest -Uri $MpvArchiveUrl -OutFile $archive
  }

  Expand-MpvArchive -ArchivePath $archive -Destination $extractDir
  $mpvExe = Get-ChildItem -Path $extractDir -Recurse -Filter "mpv.exe" -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if (-not $mpvExe) {
    throw "mpv.exe was not found in archive: $archive"
  }

  if (Test-Path $Destination) {
    Remove-Item $Destination -Recurse -Force
  }
  New-Item -ItemType Directory -Force -Path $Destination | Out-Null
  Copy-Item (Join-Path $mpvExe.Directory.FullName "*") $Destination -Recurse -Force
  if (-not (Test-Path (Join-Path $Destination "mpv.exe"))) {
    throw "Bundled mpv.exe was not copied to $Destination"
  }
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
Invoke-Native python -m pip install pyinstaller py7zr

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

$ServerDist = Join-Path $Root "dist/windows/server"
$ServerSource = Join-Path $ServerDist "mediatree-server"
$ServerWork = Join-Path $Root "build/windows/mediatree-server"
if (Test-Path $ServerSource) {
  Remove-Item $ServerSource -Recurse -Force
}
if (Test-Path $ServerWork) {
  Remove-Item $ServerWork -Recurse -Force
}
Invoke-Native pyinstaller --noconfirm --distpath dist/windows/server --workpath build/windows packaging/windows/mediatree-server.spec

$ShellServer = Join-Path $Root "windows/MediaTree.Windows/server"
if (Test-Path $ShellServer) {
  Remove-Item $ShellServer -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $ShellServer | Out-Null
Copy-Item (Join-Path $ServerSource "*") $ShellServer -Recurse -Force

$ShellMpv = Join-Path $Root "windows/MediaTree.Windows/mpv"
Install-BundledMpv -Destination $ShellMpv

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
$GeneratedCert = $null
try {
  [xml]$Manifest = Get-Content $ManifestPath
  $Manifest.Package.Identity.Version = $MsixVersion
  $Manifest.Save($ManifestPath)

  $ShellOutput = Join-Path $Root "dist/windows/publish/MediaTree.Windows"
  if (Test-Path $ShellOutput) {
    Remove-Item $ShellOutput -Recurse -Force
  }
  $MsBuild = Resolve-MSBuild
  Invoke-Native $MsBuild windows/MediaTree.Windows/MediaTree.Windows.csproj `
    /restore `
    /t:Publish `
    /p:Configuration=$Configuration `
    /p:Platform=x64 `
    /p:RuntimeIdentifier=win-x64 `
    /p:PublishDir="$ShellOutput\" `
    /p:WindowsAppSDKSelfContained=true `
    /p:WindowsPackageType=None `
    /p:SelfContained=true `
    /p:PublishSingleFile=false `
    /p:AppxPackage=false

  if (-not (Test-Path (Join-Path $ShellOutput "MediaTree.Windows.exe"))) {
    throw "WinUI output is missing MediaTree.Windows.exe: $ShellOutput"
  }
  if (-not (Test-Path (Join-Path $ShellOutput "server/mediatree-server.exe"))) {
    throw "WinUI output is missing bundled backend server: $ShellOutput"
  }
  if (-not (Test-Path (Join-Path $ShellOutput "mpv/mpv.exe"))) {
    throw "WinUI output is missing bundled mpv.exe: $ShellOutput"
  }
  $PriFiles = Get-ChildItem -Path $ShellOutput -Filter "*.pri" -File -ErrorAction SilentlyContinue
  if (-not $PriFiles) {
    throw "WinUI output is missing PRI resources: $ShellOutput"
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

  $PortableZipPath = Join-Path $MsixOutDir "MediaTree-Windows-$Version-portable.zip"
  if (Test-Path $PortableZipPath) {
    Remove-Item $PortableZipPath -Force
  }
  Compress-Archive -Path (Join-Path $ShellOutput "*") -DestinationPath $PortableZipPath -Force

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
  if (-not (Test-Path $PortableZipPath)) {
    throw "Portable package was not generated: $PortableZipPath"
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
