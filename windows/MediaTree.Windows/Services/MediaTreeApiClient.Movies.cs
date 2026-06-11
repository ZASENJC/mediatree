using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.Services;

public sealed partial class MediaTreeApiClient
{
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
}
