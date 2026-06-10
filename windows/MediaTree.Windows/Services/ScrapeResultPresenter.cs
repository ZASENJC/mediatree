using System;
using System.Collections.Generic;
using System.Linq;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.Services;

public static class ScrapeResultPresenter
{
    public static ScrapeSearchResultDto NormalizeScraper(ScrapeSearchResultDto result, string fallbackScraper)
    {
        if (string.IsNullOrWhiteSpace(result.Scraper))
        {
            result.Scraper = fallbackScraper;
        }

        return result;
    }

    public static string DisplayTitle(ScrapeSearchResultDto result)
        => !string.IsNullOrWhiteSpace(result.Title) ? result.Title : result.SourceId;

    public static IReadOnlyList<string> MetadataParts(ScrapeSearchResultDto result)
        => new[] { result.Source, result.MediaType, result.Year, result.OriginalTitle }
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .ToList();

    public static bool HasPoster(ScrapeSearchResultDto result)
        => !string.IsNullOrWhiteSpace(result.PosterUrl);

    public static string SanitizeAutomationId(string value)
        => (value ?? string.Empty).Replace("\\", "_").Replace("/", "_").Replace(":", "_");
}
