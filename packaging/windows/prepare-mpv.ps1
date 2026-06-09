param(
  [string]$Destination = "",
  [string]$MpvArchiveUrl = "https://github.com/zhongfly/mpv-winbuild/releases/download/2026-06-07-43b14a4c9f/mpv-x86_64-20260607-git-43b14a4c9f.7z",
  [string]$LibMpvArchiveUrl = "https://github.com/zhongfly/mpv-winbuild/releases/download/2026-06-07-43b14a4c9f/mpv-dev-x86_64-20260607-git-43b14a4c9f.7z",
  [string]$MpvArchivePath = "",
  [string]$LibMpvArchivePath = "",
  [string]$SevenZipUrl = "https://www.7-zip.org/a/7zr.exe",
  [switch]$SkipMpvDownload
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if (-not $Destination) {
  $Destination = Join-Path $Root "windows\MediaTree.Windows\mpv"
}

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

function Resolve-7ZipTool {
  $commands = @("7z.exe", "7za.exe", "7zr.exe")
  foreach ($command in $commands) {
    $resolved = Get-Command $command -ErrorAction SilentlyContinue
    if ($resolved) {
      return $resolved.Source
    }
  }

  $programFiles = $env:ProgramFiles
  $programFilesX86 = ${env:ProgramFiles(x86)}
  $candidates = @(
    $(if ($programFiles) { Join-Path $programFiles "7-Zip\7z.exe" }),
    $(if ($programFilesX86) { Join-Path $programFilesX86 "7-Zip\7z.exe" })
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
    if ($SkipMpvDownload) {
      throw "7-Zip extractor is missing and SkipMpvDownload was set: $downloaded"
    }
    Write-Host "Downloading 7-Zip standalone extractor: $SevenZipUrl"
    Invoke-WebRequest -Uri $SevenZipUrl -OutFile $downloaded
  }
  if (-not (Test-Path $downloaded)) {
    throw "7-Zip extractor was not available."
  }
  return $downloaded
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
  if (Get-ChildItem -Path $Destination -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1) {
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

$cacheDir = Join-Path $Root "build/windows/mpv-cache"
$extractDir = Join-Path $Root "build/windows/mpv-extract"
$libExtractDir = Join-Path $Root "build/windows/libmpv-extract"
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
$mpvDll = Get-ChildItem -Path $mpvExe.Directory.FullName -Filter "mpv-2.dll" -ErrorAction SilentlyContinue |
  Select-Object -First 1

if (Test-Path $Destination) {
  Remove-Item $Destination -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
Copy-Item (Join-Path $mpvExe.Directory.FullName "*") $Destination -Recurse -Force

if (-not $mpvDll) {
  $libArchive = $LibMpvArchivePath
  if (-not $libArchive) {
    $libArchive = Join-Path $cacheDir (Split-Path ([Uri]$LibMpvArchiveUrl).LocalPath -Leaf)
  }

  if (-not (Test-Path $libArchive)) {
    if ($SkipMpvDownload) {
      throw "Bundled libmpv archive is missing and SkipMpvDownload was set: $libArchive"
    }
    Write-Host "Downloading bundled libmpv: $LibMpvArchiveUrl"
    Invoke-WebRequest -Uri $LibMpvArchiveUrl -OutFile $libArchive
  }

  Expand-MpvArchive -ArchivePath $libArchive -Destination $libExtractDir
  $mpvDll = Get-ChildItem -Path $libExtractDir -Recurse -Filter "mpv-2.dll" -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if (-not $mpvDll) {
    $mpvDll = Get-ChildItem -Path $libExtractDir -Recurse -Filter "libmpv-2.dll" -ErrorAction SilentlyContinue |
      Select-Object -First 1
  }
}

if (-not $mpvDll) {
  throw "mpv-2.dll/libmpv-2.dll was not found in bundled mpv archives."
}

Copy-Item (Join-Path $mpvDll.Directory.FullName "*") $Destination -Recurse -Force
if ($mpvDll.Name -ieq "libmpv-2.dll") {
  Copy-Item $mpvDll.FullName (Join-Path $Destination "mpv-2.dll") -Force
}

if (-not (Test-Path (Join-Path $Destination "mpv-2.dll"))) {
  throw "Bundled mpv-2.dll was not copied to $Destination"
}
Remove-Item (Join-Path $Destination "mpv.exe") -Force -ErrorAction SilentlyContinue
Write-Host "Bundled libmpv runtime prepared: $Destination"
