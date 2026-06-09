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
