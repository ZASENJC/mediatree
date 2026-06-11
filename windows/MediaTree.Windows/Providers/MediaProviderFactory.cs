using System;

namespace MediaTree.Windows.Providers;

public static class MediaProviderFactory
{
    public static IMediaTreeProvider CreateLocalMediaTree(MediaTreeServices services)
        => new LocalMediaTreeProvider(services);

    public static IMediaProvider Create(MediaSourceProfile profile)
    {
        ArgumentNullException.ThrowIfNull(profile);

        return profile.Kind switch
        {
            MediaSourceKind.RemoteMediaTree => throw ProviderNotImplemented(profile.Kind),
            MediaSourceKind.Jellyfin => throw ProviderNotImplemented(profile.Kind),
            MediaSourceKind.Emby => throw ProviderNotImplemented(profile.Kind),
            MediaSourceKind.LocalMediaTree => throw new InvalidOperationException(
                "LocalMediaTree provider requires MediaTreeServices. Use CreateLocalMediaTree instead."),
            _ => throw new NotSupportedException($"Media source kind {profile.Kind} is not supported."),
        };
    }

    private static NotSupportedException ProviderNotImplemented(MediaSourceKind kind)
        => new($"Media provider {kind} is not implemented yet.");
}
