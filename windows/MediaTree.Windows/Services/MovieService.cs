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

    public Task<MovieDto> GetMovieDetailAsync(int movieId, CancellationToken cancellationToken = default)
        => _api.GetMovieDetailAsync(movieId, cancellationToken);

    public Task<ProgressDto> GetProgressAsync(int movieId, CancellationToken cancellationToken = default)
        => _api.GetProgressAsync(movieId, cancellationToken);

    public Task RemoveTagAsync(int movieId, string tag, CancellationToken cancellationToken = default)
        => _api.RemoveTagAsync(movieId, tag, cancellationToken);
}
