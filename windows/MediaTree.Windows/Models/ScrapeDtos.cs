using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace MediaTree.Windows.Models;

public sealed class SearchScrapeResponseDto
{
    [JsonPropertyName("results")]
    public List<ScrapeSearchResultDto> Results { get; set; } = [];
}

public sealed class ScrapeSearchResultDto
{
    [JsonPropertyName("source")]
    public string Source { get; set; } = "";

    [JsonPropertyName("source_id")]
    public string SourceId { get; set; } = "";

    [JsonPropertyName("media_type")]
    public string MediaType { get; set; } = "movie";

    [JsonPropertyName("title")]
    public string Title { get; set; } = "";

    [JsonPropertyName("original_title")]
    public string OriginalTitle { get; set; } = "";

    [JsonPropertyName("year")]
    public string Year { get; set; } = "";

    [JsonPropertyName("poster_url")]
    public string PosterUrl { get; set; } = "";

    [JsonPropertyName("overview")]
    public string Overview { get; set; } = "";

    [JsonPropertyName("scraper")]
    public string Scraper { get; set; } = "";
}

public sealed class ManualScrapeResultDto
{
    [JsonPropertyName("ok")]
    public bool Ok { get; set; }

    [JsonPropertyName("source")]
    public string Source { get; set; } = "";

    [JsonPropertyName("title")]
    public string Title { get; set; } = "";
}

public sealed class AlternativeCoversResponseDto
{
    [JsonPropertyName("covers")]
    public List<CoverChoiceDto> Covers { get; set; } = [];
}

public sealed class CoverChoiceDto
{
    [JsonPropertyName("url")]
    public string Url { get; set; } = "";

    [JsonPropertyName("source")]
    public string Source { get; set; } = "";

    [JsonPropertyName("width")]
    public int? Width { get; set; }

    [JsonPropertyName("height")]
    public int? Height { get; set; }

    [JsonPropertyName("language")]
    public string Language { get; set; } = "";

    [JsonPropertyName("vote_count")]
    public int? VoteCount { get; set; }
}

public sealed class BasicActionResultDto
{
    [JsonPropertyName("ok")]
    public bool Ok { get; set; }

    [JsonPropertyName("title")]
    public string Title { get; set; } = "";

    [JsonPropertyName("source")]
    public string Source { get; set; } = "";

    [JsonPropertyName("affected")]
    public int? Affected { get; set; }

    [JsonPropertyName("deleted")]
    public int? Deleted { get; set; }
}
