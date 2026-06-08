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
