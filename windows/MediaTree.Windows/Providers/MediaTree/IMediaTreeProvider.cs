using MediaTree.Windows.Services;

namespace MediaTree.Windows.Providers;

public interface IMediaTreeProvider : IMediaProvider
{
    IMediaApiClient Api => Services.Api;
    AuthSessionService Auth => Services.Auth;
    LibraryService Library => Services.Library;
    MovieService Movie => Services.Movie;
    UpdateService Updates => Services.Updates;
    PlaybackProgressService PlaybackProgress => Services.PlaybackProgress;
}
