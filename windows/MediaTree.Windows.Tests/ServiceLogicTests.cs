using MediaTree.Windows.Models;
using MediaTree.Windows.Services;
using System;
using System.IO;
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
            }, path);

            var json = File.ReadAllText(path);
            Assert.Contains("hideHomeTitleText", json);
            Assert.Contains("showSourceName", json);

            var preferences = UiPreferenceStore.Load(path);
            Assert.True(preferences.HideHomeTitleText);
            Assert.True(preferences.ShowSourceName);
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
