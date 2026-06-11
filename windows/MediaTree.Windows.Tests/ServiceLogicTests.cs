using MediaTree.Windows.Models;
using MediaTree.Windows.Providers;
using MediaTree.Windows.Services;
using System;
using System.IO;
using System.Net;
using System.Threading;
using System.Threading.Tasks;
using System.Text.Json;
using Xunit;

namespace MediaTree.Windows.Tests;

public sealed class ServiceLogicTests
{
    [Fact]
    public void PlaybackProgressUsesNinetyPercentWatchedThreshold()
    {
        var service = new PlaybackProgressService(null!);

        Assert.False(service.ShouldMarkWatched(10, 120));
        Assert.True(service.ShouldMarkWatched(108, 120));
        Assert.True(service.ShouldMarkWatched(60, 30));
    }

    [Fact]
    public void PlayerStateSnapshotCarriesTrackMetadataWithSafeDefaults()
    {
        var snapshot = new PlayerStateSnapshot(1, 2, false);
        var track = new PlayerTrack(3, "audio", "Japanese", "jpn", "aac", true);

        Assert.Empty(snapshot.Tracks);
        Assert.Contains("Japanese", track.DisplayName);
        Assert.Contains("JPN", track.DisplayName);
        Assert.Contains("AAC", track.DisplayName);
        Assert.Contains("外部", track.DisplayName);
    }

    [Fact]
    public void DtoDefaultsMatchWindowsFirstRunExpectations()
    {
        var root = new MediaRootDto();
        var setting = new LibrarySettingDto();
        var movie = new MovieDto { Code = "sample-code" };

        Assert.Equal("auto", root.Scraper);
        Assert.Equal("auto", setting.Scraper);
        Assert.Equal(1, setting.Enabled);
        Assert.Equal("sample-code", movie.BestTitle);
    }

    [Fact]
    public void MovieDtosAcceptWebSpecialAndTmdbCollectionFields()
    {
        var json = """
            {
              "id": 9,
              "path": "Show/sp/interview.mp4",
              "title": "Scraped title",
              "display_title": "Display title",
              "clean_title": "Clean title",
              "folder_levels": "Show/sp",
              "content_role": "special",
              "special_parent_levels": "Show",
              "tmdb_id": "12345",
              "scraper_source": "tmdb_collection",
              "source_id": "998",
              "cover_remote": "/api/media/poster.jpg",
              "cover_local": "covers/poster.jpg"
            }
            """;

        var movie = JsonSerializer.Deserialize<MovieDto>(json);

        Assert.True(movie!.IsSpecial);
        Assert.Equal(12345, movie.TmdbId);
        Assert.Equal("tmdb_collection", movie.ScraperSource);
        Assert.Equal("Show", movie.FolderForSpecials);
        Assert.Equal("interview", movie.BestTitle);
    }

    [Fact]
    public void MovieDtosAcceptWebDetailMetadataFields()
    {
        var json = """
            {
              "id": 12,
              "path": "Show/S01/E01.mkv",
              "episode_overview": "第一集简介",
              "javdb_score": "4.5",
              "javdb_likes": 123,
              "javdb_thumbnails": "[\"https://example.invalid/1.jpg\"]",
              "cast": [
                { "name": "Actor A", "character": "Lead", "person_id": "42" }
              ],
              "crew": [
                { "name": "Director B", "job": "Director", "department": "Directing" }
              ]
            }
            """;

        var movie = JsonSerializer.Deserialize<MovieDto>(json);

        Assert.Equal("第一集简介", movie!.EpisodeOverview);
        Assert.Equal(4.5, movie.JavdbScore);
        Assert.Equal(123, movie.JavdbLikes);
        Assert.Equal("https://example.invalid/1.jpg", Assert.Single(movie.JavdbThumbnails));
        Assert.Equal("Actor A", Assert.Single(movie.Cast).Name);
        Assert.Equal("Lead", movie.Cast[0].Detail);
        Assert.Equal("Director", Assert.Single(movie.Crew).Job);
    }

    [Fact]
    public void MovieDtosAcceptLegacyStaffJsonStringsFromMovieLists()
    {
        var json = """
            {
              "movies": [
                {
                  "id": 12,
                  "path": "Show/S01/E01.mkv",
                  "cast": "[{\"name\":\"Actor A\",\"role\":\"Lead\"}]",
                  "crew": "Director B, Studio C"
                }
              ],
              "total": 1
            }
            """;

        var response = JsonSerializer.Deserialize<MoviesResponseDto>(json);

        var movie = Assert.Single(response!.Movies);
        Assert.Equal("Actor A", Assert.Single(movie.Cast).Name);
        Assert.Equal("Lead", movie.Cast[0].Detail);
        Assert.Equal(["Director B", "Studio C"], movie.Crew.ConvertAll(item => item.Name));
        Assert.All(movie.Crew, item => Assert.Equal("legacy", item.Source));
    }

