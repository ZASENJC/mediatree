using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Linq;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.Services;

public sealed class MediaTreeApiClient : IDisposable
{
    private readonly HttpClient _httpClient;
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
    };
    private string _token = "";
    private string _mediaToken = "";
    private long _mediaTokenExpiresAt;

    public MediaTreeApiClient(Uri backendUri)
    {
        BackendUri = backendUri;
        _httpClient = new HttpClient
        {
            Timeout = TimeSpan.FromMinutes(10),
        };
    }

    public Uri BackendUri { get; private set; }

    public void SetBackendUri(Uri backendUri)
    {
        BackendUri = backendUri;
    }

    public void SetBearerToken(string token)
    {
        _token = token ?? "";
        _mediaToken = "";
        _mediaTokenExpiresAt = 0;
    }

    public async Task<AuthStatusDto> GetAuthStatusAsync(CancellationToken cancellationToken = default)
        => await GetAsync<AuthStatusDto>("/auth/status", cancellationToken);

    public async Task<AuthResponseDto> LoginAsync(string username, string password, CancellationToken cancellationToken = default)
        => await PostJsonAsync<AuthResponseDto>("/auth/login", new { username, password }, cancellationToken);

    public async Task<AuthResponseDto> SetupAuthAsync(string username, string password, CancellationToken cancellationToken = default)
        => await PostJsonAsync<AuthResponseDto>("/auth/setup", new { username, password }, cancellationToken);

    public async Task<SetupStatusDto> GetSetupStatusAsync(CancellationToken cancellationToken = default)
        => await GetAsync<SetupStatusDto>("/setup/status", cancellationToken);

    public async Task<ConfigDto> GetConfigAsync(CancellationToken cancellationToken = default)
        => await GetAsync<ConfigDto>("/config", cancellationToken);

    public async Task SaveConfigAsync(IEnumerable<string> extraMediaRoots, CancellationToken cancellationToken = default)
        => await PostJsonAsync<JsonElement>("/config", new { extra_media_roots = extraMediaRoots }, cancellationToken);

    public async Task SaveTmdbConfigAsync(string accessToken, CancellationToken cancellationToken = default)
        => await PostJsonAsync<JsonElement>("/config", new { tmdb_access_token = NormalizeTmdbAccessToken(accessToken) }, cancellationToken);

    public async Task SaveGlobalConfigAsync(ConfigDto config, CancellationToken cancellationToken = default)
        => await PostJsonAsync<JsonElement>("/config", new
        {
            javdb_enabled = config.JavdbEnabled,
            tmdb_api_key = config.TmdbApiKey,
            tmdb_access_token = NormalizeTmdbAccessToken(config.TmdbAccessToken),
            update_check_enabled = config.UpdateCheckEnabled,
            update_check_interval_hours = config.UpdateCheckIntervalHours,
        }, cancellationToken);

    public async Task ChangePasswordAsync(
        string oldUsername,
        string oldPassword,
        string newUsername,
        string newPassword,
        CancellationToken cancellationToken = default)
        => await PostJsonAsync<JsonElement>("/auth/change-password", new
        {
            old_username = oldUsername,
            old_password = oldPassword,
            new_username = newUsername,
            new_password = newPassword,
        }, cancellationToken);

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

    public async Task<MoviesResponseDto> GetMoviesAsync(
        string mediaRoot,
        string folder,
        string search,
        string sort,
        int limit,
        int offset,
        CancellationToken cancellationToken = default)
    {
        if (!string.IsNullOrWhiteSpace(search))
        {
            var searchPath = $"/search?q={Uri.EscapeDataString(search)}&media_root={Uri.EscapeDataString(mediaRoot)}&limit={limit}&offset={offset}";
            return await GetAsync<MoviesResponseDto>(searchPath, cancellationToken);
        }

        var folderQuery = string.IsNullOrWhiteSpace(folder) ? "" : $"&folder={Uri.EscapeDataString(folder)}";
        var path = $"/movies?media_root={Uri.EscapeDataString(mediaRoot)}{folderQuery}&sort={Uri.EscapeDataString(sort)}&limit={limit}&offset={offset}";
        return await GetAsync<MoviesResponseDto>(path, cancellationToken);
    }

    public async Task<MoviesResponseDto> GetRecentWatchedAsync(string mediaRoot, int limit, int offset, CancellationToken cancellationToken = default)
        => await GetAsync<MoviesResponseDto>($"/recent-watched?media_root={Uri.EscapeDataString(mediaRoot)}&limit={limit}&offset={offset}", cancellationToken);

    public async Task<MoviesResponseDto> GetFavoritesAsync(string mediaRoot, string sort, int limit, int offset, CancellationToken cancellationToken = default)
        => await GetAsync<MoviesResponseDto>($"/favorites?media_root={Uri.EscapeDataString(mediaRoot)}&sort={Uri.EscapeDataString(sort)}&limit={limit}&offset={offset}", cancellationToken);

    public async Task<FolderSpecialsResponseDto> GetFolderSpecialsAsync(
        string folder,
        string mediaRoot,
        bool includeMovies = false,
        CancellationToken cancellationToken = default)
    {
        var include = includeMovies ? "&include_movies=1" : "";
        return await GetAsync<FolderSpecialsResponseDto>(
            $"/folder/specials?folder={Uri.EscapeDataString(folder)}&media_root={Uri.EscapeDataString(mediaRoot)}{include}",
            cancellationToken);
    }

    public async Task<FolderSpecialsResponseDto> SetFolderSpecialsAsync(
        string folder,
        string mediaRoot,
        bool showSpecials,
        CancellationToken cancellationToken = default)
        => await PostJsonAsync<FolderSpecialsResponseDto>("/folder/specials", new
        {
            folder,
            media_root = mediaRoot,
            show_specials = showSpecials,
        }, cancellationToken);

    public async Task<SearchScrapeResponseDto> SearchScrapeAsync(
        string query,
        string scraper,
        string mediaRoot,
        CancellationToken cancellationToken = default)
        => await PostJsonAsync<SearchScrapeResponseDto>("/search-scrape", new
        {
            query,
            scraper = NormalizeManualScraper(scraper),
            media_root = mediaRoot,
        }, cancellationToken);

    public async Task<ManualScrapeResultDto> ManualScrapeMovieAsync(
        int movieId,
        string query,
        string sourceId,
        string mediaType,
        string scraper,
        CancellationToken cancellationToken = default)
        => await PostJsonAsync<ManualScrapeResultDto>($"/movies/{movieId}/manual-scrape", new
        {
            query,
            source_id = sourceId,
            media_type = string.IsNullOrWhiteSpace(mediaType) ? "movie" : mediaType,
            scraper = NormalizeManualScraper(scraper),
        }, cancellationToken);

    public async Task<BasicActionResultDto> RescrapeMovieAsync(int movieId, CancellationToken cancellationToken = default)
        => await PostJsonAsync<BasicActionResultDto>($"/movies/{movieId}/rescrape", new { }, cancellationToken);

    public async Task<BasicActionResultDto> RescrapeFolderAsync(
        string folder,
        string mediaRoot,
        CancellationToken cancellationToken = default)
        => await PostJsonAsync<BasicActionResultDto>("/rescrape-folder", new
        {
            folder,
            media_root = mediaRoot,
        }, cancellationToken);

    public async Task<BasicActionResultDto> ApplyFolderScrapeAsync(
        string folder,
        string mediaRoot,
        string sourceId,
        string source,
        string mediaType,
        CancellationToken cancellationToken = default)
        => await PostJsonAsync<BasicActionResultDto>("/apply-folder-scrape", new
        {
            folder,
            media_root = mediaRoot,
            source_id = sourceId,
            source,
            media_type = string.IsNullOrWhiteSpace(mediaType) ? "movie" : mediaType,
        }, cancellationToken);

    public async Task<AlternativeCoversResponseDto> GetAlternativeCoversAsync(int movieId, CancellationToken cancellationToken = default)
        => await GetAsync<AlternativeCoversResponseDto>($"/movies/{movieId}/alternative-covers", cancellationToken);

    public async Task<BasicActionResultDto> ChangeMovieCoverAsync(int movieId, string url, CancellationToken cancellationToken = default)
        => await PostJsonAsync<BasicActionResultDto>($"/movies/{movieId}/cover", new { url }, cancellationToken);

    public async Task<BasicActionResultDto> UploadMovieCoverAsync(int movieId, string filePath, CancellationToken cancellationToken = default)
    {
        await using var stream = File.OpenRead(filePath);
        using var request = CreateRequest(HttpMethod.Post, $"/movies/{movieId}/cover");
        using var content = new MultipartFormDataContent();
        content.Add(new StreamContent(stream), "file", Path.GetFileName(filePath));
        request.Content = content;
        return await SendAsync<BasicActionResultDto>(request, cancellationToken);
    }

    public async Task<BasicActionResultDto> ChangeFolderCoverAsync(
        string folder,
        string mediaRoot,
        string url,
        CancellationToken cancellationToken = default)
        => await PostJsonAsync<BasicActionResultDto>("/folder/cover", new
        {
            folder,
            media_root = mediaRoot,
            url,
        }, cancellationToken);

    public async Task<BasicActionResultDto> EditMovieAsync(
        int movieId,
        string title,
        string code,
        string actress,
        string releaseDate,
        int? duration,
        CancellationToken cancellationToken = default)
    {
        var body = new Dictionary<string, object?>();
        PutIfNotNull(body, "title", title);
        PutIfNotNull(body, "code", code);
        PutIfNotNull(body, "actress", actress);
        PutIfNotNull(body, "release_date", releaseDate);
        if (duration.HasValue)
        {
            body["duration"] = duration.Value;
        }

        if (body.Count == 0)
        {
            return new BasicActionResultDto { Ok = true };
        }

        return await PutJsonAsync<BasicActionResultDto>($"/movies/{movieId}", body, cancellationToken);
    }

    public async Task<BasicActionResultDto> EditFolderAsync(
        string folder,
        string mediaRoot,
        string title,
        string code,
        string actress,
        string releaseDate,
        int? duration,
        CancellationToken cancellationToken = default)
    {
        var fields = new Dictionary<string, object?>();
        PutIfNotNull(fields, "title", title);
        PutIfNotNull(fields, "code", code);
        PutIfNotNull(fields, "actress", actress);
        PutIfNotNull(fields, "release_date", releaseDate);
        if (duration.HasValue)
        {
            fields["duration"] = duration.Value;
        }

        if (fields.Count == 0)
        {
            return new BasicActionResultDto { Ok = true };
        }

        return await PutJsonAsync<BasicActionResultDto>("/folder/edit", new
        {
            folder,
            media_root = mediaRoot,
            fields,
        }, cancellationToken);
    }

    public async Task<BasicActionResultDto> DeleteMovieAsync(int movieId, CancellationToken cancellationToken = default)
        => await DeleteAsync<BasicActionResultDto>($"/movies/{movieId}", cancellationToken);

    public async Task<BasicActionResultDto> DeleteFolderAsync(string folder, string mediaRoot, CancellationToken cancellationToken = default)
        => await PostJsonAsync<BasicActionResultDto>("/folder/delete", new
        {
            folder,
            media_root = mediaRoot,
        }, cancellationToken);

    public async Task AddTagAsync(int movieId, string tag, CancellationToken cancellationToken = default)
        => await PostJsonAsync<JsonElement>($"/movies/{movieId}/tags", new { tag }, cancellationToken);

    public async Task RemoveTagAsync(int movieId, string tag, CancellationToken cancellationToken = default)
        => await DeleteAsync<JsonElement>($"/movies/{movieId}/tags/{Uri.EscapeDataString(tag)}", cancellationToken);

    public async Task<MovieDto> GetMovieDetailAsync(int movieId, CancellationToken cancellationToken = default)
        => await GetAsync<MovieDto>($"/detail/{movieId}", cancellationToken);

    public async Task<ProgressDto> GetProgressAsync(int movieId, CancellationToken cancellationToken = default)
        => await GetAsync<ProgressDto>($"/progress/{movieId}", cancellationToken);

    public async Task<ProgressDto> SaveProgressAsync(int movieId, double position, double? duration, bool stopped, CancellationToken cancellationToken = default)
        => await PostJsonAsync<ProgressDto>($"/progress/{movieId}", new { position, duration, stopped }, cancellationToken);

    public async Task<VersionInfoDto> GetVersionAsync(CancellationToken cancellationToken = default)
        => await GetAsync<VersionInfoDto>("/version", cancellationToken);

    public async Task<UpdateCheckResultDto> CheckForUpdatesAsync(CancellationToken cancellationToken = default)
        => await GetAsync<UpdateCheckResultDto>("/update/check", cancellationToken);

    public async Task<UpdateStatusDto> GetUpdateStatusAsync(CancellationToken cancellationToken = default)
        => await GetAsync<UpdateStatusDto>("/update/status", cancellationToken);

    public async Task<UpdateActionResultDto> PerformUpdateAsync(string version, string mode = "app-package", CancellationToken cancellationToken = default)
        => await PostJsonAsync<UpdateActionResultDto>("/update/perform", new { version, mode }, cancellationToken);

    public async Task<UpdateActionResultDto> RollbackUpdateAsync(CancellationToken cancellationToken = default)
        => await PostJsonAsync<UpdateActionResultDto>("/update/rollback", new { }, cancellationToken);

    public async Task<ChangelogDto> GetChangelogAsync(string version, CancellationToken cancellationToken = default)
        => await GetAsync<ChangelogDto>($"/update/changelog?version={Uri.EscapeDataString(version)}", cancellationToken);

    public Uri BuildBackupUri(string backupType)
        => new(BackendUri, $"api/backup?backup_type={Uri.EscapeDataString(backupType)}");

    public async Task<byte[]> DownloadBackupAsync(string backupType, CancellationToken cancellationToken = default)
    {
        using var request = CreateRequest(HttpMethod.Get, $"/backup?backup_type={Uri.EscapeDataString(backupType)}");
        using var response = await _httpClient.SendAsync(request, cancellationToken);
        if (response.StatusCode == HttpStatusCode.Unauthorized)
        {
            throw new UnauthorizedAccessException("MediaTree session is not authorized.");
        }

        if (!response.IsSuccessStatusCode)
        {
            var body = await response.Content.ReadAsStringAsync(cancellationToken);
            throw new InvalidOperationException($"MediaTree API failed ({(int)response.StatusCode}): {body}");
        }

        return await response.Content.ReadAsByteArrayAsync(cancellationToken);
    }

    public async Task RestoreBackupAsync(string filePath, CancellationToken cancellationToken = default)
    {
        await using var stream = File.OpenRead(filePath);
        using var request = CreateRequest(HttpMethod.Post, "/restore/upload");
        using var content = new MultipartFormDataContent();
        content.Add(new StreamContent(stream), "file", Path.GetFileName(filePath));
        request.Content = content;
        await SendAsync<JsonElement>(request, cancellationToken);
    }

    public async Task<string> EnsureMediaTokenAsync(CancellationToken cancellationToken = default)
    {
        var now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        if (!string.IsNullOrWhiteSpace(_mediaToken) && _mediaTokenExpiresAt > now + 60)
        {
            return _mediaToken;
        }

        var response = await PostJsonAsync<MediaTokenResponseDto>("/media-token", new { }, cancellationToken);
        _mediaToken = response.Token;
        _mediaTokenExpiresAt = response.ExpiresAt;
        return _mediaToken;
    }

    public async Task<string> BuildCoverUrlAsync(int movieId, CancellationToken cancellationToken = default)
    {
        var token = await EnsureMediaTokenAsync(cancellationToken);
        return new Uri(BackendUri, $"api/cover/{movieId}?token={Uri.EscapeDataString(token)}").ToString();
    }

    public async Task<string> BuildEpisodeStillUrlAsync(int movieId, CancellationToken cancellationToken = default)
    {
        var token = await EnsureMediaTokenAsync(cancellationToken);
        return new Uri(BackendUri, $"api/episode-still/{movieId}?token={Uri.EscapeDataString(token)}").ToString();
    }

    public async Task<string> BuildMediaAssetUrlAsync(string source, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(source))
        {
            return "";
        }

        if (Uri.TryCreate(source, UriKind.Absolute, out var absoluteUri))
        {
            return absoluteUri.ToString();
        }

        if (source.StartsWith("/api/", StringComparison.OrdinalIgnoreCase))
        {
            var token = await EnsureMediaTokenAsync(cancellationToken);
            var separator = source.Contains('?') ? "&" : "?";
            return new Uri(BackendUri, $"{source.TrimStart('/')}{separator}token={Uri.EscapeDataString(token)}").ToString();
        }

        var tokenForMedia = await EnsureMediaTokenAsync(cancellationToken);
        var normalized = source.Replace("\\", "/").TrimStart('/');
        var encoded = string.Join("/", normalized.Split('/').Select(Uri.EscapeDataString));
        return new Uri(BackendUri, $"api/media/{encoded}?token={Uri.EscapeDataString(tokenForMedia)}").ToString();
    }

    public async Task<string> BuildStreamUrlAsync(int movieId, CancellationToken cancellationToken = default)
    {
        var token = await EnsureMediaTokenAsync(cancellationToken);
        return new Uri(BackendUri, $"api/stream/{movieId}?token={Uri.EscapeDataString(token)}").ToString();
    }

    private async Task<T> GetAsync<T>(string path, CancellationToken cancellationToken)
    {
        using var request = CreateRequest(HttpMethod.Get, path);
        return await SendAsync<T>(request, cancellationToken);
    }

    private async Task<T> PostJsonAsync<T>(string path, object body, CancellationToken cancellationToken)
    {
        using var request = CreateRequest(HttpMethod.Post, path);
        request.Content = JsonContent.Create(body, options: _jsonOptions);
        return await SendAsync<T>(request, cancellationToken);
    }

    private async Task<T> PutJsonAsync<T>(string path, object body, CancellationToken cancellationToken)
    {
        using var request = CreateRequest(HttpMethod.Put, path);
        request.Content = JsonContent.Create(body, options: _jsonOptions);
        return await SendAsync<T>(request, cancellationToken);
    }

    private async Task<T> DeleteAsync<T>(string path, CancellationToken cancellationToken)
    {
        using var request = CreateRequest(HttpMethod.Delete, path);
        return await SendAsync<T>(request, cancellationToken);
    }

    private static string NormalizeTmdbAccessToken(string accessToken)
    {
        var value = (accessToken ?? "").Trim();
        return value.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase) ? value[7..].Trim() : value;
    }

    private static string NormalizeManualScraper(string scraper)
    {
        var value = (scraper ?? "").Trim().ToLowerInvariant();
        return value switch
        {
            "tmdb" => "tmdb_movie",
            "auto" or "tmdb_movie" or "tmdb_tv" or "tmdb_collection" or "bangumi" or "javdatabase" => value,
            _ => "auto",
        };
    }

    private static void PutIfNotNull(Dictionary<string, object?> body, string key, string value)
    {
        if (!string.IsNullOrWhiteSpace(value))
        {
            body[key] = value.Trim();
        }
    }

    private HttpRequestMessage CreateRequest(HttpMethod method, string path)
    {
        var normalized = path.TrimStart('/');
        var apiBase = new Uri(BackendUri, "api/");
        var request = new HttpRequestMessage(method, new Uri(apiBase, normalized));
        if (!string.IsNullOrWhiteSpace(_token))
        {
            request.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", _token);
        }

        return request;
    }

    private async Task<T> SendAsync<T>(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        using var response = await _httpClient.SendAsync(request, cancellationToken);
        if (response.StatusCode == HttpStatusCode.Unauthorized)
        {
            throw new UnauthorizedAccessException("MediaTree session is not authorized.");
        }

        if (!response.IsSuccessStatusCode)
        {
            var body = await response.Content.ReadAsStringAsync(cancellationToken);
            throw new InvalidOperationException($"MediaTree API failed ({(int)response.StatusCode}): {body}");
        }

        if (typeof(T) == typeof(JsonElement))
        {
            var element = await response.Content.ReadFromJsonAsync<JsonElement>(_jsonOptions, cancellationToken);
            return (T)(object)element;
        }

        var result = await response.Content.ReadFromJsonAsync<T>(_jsonOptions, cancellationToken);
        return result ?? throw new InvalidDataException($"MediaTree API returned an empty {typeof(T).Name} response.");
    }

    public void Dispose()
    {
        _httpClient.Dispose();
    }
}
