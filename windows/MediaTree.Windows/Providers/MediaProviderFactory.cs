using System;
using System.Threading;
using System.Threading.Tasks;
using MediaTree.Windows.Services;

namespace MediaTree.Windows.Providers;

public static class MediaProviderFactory
{
    public static IMediaTreeProvider CreateLocalMediaTree(MediaTreeServices services)
        => new LocalMediaTreeProvider(services);

    public static IMediaProvider Create(MediaSourceProfile profile, MediaSourceCredentials? credentials = null)
    {
        ArgumentNullException.ThrowIfNull(profile);

        return profile.Kind switch
        {
            MediaSourceKind.RemoteMediaTree => CreateRemoteMediaTree(profile, credentials ?? throw new ArgumentNullException(nameof(credentials))),
            MediaSourceKind.Jellyfin => throw ProviderNotImplemented(profile.Kind),
            MediaSourceKind.Emby => throw ProviderNotImplemented(profile.Kind),
            MediaSourceKind.LocalMediaTree => throw new InvalidOperationException(
                "LocalMediaTree provider requires MediaTreeServices. Use CreateLocalMediaTree instead."),
            _ => throw new NotSupportedException($"Media source kind {profile.Kind} is not supported."),
        };
    }

    public static RemoteMediaTreeProvider CreateRemoteMediaTree(MediaSourceProfile profile, MediaSourceCredentials credentials)
    {
        ArgumentNullException.ThrowIfNull(profile);
        ArgumentNullException.ThrowIfNull(credentials);
        if (profile.Kind != MediaSourceKind.RemoteMediaTree)
        {
            throw new ArgumentException("Remote MediaTree provider requires a RemoteMediaTree profile.", nameof(profile));
        }

        var endpoint = profile.Endpoint ?? throw new ArgumentException("Remote MediaTree endpoint is required.", nameof(profile));
        var api = new MediaTreeApiClient(endpoint);
        var services = CreateMediaTreeServices(api);
        return new RemoteMediaTreeProvider(profile, services, credentials);
    }

    public static async Task<RemoteMediaTreeProvider> CreateRemoteMediaTreeAsync(
        MediaSourceProfile profile,
        MediaSourceCredentials credentials,
        CancellationToken cancellationToken = default)
    {
        var provider = CreateRemoteMediaTree(profile, credentials);
        var api = provider.Api;
        var response = await api.LoginAsync(credentials.Username, credentials.Secret, cancellationToken);
        api.SetBearerToken(response.Token);
        return provider;
    }

    public static MediaTreeServices CreateMediaTreeServices(MediaTreeApiClient api)
    {
        return new MediaTreeServices(
            api,
            new AuthSessionService(api),
            new LibraryService(api),
            new MovieService(api),
            new UpdateService(api),
            new PlaybackProgressService(api));
    }

    private static NotSupportedException ProviderNotImplemented(MediaSourceKind kind)
        => new($"Media provider {kind} is not implemented yet.");
}