    [Fact]
    public void FolderSpecialsDtoAcceptsWebResponse()
    {
        var json = """
            {
              "show_specials": true,
              "special_count": 1,
              "movies": [
                { "id": 3, "path": "Show/sp/a.mp4", "content_role": "special" }
              ]
            }
            """;

        var response = JsonSerializer.Deserialize<FolderSpecialsResponseDto>(json);

        Assert.True(response!.ShowSpecials);
        Assert.Equal(1, response.SpecialCount);
        Assert.True(Assert.Single(response.Movies).IsSpecial);
    }

    [Fact]
    public void UpdateDtoIgnoresRemovedSyncFields()
    {
        var json = """
            {
              "current_version": "1.0.12",
              "has_update": true,
              "remote_latest": {
                "version": "1.0.11",
                "published_at": "2026-06-09T00:00:00Z"
              },
              "latest_sync_warning": {
                "type": "remote-latest-outdated",
                "severity": "warning",
                "release_version": "1.0.13",
                "message": "latest 未同步",
                "action": "请同步 latest"
              },
              "versions": []
            }
            """;

        var response = JsonSerializer.Deserialize<UpdateCheckResultDto>(json);

        Assert.Empty(response!.Versions);
    }

    [Fact]
    public void UpdateDtoMapsWindowsFullUpdateFields()
    {
        var json = """
            {
              "current_version": "1.0.12",
              "effective_version": "1.0.12",
              "has_update": true,
              "versions": [
                {
                  "version": "1.0.14",
                  "display_version": "1.0.14",
                  "update_type": "windows-full-required",
                  "requires_windows_base_update": true,
                  "reason": "需要全量更新",
                  "windows_reason": "需要更新 Windows 桌面版基础运行时",
                  "windows_download_url": "https://example.invalid/MediaTree-Windows-1.0.14.exe"
                }
              ]
            }
            """;

        var response = JsonSerializer.Deserialize<UpdateCheckResultDto>(json);

        var version = Assert.Single(response!.Versions);
        Assert.Equal("1.0.12", response.EffectiveVersion);
        Assert.True(version.RequiresFullUpdate);
        Assert.True(version.RequiresWindowsBaseUpdate);
        Assert.Equal("需要更新 Windows 桌面版基础运行时", version.FullUpdateReason);
        Assert.Equal("https://example.invalid/MediaTree-Windows-1.0.14.exe", version.FullUpdateUrl);
    }

    [Fact]
    public void UpdateDtoKeepsAppPackageUpdatesInApp()
    {
        var version = new VersionEntryDto
        {
            Version = "1.0.15",
            UpdateType = "app-package",
            HtmlUrl = "https://example.invalid/release",
            WindowsDownloadUrl = "",
        };

        Assert.False(version.RequiresFullUpdate);
        Assert.Equal("https://example.invalid/release", version.FullUpdateUrl);
    }

    [Fact]
    public void UpdateIndicatorShowsOnlyWhenUpdateExists()
    {
        Assert.False(UpdateIndicatorState.ShouldShow(null));
        Assert.False(UpdateIndicatorState.ShouldShow(new UpdateCheckResultDto { HasUpdate = false }));
        Assert.True(UpdateIndicatorState.ShouldShow(new UpdateCheckResultDto { HasUpdate = true }));
    }

    [Fact]
    public void LibraryHeaderInputsUseMatchedCompactWidth()
    {
        Assert.Equal(220, MediaTree.Windows.Views.LibraryPage.HeaderInputWidth);
    }

    [Fact]
    public void SettingsLibraryScraperHeaderUsesWinUiLabel()
    {
        Assert.Equal("刮削器", MediaTree.Windows.Views.SettingsPage.LibraryScraperHeader);
    }

    [Fact]
    public void SettingsAddLibraryButtonUsesCompactLabel()
    {
        Assert.Equal("添加", MediaTree.Windows.Views.SettingsPage.AddLibraryButtonText);
    }

    [Fact]
    public void SettingsAddLibrarySourceOptionsExposeAllPlannedProviders()
    {
        Assert.Equal(
            ["本地目录", "MediaTree 远程", "Jellyfin", "Emby"],
            MediaTree.Windows.Views.SettingsPage.AddLibrarySourceOptions);
    }

    [Fact]
    public void SettingsDeleteLibraryButtonUsesCompactDangerLabel()
    {
        Assert.Equal("删除", MediaTree.Windows.Views.SettingsPage.DeleteLibraryButtonText);
    }

    [Fact]
    public void SettingsMovesMobileLoginIntoRemoteAccess()
    {
        Assert.Equal("移动端访问", MediaTree.Windows.Views.SettingsPage.RemoteAccessTitle);
        Assert.Equal("登录用户名", MediaTree.Windows.Views.SettingsPage.RemoteLoginUsernameHeader);
        Assert.Equal("登录密码", MediaTree.Windows.Views.SettingsPage.RemoteLoginPasswordHeader);
        Assert.Equal("保存账号并重启本机服务", MediaTree.Windows.Views.SettingsPage.SaveRemoteAccessButtonText);
    }

