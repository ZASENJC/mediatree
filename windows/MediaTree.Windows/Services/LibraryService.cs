using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.Services;

public sealed class LibraryService
{
    private readonly MediaTreeApiClient _api;

    public LibraryService(MediaTreeApiClient api)
    {
        _api = api;
    }

    public async Task AddLibraryAsync(string folderPath, string scraper, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(folderPath))
        {
            throw new ArgumentException("folderPath is required.", nameof(folderPath));
        }

        var normalized = Path.GetFullPath(folderPath);
        if (!Directory.Exists(normalized))
        {
            throw new DirectoryNotFoundException(normalized);
        }

        var config = await _api.GetConfigAsync(cancellationToken);
        var roots = new List<string>(config.ExtraMediaRoots ?? []);
        if (!roots.Any(root => string.Equals(Path.GetFullPath(root), normalized, StringComparison.OrdinalIgnoreCase)))
        {
            roots.Add(normalized);
            await _api.SaveConfigAsync(roots, cancellationToken);
        }

        await _api.SaveLibrarySettingAsync(new LibrarySettingDto
        {
            MediaRoot = normalized,
            Scraper = string.IsNullOrWhiteSpace(scraper) ? "auto" : scraper,
            TmdbKey = "",
            Enabled = 1,
        }, cancellationToken);
        await _api.ScanAsync(normalized, cancellationToken);
    }

    public Task<SetupStatusDto> GetSetupStatusAsync(CancellationToken cancellationToken = default)
        => _api.GetSetupStatusAsync(cancellationToken);

    public Task<MediaRootsResponseDto> GetMediaRootsAsync(CancellationToken cancellationToken = default)
        => _api.GetMediaRootsAsync(cancellationToken);

    public Task<List<LibrarySettingDto>> GetLibrarySettingsAsync(CancellationToken cancellationToken = default)
        => _api.GetLibrarySettingsAsync(cancellationToken);

    public Task SaveLibrarySettingAsync(LibrarySettingDto setting, CancellationToken cancellationToken = default)
        => _api.SaveLibrarySettingAsync(setting, cancellationToken);

    public Task SetLibraryPasswordAsync(string mediaRoot, string password, CancellationToken cancellationToken = default)
        => _api.SetLibraryPasswordAsync(mediaRoot, password, cancellationToken);

    public Task<FoldersResponseDto> GetFoldersAsync(string mediaRoot = "", CancellationToken cancellationToken = default)
        => _api.GetFoldersAsync(mediaRoot, cancellationToken);

    public Task<ScanStatusDto> GetScanStatusAsync(string mediaRoot, CancellationToken cancellationToken = default)
        => _api.GetScanStatusAsync(mediaRoot, cancellationToken);

    public Task ScanAsync(string mediaRoot, CancellationToken cancellationToken = default)
        => _api.ScanAsync(mediaRoot, cancellationToken);

    public Task ClearLibraryAsync(string mediaRoot, CancellationToken cancellationToken = default)
        => _api.ClearLibraryAsync(mediaRoot, cancellationToken);
}
