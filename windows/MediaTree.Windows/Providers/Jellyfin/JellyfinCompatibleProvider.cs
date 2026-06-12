using System;
using MediaTree.Windows.Services;

namespace MediaTree.Windows.Providers.Jellyfin;

public sealed class JellyfinCompatibleProvider : IMediaProvider
{
    public JellyfinCompatibleProvider(MediaSourceProfile profile, MediaTreeServices services, MediaSourceCredentials credentials)
    {
        if (profile.Kind is not (MediaSourceKind.Jellyfin or MediaSourceKind.Emby))
        {
            throw new ArgumentException("Jellyfin compatible provider requires a Jellyfin or Emby profile.", nameof(profile));
        }

        Profile = profile;
        Services = services ?? throw new ArgumentNullException(nameof(services));
        Credentials = credentials ?? throw new ArgumentNullException(nameof(credentials));
    }

    public MediaSourceProfile Profile { get; }

    public MediaTreeServices Services { get; }

    public MediaSourceCredentials Credentials { get; }

    public JellyfinCompatibleApiClient Api => (JellyfinCompatibleApiClient)Services.Api;
}
