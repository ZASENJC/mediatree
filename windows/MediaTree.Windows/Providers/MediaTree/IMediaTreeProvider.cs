using MediaTree.Windows.Services;

namespace MediaTree.Windows.Providers;

public interface IMediaTreeProvider : IMediaProvider
{
    MediaTreeApiClient Api { get; }
    AuthSessionService Auth { get; }
    LibraryService Library { get; }
    MovieService Movie { get; }
    UpdateService Updates { get; }
    PlaybackProgressService PlaybackProgress { get; }
}
