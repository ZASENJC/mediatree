using System;
using CommunityToolkit.Mvvm.ComponentModel;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.ViewModels;

public sealed partial class MovieCardItem : ObservableObject
{
    public MovieCardItem(MovieDto movie, string coverUrl)
    {
        Movie = movie;
        CoverUrl = coverUrl;
    }

    public MovieDto Movie { get; }
    public int Id => Movie.Id;
    public bool IsSpecial => Movie.IsSpecial;
    public bool IsEpisode => !IsSpecial && string.Equals(Movie.TmdbType, "tv", StringComparison.OrdinalIgnoreCase) && Movie.TmdbEpisode.HasValue;
    public bool HasEpisodeStill => IsEpisode && !string.IsNullOrWhiteSpace(Movie.EpisodeStill);
    public string Title => IsEpisode
        ? $"E{Movie.TmdbEpisode.GetValueOrDefault():00} {FirstNonEmpty(Movie.EpisodeTitle, Movie.Title, Movie.Code)}"
        : Movie.BestTitle;
    public string Subtitle => IsSpecial
        ? string.IsNullOrWhiteSpace(Movie.FolderLevels) ? "花絮" : Movie.FolderLevels
        : IsEpisode ? Movie.Code : string.IsNullOrWhiteSpace(Movie.ReleaseDate) ? Movie.Genre : Movie.ReleaseDate;
    public string CoverUrl { get; }
    public string FallbackCoverUrl { get; init; } = "";
    public string ProgressText => Movie.ProgressPercent > 0 ? $"{Movie.ProgressPercent:0}%" : "";

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
