using System;
using MediaTree.Windows.Services;

namespace MediaTree.Windows.Providers;

public sealed class LocalMediaTreeProvider : IMediaTreeProvider
{
    public LocalMediaTreeProvider(MediaTreeServices services)
    {
        Services = services ?? throw new ArgumentNullException(nameof(services));
    }

    public MediaSourceProfile Profile => MediaSourceProfile.LocalMediaTree(Services.Api.BackendUri);
    public MediaTreeServices Services { get; }
    public IMediaApiClient Api => Services.Api;
    public AuthSessionService Auth => Services.Auth;
    public LibraryService Library => Services.Library;
    public MovieService Movie => Services.Movie;
    public UpdateService Updates => Services.Updates;
    public PlaybackProgressService PlaybackProgress => Services.PlaybackProgress;
}