    [Fact]
    public void SettingsDoesNotExposeSeparateAccountSecurityCard()
    {
        Assert.DoesNotContain("账号安全", MediaTree.Windows.Views.SettingsPage.RemoteAccessTitle);
        Assert.DoesNotContain("当前用户名", MediaTree.Windows.Views.SettingsPage.RemoteLoginUsernameHeader);
        Assert.DoesNotContain("新用户名", MediaTree.Windows.Views.SettingsPage.RemoteLoginUsernameHeader);
    }

    [Fact]
    public void BackendAccessSettingsDefaultToLoopbackOnly()
    {
        var settings = new BackendAccessSettings();

        Assert.False(settings.AllowRemoteAccess);
        Assert.Equal(BackendAccessSettings.DefaultRemotePort, settings.RemotePort);
        Assert.Equal("127.0.0.1", settings.BindHost);
        Assert.Equal("本机访问", settings.AccessModeLabel);
    }

    [Fact]
    public void BackendAccessSettingsUseFixedPublicPortWhenEnabled()
    {
        var settings = new BackendAccessSettings
        {
            AllowRemoteAccess = true,
            RemotePort = 27581,
        };

        Assert.Equal("0.0.0.0", settings.BindHost);
        Assert.Equal(27581, settings.EffectivePort(43000));
        Assert.Equal("局域网访问", settings.AccessModeLabel);
        Assert.Contains(":27581", settings.DisplayUrl("192.168.100.102"));
    }

    [Fact]
    public void BackendAccessSettingsClampInvalidPorts()
    {
        Assert.Equal(
            BackendAccessSettings.DefaultRemotePort,
            new BackendAccessSettings { AllowRemoteAccess = true, RemotePort = 20 }.EffectivePort(43000));
        Assert.Equal(
            BackendAccessSettings.DefaultRemotePort,
            new BackendAccessSettings { AllowRemoteAccess = true, RemotePort = 70000 }.EffectivePort(43000));
    }

