using System.Threading;
using System.Threading.Tasks;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.Services;

public sealed class MovieService
{
    private readonly MediaTreeApiClient _api;

    public MovieService(MediaTreeApiClient api)
    {
        _api = api;
    }

    public Task<MoviesResponseDto> GetMoviesAsync(string mediaRoot, string search, string sort, int limit, int offset, CancellationToken cancellationToken = default)
        => _api.GetMoviesAsync(mediaRoot, "", search, sort, limit, offset, cancellationToken);

    public Task<MoviesResponseDto> GetMoviesAsync(string mediaRoot, string folder, string search, string sort, int limit, int offset, CancellationToken cancellationToken = default)
        => _api.GetMoviesAsync(mediaRoot, folder, search, sort, limit, offset, cancellationToken);

    public Task<MoviesResponseDto> GetRecentWatchedAsync(string mediaRoot, int limit, int offset, CancellationToken cancellationToken = default)
        => _api.GetRecentWatchedAsync(mediaRoot, limit, offset, cancellationToken);

    public Task<MoviesResponseDto> GetFavoritesAsync(string mediaRoot, string sort, int limit, int offset, CancellationToken cancellationToken = default)
        => _api.GetFavoritesAsync(mediaRoot, sort, limit, offset, cancellationToken);

    public Task<FolderSpecialsResponseDto> GetFolderSpecialsAsync(string folder, string mediaRoot, bool includeMovies = false, CancellationToken cancellationToken = default)
        => _api.GetFolderSpecialsAsync(folder, mediaRoot, includeMovies, cancellationToken);

    public Task<FolderSpecialsResponseDto> SetFolderSpecialsAsync(string folder, string mediaRoot, bool showSpecials, CancellationToken cancellationToken = default)
        => _api.SetFolderSpecialsAsync(folder, mediaRoot, showSpecials, cancellationToken);

    public Task<SearchScrapeResponseDto> SearchScrapeAsync(string query, string scraper, string mediaRoot, CancellationToken cancellationToken = default)
        => _api.SearchScrapeAsync(query, scraper, mediaRoot, cancellationToken);

    public Task<ManualScrapeResultDto> ManualScrapeMovieAsync(int movieId, string query, string sourceId, string mediaType, string scraper, CancellationToken cancellationToken = default)
        => _api.ManualScrapeMovieAsync(movieId, query, sourceId, mediaType, scraper, cancellationToken);

    public Task<BasicActionResultDto> RescrapeMovieAsync(int movieId, CancellationToken cancellationToken = default)
        => _api.RescrapeMovieAsync(movieId, cancellationToken);

    public Task<BasicActionResultDto> RescrapeFolderAsync(string folder, string mediaRoot, CancellationToken cancellationToken = default)
        => _api.RescrapeFolderAsync(folder, mediaRoot, cancellationToken);

    public Task<BasicActionResultDto> ApplyFolderScrapeAsync(string folder, string mediaRoot, string sourceId, string source, string mediaType, CancellationToken cancellationToken = default)
        => _api.ApplyFolderScrapeAsync(folder, mediaRoot, sourceId, source, mediaType, cancellationToken);

    public Task<AlternativeCoversResponseDto> GetAlternativeCoversAsync(int movieId, CancellationToken cancellationToken = default)
        => _api.GetAlternativeCoversAsync(movieId, cancellationToken);

    public Task<BasicActionResultDto> ChangeMovieCoverAsync(int movieId, string url, CancellationToken cancellationToken = default)
        => _api.ChangeMovieCoverAsync(movieId, url, cancellationToken);

    public Task<BasicActionResultDto> UploadMovieCoverAsync(int movieId, string filePath, CancellationToken cancellationToken = default)
        => _api.UploadMovieCoverAsync(movieId, filePath, cancellationToken);

    public Task<BasicActionResultDto> ChangeFolderCoverAsync(string folder, string mediaRoot, string url, CancellationToken cancellationToken = default)
        => _api.ChangeFolderCoverAsync(folder, mediaRoot, url, cancellationToken);

    public Task<BasicActionResultDto> EditMovieAsync(int movieId, string title, string code, string actress, string releaseDate, int? duration, CancellationToken cancellationToken = default)
        => _api.EditMovieAsync(movieId, title, code, actress, releaseDate, duration, cancellationToken);

    public Task<BasicActionResultDto> EditFolderAsync(string folder, string mediaRoot, string title, string code, string actress, string releaseDate, int? duration, CancellationToken cancellationToken = default)
        => _api.EditFolderAsync(folder, mediaRoot, title, code, actress, releaseDate, duration, cancellationToken);

    public Task<BasicActionResultDto> DeleteMovieAsync(int movieId, CancellationToken cancellationToken = default)
        => _api.DeleteMovieAsync(movieId, cancellationToken);

    public Task<BasicActionResultDto> DeleteFolderAsync(string folder, string mediaRoot, CancellationToken cancellationToken = default)
        => _api.DeleteFolderAsync(folder, mediaRoot, cancellationToken);

    public Task<MovieDto> GetMovieDetailAsync(int movieId, CancellationToken cancellationToken = default)
        => _api.GetMovieDetailAsync(movieId, cancellationToken);

    public Task<ProgressDto> GetProgressAsync(int movieId, CancellationToken cancellationToken = default)
        => _api.GetProgressAsync(movieId, cancellationToken);

    public Task AddTagAsync(int movieId, string tag, CancellationToken cancellationToken = default)
        => _api.AddTagAsync(movieId, tag, cancellationToken);

    public Task RemoveTagAsync(int movieId, string tag, CancellationToken cancellationToken = default)
        => _api.RemoveTagAsync(movieId, tag, cancellationToken);
}
