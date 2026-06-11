using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.Services;

public sealed partial class MediaTreeApiClient
{
    public async Task<SetupStatusDto> GetSetupStatusAsync(CancellationToken cancellationToken = default)
        => await GetAsync<SetupStatusDto>("/setup/status", cancellationToken);

    public async Task<MediaRootsResponseDto> GetMediaRootsAsync(CancellationToken cancellationToken = default)
        => await GetAsync<MediaRootsResponseDto>("/media-roots", cancellationToken);

    public async Task<List<LibrarySettingDto>> GetLibrarySettingsAsync(CancellationToken cancellationToken = default)
        => await GetAsync<List<LibrarySettingDto>>("/library-settings", cancellationToken);

    public async Task<FoldersResponseDto> GetFoldersAsync(string mediaRoot = "", CancellationToken cancellationToken = default)
    {
        var suffix = string.IsNullOrWhiteSpace(mediaRoot) ? "" : $"?media_root={Uri.EscapeDataString(mediaRoot)}";
        return await GetAsync<FoldersResponseDto>($"/folders{suffix}", cancellationToken);
    }

    public async Task SaveLibrarySettingAsync(LibrarySettingDto setting, CancellationToken cancellationToken = default)
        => await PostJsonAsync<JsonElement>("/library-settings", new
        {
            media_root = setting.MediaRoot,
            scraper = setting.Scraper,
            tmdb_key = setting.TmdbKey,
            enabled = setting.Enabled,
        }, cancellationToken);

    public async Task SetLibraryPasswordAsync(string mediaRoot, string password, CancellationToken cancellationToken = default)
        => await PostJsonAsync<JsonElement>("/library-passwords", new
        {
            media_root = mediaRoot,
            password,
        }, cancellationToken);

    public async Task ScanAsync(string mediaRoot, CancellationToken cancellationToken = default)
        => await GetAsync<JsonElement>($"/scan?media_root={Uri.EscapeDataString(mediaRoot)}", cancellationToken);

    public async Task ClearLibraryAsync(string mediaRoot, CancellationToken cancellationToken = default)
        => await PostJsonAsync<JsonElement>("/library/clear", new { media_root = mediaRoot }, cancellationToken);

    public async Task<ScanStatusDto> GetScanStatusAsync(string mediaRoot, CancellationToken cancellationToken = default)
        => await GetAsync<ScanStatusDto>($"/scan/status?media_root={Uri.EscapeDataString(mediaRoot)}", cancellationToken);

    public async Task<ScanLogDto> GetScanLogAsync(string mediaRoot, int lines = 80, CancellationToken cancellationToken = default)
        => await GetAsync<ScanLogDto>($"/scan/log?media_root={Uri.EscapeDataString(mediaRoot)}&lines={lines}", cancellationToken);
}
