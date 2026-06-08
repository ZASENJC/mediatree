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

    [JsonPropertyName("playback_position")]
    [JsonConverter(typeof(NullToZeroDoubleConverter))]
    public double PlaybackPosition { get; set; }

    [JsonPropertyName("progress_percent")]
    [JsonConverter(typeof(NullToZeroDoubleConverter))]
    public double ProgressPercent { get; set; }

    [JsonIgnore]
    public string BestTitle => FirstNonEmpty(DisplayTitle, Title, OriginalTitle, Code, System.IO.Path.GetFileNameWithoutExtension(Path));

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