    [Fact]
    public void BackendAccessSettingsRoundTrip()
    {
        var path = Path.Combine(Path.GetTempPath(), $"mediatree-backend-access-{Guid.NewGuid():N}.json");
        try
        {
            BackendAccessSettingsStore.Save(new BackendAccessSettings
            {
                AllowRemoteAccess = true,
                RemotePort = 27581,
            }, path);

            var json = File.ReadAllText(path);
            Assert.Contains("allowRemoteAccess", json);
            Assert.Contains("remotePort", json);

            var settings = BackendAccessSettingsStore.Load(path);
            Assert.True(settings.AllowRemoteAccess);
            Assert.Equal(27581, settings.RemotePort);
        }
        finally
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }
    }

    [Fact]
    public void LocalMediaTreeProviderDescribesBundledBackendSource()
    {
        using var api = new MediaTreeApiClient(new Uri("http://127.0.0.1:27580/"));
        var services = CreateMediaTreeServices(api);
        var provider = new LocalMediaTreeProvider(services);

        Assert.Equal(MediaSourceKind.LocalMediaTree, provider.Profile.Kind);
        Assert.Equal("本机 MediaTree", provider.Profile.DisplayName);
        Assert.True(provider.Profile.RequiresBundledBackend);
        Assert.Equal(api.BackendUri, provider.Profile.Endpoint);
        Assert.IsAssignableFrom<IMediaProvider>(provider);
        Assert.IsAssignableFrom<IMediaTreeProvider>(provider);
    }

    [Fact]
    public void MediaSourceProfilesDescribeEachPlannedSourceBoundary()
    {
        var localEndpoint = new Uri("http://127.0.0.1:27580/");
        var remoteEndpoint = new Uri("https://media.example.invalid/");
        var jellyfinEndpoint = new Uri("https://jellyfin.example.invalid/");
        var embyEndpoint = new Uri("https://emby.example.invalid/");

        var local = MediaSourceProfile.LocalMediaTree(localEndpoint);
        var remote = MediaSourceProfile.RemoteMediaTree("NAS MediaTree", remoteEndpoint);
        var jellyfin = MediaSourceProfile.Jellyfin("Living Room Jellyfin", jellyfinEndpoint);
        var emby = MediaSourceProfile.Emby("Home Emby", embyEndpoint);

        Assert.Equal(MediaSourceKind.LocalMediaTree, local.Kind);
        Assert.Equal("本机 MediaTree", local.DisplayName);
        Assert.True(local.RequiresBundledBackend);
        Assert.Equal(localEndpoint, local.Endpoint);

        Assert.Equal(MediaSourceKind.RemoteMediaTree, remote.Kind);
        Assert.Equal("NAS MediaTree", remote.DisplayName);
        Assert.False(remote.RequiresBundledBackend);
        Assert.Equal(remoteEndpoint, remote.Endpoint);

        Assert.Equal(MediaSourceKind.Jellyfin, jellyfin.Kind);
        Assert.Equal("Living Room Jellyfin", jellyfin.DisplayName);
        Assert.False(jellyfin.RequiresBundledBackend);
        Assert.Equal(jellyfinEndpoint, jellyfin.Endpoint);

        Assert.Equal(MediaSourceKind.Emby, emby.Kind);
        Assert.Equal("Home Emby", emby.DisplayName);
        Assert.False(emby.RequiresBundledBackend);
        Assert.Equal(embyEndpoint, emby.Endpoint);
    }

    [Fact]
    public void MediaSourceProfilesRejectInvalidRemoteInputs()
    {
        var endpoint = new Uri("https://media.example.invalid/");

        Assert.Throws<ArgumentException>("displayName", () => MediaSourceProfile.RemoteMediaTree("", endpoint));
        Assert.Throws<ArgumentNullException>("endpoint", () => MediaSourceProfile.Jellyfin("Jellyfin", null!));
    }

    [Fact]
    public void MediaProviderFactoryCreatesLocalMediaTreeProvider()
    {
        using var api = new MediaTreeApiClient(new Uri("http://127.0.0.1:27580/"));
        var services = CreateMediaTreeServices(api);

        var provider = MediaProviderFactory.CreateLocalMediaTree(services);

        var mediaTreeProvider = Assert.IsType<LocalMediaTreeProvider>(provider);
        Assert.Same(services, mediaTreeProvider.Services);
        Assert.Equal(MediaSourceKind.LocalMediaTree, mediaTreeProvider.Profile.Kind);
    }

    [Theory]
    [InlineData(MediaSourceKind.RemoteMediaTree)]
    [InlineData(MediaSourceKind.Jellyfin)]
    [InlineData(MediaSourceKind.Emby)]
    public void MediaProviderFactoryRejectsRemoteSourcesUntilImplemented(MediaSourceKind kind)
    {
        var profile = new MediaSourceProfile(kind, "Remote source", new Uri("https://media.example.invalid/"), RequiresBundledBackend: false);

        var exception = Assert.Throws<NotSupportedException>(() => MediaProviderFactory.Create(profile));

        Assert.Contains(kind.ToString(), exception.Message);
        Assert.Contains("not implemented", exception.Message);
    }

    [Fact]
    public void MediaSourceProfileStoreDefaultsToLocalMediaTree()
    {
        var path = Path.Combine(Path.GetTempPath(), $"mediatree-sources-{Guid.NewGuid():N}.json");

        var state = MediaSourceProfileStore.Load(path);

        var source = Assert.Single(state.Sources);
        Assert.Equal(MediaSourceProfileStore.LocalSourceId, state.ActiveSourceId);
        Assert.Equal(MediaSourceProfileStore.LocalSourceId, source.Id);
        Assert.Equal(MediaSourceKind.LocalMediaTree, source.Kind);
        Assert.Equal("本机 MediaTree", source.DisplayName);
        Assert.True(source.RequiresBundledBackend);
        Assert.Equal("", source.Endpoint);
    }

    [Fact]
    public void MediaSourceProfileStoreUpsertsExternalSources()
    {
        var path = Path.Combine(Path.GetTempPath(), $"mediatree-sources-{Guid.NewGuid():N}.json");
        try
        {
            var remote = MediaSourceProfileStore.UpsertExternalSource(
                MediaSourceKind.RemoteMediaTree,
                " NAS MediaTree ",
                new Uri("https://media.example.invalid/"),
                path);
            var jellyfin = MediaSourceProfileStore.UpsertExternalSource(
                MediaSourceKind.Jellyfin,
                "Jellyfin",
                new Uri("https://jellyfin.example.invalid/"),
                path);

            var state = MediaSourceProfileStore.Load(path);
            Assert.Equal(MediaSourceProfileStore.LocalSourceId, state.ActiveSourceId);
            Assert.Equal(3, state.Sources.Count);
            Assert.Equal("NAS MediaTree", remote.DisplayName);
            Assert.False(remote.RequiresBundledBackend);
            Assert.Equal(remote, state.Sources.First(source => source.Id == remote.Id));
            Assert.Equal(jellyfin, state.Sources.First(source => source.Id == jellyfin.Id));
            Assert.Contains("RemoteMediaTree", File.ReadAllText(path));
            Assert.Throws<ArgumentException>(() => MediaSourceProfileStore.UpsertExternalSource(
                MediaSourceKind.LocalMediaTree,
                "Local",
                new Uri("http://127.0.0.1:27580/"),
                path));
        }
        finally
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }
    }

    [Fact]
    public void LocalMediaTreeProviderExposesExistingServiceLayer()
    {
        using var api = new MediaTreeApiClient(new Uri("http://127.0.0.1:27580/"));
        var services = CreateMediaTreeServices(api);

        var provider = new LocalMediaTreeProvider(services);

        Assert.Same(services, provider.Services);
        Assert.Same(services.Api, provider.Api);
        Assert.Same(services.Auth, provider.Auth);
        Assert.Same(services.Library, provider.Library);
        Assert.Same(services.Movie, provider.Movie);
        Assert.Same(services.Updates, provider.Updates);
        Assert.Same(services.PlaybackProgress, provider.PlaybackProgress);
    }

    [Fact]
    public void AppServicesExposeActiveMediaTreeServices()
    {
        using var api = new MediaTreeApiClient(new Uri("http://127.0.0.1:27580/"));
        var services = CreateMediaTreeServices(api);
        var provider = new LocalMediaTreeProvider(services);

        AppServices.Initialize(new BackendProcessService(), provider);

        Assert.Same(services, AppServices.MediaTree);
        Assert.Same(provider, AppServices.ActiveMediaTreeProvider);
        Assert.Same(provider, AppServices.ActiveProvider);
        Assert.Same(services.Api, AppServices.MediaTree.Api);
        Assert.Same(services.Auth, AppServices.MediaTree.Auth);
        Assert.Same(services.Library, AppServices.MediaTree.Library);
        Assert.Same(services.Movie, AppServices.MediaTree.Movie);
        Assert.Same(services.Updates, AppServices.MediaTree.Updates);
        Assert.Same(services.PlaybackProgress, AppServices.MediaTree.PlaybackProgress);
    }

    [Fact]
    public void MediaTreeServicesRequireAllServiceDependencies()
    {
        using var api = new MediaTreeApiClient(new Uri("http://127.0.0.1:27580/"));
        var auth = new AuthSessionService(api);
        var library = new LibraryService(api);
        var movie = new MovieService(api);
        var updates = new UpdateService(api);
        var playbackProgress = new PlaybackProgressService(api);

        Assert.Throws<ArgumentNullException>("api", () => new MediaTreeServices(null!, auth, library, movie, updates, playbackProgress));
        Assert.Throws<ArgumentNullException>("auth", () => new MediaTreeServices(api, null!, library, movie, updates, playbackProgress));
        Assert.Throws<ArgumentNullException>("library", () => new MediaTreeServices(api, auth, null!, movie, updates, playbackProgress));
        Assert.Throws<ArgumentNullException>("movie", () => new MediaTreeServices(api, auth, library, null!, updates, playbackProgress));
        Assert.Throws<ArgumentNullException>("updates", () => new MediaTreeServices(api, auth, library, movie, null!, playbackProgress));
        Assert.Throws<ArgumentNullException>("playbackProgress", () => new MediaTreeServices(api, auth, library, movie, updates, null!));
    }

    private static MediaTreeServices CreateMediaTreeServices(MediaTreeApiClient api)
    {
        return new MediaTreeServices(
            api,
            new AuthSessionService(api),
            new LibraryService(api),
            new MovieService(api),
            new UpdateService(api),
            new PlaybackProgressService(api));
    }

    [Fact]
    public async Task ApiClientCanChangeBackendUriAfterRequestsHaveStarted()
    {
        using var firstBackend = new OneShotJsonServer("""{"needs_setup":true,"roots":["first"]}""");
        using var secondBackend = new OneShotJsonServer("""{"needs_setup":false,"roots":["second"]}""");
        using var client = new MediaTreeApiClient(firstBackend.BaseUri);
        using var cancellation = new CancellationTokenSource(TimeSpan.FromSeconds(5));

        var firstStatus = await client.GetSetupStatusAsync(cancellation.Token);
        client.SetBackendUri(secondBackend.BaseUri);
        var secondStatus = await client.GetSetupStatusAsync(cancellation.Token);

        Assert.True(firstStatus.NeedsSetup);
        Assert.Equal(["first"], firstStatus.Roots);
        Assert.False(secondStatus.NeedsSetup);
        Assert.Equal(["second"], secondStatus.Roots);
        Assert.Equal(secondBackend.BaseUri, client.BackendUri);
        Assert.Equal("/api/setup/status", firstBackend.RequestPath);
        Assert.Equal("/api/setup/status", secondBackend.RequestPath);
    }

    [Fact]
    public void LibraryServiceRemovesMatchingRootFromConfig()
    {
        var roots = new[]
        {
            @"\\SAMNAS\o2\test",
            @"D:\Movies",
        };

        var remaining = LibraryService.RemoveLibraryRootFromConfig(roots, @"\\SAMNAS\o2\test\");

        Assert.Equal([@"D:\Movies"], remaining);
        Assert.True(LibraryService.RootsMatch(@"\\SAMNAS\o2\test", @"\\SAMNAS\o2\test\"));
    }

    [Fact]
    public void BrowsePresenterUsesOnlyCurrentMediaRootPaths()
    {
        var roots = new[]
        {
            new MediaRootDto { Path = @"D:\Movies", Label = "Movies" },
            new MediaRootDto { Path = @"D:\Movies\", Label = "Duplicate" },
            new MediaRootDto { Path = "" },
        };

        var paths = BrowseLibraryPresenter.ActiveMediaRootPaths(roots);

        Assert.Equal([@"D:\Movies"], paths);
    }

    [Fact]
    public void BrowsePresenterMergesMoviesFromActiveRootsWithGlobalLimit()
    {
        var first = new MoviesResponseDto
        {
            Total = 2,
            Movies =
            [
                new MovieDto { Id = 1, CreatedAt = "2026-06-10T10:00:00", MediaRoot = @"D:\Movies" },
                new MovieDto { Id = 2, CreatedAt = "2026-06-08T10:00:00", MediaRoot = @"D:\Movies" },
            ],
        };
        var second = new MoviesResponseDto
        {
            Total = 1,
            Movies =
            [
                new MovieDto { Id = 3, CreatedAt = "2026-06-11T10:00:00", MediaRoot = @"E:\Series" },
            ],
        };

        var merged = BrowseLibraryPresenter.MergeMovieResponses([first, second], "created_desc", 2);

        Assert.Equal(3, merged.Total);
        Assert.Equal([3, 1], merged.Movies.Select(movie => movie.Id).ToList());
    }

    [Fact]
    public void BrowsePresenterFiltersExcludedFoldersAndDescendantMovies()
    {
        var folders = new[]
        {
            new FolderNodeDto { Path = "Series", MovieCount = 2 },
            new FolderNodeDto { Path = "Other", MovieCount = 1 },
        };
        var movies = new MoviesResponseDto
        {
            Movies =
            [
                new MovieDto { Id = 1, FolderLevels = "Series" },
                new MovieDto { Id = 2, FolderLevels = "Series/Season 1" },
                new MovieDto { Id = 3, FolderLevels = "Other" },
            ],
            Total = 3,
        };
        var excluded = new HashSet<string> { "Series" };

        var visibleFolders = BrowseLibraryPresenter.FilterExcludedFolders(folders, excluded);
        var visibleMovies = BrowseLibraryPresenter.FilterExcludedMovies(movies, excluded);

        Assert.Equal(["Other"], visibleFolders.Select(folder => folder.Path).ToList());
        Assert.Equal([3], visibleMovies.Movies.Select(movie => movie.Id).ToList());
        Assert.Equal(1, visibleMovies.Total);
    }

    [Fact]
    public void ScrapeResultPresenterBuildsCompactDisplayState()
    {
        var result = new ScrapeSearchResultDto
        {
            Source = "tmdb",
            SourceId = "movie/12:34",
            MediaType = "movie",
            Year = "2026",
            OriginalTitle = "",
            PosterUrl = "/api/poster.jpg",
        };

        Assert.Equal("movie/12:34", ScrapeResultPresenter.DisplayTitle(result));
        Assert.Equal(new[] { "tmdb", "movie", "2026" }, ScrapeResultPresenter.MetadataParts(result));
        Assert.True(ScrapeResultPresenter.HasPoster(result));
        Assert.Equal("movie_12_34", ScrapeResultPresenter.SanitizeAutomationId(result.SourceId));
    }

    [Fact]
    public void ScrapeResultPresenterKeepsReturnedScraperOrAppliesFallback()
    {
        var missingScraper = new ScrapeSearchResultDto { Scraper = "" };
        var explicitScraper = new ScrapeSearchResultDto { Scraper = "tmdb_tv" };

        Assert.Equal("auto", ScrapeResultPresenter.NormalizeScraper(missingScraper, "auto").Scraper);
        Assert.Equal("tmdb_tv", ScrapeResultPresenter.NormalizeScraper(explicitScraper, "auto").Scraper);
    }

    [Fact]
    public void ScrapeSearchDtoAcceptsTmdbCollectionCandidates()
    {
        var json = """
            {
              "results": [
                {
                  "source": "tmdb_collection",
                  "source_id": "998",
                  "media_type": "collection",
                  "title": "Sample Collection",
                  "year": "2026",
                  "scraper": "tmdb_collection"
                }
              ]
            }
            """;

        var response = JsonSerializer.Deserialize<SearchScrapeResponseDto>(json);

        var result = Assert.Single(response!.Results);
        Assert.Equal("tmdb_collection", result.Source);
        Assert.Equal("collection", result.MediaType);
        Assert.Equal("tmdb_collection", result.Scraper);
    }

    [Fact]
    public void ContextMenuDtosAcceptWebCoverAndActionResponses()
    {
        var coversJson = """
            {
              "covers": [
                {
                  "url": "https://image.tmdb.org/t/p/w500/sample.jpg",
                  "source": "tmdb_poster",
                  "width": 500,
                  "height": 750,
                  "language": "zh",
                  "vote_count": 8
                }
              ]
            }
            """;
        var actionJson = """{"ok": true, "title": "Sample", "affected": 2, "deleted": 1}""";

        var covers = JsonSerializer.Deserialize<AlternativeCoversResponseDto>(coversJson);
        var action = JsonSerializer.Deserialize<BasicActionResultDto>(actionJson);

        var cover = Assert.Single(covers!.Covers);
        Assert.Equal("tmdb_poster", cover.Source);
        Assert.Equal(500, cover.Width);
        Assert.True(action!.Ok);
        Assert.Equal(2, action.Affected);
        Assert.Equal(1, action.Deleted);
    }

    [Fact]
    public void MovieDtosTreatNullNumericFieldsAsZero()
    {
        var json = """
            {
              "movies": [
                {
                  "id": 7,
                  "path": "sample.mp4",
                  "duration": null,
                  "playback_position": null,
                  "progress_percent": null
                }
              ],
              "total": 1
            }
            """;

        var response = JsonSerializer.Deserialize<MoviesResponseDto>(json);

        var movie = Assert.Single(response!.Movies);
        Assert.Equal(0, movie.Duration);
        Assert.Equal(0, movie.PlaybackPosition);
        Assert.Equal(0, movie.ProgressPercent);
    }

    [Fact]
    public void FolderDtosTreatNullNumericProgressAsZero()
    {
        var json = """
            {
              "tree": [
                {
                  "name": "S01",
                  "path": "Show/S01",
                  "movie_count": 12,
                  "progress_percent": null,
                  "children": []
                }
              ]
            }
            """;

        var response = JsonSerializer.Deserialize<FoldersResponseDto>(json);

        var folder = Assert.Single(response!.Tree);
        Assert.Equal(0, folder.ProgressPercent);
        Assert.Equal("S01", folder.BestTitle);
    }

    [Fact]
    public void BrowseFolderTreePresenterIncludesEmptyParentFolders()
    {
        var tree = new[]
        {
            new FolderNodeDto
            {
                Name = "Series",
                Path = "Series",
                MovieCount = 0,
                Children =
                [
                    new FolderNodeDto
                    {
                        Name = "Season 1",
                        Path = "Series/Season 1",
                        MovieCount = 12,
                    },
                    new FolderNodeDto
                    {
                        Name = "Extras",
                        Path = "Series/Extras",
                        MovieCount = 0,
                    },
                ],
            },
        };

        var items = BrowseFolderTreePresenter.FlattenAll(tree);

        Assert.Collection(
            items,
            item =>
            {
                Assert.Equal("Series", item.Folder.Path);
                Assert.Equal(0, item.Depth);
            },
            item =>
            {
                Assert.Equal("Series/Season 1", item.Folder.Path);
                Assert.Equal(1, item.Depth);
            },
            item =>
            {
                Assert.Equal("Series/Extras", item.Folder.Path);
                Assert.Equal(1, item.Depth);
            });
    }

    [Fact]
    public void BrowseFolderTreePresenterAssignsFallbackMediaRoot()
    {
        var tree = new[]
        {
            new FolderNodeDto
            {
                Name = "Series",
                Path = "Series",
                Children =
                [
                    new FolderNodeDto
                    {
                        Name = "Season 1",
                        Path = "Series/Season 1",
                    },
                ],
            },
        };

        var items = BrowseFolderTreePresenter.FlattenForMediaRoot(@"D:\Movies", tree);

        Assert.All(items, item => Assert.Equal(@"D:\Movies", item.Folder.MediaRoot));
    }

    [Fact]
    public void BrowseFolderTreePresenterBuildsWebLikeNodeState()
    {
        var folder = new FolderNodeDto { Name = "Season 1", Path = "Series/Season 1", MediaRoot = @"D:\Movies" };
        var item = new BrowseFolderTreeItem(folder, 2);
        var excluded = new HashSet<string> { "Series/Season 1" };
        var expanded = new HashSet<string>();
        var collapsed = new HashSet<string>();

        var collapsedState = BrowseFolderTreePresenter.CreateNodeState(item, excluded, expanded, collapsed);
        BrowseFolderTreePresenter.ToggleExpanded(expanded, collapsed, folder, item.Depth);
        var expandedState = BrowseFolderTreePresenter.CreateNodeState(item, excluded, expanded, collapsed);
        BrowseFolderTreePresenter.ToggleIncluded(excluded, folder.Path);
        var includedState = BrowseFolderTreePresenter.CreateNodeState(item, excluded, expanded, collapsed);
        BrowseFolderTreePresenter.SetIncluded(excluded, folder.Path, false);
        var excludedAgainState = BrowseFolderTreePresenter.CreateNodeState(item, excluded, expanded, collapsed);

        Assert.False(collapsedState.IsExpanded);
        Assert.False(collapsedState.IsIncluded);
        Assert.True(expandedState.IsExpanded);
        Assert.True(includedState.IsIncluded);
        Assert.False(excludedAgainState.IsIncluded);
    }

    [Fact]
    public void BrowseFolderTreePresenterCanCollapseDefaultExpandedNodes()
    {
        var folder = new FolderNodeDto
        {
            Name = "Series",
            Path = "Series",
            MediaRoot = @"D:\Movies",
            Children =
            [
                new FolderNodeDto { Name = "Season 1", Path = "Series/Season 1", MediaRoot = @"D:\Movies" },
            ],
        };
        var item = new BrowseFolderTreeItem(folder, 0);
        var expanded = new HashSet<string>();
        var collapsed = new HashSet<string>();

        var initialState = BrowseFolderTreePresenter.CreateNodeState(item, new HashSet<string>(), expanded, collapsed);
        var initialVisible = BrowseFolderTreePresenter.VisibleNodeStatesForMediaRoot(@"D:\Movies", [folder], new HashSet<string>(), expanded, collapsed);
        BrowseFolderTreePresenter.ToggleExpanded(expanded, collapsed, folder, item.Depth);
        var toggledState = BrowseFolderTreePresenter.CreateNodeState(item, new HashSet<string>(), expanded, collapsed);
        var toggledVisible = BrowseFolderTreePresenter.VisibleNodeStatesForMediaRoot(@"D:\Movies", [folder], new HashSet<string>(), expanded, collapsed);

        Assert.True(initialState.IsExpanded);
        Assert.Equal(["Series", "Series/Season 1"], initialVisible.Select(state => state.Folder.Path).ToList());
        Assert.False(toggledState.IsExpanded);
        Assert.Equal(["Series"], toggledVisible.Select(state => state.Folder.Path).ToList());
    }

    [Fact]
    public void ConfigDtosAcceptIntegerFieldsFromFloatOrStringJson()
    {
        var json = """
            {
              "javdb_cache_hours": "24",
              "tmdb_cache_hours": 168.0,
              "bangumi_cache_hours": null,
              "javdb_request_interval": 3.0
            }
            """;

        var config = JsonSerializer.Deserialize<ConfigDto>(json);

        Assert.Equal(24, config!.JavdbCacheHours);
        Assert.Equal(168, config.TmdbCacheHours);
        Assert.Equal(0, config.BangumiCacheHours);
        Assert.Equal(3, config.JavdbRequestInterval);
    }

    [Fact]
    public void UiPreferencesRoundTripWithWebCompatibleJsonNames()
    {
        var path = Path.Combine(Path.GetTempPath(), $"mediatree-ui-prefs-{Guid.NewGuid():N}.json");
        try
        {
            UiPreferenceStore.Save(new UiPreferenceState
            {
                HideHomeTitleText = true,
                ShowSourceName = true,
                ExcludedFolders = ["Series/Season 1"],
            }, path);

            var json = File.ReadAllText(path);
            Assert.Contains("hideHomeTitleText", json);
            Assert.Contains("showSourceName", json);
            Assert.Contains("excludedFolders", json);

            var preferences = UiPreferenceStore.Load(path);
            Assert.True(preferences.HideHomeTitleText);
            Assert.True(preferences.ShowSourceName);
            Assert.Equal(["Series/Season 1"], preferences.ExcludedFolders);
        }
        finally
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }
    }
}

file sealed class OneShotJsonServer : IDisposable
{
    private readonly System.Net.Sockets.TcpListener _listener;
    private readonly Task _task;

    public OneShotJsonServer(string responseJson)
    {
        _listener = new System.Net.Sockets.TcpListener(IPAddress.Loopback, 0);
        _listener.Start();
        var port = ((IPEndPoint)_listener.LocalEndpoint).Port;
        BaseUri = new Uri($"http://127.0.0.1:{port}/");
        _task = Task.Run(async () =>
        {
            using var client = await _listener.AcceptTcpClientAsync();
            await using var stream = client.GetStream();
            using var reader = new StreamReader(stream, leaveOpen: true);
            var requestLine = await reader.ReadLineAsync();
            RequestPath = requestLine?.Split(' ', StringSplitOptions.RemoveEmptyEntries).ElementAtOrDefault(1) ?? "";
            while (!string.IsNullOrEmpty(await reader.ReadLineAsync()))
            {
            }

            var responseBytes = System.Text.Encoding.UTF8.GetBytes(responseJson);
            using var writer = new StreamWriter(stream, leaveOpen: true);
            await writer.WriteAsync(
                $"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {responseBytes.Length}\r\nConnection: close\r\n\r\n");
            await writer.FlushAsync();
            await stream.WriteAsync(responseBytes);
        });
    }

    public Uri BaseUri { get; }

    public string RequestPath { get; private set; } = "";

    public void Dispose()
    {
        _listener.Stop();
        try
        {
            _task.Wait(TimeSpan.FromSeconds(1));
        }
        catch
        {
        }
    }
}
