using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using MediaTree.Windows.Models;
using MediaTree.Windows.Platform;
using MediaTree.Windows.Services;

namespace MediaTree.Windows.Providers.Jellyfin;

public sealed class JellyfinCompatibleApiClient : IMediaApiClient
{
    private const long TicksPerSecond = 10_000_000;
    private const string MediaItemTypes = "Movie,Episode,Video";
    private const string FolderItemTypes = "Folder,Movie,Series,Season,Episode,BoxSet,Video,MusicVideo";
    private const string ItemFields = "Overview,People,Genres,DateCreated,PremiereDate,RuntimeTicks,UserData,SeriesName,SeasonName,IndexNumber,ParentIndexNumber,Path,ChildCount,CollectionType";
    private readonly HttpClient _httpClient;
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };
    private readonly Dictionary<string, int> _localIdsByExternalId = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<int, string> _externalIdsByLocalId = [];
    private readonly Dictionary<int, MovieDto> _moviesByLocalId = [];
    private readonly Dictionary<string, string> _containerIdsByPath = new(StringComparer.OrdinalIgnoreCase);
    private int _nextLocalId = 1;
    private string _token = "";
    private string _userId = "";

    public JellyfinCompatibleApiClient(Uri endpoint, MediaSourceKind kind)
    {
        if (kind is not (MediaSourceKind.Jellyfin or MediaSourceKind.Emby))
        {
            throw new ArgumentException("Jellyfin compatible API client requires a Jellyfin or Emby source kind.", nameof(kind));
        }

        BackendUri = NormalizeEndpoint(endpoint);
        Kind = kind;
        _httpClient = new HttpClient
        {
            Timeout = TimeSpan.FromMinutes(10),
        };
    }

    public Uri BackendUri { get; private set; }

    public MediaSourceKind Kind { get; }

    public void SetBackendUri(Uri backendUri)
    {
        BackendUri = NormalizeEndpoint(backendUri);
    }

    public void SetBearerToken(string token)
    {
        _token = token ?? "";
    }

    public void SetUserId(string userId)
    {
        _userId = userId ?? "";
    }

    public Task<AuthStatusDto> GetAuthStatusAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(new AuthStatusDto { AuthConfigured = true, NeedAuth = true });

    public async Task<AuthResponseDto> LoginAsync(string username, string password, CancellationToken cancellationToken = default)
    {
        var response = await AuthenticateByNameAsync(username, password, cancellationToken);
        SetBearerToken(response.AccessToken);
        SetUserId(response.User?.Id ?? "");
        return new AuthResponseDto { Ok = true, Token = response.AccessToken };
    }

    public Task<AuthResponseDto> SetupAuthAsync(string username, string password, CancellationToken cancellationToken = default)
        => LoginAsync(username, password, cancellationToken);

    public Task ChangePasswordAsync(string oldUsername, string oldPassword, string newUsername, string newPassword, CancellationToken cancellationToken = default)
        => throw Unsupported("修改账号密码");

    public async Task<SetupStatusDto> GetSetupStatusAsync(CancellationToken cancellationToken = default)
    {
        var roots = await GetMediaRootsAsync(cancellationToken);
        return new SetupStatusDto
        {
            NeedsSetup = roots.Items.Count == 0,
            Roots = roots.Items.Select(root => root.Path).ToList(),
        };
    }

    public async Task<MediaRootsResponseDto> GetMediaRootsAsync(CancellationToken cancellationToken = default)
    {
        var userId = RequireUserId();
        var response = await GetAsync<JellyfinItemsResponse>($"/Users/{EscapePath(userId)}/Views", cancellationToken);
        var roots = response.Items
            .Where(item => !string.IsNullOrWhiteSpace(item.Id))
            .Where(item => !string.IsNullOrWhiteSpace(item.Name))
            .Select(item => new MediaRootDto
            {
                Path = item.Id,
                Label = item.Name,
                MovieCount = item.ChildCount ?? 0,
                Scraper = "none",
            })
            .ToList();
        foreach (var root in roots)
        {
            _containerIdsByPath[root.Path] = root.Path;
        }

        return new MediaRootsResponseDto
        {
            Items = roots,
        };
    }

    public async Task<List<LibrarySettingDto>> GetLibrarySettingsAsync(CancellationToken cancellationToken = default)
    {
        var roots = await GetMediaRootsAsync(cancellationToken);
        return roots.Items
            .Select(root => new LibrarySettingDto
            {
                MediaRoot = root.Path,
                Scraper = "none",
                Enabled = 1,
            })
            .ToList();
    }

    public async Task<FoldersResponseDto> GetFoldersAsync(string mediaRoot = "", CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(mediaRoot))
        {
            var roots = await GetMediaRootsAsync(cancellationToken);
            return new FoldersResponseDto
            {
                Tree = roots.Items.Select(root => new FolderNodeDto
                {
                    Name = root.Label,
                    DisplayTitle = root.Label,
                    Path = root.Path,
                    MediaRoot = root.Path,
                    MovieCount = root.MovieCount,
                    IsLeaf = false,
                }).ToList(),
            };
        }

        var userId = RequireUserId();
        var parentId = ResolveContainerId(mediaRoot);
        var path = $"/Users/{EscapePath(userId)}/Items?{Query(
            ("ParentId", parentId),
            ("IncludeItemTypes", FolderItemTypes),
            ("Recursive", "false"),
            ("Fields", ItemFields),
            ("Limit", "200"))}";
        var response = await GetAsync<JellyfinItemsResponse>(path, cancellationToken);
        return new FoldersResponseDto
        {
            Tree = response.Items
                .Where(item => !string.IsNullOrWhiteSpace(item.Id))
                .Select(item => MapFolder(item, mediaRoot))
                .ToList(),
        };
    }

    public Task SaveLibrarySettingAsync(LibrarySettingDto setting, CancellationToken cancellationToken = default)
        => Task.FromException(Unsupported("保存媒体库设置"));

    public Task SetLibraryPasswordAsync(string mediaRoot, string password, CancellationToken cancellationToken = default)
        => Task.FromException(Unsupported("设置媒体库密码"));

    public Task ScanAsync(string mediaRoot, CancellationToken cancellationToken = default)
        => Task.FromException(Unsupported("扫描媒体库"));

    public Task ClearLibraryAsync(string mediaRoot, CancellationToken cancellationToken = default)
        => Task.FromException(Unsupported("清空媒体库"));

    public Task<ScanStatusDto> GetScanStatusAsync(string mediaRoot, CancellationToken cancellationToken = default)
        => Task.FromResult(new ScanStatusDto { MediaRoot = mediaRoot, Status = "disabled", Done = 0, Total = 0 });

    public Task<ScanLogDto> GetScanLogAsync(string mediaRoot, int lines = 80, CancellationToken cancellationToken = default)
        => Task.FromResult(new ScanLogDto());

    public Task<ConfigDto> GetConfigAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(new ConfigDto
        {
            ExtraMediaRoots = [],
            JavdbEnabled = false,
            UpdateCheckEnabled = false,
        });

    public Task SaveConfigAsync(IEnumerable<string> extraMediaRoots, CancellationToken cancellationToken = default)
        => Task.FromException(Unsupported("保存本机目录配置"));

    public Task SaveTmdbConfigAsync(string accessToken, CancellationToken cancellationToken = default)
        => Task.FromException(Unsupported("保存 TMDB 配置"));

    public Task SaveGlobalConfigAsync(ConfigDto config, CancellationToken cancellationToken = default)
        => Task.FromException(Unsupported("保存全局配置"));

    public Uri BuildBackupUri(string backupType)
        => new(BackendUri, "web/index.html");

    public Task<byte[]> DownloadBackupAsync(string backupType, CancellationToken cancellationToken = default)
        => throw Unsupported("备份下载");

    public Task RestoreBackupAsync(string filePath, CancellationToken cancellationToken = default)
        => throw Unsupported("备份恢复");

    public async Task<MoviesResponseDto> GetMoviesAsync(
        string mediaRoot,
        string folder,
        string search,
        string sort,
        int limit,
        int offset,
        CancellationToken cancellationToken = default)
    {
        var parentId = ResolveContainerId(string.IsNullOrWhiteSpace(folder) ? mediaRoot : folder);
        var response = await FetchItemsAsync(
            parentId,
            search,
            sort,
            Math.Max(0, limit),
            Math.Max(0, offset),
            filters: "",
            isPlayed: null,
            cancellationToken);
        return MapMovies(response, mediaRoot);
    }

    public async Task<MoviesResponseDto> GetRecentWatchedAsync(string mediaRoot, int limit, int offset, CancellationToken cancellationToken = default)
    {
        var response = await FetchItemsAsync(
            ResolveContainerId(mediaRoot),
            search: "",
            sort: "date_played_desc",
            limit: Math.Max(0, limit),
            offset: Math.Max(0, offset),
            filters: "IsResumable",
            isPlayed: null,
            cancellationToken);
        return MapMovies(response, mediaRoot);
    }

    public async Task<MoviesResponseDto> GetFavoritesAsync(string mediaRoot, string sort, int limit, int offset, CancellationToken cancellationToken = default)
    {
        var response = await FetchItemsAsync(
            ResolveContainerId(mediaRoot),
            search: "",
            sort,
            limit: Math.Max(0, limit),
            offset: Math.Max(0, offset),
            filters: "IsFavorite",
            isPlayed: null,
            cancellationToken);
        return MapMovies(response, mediaRoot);
    }

    public Task<FolderSpecialsResponseDto> GetFolderSpecialsAsync(string folder, string mediaRoot, bool includeMovies = false, CancellationToken cancellationToken = default)
        => Task.FromResult(new FolderSpecialsResponseDto());

    public Task<FolderSpecialsResponseDto> SetFolderSpecialsAsync(string folder, string mediaRoot, bool showSpecials, CancellationToken cancellationToken = default)
        => Task.FromResult(new FolderSpecialsResponseDto());

    public Task<SearchScrapeResponseDto> SearchScrapeAsync(string query, string scraper, string mediaRoot, CancellationToken cancellationToken = default)
        => Task.FromResult(new SearchScrapeResponseDto());

    public Task<ManualScrapeResultDto> ManualScrapeMovieAsync(int movieId, string query, string sourceId, string mediaType, string scraper, CancellationToken cancellationToken = default)
        => throw Unsupported("手动刮削");

    public Task<BasicActionResultDto> RescrapeMovieAsync(int movieId, CancellationToken cancellationToken = default)
        => throw Unsupported("重新刮削");

    public Task<BasicActionResultDto> RescrapeFolderAsync(string folder, string mediaRoot, CancellationToken cancellationToken = default)
        => throw Unsupported("重新刮削目录");

    public Task<BasicActionResultDto> ApplyFolderScrapeAsync(string folder, string mediaRoot, string sourceId, string source, string mediaType, CancellationToken cancellationToken = default)
        => throw Unsupported("应用目录刮削结果");

    public Task<AlternativeCoversResponseDto> GetAlternativeCoversAsync(int movieId, CancellationToken cancellationToken = default)
        => Task.FromResult(new AlternativeCoversResponseDto());

    public Task<BasicActionResultDto> ChangeMovieCoverAsync(int movieId, string url, CancellationToken cancellationToken = default)
        => throw Unsupported("更换封面");

    public Task<BasicActionResultDto> UploadMovieCoverAsync(int movieId, string filePath, CancellationToken cancellationToken = default)
        => throw Unsupported("上传封面");

    public Task<BasicActionResultDto> ChangeFolderCoverAsync(string folder, string mediaRoot, string url, CancellationToken cancellationToken = default)
        => throw Unsupported("更换目录封面");

    public Task<BasicActionResultDto> EditMovieAsync(int movieId, string title, string code, string actress, string releaseDate, int? duration, CancellationToken cancellationToken = default)
        => throw Unsupported("编辑影片信息");

    public Task<BasicActionResultDto> EditFolderAsync(string folder, string mediaRoot, string title, string code, string actress, string releaseDate, int? duration, CancellationToken cancellationToken = default)
        => throw Unsupported("编辑目录信息");

    public Task<BasicActionResultDto> DeleteMovieAsync(int movieId, CancellationToken cancellationToken = default)
        => throw Unsupported("删除影片");

    public Task<BasicActionResultDto> DeleteFolderAsync(string folder, string mediaRoot, CancellationToken cancellationToken = default)
        => throw Unsupported("删除目录");

    public async Task AddTagAsync(int movieId, string tag, CancellationToken cancellationToken = default)
    {
        var normalized = NormalizeTag(tag);
        if (normalized is not ("favorite" or "watched"))
        {
            return;
        }

        var userId = RequireUserId();
        var externalId = ResolveExternalId(movieId);
        var path = normalized == "favorite"
            ? $"/Users/{EscapePath(userId)}/FavoriteItems/{EscapePath(externalId)}"
            : $"/Users/{EscapePath(userId)}/PlayedItems/{EscapePath(externalId)}";
        await SendNoContentAsync(CreateRequest(HttpMethod.Post, path), cancellationToken);
        if (_moviesByLocalId.TryGetValue(movieId, out var movie) && !movie.Tags.Contains(normalized, StringComparer.OrdinalIgnoreCase))
        {
            movie.Tags.Add(normalized);
        }
    }

    public async Task RemoveTagAsync(int movieId, string tag, CancellationToken cancellationToken = default)
    {
        var normalized = NormalizeTag(tag);
        if (normalized is not ("favorite" or "watched"))
        {
            return;
        }

        var userId = RequireUserId();
        var externalId = ResolveExternalId(movieId);
        var path = normalized == "favorite"
            ? $"/Users/{EscapePath(userId)}/FavoriteItems/{EscapePath(externalId)}"
            : $"/Users/{EscapePath(userId)}/PlayedItems/{EscapePath(externalId)}";
        await SendNoContentAsync(CreateRequest(HttpMethod.Delete, path), cancellationToken);
        if (_moviesByLocalId.TryGetValue(movieId, out var movie))
        {
            movie.Tags.RemoveAll(value => string.Equals(value, normalized, StringComparison.OrdinalIgnoreCase));
        }
    }

    public async Task<MovieDto> GetMovieDetailAsync(int movieId, CancellationToken cancellationToken = default)
    {
        var userId = RequireUserId();
        var externalId = ResolveExternalId(movieId);
        var item = await GetAsync<JellyfinItemDto>($"/Users/{EscapePath(userId)}/Items/{EscapePath(externalId)}", cancellationToken);
        var mediaRoot = _moviesByLocalId.TryGetValue(movieId, out var cached) ? cached.MediaRoot : "";
        return MapItem(item, mediaRoot);
    }

    public async Task<ProgressDto> GetProgressAsync(int movieId, CancellationToken cancellationToken = default)
    {
        if (!_moviesByLocalId.TryGetValue(movieId, out var movie))
        {
            movie = await GetMovieDetailAsync(movieId, cancellationToken);
        }

        return new ProgressDto
        {
            Position = movie.PlaybackPosition,
            ProgressPercent = movie.ProgressPercent,
            Played = IsWatched(movie),
        };
    }

    public async Task<ProgressDto> SaveProgressAsync(int movieId, double position, double? duration, bool stopped, CancellationToken cancellationToken = default)
    {
        var userId = RequireUserId();
        var externalId = ResolveExternalId(movieId);
        using var request = CreateProgressRequest(userId, externalId, position);
        await SendNoContentAsync(request, cancellationToken);

        var durationSeconds = duration.GetValueOrDefault();
        var progressPercent = durationSeconds > 0
            ? Math.Clamp(Math.Max(0, position) / durationSeconds * 100, 0, 100)
            : 0;
        if (_moviesByLocalId.TryGetValue(movieId, out var movie))
        {
            movie.PlaybackPosition = Math.Max(0, position);
            movie.ProgressPercent = progressPercent;
        }

        return new ProgressDto
        {
            Position = Math.Max(0, position),
            ProgressPercent = progressPercent,
            Played = progressPercent >= 90,
        };
    }

    public Task<string> EnsureMediaTokenAsync(CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(_token))
        {
            throw new UnauthorizedAccessException("Jellyfin compatible media source is not authorized.");
        }

        return Task.FromResult(_token);
    }

    public async Task<string> BuildCoverUrlAsync(int movieId, CancellationToken cancellationToken = default)
    {
        await EnsureMediaTokenAsync(cancellationToken);
        return await CacheImageAsync(new Uri(BuildImageUrl(ResolveExternalId(movieId), "Primary")), cancellationToken);
    }

    public async Task<string> BuildEpisodeStillUrlAsync(int movieId, CancellationToken cancellationToken = default)
    {
        await EnsureMediaTokenAsync(cancellationToken);
        return await CacheImageAsync(new Uri(BuildImageUrl(ResolveExternalId(movieId), "Primary")), cancellationToken);
    }

    public async Task<string> BuildMediaAssetUrlAsync(string source, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(source))
        {
            return "";
        }

        if (Uri.TryCreate(source, UriKind.Absolute, out var absolute))
        {
            if (!IsBackendUri(absolute) || string.Equals(absolute.Scheme, Uri.UriSchemeFile, StringComparison.OrdinalIgnoreCase))
            {
                return absolute.ToString();
            }

            return await CacheImageAsync(absolute, cancellationToken);
        }

        return await CacheImageAsync(new Uri(BackendUri, source.TrimStart('/')), cancellationToken);
    }

    public async Task<string> BuildStreamUrlAsync(int movieId, CancellationToken cancellationToken = default)
    {
        await EnsureMediaTokenAsync(cancellationToken);
        var externalId = ResolveExternalId(movieId);
        return new Uri(BackendUri, $"Videos/{EscapePath(externalId)}/stream?static=true").ToString();
    }

    public async Task<MediaPlaybackSource> BuildPlaybackSourceAsync(int movieId, CancellationToken cancellationToken = default)
        => new(await BuildStreamUrlAsync(movieId, cancellationToken), BuildAuthHeaders());

    public Task<VersionInfoDto> GetVersionAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(new VersionInfoDto
        {
            Version = Kind.ToString(),
            CurrentSource = Kind.ToString(),
            StatusNote = "外部媒体库由对应服务端管理。",
        });

    public Task<UpdateCheckResultDto> CheckForUpdatesAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(new UpdateCheckResultDto
        {
            CurrentVersion = Kind.ToString(),
            CurrentSource = Kind.ToString(),
            HasUpdate = false,
            StatusNote = "外部媒体库不使用 MediaTree 后端更新通道。",
            Versions = [],
        });

    public Task<UpdateStatusDto> GetUpdateStatusAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(new UpdateStatusDto
        {
            Status = "disabled",
            Message = "外部媒体库不使用 MediaTree 后端更新通道。",
        });

    public Task<UpdateActionResultDto> PerformUpdateAsync(string version, string mode = "app-package", CancellationToken cancellationToken = default)
        => Task.FromResult(new UpdateActionResultDto
        {
            Ok = false,
            Version = version,
            Error = "外部媒体库不支持 MediaTree 后端应用包更新。",
        });

    public Task<UpdateActionResultDto> RollbackUpdateAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(new UpdateActionResultDto
        {
            Ok = false,
            Error = "外部媒体库不支持 MediaTree 后端回滚。",
        });

    public Task<ChangelogDto> GetChangelogAsync(string version, CancellationToken cancellationToken = default)
        => Task.FromResult(new ChangelogDto
        {
            Version = version,
            Body = "",
        });

    public void Dispose()
    {
        _httpClient.Dispose();
    }

    private async Task<JellyfinAuthResponse> AuthenticateByNameAsync(string username, string password, CancellationToken cancellationToken)
    {
        using var request = CreateRequest(HttpMethod.Post, "/Users/AuthenticateByName");
        request.Content = JsonBody(new
        {
            Username = username,
            Pw = password,
        });

        var response = await SendAsync<JellyfinAuthResponse>(request, cancellationToken);
        if (string.IsNullOrWhiteSpace(response.AccessToken))
        {
            throw new InvalidDataException("Jellyfin compatible login response is missing AccessToken.");
        }

        if (string.IsNullOrWhiteSpace(response.User?.Id))
        {
            throw new InvalidDataException("Jellyfin compatible login response is missing User.Id.");
        }

        return response;
    }

    private async Task<JellyfinItemsResponse> FetchItemsAsync(
        string parentId,
        string search,
        string sort,
        int limit,
        int offset,
        string filters,
        bool? isPlayed,
        CancellationToken cancellationToken)
    {
        var userId = RequireUserId();
        var (sortBy, sortOrder) = MapSort(sort);
        var query = new List<(string Key, string? Value)>
        {
            ("ParentId", parentId),
            ("IncludeItemTypes", MediaItemTypes),
            ("Recursive", "true"),
            ("SearchTerm", search ?? ""),
            ("SortBy", sortBy),
            ("SortOrder", sortOrder),
            ("StartIndex", offset.ToString(CultureInfo.InvariantCulture)),
            ("Limit", limit.ToString(CultureInfo.InvariantCulture)),
            ("Fields", ItemFields),
        };
        if (!string.IsNullOrWhiteSpace(filters))
        {
            query.Add(("Filters", filters));
        }

        if (isPlayed.HasValue)
        {
            query.Add(("IsPlayed", isPlayed.Value ? "true" : "false"));
        }

        var path = $"/Users/{EscapePath(userId)}/Items?{Query(query.ToArray())}";
        return await GetAsync<JellyfinItemsResponse>(path, cancellationToken);
    }

    private MoviesResponseDto MapMovies(JellyfinItemsResponse response, string mediaRoot)
    {
        var movies = response.Items
            .Where(IsPlayableItem)
            .Select(item => MapItem(item, mediaRoot))
            .ToList();
        return new MoviesResponseDto
        {
            Movies = movies,
            Total = response.TotalRecordCount > 0 ? response.TotalRecordCount : movies.Count,
        };
    }

    private FolderNodeDto MapFolder(JellyfinItemDto item, string mediaRoot)
    {
        var path = item.Id;
        _containerIdsByPath[path] = item.Id;
        if (IsPlayableItem(item))
        {
            var movie = MapItem(item, mediaRoot);
            return new FolderNodeDto
            {
                Name = item.Name,
                DisplayTitle = item.Name,
                Path = path,
                MediaRoot = mediaRoot,
                MovieCount = 1,
                MovieId = movie.Id,
                Cover = BuildImageUrl(item.Id, "Primary"),
                RandomCover = BuildImageUrl(item.Id, "Primary"),
                IsLeaf = true,
                CreatedMax = FormatDateTime(item.DateCreated),
                ReleaseDateMax = FormatDate(item.PremiereDate),
                ProgressPercent = movie.ProgressPercent,
                FolderWatched = IsWatched(movie),
            };
        }

        return new FolderNodeDto
        {
            Name = item.Name,
            DisplayTitle = item.Name,
            Path = path,
            MediaRoot = mediaRoot,
            MovieCount = item.ChildCount ?? 0,
            Cover = BuildImageUrl(item.Id, "Primary"),
            RandomCover = BuildImageUrl(item.Id, "Primary"),
            IsLeaf = item.ChildCount.GetValueOrDefault() <= 0,
            CreatedMax = FormatDateTime(item.DateCreated),
            ReleaseDateMax = FormatDate(item.PremiereDate),
        };
    }

    private MovieDto MapItem(JellyfinItemDto item, string mediaRoot)
    {
        if (string.IsNullOrWhiteSpace(item.Id))
        {
            throw new InvalidDataException("Jellyfin compatible item is missing Id.");
        }

        var localId = LocalIdFor(item.Id);
        var cachedRoot = _moviesByLocalId.TryGetValue(localId, out var cached) ? cached.MediaRoot : "";
        var effectiveMediaRoot = string.IsNullOrWhiteSpace(mediaRoot) ? cachedRoot : mediaRoot;
        var folderLevels = FolderLevelsFor(item);
        if (!string.IsNullOrWhiteSpace(folderLevels) && !string.IsNullOrWhiteSpace(item.ParentId))
        {
            _containerIdsByPath[folderLevels] = item.ParentId;
        }

        var movie = new MovieDto
        {
            Id = localId,
            Path = $"jellyfin-compatible://{EscapePath(item.Id)}",
            Code = item.ProductionYear?.ToString(CultureInfo.InvariantCulture) ?? "",
            Title = item.Name,
            DisplayTitle = item.Name,
            OriginalTitle = item.OriginalTitle ?? "",
            Overview = item.Overview ?? "",
            Actress = PeopleByKind(item.People, "Actor"),
            ReleaseDate = FormatDate(item.PremiereDate),
            CreatedAt = FormatDateTime(item.DateCreated),
            UpdatedAt = FormatDateTime(item.DateLastMediaAdded),
            Duration = TicksToSeconds(item.RunTimeTicks),
            MediaRoot = effectiveMediaRoot,
            Genre = string.Join(", ", item.Genres ?? []),
            ContentRating = item.OfficialRating ?? "",
            FolderLevels = folderLevels,
            TmdbType = string.Equals(item.Type, "Episode", StringComparison.OrdinalIgnoreCase) ? "tv" : "movie",
            TmdbSeason = item.ParentIndexNumber,
            TmdbEpisode = item.IndexNumber,
            EpisodeNumber = item.IndexNumber,
            EpisodeTitle = string.Equals(item.Type, "Episode", StringComparison.OrdinalIgnoreCase) ? item.Name : "",
            EpisodeStill = BuildImageUrl(item.Id, "Primary"),
            EpisodeLabel = EpisodeLabelFor(item),
            EpisodeOverview = item.Overview ?? "",
            CoverRemote = BuildImageUrl(item.Id, "Primary"),
            CoverLocal = "",
            ContentRole = "main",
            PlaybackPosition = TicksToSeconds(item.UserData?.PlaybackPositionTicks),
            ProgressPercent = item.UserData?.PlayedPercentage ?? 0,
            Tags = item.UserData?.IsFavorite == true ? ["favorite"] : [],
            Cast = StaffByKind(item.People, "Actor"),
            Crew = item.People is null ? [] : item.People.Where(person => !string.Equals(person.Type, "Actor", StringComparison.OrdinalIgnoreCase)).Select(MapStaff).ToList(),
        };
        if (item.UserData?.Played == true && !movie.Tags.Contains("watched", StringComparer.OrdinalIgnoreCase))
        {
            movie.Tags.Add("watched");
        }

        _moviesByLocalId[localId] = movie;
        return movie;
    }

    private int LocalIdFor(string externalId)
    {
        if (_localIdsByExternalId.TryGetValue(externalId, out var existing))
        {
            return existing;
        }

        var localId = _nextLocalId++;
        _localIdsByExternalId[externalId] = localId;
        _externalIdsByLocalId[localId] = externalId;
        return localId;
    }

    private string ResolveExternalId(int movieId)
    {
        return _externalIdsByLocalId.TryGetValue(movieId, out var externalId)
            ? externalId
            : throw new InvalidOperationException("影片来自当前媒体库列表后才能打开。");
    }

    private string ResolveContainerId(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        return _containerIdsByPath.TryGetValue(value, out var id) ? id : value;
    }

    private static bool IsPlayableItem(JellyfinItemDto item)
        => item.Type is "Movie" or "Episode" or "Video";

    private string BuildImageUrl(string externalId, string imageType)
        => new Uri(BackendUri, $"Items/{EscapePath(externalId)}/Images/{EscapePath(imageType)}").ToString();

    private string AppendQuery(string path, params (string Key, string? Value)[] values)
        => new Uri(BackendUri, $"{path.TrimStart('/')}?{Query(values)}").ToString();

    private static string AppendPathQuery(string path, params (string Key, string? Value)[] values)
        => $"{path}?{Query(values)}";

    private static string Query(params (string Key, string? Value)[] values)
        => string.Join("&", values
            .Where(item => item.Value is not null)
            .Select(item => $"{Uri.EscapeDataString(item.Key)}={Uri.EscapeDataString(item.Value ?? "")}"));

    private static (string SortBy, string SortOrder) MapSort(string sort)
        => (sort ?? "").Trim().ToLowerInvariant() switch
        {
            "created_asc" => ("DateCreated", "Ascending"),
            "name" => ("SortName", "Ascending"),
            "release_date_desc" => ("PremiereDate", "Descending"),
            "release_date_asc" => ("PremiereDate", "Ascending"),
            "random" => ("Random", "Ascending"),
            "date_played_desc" => ("DatePlayed", "Descending"),
            _ => ("DateCreated", "Descending"),
        };

    private string RequireUserId()
        => string.IsNullOrWhiteSpace(_userId)
            ? throw new UnauthorizedAccessException("Jellyfin compatible media source is not authorized.")
            : _userId;

    private static Uri NormalizeEndpoint(Uri endpoint)
    {
        ArgumentNullException.ThrowIfNull(endpoint);
        var text = endpoint.ToString();
        if (!text.EndsWith("/", StringComparison.Ordinal))
        {
            text += "/";
        }

        return new Uri(text);
    }

    private static string EscapePath(string value)
        => Uri.EscapeDataString(value ?? "");

    private HttpRequestMessage CreateRequest(HttpMethod method, string path)
        => CreateRequest(method, new Uri(BackendUri, path.TrimStart('/')));

    private HttpRequestMessage CreateRequest(HttpMethod method, Uri uri)
    {
        var request = new HttpRequestMessage(method, uri);
        foreach (var header in BuildAuthHeaders())
        {
            request.Headers.TryAddWithoutValidation(header.Key, header.Value);
        }

        return request;
    }

    private IReadOnlyDictionary<string, string> BuildAuthHeaders()
    {
        var headers = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var scheme = Kind == MediaSourceKind.Emby ? "Emby" : "MediaBrowser";
        var authorization = new StringBuilder(
            $"{scheme} Client=\"MediaTree Windows\", Device=\"Windows\", DeviceId=\"mediatree-windows\", Version=\"1.0\"");
        if (!string.IsNullOrWhiteSpace(_userId))
        {
            authorization.Append($", UserId=\"{HeaderValue(_userId)}\"");
        }

        if (!string.IsNullOrWhiteSpace(_token))
        {
            authorization.Append($", Token=\"{HeaderValue(_token)}\"");
            headers["X-Emby-Token"] = _token;
        }

        headers[Kind == MediaSourceKind.Emby ? "Authorization" : "X-Emby-Authorization"] = authorization.ToString();
        return headers;
    }

    private static string HeaderValue(string value)
        => value.Replace("\"", "", StringComparison.Ordinal);

    private async Task<string> CacheImageAsync(Uri uri, CancellationToken cancellationToken)
    {
        if (!IsBackendUri(uri))
        {
            return uri.ToString();
        }

        var cachePath = CachePathFor(uri);
        if (File.Exists(cachePath) && new FileInfo(cachePath).Length > 0)
        {
            return new Uri(cachePath).AbsoluteUri;
        }

        Directory.CreateDirectory(Path.GetDirectoryName(cachePath)!);
        using var request = CreateRequest(HttpMethod.Get, uri);
        using var response = await _httpClient.SendAsync(request, cancellationToken);
        if (response.StatusCode == HttpStatusCode.NotFound)
        {
            return "";
        }

        if (response.StatusCode == HttpStatusCode.Unauthorized)
        {
            throw new UnauthorizedAccessException($"{Kind} session is not authorized.");
        }

        if (!response.IsSuccessStatusCode)
        {
            var body = await response.Content.ReadAsStringAsync(cancellationToken);
            throw new InvalidOperationException($"{Kind} image request failed ({(int)response.StatusCode}): {body}");
        }

        await using var source = await response.Content.ReadAsStreamAsync(cancellationToken);
        await using var destination = File.Create(cachePath);
        await source.CopyToAsync(destination, cancellationToken);
        return new Uri(cachePath).AbsoluteUri;
    }

    private string CachePathFor(Uri uri)
    {
        var cacheDirectory = Path.Combine(
            AppPaths.WindowsStateDirectory,
            "media-source-cache",
            Kind.ToString().ToLowerInvariant());
        var hash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(uri.ToString()))).ToLowerInvariant();
        return Path.Combine(cacheDirectory, $"{hash}.jpg");
    }

    private bool IsBackendUri(Uri uri)
        => string.Equals(uri.Scheme, BackendUri.Scheme, StringComparison.OrdinalIgnoreCase)
            && string.Equals(uri.Host, BackendUri.Host, StringComparison.OrdinalIgnoreCase)
            && uri.Port == BackendUri.Port;

    private async Task<T> GetAsync<T>(string path, CancellationToken cancellationToken)
    {
        using var request = CreateRequest(HttpMethod.Get, path);
        return await SendAsync<T>(request, cancellationToken);
    }

    private async Task<T> SendAsync<T>(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        using var response = await _httpClient.SendAsync(request, cancellationToken);
        if (response.StatusCode == HttpStatusCode.Unauthorized)
        {
            throw new UnauthorizedAccessException($"{Kind} session is not authorized.");
        }

        if (!response.IsSuccessStatusCode)
        {
            var body = await response.Content.ReadAsStringAsync(cancellationToken);
            throw new InvalidOperationException($"{Kind} API failed ({(int)response.StatusCode}): {body}");
        }

        var result = await response.Content.ReadFromJsonAsync<T>(_jsonOptions, cancellationToken);
        return result ?? throw new InvalidDataException($"{Kind} API returned an empty {typeof(T).Name} response.");
    }

    private async Task SendNoContentAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        using (request)
        using (var response = await _httpClient.SendAsync(request, cancellationToken))
        {
            if (response.StatusCode == HttpStatusCode.Unauthorized)
            {
                throw new UnauthorizedAccessException($"{Kind} session is not authorized.");
            }

            if (!response.IsSuccessStatusCode)
            {
                var body = await response.Content.ReadAsStringAsync(cancellationToken);
                throw new InvalidOperationException($"{Kind} API failed ({(int)response.StatusCode}): {body}");
            }
        }
    }

    private StringContent JsonBody(object body)
        => new(JsonSerializer.Serialize(body, _jsonOptions), Encoding.UTF8, "application/json");

    private static double TicksToSeconds(long? ticks)
    {
        var value = ticks.GetValueOrDefault();
        return value <= 0 ? 0 : value / (double)TicksPerSecond;
    }

    private static long SecondsToTicks(double seconds)
        => (long)(Math.Max(0, seconds) * TicksPerSecond);

    private static string FormatDate(DateTimeOffset? value)
        => value.HasValue ? value.Value.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture) : "";

    private static string FormatDateTime(DateTimeOffset? value)
        => value.HasValue ? value.Value.ToString("O", CultureInfo.InvariantCulture) : "";

    private static string FolderLevelsFor(JellyfinItemDto item)
    {
        if (!string.IsNullOrWhiteSpace(item.SeriesName) && !string.IsNullOrWhiteSpace(item.SeasonName))
        {
            return $"{item.SeriesName}/{item.SeasonName}";
        }

        if (!string.IsNullOrWhiteSpace(item.SeriesName))
        {
            return item.SeriesName;
        }

        return item.ParentId ?? "";
    }

    private static string EpisodeLabelFor(JellyfinItemDto item)
    {
        if (item.ParentIndexNumber.HasValue && item.IndexNumber.HasValue)
        {
            return $"S{item.ParentIndexNumber.Value:00}E{item.IndexNumber.Value:00}";
        }

        return item.IndexNumber.HasValue ? $"E{item.IndexNumber.Value:00}" : "";
    }

    private static string PeopleByKind(List<JellyfinPersonDto>? people, string kind)
        => string.Join(", ", people?.Where(person => string.Equals(person.Type, kind, StringComparison.OrdinalIgnoreCase)).Select(person => person.Name).Where(name => !string.IsNullOrWhiteSpace(name)) ?? []);

    private static List<MovieStaffDto> StaffByKind(List<JellyfinPersonDto>? people, string kind)
        => people?
            .Where(person => string.Equals(person.Type, kind, StringComparison.OrdinalIgnoreCase))
            .Select(MapStaff)
            .ToList() ?? [];

    private static MovieStaffDto MapStaff(JellyfinPersonDto person)
        => new()
        {
            Name = person.Name ?? "",
            Role = person.Role ?? "",
            Job = person.Type ?? "",
            Source = "jellyfin-compatible",
        };

    private HttpRequestMessage CreateProgressRequest(string userId, string externalId, double position)
    {
        var positionTicks = SecondsToTicks(position).ToString(CultureInfo.InvariantCulture);
        if (Kind == MediaSourceKind.Emby)
        {
            return CreateRequest(
                HttpMethod.Post,
                AppendPathQuery(
                    $"/Users/{EscapePath(userId)}/PlayingItems/{EscapePath(externalId)}/Progress",
                    ("PositionTicks", positionTicks)));
        }

        return CreateRequest(
            HttpMethod.Post,
            AppendPathQuery(
                "/Sessions/Playing/Progress",
                ("ItemId", externalId),
                ("PositionTicks", positionTicks),
                ("IsPaused", "false"),
                ("EventName", "timeupdate")));
    }

    private static string NormalizeTag(string tag)
        => (tag ?? "").Trim().ToLowerInvariant();

    private static bool IsWatched(MovieDto movie)
        => movie.ProgressPercent >= 90 || movie.Tags.Contains("watched", StringComparer.OrdinalIgnoreCase);

    private Task<T> Unsupported<T>(string action)
        => Task.FromException<T>(Unsupported(action));

    private NotSupportedException Unsupported(string action)
        => new($"{Kind} 媒体源不支持 MediaTree 的{action}功能。");

    private sealed class JellyfinAuthResponse
    {
        public string AccessToken { get; set; } = "";

        public JellyfinUserDto? User { get; set; }
    }

    private sealed class JellyfinUserDto
    {
        public string Id { get; set; } = "";

        public string Name { get; set; } = "";
    }

    private sealed class JellyfinItemsResponse
    {
        public List<JellyfinItemDto> Items { get; set; } = [];

        public int TotalRecordCount { get; set; }
    }

    private sealed class JellyfinItemDto
    {
        public string Id { get; set; } = "";

        public string Name { get; set; } = "";

        public string? OriginalTitle { get; set; }

        public string Type { get; set; } = "";

        public string? Overview { get; set; }

        public string? Path { get; set; }

        public string? CollectionType { get; set; }

        public string? ParentId { get; set; }

        public string? SeriesName { get; set; }

        public string? SeasonName { get; set; }

        public int? IndexNumber { get; set; }

        public int? ParentIndexNumber { get; set; }

        public int? ChildCount { get; set; }

        public int? ProductionYear { get; set; }

        public string? OfficialRating { get; set; }

        public DateTimeOffset? DateCreated { get; set; }

        public DateTimeOffset? DateLastMediaAdded { get; set; }

        public DateTimeOffset? PremiereDate { get; set; }

        public long? RunTimeTicks { get; set; }

        public List<string>? Genres { get; set; }

        public List<JellyfinPersonDto>? People { get; set; }

        public JellyfinUserDataDto? UserData { get; set; }
    }

    private sealed class JellyfinPersonDto
    {
        public string? Name { get; set; }

        public string? Type { get; set; }

        public string? Role { get; set; }
    }

    private sealed class JellyfinUserDataDto
    {
        public long? PlaybackPositionTicks { get; set; }

        public double? PlayedPercentage { get; set; }

        public bool IsFavorite { get; set; }

        public bool Played { get; set; }
    }
}
