using System;
using System.Threading;
using System.Threading.Tasks;
using MediaTree.Windows.Services;

namespace MediaTree.Windows.Providers;

public static class MediaSourceActivator
{
    public static async Task<IMediaProvider> CreateProviderAsync(
        MediaSourceProfileRecord source,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(source);
        if (source.Kind == MediaSourceKind.LocalMediaTree)
        {
            throw new ArgumentException("Local MediaTree activation requires the existing bundled provider.", nameof(source));
        }

        if (string.IsNullOrWhiteSpace(source.Endpoint) || !Uri.TryCreate(source.Endpoint, UriKind.Absolute, out var endpoint))
        {
            throw new ArgumentException("Media source endpoint is invalid.", nameof(source));
        }

        var credentials = MediaSourceCredentialStore.Load(source.Id)
            ?? throw new InvalidOperationException("Media source credentials are not saved.");
        var profile = new MediaSourceProfile(source.Kind, source.DisplayName, endpoint, source.RequiresBundledBackend);
        return await CreateProviderAsync(profile, credentials, cancellationToken);
    }

    public static async Task<IMediaProvider> CreateProviderAsync(
        MediaSourceProfile profile,
        MediaSourceCredentials credentials,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(profile);
        ArgumentNullException.ThrowIfNull(credentials);
        return profile.Kind switch
        {
            MediaSourceKind.RemoteMediaTree => await MediaProviderFactory.CreateRemoteMediaTreeAsync(profile, credentials, cancellationToken),
            MediaSourceKind.Jellyfin or MediaSourceKind.Emby => await MediaProviderFactory.CreateJellyfinCompatibleAsync(profile, credentials, cancellationToken),
            _ => throw new NotSupportedException($"Media source kind {profile.Kind} cannot be activated here."),
        };
    }
}
