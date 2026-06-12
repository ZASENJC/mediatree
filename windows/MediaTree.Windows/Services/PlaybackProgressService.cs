using System;
using System.Threading;
using System.Threading.Tasks;

namespace MediaTree.Windows.Services;

public sealed class PlaybackProgressService
{
    private const double WatchedRatio = 0.9;
    private readonly IMediaApiClient _api;

    public PlaybackProgressService(IMediaApiClient api)
    {
        _api = api;
    }

    public bool ShouldMarkWatched(double position, double duration)
    {
        return duration > 0 && position >= Math.Max(60, duration * WatchedRatio);
    }

    public Task SaveAsync(int movieId, double position, double duration, bool stopped, CancellationToken cancellationToken = default)
    {
        return _api.SaveProgressAsync(movieId, Math.Max(0, position), duration > 0 ? duration : null, stopped, cancellationToken);
    }
}
