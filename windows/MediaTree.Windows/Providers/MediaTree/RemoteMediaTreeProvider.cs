using System;
using MediaTree.Windows.Services;

namespace MediaTree.Windows.Providers;

public sealed class RemoteMediaTreeProvider : IMediaTreeProvider
{
    public RemoteMediaTreeProvider(MediaSourceProfile profile, MediaTreeServices services, MediaSourceCredentials credentials)
    {
        ArgumentNullException.ThrowIfNull(profile);
        if (profile.Kind != MediaSourceKind.RemoteMediaTree)
        {
            throw new ArgumentException("RemoteMediaTreeProvider requires a RemoteMediaTree profile.", nameof(profile));
        }

        Profile = profile;
        Services = services ?? throw new ArgumentNullException(nameof(services));
        Credentials = credentials ?? throw new ArgumentNullException(nameof(credentials));
    }

    public MediaSourceProfile Profile { get; }
    public MediaTreeServices Services { get; }
    public MediaSourceCredentials Credentials { get; }
    public IMediaApiClient Api => Services.Api;
    public AuthSessionService Auth => Services.Auth;
    public LibraryService Library => Services.Library;
    public MovieService Movie => Services.Movie;
    public UpdateService Updates => Services.Updates;
    public PlaybackProgressService PlaybackProgress => Services.PlaybackProgress;
}
