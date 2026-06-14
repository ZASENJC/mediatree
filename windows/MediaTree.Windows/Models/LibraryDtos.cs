using System.Collections.Generic;
using System.Globalization;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace MediaTree.Windows.Models;

public sealed class MediaRootsResponseDto
{
    [JsonPropertyName("items")]
    public List<MediaRootDto> Items { get; set; } = [];
}

public sealed class FoldersResponseDto
{
    [JsonPropertyName("tree")]
    public List<FolderNodeDto> Tree { get; set; } = [];
}

public sealed class FolderNodeDto
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = "";

    [JsonPropertyName("path")]
    public string Path { get; set; } = "";

    [JsonPropertyName("children")]
    public List<FolderNodeDto> Children { get; set; } = [];

    [JsonPropertyName("movie_count")]
    public int MovieCount { get; set; }

    [JsonPropertyName("video_count")]
    public int VideoCount { get; set; }

    [JsonPropertyName("cover")]
    public string Cover { get; set; } = "";

    [JsonPropertyName("random_cover")]
    public string RandomCover { get; set; } = "";

    [JsonPropertyName("backdrop")]
    public string Backdrop { get; set; } = "";

    [JsonPropertyName("is_leaf")]
    public bool IsLeaf { get; set; }

    [JsonIgnore]
    public int MovieId { get; set; }

    [JsonPropertyName("media_root")]
    public string MediaRoot { get; set; } = "";

    [JsonPropertyName("created_max")]
    public string CreatedMax { get; set; } = "";

    [JsonPropertyName("release_date_max")]
    public string ReleaseDateMax { get; set; } = "";

    [JsonPropertyName("watched_count")]
    public int WatchedCount { get; set; }

    [JsonPropertyName("folder_watched")]
    public bool FolderWatched { get; set; }

    [JsonPropertyName("progress_percent")]
    [JsonConverter(typeof(NullToZeroDoubleConverter))]
    public double ProgressPercent { get; set; }

    [JsonPropertyName("tmdb_id")]
    public int? TmdbId { get; set; }

    [JsonPropertyName("tmdb_type")]
    public string TmdbType { get; set; } = "";

    [JsonPropertyName("special_count")]
    public int SpecialCount { get; set; }

    [JsonPropertyName("show_specials")]
    public bool ShowSpecials { get; set; }

    [JsonPropertyName("display_title")]
    public string DisplayTitle { get; set; } = "";

    [JsonIgnore]
    public string BestTitle => string.IsNullOrWhiteSpace(DisplayTitle) ? Name : DisplayTitle;
}

public sealed class MediaRootDto
{
    [JsonPropertyName("path")]
    public string Path { get; set; } = "";

    [JsonPropertyName("label")]
    public string Label { get; set; } = "";

    [JsonPropertyName("movie_count")]
    public int MovieCount { get; set; }

    [JsonPropertyName("locked")]
    public bool Locked { get; set; }

    [JsonPropertyName("scraper")]
    public string Scraper { get; set; } = "auto";
}

public sealed class LibrarySettingDto
{
    [JsonPropertyName("media_root")]
    public string MediaRoot { get; set; } = "";

    [JsonPropertyName("scraper")]
    public string Scraper { get; set; } = "auto";

    [JsonPropertyName("tmdb_key")]
    public string TmdbKey { get; set; } = "";

    [JsonPropertyName("enabled")]
    public int Enabled { get; set; } = 1;
}

public sealed class SetupStatusDto
{
    [JsonPropertyName("needs_setup")]
    public bool NeedsSetup { get; set; }

    [JsonPropertyName("roots")]
    public List<string> Roots { get; set; } = [];
}

public sealed class ConfigDto
{
    [JsonPropertyName("extra_media_roots")]
    public List<string> ExtraMediaRoots { get; set; } = [];

    [JsonPropertyName("media_root")]
    public string MediaRoot { get; set; } = "";

    [JsonPropertyName("javdb_enabled")]
    public bool JavdbEnabled { get; set; } = true;

    [JsonPropertyName("javdb_cache_hours")]
    [JsonConverter(typeof(FlexibleIntConverter))]
    public int JavdbCacheHours { get; set; } = 24;

    [JsonPropertyName("tmdb_cache_hours")]
    [JsonConverter(typeof(FlexibleIntConverter))]
    public int TmdbCacheHours { get; set; } = 168;

    [JsonPropertyName("bangumi_cache_hours")]
    [JsonConverter(typeof(FlexibleIntConverter))]
    public int BangumiCacheHours { get; set; } = 168;

    [JsonPropertyName("tmdb_api_key")]
    public string TmdbApiKey { get; set; } = "";

    [JsonPropertyName("tmdb_access_token")]
    public string TmdbAccessToken { get; set; } = "";

    [JsonPropertyName("tmdb_configured")]
    public bool TmdbConfigured { get; set; }

    [JsonPropertyName("javdb_request_interval")]
    [JsonConverter(typeof(FlexibleIntConverter))]
    public int JavdbRequestInterval { get; set; } = 3;

    [JsonPropertyName("update_check_enabled")]
    public bool UpdateCheckEnabled { get; set; } = true;

    [JsonPropertyName("update_check_interval_hours")]
    [JsonConverter(typeof(FlexibleIntConverter))]
    public int UpdateCheckIntervalHours { get; set; } = 24;
}

internal sealed class FlexibleIntConverter : JsonConverter<int>
{
    public override int Read(ref Utf8JsonReader reader, System.Type typeToConvert, JsonSerializerOptions options)
    {
        if (reader.TokenType == JsonTokenType.Null)
        {
            return 0;
        }

        if (reader.TokenType == JsonTokenType.Number)
        {
            if (reader.TryGetInt32(out var intValue))
            {
                return intValue;
            }

            return (int)reader.GetDouble();
        }

        if (reader.TokenType == JsonTokenType.String)
        {
            var value = reader.GetString();
            if (int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var intValue))
            {
                return intValue;
            }

            if (double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var doubleValue))
            {
                return (int)doubleValue;
            }
        }

        throw new JsonException($"Cannot convert {reader.TokenType} to int.");
    }

    public override void Write(Utf8JsonWriter writer, int value, JsonSerializerOptions options)
    {
        writer.WriteNumberValue(value);
    }
}

public sealed class ScanStatusDto
{
    [JsonPropertyName("media_root")]
    public string MediaRoot { get; set; } = "";

    [JsonPropertyName("status")]
    public string Status { get; set; } = "idle";

    [JsonPropertyName("done")]
    public int Done { get; set; }

    [JsonPropertyName("total")]
    public int Total { get; set; }
}

public sealed class ScanLogDto
{
    [JsonPropertyName("lines")]
    public List<string> Lines { get; set; } = [];

    [JsonPropertyName("total")]
    public int Total { get; set; }
}

public sealed class ScanResultDto
{
    [JsonPropertyName("media_root")]
    public string MediaRoot { get; set; } = "";

    [JsonPropertyName("files")]
    public int Files { get; set; }

    [JsonPropertyName("ok")]
    public bool Ok { get; set; } = true;
}
