using System;
using MediaTree.Windows.Services;

namespace MediaTree.Windows.Providers;

public sealed class MediaTreeServices
{
    public MediaTreeServices(
        IMediaApiClient api,
        AuthSessionService auth,
        LibraryService library,
        MovieService movie,
        UpdateService updates,
        PlaybackProgressService playbackProgress)
    {
        Api = api ?? throw new ArgumentNullException(nameof(api));
        Auth = auth ?? throw new ArgumentNullException(nameof(auth));
        Library = library ?? throw new ArgumentNullException(nameof(library));
        Movie = movie ?? throw new ArgumentNullException(nameof(movie));
        Updates = updates ?? throw new ArgumentNullException(nameof(updates));
        PlaybackProgress = playbackProgress ?? throw new ArgumentNullException(nameof(playbackProgress));
    }

    public IMediaApiClient Api { get; }
    public AuthSessionService Auth { get; }
    public LibraryService Library { get; }
    public MovieService Movie { get; }
    public UpdateService Updates { get; }
    public PlaybackProgressService PlaybackProgress { get; }
}
