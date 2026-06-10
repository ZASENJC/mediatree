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

    public event EventHandler? LibrariesChanged;

    public LibraryService(MediaTreeApiClient api)
    {
        _api = api;
    }

    public async Task AddLibraryAsync(
        string folderPath,
        string scraper,
        string password = "",
        string tmdbAccessToken = "",
        CancellationToken cancellationToken = default)
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
            NotifyLibrariesChanged();
        }

        if (!string.IsNullOrWhiteSpace(tmdbAccessToken))
        {
            await _api.SaveTmdbConfigAsync(tmdbAccessToken, cancellationToken);
        }

        await _api.SaveLibrarySettingAsync(new LibrarySettingDto
        {
            MediaRoot = normalized,
            Scraper = NormalizeScraper(scraper),
            TmdbKey = "",
            Enabled = 1,
        }, cancellationToken);
        if (!string.IsNullOrWhiteSpace(password))
        {
            await _api.SetLibraryPasswordAsync(normalized, password, cancellationToken);
        }

        await _api.ScanAsync(normalized, cancellationToken);
    }

    public async Task<bool> AddLibraryRootAsync(string folderPath, string scraper = "auto", CancellationToken cancellationToken = default)
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
        var alreadyExists = roots.Any(root => string.Equals(Path.GetFullPath(root), normalized, StringComparison.OrdinalIgnoreCase));
        if (!alreadyExists)
        {
            roots.Add(normalized);
            await _api.SaveConfigAsync(roots, cancellationToken);
            NotifyLibrariesChanged();
        }

        await _api.SaveLibrarySettingAsync(new LibrarySettingDto
        {
            MediaRoot = normalized,
            Scraper = NormalizeScraper(scraper),
            TmdbKey = "",
            Enabled = 1,
        }, cancellationToken);

        return !alreadyExists;
    }

    public Task<SetupStatusDto> GetSetupStatusAsync(CancellationToken cancellationToken = default)
        => _api.GetSetupStatusAsync(cancellationToken);

    public Task<MediaRootsResponseDto> GetMediaRootsAsync(CancellationToken cancellationToken = default)
        => _api.GetMediaRootsAsync(cancellationToken);

    public Task<List<LibrarySettingDto>> GetLibrarySettingsAsync(CancellationToken cancellationToken = default)
        => _api.GetLibrarySettingsAsync(cancellationToken);

    public Task SaveLibrarySettingAsync(LibrarySettingDto setting, CancellationToken cancellationToken = default)
        => _api.SaveLibrarySettingAsync(setting, cancellationToken);

    public async Task<BasicActionResultDto> DeleteLibraryAsync(string mediaRoot, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(mediaRoot))
        {
            throw new ArgumentException("mediaRoot is required.", nameof(mediaRoot));
        }

        var config = await _api.GetConfigAsync(cancellationToken);
        var roots = RemoveLibraryRootFromConfig(config.ExtraMediaRoots ?? [], mediaRoot);
        await _api.SaveConfigAsync(roots, cancellationToken);
        NotifyLibrariesChanged();
        return new BasicActionResultDto { Ok = true, Deleted = 1 };
    }

    public Task SetLibraryPasswordAsync(string mediaRoot, string password, CancellationToken cancellationToken = default)
        => _api.SetLibraryPasswordAsync(mediaRoot, password, cancellationToken);

    public Task<FoldersResponseDto> GetFoldersAsync(string mediaRoot = "", CancellationToken cancellationToken = default)
        => _api.GetFoldersAsync(mediaRoot, cancellationToken);

    public Task<ScanStatusDto> GetScanStatusAsync(string mediaRoot, CancellationToken cancellationToken = default)
        => _api.GetScanStatusAsync(mediaRoot, cancellationToken);

    public Task<ScanLogDto> GetScanLogAsync(string mediaRoot, int lines = 80, CancellationToken cancellationToken = default)
        => _api.GetScanLogAsync(mediaRoot, lines, cancellationToken);

    public Task ScanAsync(string mediaRoot, CancellationToken cancellationToken = default)
        => _api.ScanAsync(mediaRoot, cancellationToken);

    public Task ClearLibraryAsync(string mediaRoot, CancellationToken cancellationToken = default)
        => _api.ClearLibraryAsync(mediaRoot, cancellationToken);

    private static string NormalizeScraper(string scraper)
    {
        var value = (scraper ?? "").Trim().ToLowerInvariant();
        return value switch
        {
            "" => "auto",
            "tmdb" => "tmdb_movie",
            "tmdb_movie" or "tmdb_tv" or "tmdb_collection" or "bangumi" or "javdatabase" or "auto" or "none" => value,
            _ => "auto",
        };
    }

    public static List<string> RemoveLibraryRootFromConfig(IEnumerable<string> roots, string mediaRoot)
    {
        var normalizedTarget = NormalizePathForComparison(mediaRoot);
        return roots
            .Where(root => !string.Equals(NormalizePathForComparison(root), normalizedTarget, StringComparison.OrdinalIgnoreCase))
            .ToList();
    }

    public static bool RootsMatch(string left, string right)
        => string.Equals(NormalizePathForComparison(left), NormalizePathForComparison(right), StringComparison.OrdinalIgnoreCase);

    public void NotifyLibrariesChanged()
        => LibrariesChanged?.Invoke(this, EventArgs.Empty);

    private static string NormalizePathForComparison(string path)
    {
        try
        {
            return Path.GetFullPath(path).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        }
        catch (ArgumentException)
        {
            return (path ?? "").Trim().TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        }
        catch (NotSupportedException)
        {
            return (path ?? "").Trim().TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        }
        catch (PathTooLongException)
        {
            return (path ?? "").Trim().TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        }
    }
}
