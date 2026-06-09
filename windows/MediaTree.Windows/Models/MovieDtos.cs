using System.Collections.Generic;
using System.Globalization;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace MediaTree.Windows.Models;

public sealed class MoviesResponseDto
{
    [JsonPropertyName("movies")]
    public List<MovieDto> Movies { get; set; } = [];

    [JsonPropertyName("total")]
    public int Total { get; set; }
}

public sealed class MovieDto
{
    [JsonPropertyName("id")]
    public int Id { get; set; }

    [JsonPropertyName("path")]
    public string Path { get; set; } = "";

    [JsonPropertyName("code")]
    public string Code { get; set; } = "";

    [JsonPropertyName("title")]
    public string Title { get; set; } = "";

    [JsonPropertyName("display_title")]
    public string DisplayTitle { get; set; } = "";

    [JsonPropertyName("original_title")]
    public string OriginalTitle { get; set; } = "";

    [JsonPropertyName("overview")]
    public string Overview { get; set; } = "";

    [JsonPropertyName("actress")]
    public string Actress { get; set; } = "";

    [JsonPropertyName("release_date")]
    public string ReleaseDate { get; set; } = "";

    [JsonPropertyName("duration")]
    [JsonConverter(typeof(NullToZeroDoubleConverter))]
    public double Duration { get; set; }

    [JsonPropertyName("media_root")]
    public string MediaRoot { get; set; } = "";

    [JsonPropertyName("genre")]
    public string Genre { get; set; } = "";

    [JsonPropertyName("content_rating")]
    public string ContentRating { get; set; } = "";

    [JsonPropertyName("folder_levels")]
    public string FolderLevels { get; set; } = "";

    [JsonPropertyName("tmdb_type")]
    public string TmdbType { get; set; } = "";

    [JsonPropertyName("tmdb_id")]
    [JsonConverter(typeof(NullToNullableIntConverter))]
    public int? TmdbId { get; set; }

    [JsonPropertyName("tmdb_season")]
    [JsonConverter(typeof(NullToNullableIntConverter))]
    public int? TmdbSeason { get; set; }

    [JsonPropertyName("tmdb_episode")]
    [JsonConverter(typeof(NullToNullableIntConverter))]
    public int? TmdbEpisode { get; set; }

    [JsonPropertyName("episode_number")]
    [JsonConverter(typeof(NullToNullableIntConverter))]
    public int? EpisodeNumber { get; set; }

    [JsonPropertyName("episode_title")]
    public string EpisodeTitle { get; set; } = "";

    [JsonPropertyName("episode_still")]
    public string EpisodeStill { get; set; } = "";

    [JsonPropertyName("episode_label")]
    public string EpisodeLabel { get; set; } = "";

    [JsonPropertyName("clean_title")]
    public string CleanTitle { get; set; } = "";

    [JsonPropertyName("scraper_source")]
    public string ScraperSource { get; set; } = "";

    [JsonPropertyName("source_id")]
    public string SourceId { get; set; } = "";

    [JsonPropertyName("cover_remote")]
    public string CoverRemote { get; set; } = "";

    [JsonPropertyName("cover_local")]
    public string CoverLocal { get; set; } = "";

    [JsonPropertyName("content_role")]
    public string ContentRole { get; set; } = "main";

    [JsonPropertyName("special_parent_levels")]
    public string SpecialParentLevels { get; set; } = "";

    [JsonPropertyName("playback_position")]
    [JsonConverter(typeof(NullToZeroDoubleConverter))]
    public double PlaybackPosition { get; set; }

    [JsonPropertyName("progress_percent")]
    [JsonConverter(typeof(NullToZeroDoubleConverter))]
    public double ProgressPercent { get; set; }

    [JsonPropertyName("tags")]
    public List<string> Tags { get; set; } = [];

    [JsonIgnore]
    public bool IsSpecial => string.Equals(ContentRole, "special", System.StringComparison.OrdinalIgnoreCase);

    [JsonIgnore]
    public string BestTitle => IsSpecial
        ? FirstNonEmpty(System.IO.Path.GetFileNameWithoutExtension(Path), DisplayTitle, Title, CleanTitle, Code)
        : FirstNonEmpty(DisplayTitle, Title, OriginalTitle, CleanTitle, Code, System.IO.Path.GetFileNameWithoutExtension(Path));

    [JsonIgnore]
    public string FolderForSpecials => IsSpecial
        ? FirstNonEmpty(SpecialParentLevels, ParentFolder(FolderLevels))
        : FolderLevels;

    private static string FirstNonEmpty(params string[] values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
            {
                return value;
            }
        }

        return "未命名影片";
    }

    private static string ParentFolder(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        var normalized = value.Replace("\\", "/").TrimEnd('/');
        var index = normalized.LastIndexOf("/", System.StringComparison.Ordinal);
        return index <= 0 ? "" : normalized[..index];
    }
}

public sealed class FolderSpecialsResponseDto
{
    [JsonPropertyName("show_specials")]
    public bool ShowSpecials { get; set; }

    [JsonPropertyName("special_count")]
    public int SpecialCount { get; set; }

    [JsonPropertyName("movies")]
    public List<MovieDto> Movies { get; set; } = [];
}

public sealed class ProgressDto
{
    [JsonPropertyName("position")]
    [JsonConverter(typeof(NullToZeroDoubleConverter))]
    public double Position { get; set; }

    [JsonPropertyName("played")]
    public bool Played { get; set; }

    [JsonPropertyName("progress_percent")]
    [JsonConverter(typeof(NullToZeroDoubleConverter))]
    public double ProgressPercent { get; set; }
}

internal sealed class NullToZeroDoubleConverter : JsonConverter<double>
{
    public override double Read(ref Utf8JsonReader reader, System.Type typeToConvert, JsonSerializerOptions options)
    {
        if (reader.TokenType == JsonTokenType.Null)
        {
            return 0;
        }

        if (reader.TokenType == JsonTokenType.Number)
        {
            return reader.GetDouble();
        }

        if (reader.TokenType == JsonTokenType.String &&
            double.TryParse(reader.GetString(), NumberStyles.Float, CultureInfo.InvariantCulture, out var value))
        {
            return value;
        }

        throw new JsonException($"Cannot convert {reader.TokenType} to double.");
    }

    public override void Write(Utf8JsonWriter writer, double value, JsonSerializerOptions options)
    {
        writer.WriteNumberValue(value);
    }
}

internal sealed class NullToNullableIntConverter : JsonConverter<int?>
{
    public override int? Read(ref Utf8JsonReader reader, System.Type typeToConvert, JsonSerializerOptions options)
    {
        if (reader.TokenType == JsonTokenType.Null)
        {
            return null;
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
            if (string.IsNullOrWhiteSpace(value))
            {
                return null;
            }

            if (int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var intValue))
            {
                return intValue;
            }

            if (double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var doubleValue))
            {
                return (int)doubleValue;
            }
        }

        throw new JsonException($"Cannot convert {reader.TokenType} to nullable int.");
    }

    public override void Write(Utf8JsonWriter writer, int? value, JsonSerializerOptions options)
    {
        if (value.HasValue)
        {
            writer.WriteNumberValue(value.Value);
        }
        else
        {
            writer.WriteNullValue();
        }
    }
}
