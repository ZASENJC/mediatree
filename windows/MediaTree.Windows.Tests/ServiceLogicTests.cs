using MediaTree.Windows.Models;
using MediaTree.Windows.Providers;
using MediaTree.Windows.Providers.Jellyfin;
using MediaTree.Windows.Services;
using MediaTree.Windows.ViewModels;
using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Diagnostics;
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
    public void SettingsExplainsLocalOnlyAndExternalReadOnlyProviderBoundaries()
    {
        Assert.Contains("本机 MediaTree", MediaTree.Windows.Views.SettingsPage.LocalMediaTreeOnlyMessage);
        Assert.Contains("外部服务端管理", MediaTree.Windows.Views.SettingsPage.ExternalLibraryReadOnlyMessage);
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
    public void RemoteMediaTreeProviderUsesSharedMediaTreeServices()
    {
        using var api = new MediaTreeApiClient(new Uri("https://media.example.invalid/"));
        var services = CreateMediaTreeServices(api);
        var profile = MediaSourceProfile.RemoteMediaTree("NAS MediaTree", api.BackendUri);
        var provider = new RemoteMediaTreeProvider(profile, services, new MediaSourceCredentials("admin", "password"));

        Assert.Equal(MediaSourceKind.RemoteMediaTree, provider.Profile.Kind);
        Assert.Equal("NAS MediaTree", provider.Profile.DisplayName);
        Assert.False(provider.Profile.RequiresBundledBackend);
        Assert.Equal(api.BackendUri, provider.Profile.Endpoint);
        Assert.Same(services, provider.Services);
        Assert.Same(services.Api, provider.Api);
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

    [Fact]
    public void MediaProviderFactoryCreatesRemoteMediaTreeProvider()
    {
        var profile = MediaSourceProfile.RemoteMediaTree("NAS MediaTree", new Uri("https://media.example.invalid/"));
        var credentials = new MediaSourceCredentials("admin", "password");

        var provider = MediaProviderFactory.Create(profile, credentials);

        var mediaTreeProvider = Assert.IsType<RemoteMediaTreeProvider>(provider);
        Assert.Equal(MediaSourceKind.RemoteMediaTree, mediaTreeProvider.Profile.Kind);
        Assert.Equal(profile.Endpoint, mediaTreeProvider.Api.BackendUri);
        Assert.Same(mediaTreeProvider.Services, provider.Services);
    }

    [Fact]
    public async Task MediaProviderFactoryCanAuthenticateRemoteMediaTreeProvider()
    {
        using var server = new OneShotJsonServer(new OneShotJsonResponse(200, """{"token":"remote-token","ok":true}"""));
        var profile = MediaSourceProfile.RemoteMediaTree("NAS MediaTree", server.BaseUri);
        var credentials = new MediaSourceCredentials("admin", "password");
        using var cancellation = new CancellationTokenSource(TimeSpan.FromSeconds(5));

        var provider = await MediaProviderFactory.CreateRemoteMediaTreeAsync(profile, credentials, cancellation.Token);

        Assert.Equal(MediaSourceKind.RemoteMediaTree, provider.Profile.Kind);
        Assert.Equal(server.BaseUri, provider.Api.BackendUri);
        Assert.Equal("/api/auth/login", server.RequestPath);
    }

    [Theory]
    [InlineData(MediaSourceKind.Jellyfin, "https://jellyfin.example.invalid/")]
    [InlineData(MediaSourceKind.Emby, "https://emby.example.invalid/")]
    public void MediaProviderFactoryCreatesJellyfinCompatibleProviders(MediaSourceKind kind, string endpoint)
    {
        var profile = new MediaSourceProfile(kind, "Remote source", new Uri(endpoint), RequiresBundledBackend: false);
        var credentials = new MediaSourceCredentials("user", "secret");

        var provider = MediaProviderFactory.Create(profile, credentials);

        var compatible = Assert.IsType<JellyfinCompatibleProvider>(provider);
        Assert.Equal(kind, compatible.Profile.Kind);
        Assert.Equal(profile.Endpoint, compatible.Services.Api.BackendUri);
        Assert.Same(compatible.Services, provider.Services);
        Assert.Same(credentials, compatible.Credentials);
    }

    [Theory]
    [InlineData(MediaSourceKind.Jellyfin)]
    [InlineData(MediaSourceKind.Emby)]
    public async Task MediaProviderFactoryCanAuthenticateJellyfinCompatibleProviders(MediaSourceKind kind)
    {
        using var server = new OneShotJsonServer(new OneShotJsonResponse(200, """{"AccessToken":"media-token","User":{"Id":"user-id","Name":"media-user"}}"""));
        var profile = new MediaSourceProfile(kind, "Remote source", server.BaseUri, RequiresBundledBackend: false);
        var credentials = new MediaSourceCredentials("media-user", "media-password");
        using var cancellation = new CancellationTokenSource(TimeSpan.FromSeconds(5));

        var provider = await MediaProviderFactory.CreateJellyfinCompatibleAsync(profile, credentials, cancellation.Token);

        Assert.Equal(kind, provider.Profile.Kind);
        Assert.Equal(server.BaseUri, provider.Services.Api.BackendUri);
        Assert.Equal("/Users/AuthenticateByName", server.RequestPath);
        Assert.Contains("\"Username\":\"media-user\"", server.RequestBodies[0]);
        Assert.Contains("\"Pw\":\"media-password\"", server.RequestBodies[0]);
    }

    [Fact]
    public async Task JellyfinCompatibleClientMapsLibrariesFoldersMoviesAndPlaybackUrls()
    {
        using var server = new OneShotJsonServer(
            new OneShotJsonResponse(200, """
                {
                  "Items": [
                    { "Id": "lib-1", "Name": "Movies", "CollectionType": "movies" }
                  ]
                }
                """),
            new OneShotJsonResponse(200, """
                {
                  "Items": [
                    { "Id": "folder-1", "Name": "Shows", "Type": "Folder", "ChildCount": 2 },
                    { "Id": "movie-leaf", "Name": "Standalone Movie", "Type": "Movie", "ChildCount": 0, "RunTimeTicks": 1200000000 }
                  ],
                  "TotalRecordCount": 2
                }
                """),
            new OneShotJsonResponse(200, """
                {
                  "Items": [
                    {
                      "Id": "movie-1",
                      "Name": "Episode One",
                      "OriginalTitle": "Episode One Original",
                      "Overview": "Pilot",
                      "Type": "Episode",
                      "SeriesName": "Sample Show",
                      "SeasonName": "Season 1",
                      "IndexNumber": 1,
                      "ParentIndexNumber": 1,
                      "RunTimeTicks": 600000000,
                      "DateCreated": "2026-06-10T10:00:00Z",
                      "PremiereDate": "2026-06-09T00:00:00Z",
                      "UserData": { "PlaybackPositionTicks": 300000000, "PlayedPercentage": 50, "IsFavorite": true, "Played": true }
                    }
                  ],
                  "TotalRecordCount": 1
                }
                """),
            new OneShotJsonResponse(200, """
                {
                  "Id": "movie-1",
                  "Name": "Episode One",
                  "Overview": "Pilot",
                  "Type": "Episode",
                  "SeriesName": "Sample Show",
                  "SeasonName": "Season 1",
                  "IndexNumber": 1,
                  "ParentIndexNumber": 1,
                  "RunTimeTicks": 600000000,
                  "UserData": { "PlaybackPositionTicks": 300000000, "PlayedPercentage": 50, "IsFavorite": true, "Played": true }
                }
                """),
            new OneShotJsonResponse(204, ""),
            new OneShotJsonResponse(200, "image-bytes"));
        using var api = new JellyfinCompatibleApiClient(server.BaseUri, MediaSourceKind.Jellyfin);
        api.SetBearerToken("media-token");
        api.SetUserId("user-id");
        using var cancellation = new CancellationTokenSource(TimeSpan.FromSeconds(5));

        var roots = await api.GetMediaRootsAsync(cancellation.Token);
        var folders = await api.GetFoldersAsync("lib-1", cancellation.Token);
        var movies = await api.GetMoviesAsync("lib-1", "folder-1", "", "created_desc", 20, 0, cancellation.Token);
        var detail = await api.GetMovieDetailAsync(movies.Movies[0].Id, cancellation.Token);
        var progress = await api.GetProgressAsync(detail.Id, cancellation.Token);
        await api.SaveProgressAsync(detail.Id, 42, 60, stopped: false, cancellation.Token);
        var coverUrl = await api.BuildCoverUrlAsync(detail.Id, cancellation.Token);
        var streamUrl = await api.BuildStreamUrlAsync(detail.Id, cancellation.Token);
        var playbackSource = await api.BuildPlaybackSourceAsync(detail.Id, cancellation.Token);

        var root = Assert.Single(roots.Items);
        Assert.Equal("lib-1", root.Path);
        Assert.Equal("Movies", root.Label);
        Assert.Equal(2, folders.Tree.Count);
        var folder = Assert.Single(folders.Tree, item => item.Path == "folder-1");
        Assert.Equal("folder-1", folder.Path);
        Assert.Equal("lib-1", folder.MediaRoot);
        var leaf = Assert.Single(folders.Tree, item => item.Path == "movie-leaf");
        Assert.True(leaf.IsLeaf);
        Assert.True(leaf.MovieId > 0);
        Assert.Equal(1, leaf.MovieCount);
        var movie = Assert.Single(movies.Movies);
        Assert.Equal("Episode One", movie.Title);
        Assert.StartsWith("jellyfin-compatible://", movie.Path);
        Assert.Equal("Sample Show/Season 1", movie.FolderLevels);
        Assert.Equal(60, movie.Duration);
        Assert.Equal(30, movie.PlaybackPosition);
        Assert.Contains("favorite", movie.Tags);
        Assert.Contains("watched", movie.Tags);
        Assert.Equal(movie.Id, detail.Id);
        Assert.True(progress.Played);
        Assert.Equal(50, progress.ProgressPercent);
        Assert.StartsWith("file://", coverUrl);
        Assert.DoesNotContain("media-token", coverUrl);
        Assert.Contains("/Videos/movie-1/stream?static=true", streamUrl);
        Assert.DoesNotContain("api_key", streamUrl);
        Assert.Equal(streamUrl, playbackSource.Uri);
        Assert.Equal("media-token", playbackSource.Headers["X-Emby-Token"]);
        Assert.Contains("MediaBrowser ", playbackSource.Headers["X-Emby-Authorization"]);
        Assert.Contains("Token=\"media-token\"", playbackSource.Headers["X-Emby-Authorization"]);
        Assert.Equal(
            [
                "/Users/user-id/Views",
                "/Users/user-id/Items?ParentId=lib-1&IncludeItemTypes=Folder%2CMovie%2CSeries%2CSeason%2CEpisode%2CBoxSet%2CVideo%2CMusicVideo&Recursive=false&Fields=Overview%2CPeople%2CGenres%2CDateCreated%2CPremiereDate%2CRuntimeTicks%2CUserData%2CSeriesName%2CSeasonName%2CIndexNumber%2CParentIndexNumber%2CPath%2CChildCount%2CCollectionType&Limit=200",
                "/Users/user-id/Items?ParentId=folder-1&IncludeItemTypes=Movie%2CEpisode%2CVideo&Recursive=true&SearchTerm=&SortBy=DateCreated&SortOrder=Descending&StartIndex=0&Limit=20&Fields=Overview%2CPeople%2CGenres%2CDateCreated%2CPremiereDate%2CRuntimeTicks%2CUserData%2CSeriesName%2CSeasonName%2CIndexNumber%2CParentIndexNumber%2CPath%2CChildCount%2CCollectionType",
                $"/Users/user-id/Items/movie-1",
                "/Sessions/Playing/Progress?ItemId=movie-1&PositionTicks=420000000&IsPaused=false&EventName=timeupdate",
                "/Items/movie-1/Images/Primary"
            ],
            server.RequestPaths);
        Assert.Equal("media-token", server.RequestHeaders[^1]["X-Emby-Token"]);
        Assert.Contains("Token=\"media-token\"", server.RequestHeaders[^1]["X-Emby-Authorization"]);
    }

    [Fact]
    public async Task JellyfinCompatibleClientUsesEmbyProgressPathAndMediaBrowserWatchedPaths()
    {
        using var server = new OneShotJsonServer(
            new OneShotJsonResponse(200, """
                {
                  "Items": [
                    {
                      "Id": "movie-1",
                      "Name": "Movie One",
                      "Type": "Movie",
                      "RunTimeTicks": 600000000,
                      "UserData": { "PlaybackPositionTicks": 0, "PlayedPercentage": 0, "Played": false }
                    }
                  ],
                  "TotalRecordCount": 1
                }
                """),
            new OneShotJsonResponse(204, ""),
            new OneShotJsonResponse(204, ""),
            new OneShotJsonResponse(204, ""));
        using var api = new JellyfinCompatibleApiClient(server.BaseUri, MediaSourceKind.Emby);
        api.SetBearerToken("media-token");
        api.SetUserId("user-id");
        using var cancellation = new CancellationTokenSource(TimeSpan.FromSeconds(5));

        var movies = await api.GetMoviesAsync("lib-1", "", "", "created_desc", 20, 0, cancellation.Token);
        var movie = Assert.Single(movies.Movies);
        await api.SaveProgressAsync(movie.Id, 42, 60, stopped: false, cancellation.Token);
        await api.AddTagAsync(movie.Id, "watched", cancellation.Token);
        await api.RemoveTagAsync(movie.Id, "watched", cancellation.Token);

        Assert.Equal(
            [
                "/Users/user-id/Items?ParentId=lib-1&IncludeItemTypes=Movie%2CEpisode%2CVideo&Recursive=true&SearchTerm=&SortBy=DateCreated&SortOrder=Descending&StartIndex=0&Limit=20&Fields=Overview%2CPeople%2CGenres%2CDateCreated%2CPremiereDate%2CRuntimeTicks%2CUserData%2CSeriesName%2CSeasonName%2CIndexNumber%2CParentIndexNumber%2CPath%2CChildCount%2CCollectionType",
                "/Users/user-id/PlayingItems/movie-1/Progress?PositionTicks=420000000",
                "/Users/user-id/PlayedItems/movie-1",
                "/Users/user-id/PlayedItems/movie-1"
            ],
            server.RequestPaths);
        Assert.All(server.RequestHeaders, headers =>
        {
            Assert.Equal("media-token", headers["X-Emby-Token"]);
            Assert.StartsWith("Emby ", headers["Authorization"]);
            Assert.Contains("Token=\"media-token\"", headers["Authorization"]);
        });
    }

    [Fact]
    public async Task JellyfinCompatibleClientUsesDistinctReadPathsForRecentFavoritesAndSearch()
    {
        using var server = new OneShotJsonServer(
            new OneShotJsonResponse(200, """{"Items":[],"TotalRecordCount":0}"""),
            new OneShotJsonResponse(200, """{"Items":[],"TotalRecordCount":0}"""),
            new OneShotJsonResponse(200, """{"Items":[],"TotalRecordCount":0}"""));
        using var api = new JellyfinCompatibleApiClient(server.BaseUri, MediaSourceKind.Emby);
        api.SetBearerToken("media-token");
        api.SetUserId("user-id");
        using var cancellation = new CancellationTokenSource(TimeSpan.FromSeconds(5));

        await api.GetRecentWatchedAsync("lib-1", 10, 0, cancellation.Token);
        await api.GetFavoritesAsync("lib-1", "name", 10, 0, cancellation.Token);
        await api.GetMoviesAsync("lib-1", "", "matrix", "release_date_desc", 10, 0, cancellation.Token);

        Assert.Contains("SortBy=DatePlayed", server.RequestPaths[0]);
        Assert.Contains("Filters=IsResumable", server.RequestPaths[0]);
        Assert.DoesNotContain("IsPlayed=true", server.RequestPaths[0]);
        Assert.Contains("Filters=IsFavorite", server.RequestPaths[1]);
        Assert.Contains("SortBy=SortName", server.RequestPaths[1]);
        Assert.Contains("SearchTerm=matrix", server.RequestPaths[2]);
        Assert.Contains("SortBy=PremiereDate", server.RequestPaths[2]);
    }

    [Fact]
    public async Task JellyfinCompatibleClientCachesMediaRootsForStartupReuse()
    {
        using var server = new OneShotJsonServer(new OneShotJsonResponse(200, """
            {
              "Items": [
                { "Id": "lib-1", "Name": "Movies", "CollectionType": "movies" }
              ]
            }
            """));
        using var api = new JellyfinCompatibleApiClient(server.BaseUri, MediaSourceKind.Jellyfin);
        api.SetBearerToken("media-token");
        api.SetUserId("user-id");
        using var cancellation = new CancellationTokenSource(TimeSpan.FromSeconds(5));

        var setup = await api.GetSetupStatusAsync(cancellation.Token);
        var roots = await api.GetMediaRootsAsync(cancellation.Token);

        Assert.False(setup.NeedsSetup);
        Assert.Equal(["lib-1"], setup.Roots);
        Assert.Equal("Movies", Assert.Single(roots.Items).Label);
        Assert.Equal(["/Users/user-id/Views"], server.RequestPaths);
    }

    [Fact]
    public async Task JellyfinCompatibleClientRejectsMediaTreeLibraryManagementWrites()
    {
        using var api = new JellyfinCompatibleApiClient(new Uri("https://jellyfin.example.invalid/"), MediaSourceKind.Jellyfin);
        using var cancellation = new CancellationTokenSource(TimeSpan.FromSeconds(5));

        await Assert.ThrowsAsync<NotSupportedException>(() => api.SaveLibrarySettingAsync(new LibrarySettingDto { MediaRoot = "lib-1" }, cancellation.Token));
        await Assert.ThrowsAsync<NotSupportedException>(() => api.SetLibraryPasswordAsync("lib-1", "secret", cancellation.Token));
        await Assert.ThrowsAsync<NotSupportedException>(() => api.ScanAsync("lib-1", cancellation.Token));
        await Assert.ThrowsAsync<NotSupportedException>(() => api.ClearLibraryAsync("lib-1", cancellation.Token));
        await Assert.ThrowsAsync<NotSupportedException>(() => api.SaveConfigAsync(["C:\\Media"], cancellation.Token));
        await Assert.ThrowsAsync<NotSupportedException>(() => api.SaveGlobalConfigAsync(new ConfigDto(), cancellation.Token));
    }

    [Fact]
    public void MediaProviderFactoryRequiresCredentialsForRemoteMediaTree()
    {
        var profile = MediaSourceProfile.RemoteMediaTree("NAS MediaTree", new Uri("https://media.example.invalid/"));

        Assert.Throws<ArgumentNullException>("credentials", () => MediaProviderFactory.Create(profile));
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
    public void MediaSourceProfileStoreCanActivateSavedSources()
    {
        var path = Path.Combine(Path.GetTempPath(), $"mediatree-sources-{Guid.NewGuid():N}.json");
        try
        {
            var remote = MediaSourceProfileStore.UpsertExternalSource(
                MediaSourceKind.RemoteMediaTree,
                "NAS MediaTree",
                new Uri("https://media.example.invalid/"),
                path);

            var active = MediaSourceProfileStore.SetActiveSource(remote.Id, path);

            Assert.Equal(remote.Id, active.ActiveSourceId);
            Assert.Equal(remote.Id, MediaSourceProfileStore.Load(path).ActiveSourceId);
            Assert.Equal(MediaSourceProfileStore.LocalSourceId, MediaSourceProfileStore.SetActiveSource(MediaSourceProfileStore.LocalSourceId, path).ActiveSourceId);
            Assert.Throws<ArgumentException>("sourceId", () => MediaSourceProfileStore.SetActiveSource("missing-source", path));
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
    public void MediaSourceProfileStoreRemovesExternalSourcesAndFallsBackToLocal()
    {
        var path = Path.Combine(Path.GetTempPath(), $"mediatree-sources-{Guid.NewGuid():N}.json");
        try
        {
            var remote = MediaSourceProfileStore.UpsertExternalSource(
                MediaSourceKind.RemoteMediaTree,
                "NAS MediaTree",
                new Uri("https://media.example.invalid/"),
                path);
            var jellyfin = MediaSourceProfileStore.UpsertExternalSource(
                MediaSourceKind.Jellyfin,
                "Living Room Jellyfin",
                new Uri("https://jellyfin.example.invalid/"),
                path);
            MediaSourceProfileStore.SetActiveSource(remote.Id, path);

            var afterRemovingActive = MediaSourceProfileStore.RemoveSource(remote.Id, path);

            Assert.Equal(MediaSourceProfileStore.LocalSourceId, afterRemovingActive.ActiveSourceId);
            Assert.DoesNotContain(afterRemovingActive.Sources, source => source.Id == remote.Id);
            Assert.Contains(afterRemovingActive.Sources, source => source.Id == jellyfin.Id);

            var afterRemovingInactive = MediaSourceProfileStore.RemoveSource(jellyfin.Id, path);

            Assert.Equal(MediaSourceProfileStore.LocalSourceId, afterRemovingInactive.ActiveSourceId);
            Assert.Single(afterRemovingInactive.Sources);
            Assert.Throws<ArgumentException>("sourceId", () => MediaSourceProfileStore.RemoveSource(MediaSourceProfileStore.LocalSourceId, path));
            Assert.Throws<ArgumentException>("sourceId", () => MediaSourceProfileStore.RemoveSource("missing-source", path));
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
    public void MediaSourceListPresenterGroupsSavedSourcesByKindAndMarksActiveSource()
    {
        var state = new MediaSourceProfileState(
            "Jellyfin:https://jellyfin.example.invalid/",
            [
                new(MediaSourceProfileStore.LocalSourceId, MediaSourceKind.LocalMediaTree, "本机 MediaTree", "", true),
                new("RemoteMediaTree:https://media.example.invalid/", MediaSourceKind.RemoteMediaTree, "NAS MediaTree", "https://media.example.invalid/", false),
                new("Jellyfin:https://jellyfin.example.invalid/", MediaSourceKind.Jellyfin, "Living Room Jellyfin", "https://jellyfin.example.invalid/", false),
            ]);

        var groups = MediaSourceListPresenter.BuildGroups(state);

        Assert.Equal(
            ["本机 MediaTree", "MediaTree 远程", "Jellyfin"],
            groups.Select(group => group.Title));
        Assert.Equal([1, 1, 1], groups.Select(group => group.Sources.Count));
        Assert.DoesNotContain(groups, group => group.Kind == MediaSourceKind.Emby);
        Assert.True(groups.Single(group => group.Kind == MediaSourceKind.Jellyfin).Sources.Single().IsActive);
        Assert.False(groups.Single(group => group.Kind == MediaSourceKind.RemoteMediaTree).Sources.Single().IsActive);
        Assert.Equal("Living Room Jellyfin", groups.Single(group => group.Kind == MediaSourceKind.Jellyfin).Sources.Single().DisplayName);
        Assert.Equal("https://jellyfin.example.invalid/", groups.Single(group => group.Kind == MediaSourceKind.Jellyfin).Sources.Single().Endpoint);
    }

    [Fact]
    public void MediaSourceListPresenterBuildsOrderedBackendCards()
    {
        var state = new MediaSourceProfileState(
            "RemoteMediaTree:https://media.example.invalid/",
            [
                new("Jellyfin:https://jellyfin.example.invalid/", MediaSourceKind.Jellyfin, "Living Room Jellyfin", "https://jellyfin.example.invalid/", false),
                new(MediaSourceProfileStore.LocalSourceId, MediaSourceKind.LocalMediaTree, "本机 MediaTree", "", true),
                new("RemoteMediaTree:https://media.example.invalid/", MediaSourceKind.RemoteMediaTree, "NAS MediaTree", "https://media.example.invalid/", false),
            ]);

        var items = MediaSourceListPresenter.BuildItems(state);

        Assert.Equal(
            [MediaSourceKind.LocalMediaTree, MediaSourceKind.RemoteMediaTree, MediaSourceKind.Jellyfin],
            items.Select(item => item.Kind));
        Assert.True(items.Single(item => item.Kind == MediaSourceKind.RemoteMediaTree).IsActive);
        Assert.False(items.Single(item => item.Kind == MediaSourceKind.LocalMediaTree).IsActive);
        Assert.Equal("NAS MediaTree", items.Single(item => item.Kind == MediaSourceKind.RemoteMediaTree).DisplayName);
    }

    [Fact]
    public void MediaSourceCredentialStoreProtectsExternalSourceSecrets()
    {
        var path = Path.Combine(Path.GetTempPath(), $"mediatree-source-credentials-{Guid.NewGuid():N}.json");
        var sourceId = "RemoteMediaTree:https://media.example.invalid/";
        try
        {
            var credentials = new MediaSourceCredentials("admin-user", "sample-password");

            MediaSourceCredentialStore.Save(sourceId, credentials, path);

            var json = File.ReadAllText(path);
            Assert.Contains("Payload", json);
            Assert.DoesNotContain("admin-user", json);
            Assert.DoesNotContain("sample-password", json);
            Assert.Equal(credentials, MediaSourceCredentialStore.Load(sourceId, path));

            MediaSourceCredentialStore.Clear(sourceId, path);

            Assert.Null(MediaSourceCredentialStore.Load(sourceId, path));
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
    public async Task MediaSourceConnectionTesterChecksRemoteMediaTreeHealthAndLogin()
    {
        using var server = new OneShotJsonServer(
            new OneShotJsonResponse(200, """{"status":"ok"}"""),
            new OneShotJsonResponse(200, """{"token":"remote-token"}"""));
        using var tester = new MediaSourceConnectionTester();
        using var cancellation = new CancellationTokenSource(TimeSpan.FromSeconds(5));

        var result = await tester.TestAsync(
            MediaSourceKind.RemoteMediaTree,
            server.BaseUri,
            new MediaSourceCredentials("admin", "password"),
            cancellation.Token);

        Assert.True(result.Succeeded, result.Message);
        Assert.Equal(["/api/health", "/api/auth/login"], server.RequestPaths);
        Assert.Contains("\"username\":\"admin\"", server.RequestBodies[1]);
        Assert.Contains("\"password\":\"password\"", server.RequestBodies[1]);
    }

    [Theory]
    [InlineData(MediaSourceKind.Jellyfin)]
    [InlineData(MediaSourceKind.Emby)]
    public async Task MediaSourceConnectionTesterChecksJellyfinCompatibleLogin(MediaSourceKind kind)
    {
        using var server = new OneShotJsonServer(new OneShotJsonResponse(200, """{"AccessToken":"media-token","User":{"Id":"user-id"}}"""));
        using var tester = new MediaSourceConnectionTester();
        using var cancellation = new CancellationTokenSource(TimeSpan.FromSeconds(5));

        var result = await tester.TestAsync(
            kind,
            server.BaseUri,
            new MediaSourceCredentials("media-user", "media-password"),
            cancellation.Token);

        Assert.True(result.Succeeded, result.Message);
        Assert.Equal("/Users/AuthenticateByName", server.RequestPath);
        Assert.Contains("\"Username\":\"media-user\"", server.RequestBodies[0]);
        Assert.Contains("\"Pw\":\"media-password\"", server.RequestBodies[0]);
    }

    [Theory]
    [InlineData(MediaSourceKind.Jellyfin, "X-Emby-Authorization", "MediaBrowser ")]
    [InlineData(MediaSourceKind.Emby, "Authorization", "Emby ")]
    public async Task MediaSourceConnectionTesterUsesJellyfinCompatibleClientAuthHeader(
        MediaSourceKind kind,
        string headerName,
        string expectedPrefix)
    {
        using var server = new OneShotJsonServer(new OneShotJsonResponse(200, """{"AccessToken":"media-token","User":{"Id":"user-id"}}"""));
        using var tester = new MediaSourceConnectionTester();
        using var cancellation = new CancellationTokenSource(TimeSpan.FromSeconds(5));

        var result = await tester.TestAsync(
            kind,
            server.BaseUri,
            new MediaSourceCredentials("media-user", "media-password"),
            cancellation.Token);

        Assert.True(result.Succeeded, result.Message);
        Assert.True(server.RequestHeaders[0].TryGetValue(headerName, out var authorization));
        Assert.StartsWith(expectedPrefix, authorization);
        Assert.Contains("Client=\"MediaTree Windows\"", authorization);
        Assert.Contains("Device=\"Windows\"", authorization);
        Assert.DoesNotContain("media-password", authorization);
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

        Assert.Same(services, AppServices.Media);
        Assert.Same(provider, AppServices.ActiveMediaTreeProvider);
        Assert.Same(provider, AppServices.ActiveProvider);
        Assert.Same(services, AppServices.ActiveProvider.Services);
        Assert.Same(services.Api, AppServices.Media.Api);
        Assert.Same(services.Auth, AppServices.Media.Auth);
        Assert.Same(services.Library, AppServices.Media.Library);
        Assert.Same(services.Movie, AppServices.Media.Movie);
        Assert.Same(services.Updates, AppServices.Media.Updates);
        Assert.Same(services.PlaybackProgress, AppServices.Media.PlaybackProgress);
    }

    [Fact]
    public void AppServicesExposeExternalProviderServicesWithoutMediaTreeProviderAlias()
    {
        using var api = new JellyfinCompatibleApiClient(new Uri("https://jellyfin.example.invalid/"), MediaSourceKind.Jellyfin);
        var services = CreateMediaTreeServices(api);
        var profile = MediaSourceProfile.Jellyfin("Jellyfin", api.BackendUri);
        var provider = new JellyfinCompatibleProvider(profile, services, new MediaSourceCredentials("user", "secret"));

        AppServices.Initialize(new BackendProcessService(), provider);

        Assert.Same(provider, AppServices.ActiveProvider);
        Assert.Null(AppServices.ActiveMediaTreeProvider);
        Assert.Same(services, AppServices.Media);
        Assert.Same(services.Api, AppServices.Media.Api);
        Assert.Same(services.Library, AppServices.Media.Library);
        Assert.Same(services.Movie, AppServices.Media.Movie);
        Assert.Same(services.PlaybackProgress, AppServices.Media.PlaybackProgress);
    }

    [Fact]
    public void AppServicesCanSwitchActiveProviderWithoutRestart()
    {
        var localDisposed = false;
        using var firstApi = new TrackingMediaApiClient(new Uri("http://127.0.0.1:27580/"), () => localDisposed = true);
        using var secondApi = new TrackingMediaApiClient(new Uri("https://jellyfin.example.invalid/"), () => { });
        var firstServices = CreateMediaTreeServices(firstApi);
        var secondServices = CreateMediaTreeServices(secondApi);
        var firstProvider = new LocalMediaTreeProvider(firstServices);
        var secondProvider = new JellyfinCompatibleProvider(
            MediaSourceProfile.Jellyfin("Jellyfin", secondApi.BackendUri),
            secondServices,
            new MediaSourceCredentials("user", "secret"));

        AppServices.Initialize(new BackendProcessService(), firstProvider);

        AppServices.SwitchProvider(secondProvider);

        Assert.False(localDisposed);
        Assert.Same(secondProvider, AppServices.ActiveProvider);
        Assert.Null(AppServices.ActiveMediaTreeProvider);
        Assert.Same(secondServices, AppServices.Media);
    }

    [Fact]
    public void AppServicesCanSwitchBackToLocalMediaTreeWithoutRestart()
    {
        var remoteDisposed = false;
        using var localApi = new TrackingMediaApiClient(new Uri("http://127.0.0.1:27580/"), () => { });
        using var remoteApi = new TrackingMediaApiClient(new Uri("https://jellyfin.example.invalid/"), () => remoteDisposed = true);
        var localServices = CreateMediaTreeServices(localApi);
        var remoteServices = CreateMediaTreeServices(remoteApi);
        var localProvider = new LocalMediaTreeProvider(localServices);
        var remoteProvider = new JellyfinCompatibleProvider(
            MediaSourceProfile.Jellyfin("Jellyfin", remoteApi.BackendUri),
            remoteServices,
            new MediaSourceCredentials("user", "secret"));

        AppServices.Initialize(new BackendProcessService(), localProvider);
        AppServices.SwitchProvider(remoteProvider);

        AppServices.SwitchToLocalMediaTree();

        Assert.True(remoteDisposed);
        Assert.Same(localProvider, AppServices.ActiveProvider);
        Assert.Same(localProvider, AppServices.ActiveMediaTreeProvider);
        Assert.Same(localServices, AppServices.Media);
    }

    [Fact]
    public async Task ConcurrentMediaItemLoaderPreservesOrderWhileLimitingConcurrency()
    {
        var inFlight = 0;
        var maxInFlight = 0;
        using var cancellation = new CancellationTokenSource(TimeSpan.FromSeconds(5));

        var stopwatch = Stopwatch.StartNew();
        var results = await ConcurrentMediaItemLoader.MapAsync(
            Enumerable.Range(1, 6).ToList(),
            maxConcurrency: 3,
            async (value, token) =>
            {
                var current = Interlocked.Increment(ref inFlight);
                maxInFlight = Math.Max(maxInFlight, current);
                await Task.Delay(120, token);
                Interlocked.Decrement(ref inFlight);
                return value * 10;
            },
            cancellation.Token);
        stopwatch.Stop();

        Assert.Equal([10, 20, 30, 40, 50, 60], results);
        Assert.InRange(maxInFlight, 2, 3);
        Assert.True(stopwatch.Elapsed < TimeSpan.FromMilliseconds(500), $"Expected concurrent loading, took {stopwatch.Elapsed}.");
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

    private static MediaTreeServices CreateMediaTreeServices(IMediaApiClient api)
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
    public void BrowsePresenterMergesMoviesFromActiveRootsWithGlobalPagination()
    {
        var first = new MoviesResponseDto
        {
            Total = 3,
            Movies =
            [
                new MovieDto { Id = 1, CreatedAt = "2026-06-10T10:00:00", MediaRoot = @"D:\Movies" },
                new MovieDto { Id = 2, CreatedAt = "2026-06-08T10:00:00", MediaRoot = @"D:\Movies" },
                new MovieDto { Id = 5, CreatedAt = "2026-06-06T10:00:00", MediaRoot = @"D:\Movies" },
            ],
        };
        var second = new MoviesResponseDto
        {
            Total = 2,
            Movies =
            [
                new MovieDto { Id = 3, CreatedAt = "2026-06-11T10:00:00", MediaRoot = @"E:\Series" },
                new MovieDto { Id = 4, CreatedAt = "2026-06-09T10:00:00", MediaRoot = @"E:\Series" },
            ],
        };

        var merged = BrowseLibraryPresenter.MergeMovieResponses([first, second], "created_desc", limit: 2, offset: 2);

        Assert.Equal(5, merged.Total);
        Assert.Equal([4, 2], merged.Movies.Select(movie => movie.Id).ToList());
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
    public void BrowsePresenterCanPreservePagedTotalWhenFilteringExcludedMovies()
    {
        var movies = new MoviesResponseDto
        {
            Movies =
            [
                new MovieDto { Id = 1, FolderLevels = "Series" },
                new MovieDto { Id = 2, FolderLevels = "Other" },
            ],
            Total = 250,
        };

        var visibleMovies = BrowseLibraryPresenter.FilterExcludedMovies(movies, ["Series"], preserveTotal: true);

        Assert.Equal([2], visibleMovies.Movies.Select(movie => movie.Id).ToList());
        Assert.Equal(250, visibleMovies.Total);
    }

    [Fact]
    public void BrowsePresenterPreservesMovieTotalWhenNoFoldersAreExcluded()
    {
        var movies = new MoviesResponseDto
        {
            Movies =
            [
                new MovieDto { Id = 1, FolderLevels = "Series" },
                new MovieDto { Id = 2, FolderLevels = "Other" },
            ],
            Total = 250,
        };

        var visibleMovies = BrowseLibraryPresenter.FilterExcludedMovies(movies, []);

        Assert.Equal([1, 2], visibleMovies.Movies.Select(movie => movie.Id).ToList());
        Assert.Equal(250, visibleMovies.Total);
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
    public void MovieCardItemPublishesCoverUrlChangesAfterInitialRender()
    {
        var item = new MovieCardItem(new MovieDto { Id = 42, Code = "sample" }, "");
        var changed = new List<string>();
        item.PropertyChanged += (_, args) =>
        {
            if (args.PropertyName is not null)
            {
                changed.Add(args.PropertyName);
            }
        };

        item.CoverUrl = "https://example.invalid/cover.jpg";
        item.FallbackCoverUrl = "https://example.invalid/fallback.jpg";

        Assert.Equal("https://example.invalid/cover.jpg", item.CoverUrl);
        Assert.Equal("https://example.invalid/fallback.jpg", item.FallbackCoverUrl);
        Assert.Contains(nameof(MovieCardItem.CoverUrl), changed);
        Assert.Contains(nameof(MovieCardItem.FallbackCoverUrl), changed);
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
    public void FolderCardItemUsesVideoCountForEpisodeSubtitle()
    {
        var folder = new FolderNodeDto
        {
            Name = "Season 1",
            Path = "Series/Season 1",
            MovieCount = 1,
            VideoCount = 12,
        };

        var item = new FolderCardItem(folder, "");

        Assert.Equal(12, item.DisplayVideoCount);
        Assert.Equal("集", item.DisplayCountUnit);
        Assert.Equal("12 集", item.Subtitle);
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
        : this(new OneShotJsonResponse(200, responseJson))
    {
    }

    public OneShotJsonServer(params OneShotJsonResponse[] responses)
    {
        _listener = new System.Net.Sockets.TcpListener(IPAddress.Loopback, 0);
        _listener.Start();
        var port = ((IPEndPoint)_listener.LocalEndpoint).Port;
        BaseUri = new Uri($"http://127.0.0.1:{port}/");
        _task = Task.Run(async () =>
        {
            foreach (var response in responses)
            {
                using var client = await _listener.AcceptTcpClientAsync();
                await using var stream = client.GetStream();
                using var reader = new StreamReader(stream, leaveOpen: true);
                var requestLine = await reader.ReadLineAsync();
                RequestPaths.Add(requestLine?.Split(' ', StringSplitOptions.RemoveEmptyEntries).ElementAtOrDefault(1) ?? "");
                var contentLength = 0;
                var requestHeaders = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                string? header;
                while (!string.IsNullOrEmpty(header = await reader.ReadLineAsync()))
                {
                    var separator = header.IndexOf(':', StringComparison.Ordinal);
                    if (separator > 0)
                    {
                        requestHeaders[header[..separator]] = header[(separator + 1)..].Trim();
                    }

                    if (header.StartsWith("Content-Length:", StringComparison.OrdinalIgnoreCase)
                        && int.TryParse(header["Content-Length:".Length..].Trim(), out var parsedLength))
                    {
                        contentLength = parsedLength;
                    }
                }
                RequestHeaders.Add(requestHeaders);

                if (contentLength > 0)
                {
                    var body = new char[contentLength];
                    var read = 0;
                    while (read < contentLength)
                    {
                        var count = await reader.ReadAsync(body, read, contentLength - read);
                        if (count == 0)
                        {
                            break;
                        }

                        read += count;
                    }

                    RequestBodies.Add(new string(body, 0, read));
                }
                else
                {
                    RequestBodies.Add("");
                }

                var responseBytes = System.Text.Encoding.UTF8.GetBytes(response.Json);
                using var writer = new StreamWriter(stream, leaveOpen: true);
                await writer.WriteAsync(
                    $"HTTP/1.1 {response.StatusCode} OK\r\nContent-Type: application/json\r\nContent-Length: {responseBytes.Length}\r\nConnection: close\r\n\r\n");
                await writer.FlushAsync();
                await stream.WriteAsync(responseBytes);
            }
        });
    }

    public Uri BaseUri { get; }

    public List<string> RequestPaths { get; } = [];

    public List<string> RequestBodies { get; } = [];

    public List<Dictionary<string, string>> RequestHeaders { get; } = [];

    public string RequestPath => RequestPaths.FirstOrDefault() ?? "";

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

file sealed record OneShotJsonResponse(int StatusCode, string Json);

file sealed class TrackingMediaApiClient(Uri backendUri, Action onDispose) : IMediaApiClient
{
    public Uri BackendUri { get; private set; } = backendUri;

    public void SetBackendUri(Uri backendUri)
    {
        BackendUri = backendUri;
    }

    public void SetBearerToken(string token)
    {
    }

    public Task<AuthStatusDto> GetAuthStatusAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(new AuthStatusDto());

    public Task<AuthResponseDto> LoginAsync(string username, string password, CancellationToken cancellationToken = default)
        => Task.FromResult(new AuthResponseDto { Ok = true, Token = "token" });

    public Task<AuthResponseDto> SetupAuthAsync(string username, string password, CancellationToken cancellationToken = default)
        => LoginAsync(username, password, cancellationToken);

    public Task ChangePasswordAsync(string oldUsername, string oldPassword, string newUsername, string newPassword, CancellationToken cancellationToken = default)
        => Task.CompletedTask;

    public Task<SetupStatusDto> GetSetupStatusAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(new SetupStatusDto());

    public Task<MediaRootsResponseDto> GetMediaRootsAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(new MediaRootsResponseDto());

    public Task<List<LibrarySettingDto>> GetLibrarySettingsAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(new List<LibrarySettingDto>());

    public Task<FoldersResponseDto> GetFoldersAsync(string mediaRoot = "", CancellationToken cancellationToken = default)
        => Task.FromResult(new FoldersResponseDto());

    public Task SaveLibrarySettingAsync(LibrarySettingDto setting, CancellationToken cancellationToken = default)
        => Task.CompletedTask;

    public Task SetLibraryPasswordAsync(string mediaRoot, string password, CancellationToken cancellationToken = default)
        => Task.CompletedTask;

    public Task ScanAsync(string mediaRoot, CancellationToken cancellationToken = default)
        => Task.CompletedTask;

    public Task ClearLibraryAsync(string mediaRoot, CancellationToken cancellationToken = default)
        => Task.CompletedTask;

    public Task<ScanStatusDto> GetScanStatusAsync(string mediaRoot, CancellationToken cancellationToken = default)
        => Task.FromResult(new ScanStatusDto());

    public Task<ScanLogDto> GetScanLogAsync(string mediaRoot, int lines = 80, CancellationToken cancellationToken = default)
        => Task.FromResult(new ScanLogDto());

    public Task<ConfigDto> GetConfigAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(new ConfigDto());

    public Task SaveConfigAsync(IEnumerable<string> extraMediaRoots, CancellationToken cancellationToken = default)
        => Task.CompletedTask;

    public Task SaveTmdbConfigAsync(string accessToken, CancellationToken cancellationToken = default)
        => Task.CompletedTask;

    public Task SaveGlobalConfigAsync(ConfigDto config, CancellationToken cancellationToken = default)
        => Task.CompletedTask;

    public Uri BuildBackupUri(string backupType)
        => BackendUri;

    public Task<byte[]> DownloadBackupAsync(string backupType, CancellationToken cancellationToken = default)
        => Task.FromResult(Array.Empty<byte>());

    public Task RestoreBackupAsync(string filePath, CancellationToken cancellationToken = default)
        => Task.CompletedTask;

    public Task<MoviesResponseDto> GetMoviesAsync(string mediaRoot, string folder, string search, string sort, int limit, int offset, CancellationToken cancellationToken = default)
        => Task.FromResult(new MoviesResponseDto());

    public Task<MoviesResponseDto> GetRecentWatchedAsync(string mediaRoot, int limit, int offset, CancellationToken cancellationToken = default)
        => Task.FromResult(new MoviesResponseDto());

    public Task<MoviesResponseDto> GetFavoritesAsync(string mediaRoot, string sort, int limit, int offset, CancellationToken cancellationToken = default)
        => Task.FromResult(new MoviesResponseDto());

    public Task<FolderSpecialsResponseDto> GetFolderSpecialsAsync(string folder, string mediaRoot, bool includeMovies = false, CancellationToken cancellationToken = default)
        => Task.FromResult(new FolderSpecialsResponseDto());

    public Task<FolderSpecialsResponseDto> SetFolderSpecialsAsync(string folder, string mediaRoot, bool showSpecials, CancellationToken cancellationToken = default)
        => Task.FromResult(new FolderSpecialsResponseDto());

    public Task<SearchScrapeResponseDto> SearchScrapeAsync(string query, string scraper, string mediaRoot, CancellationToken cancellationToken = default)
        => Task.FromResult(new SearchScrapeResponseDto());

    public Task<ManualScrapeResultDto> ManualScrapeMovieAsync(int movieId, string query, string sourceId, string mediaType, string scraper, CancellationToken cancellationToken = default)
        => Task.FromResult(new ManualScrapeResultDto());

    public Task<BasicActionResultDto> RescrapeMovieAsync(int movieId, CancellationToken cancellationToken = default)
        => Task.FromResult(new BasicActionResultDto());

    public Task<BasicActionResultDto> RescrapeFolderAsync(string folder, string mediaRoot, CancellationToken cancellationToken = default)
        => Task.FromResult(new BasicActionResultDto());

    public Task<BasicActionResultDto> ApplyFolderScrapeAsync(string folder, string mediaRoot, string sourceId, string source, string mediaType, CancellationToken cancellationToken = default)
        => Task.FromResult(new BasicActionResultDto());

    public Task<AlternativeCoversResponseDto> GetAlternativeCoversAsync(int movieId, CancellationToken cancellationToken = default)
        => Task.FromResult(new AlternativeCoversResponseDto());

    public Task<BasicActionResultDto> ChangeMovieCoverAsync(int movieId, string url, CancellationToken cancellationToken = default)
        => Task.FromResult(new BasicActionResultDto());

    public Task<BasicActionResultDto> UploadMovieCoverAsync(int movieId, string filePath, CancellationToken cancellationToken = default)
        => Task.FromResult(new BasicActionResultDto());

    public Task<BasicActionResultDto> ChangeFolderCoverAsync(string folder, string mediaRoot, string url, CancellationToken cancellationToken = default)
        => Task.FromResult(new BasicActionResultDto());

    public Task<BasicActionResultDto> EditMovieAsync(int movieId, string title, string code, string actress, string releaseDate, int? duration, CancellationToken cancellationToken = default)
        => Task.FromResult(new BasicActionResultDto());

    public Task<BasicActionResultDto> EditFolderAsync(string folder, string mediaRoot, string title, string code, string actress, string releaseDate, int? duration, CancellationToken cancellationToken = default)
        => Task.FromResult(new BasicActionResultDto());

    public Task<BasicActionResultDto> DeleteMovieAsync(int movieId, CancellationToken cancellationToken = default)
        => Task.FromResult(new BasicActionResultDto());

    public Task<BasicActionResultDto> DeleteFolderAsync(string folder, string mediaRoot, CancellationToken cancellationToken = default)
        => Task.FromResult(new BasicActionResultDto());

    public Task AddTagAsync(int movieId, string tag, CancellationToken cancellationToken = default)
        => Task.CompletedTask;

    public Task RemoveTagAsync(int movieId, string tag, CancellationToken cancellationToken = default)
        => Task.CompletedTask;

    public Task<MovieDto> GetMovieDetailAsync(int movieId, CancellationToken cancellationToken = default)
        => Task.FromResult(new MovieDto { Id = movieId });

    public Task<ProgressDto> GetProgressAsync(int movieId, CancellationToken cancellationToken = default)
        => Task.FromResult(new ProgressDto());

    public Task<ProgressDto> SaveProgressAsync(int movieId, double position, double? duration, bool stopped, CancellationToken cancellationToken = default)
        => Task.FromResult(new ProgressDto());

    public Task<string> EnsureMediaTokenAsync(CancellationToken cancellationToken = default)
        => Task.FromResult("token");

    public Task<string> BuildCoverUrlAsync(int movieId, CancellationToken cancellationToken = default)
        => Task.FromResult("");

    public Task<string> BuildEpisodeStillUrlAsync(int movieId, CancellationToken cancellationToken = default)
        => Task.FromResult("");

    public Task<string> BuildMediaAssetUrlAsync(string source, CancellationToken cancellationToken = default)
        => Task.FromResult(source);

    public Task<string> BuildStreamUrlAsync(int movieId, CancellationToken cancellationToken = default)
        => Task.FromResult(new Uri(BackendUri, $"stream/{movieId}").ToString());

    public Task<MediaPlaybackSource> BuildPlaybackSourceAsync(int movieId, CancellationToken cancellationToken = default)
        => Task.FromResult(new MediaPlaybackSource(new Uri(BackendUri, $"stream/{movieId}").ToString()));

    public Task<VersionInfoDto> GetVersionAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(new VersionInfoDto());

    public Task<UpdateCheckResultDto> CheckForUpdatesAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(new UpdateCheckResultDto());

    public Task<UpdateStatusDto> GetUpdateStatusAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(new UpdateStatusDto());

    public Task<UpdateActionResultDto> PerformUpdateAsync(string version, string mode = "app-package", CancellationToken cancellationToken = default)
        => Task.FromResult(new UpdateActionResultDto());

    public Task<UpdateActionResultDto> RollbackUpdateAsync(CancellationToken cancellationToken = default)
        => Task.FromResult(new UpdateActionResultDto());

    public Task<ChangelogDto> GetChangelogAsync(string version, CancellationToken cancellationToken = default)
        => Task.FromResult(new ChangelogDto());

    public void Dispose()
    {
        onDispose();
    }
}
