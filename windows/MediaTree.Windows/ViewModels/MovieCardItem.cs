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
    public string Title => Movie.BestTitle;
    public string Subtitle => string.IsNullOrWhiteSpace(Movie.ReleaseDate) ? Movie.Genre : Movie.ReleaseDate;
    public string CoverUrl { get; }
    public string ProgressText => Movie.ProgressPercent > 0 ? $"{Movie.ProgressPercent:0}%" : "";
}

