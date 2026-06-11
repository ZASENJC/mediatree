using System;

namespace MediaTree.Windows.Providers;

public sealed record MediaSourceProfile(
    MediaSourceKind Kind,
    string DisplayName,
    Uri? Endpoint,
    bool RequiresBundledBackend)
{
    public static MediaSourceProfile LocalMediaTree(Uri endpoint)
        => new(MediaSourceKind.LocalMediaTree, "本机 MediaTree", RequireEndpoint(endpoint), RequiresBundledBackend: true);

    public static MediaSourceProfile RemoteMediaTree(string displayName, Uri endpoint)
        => Remote(MediaSourceKind.RemoteMediaTree, displayName, endpoint);

    public static MediaSourceProfile Jellyfin(string displayName, Uri endpoint)
        => Remote(MediaSourceKind.Jellyfin, displayName, endpoint);

    public static MediaSourceProfile Emby(string displayName, Uri endpoint)
        => Remote(MediaSourceKind.Emby, displayName, endpoint);

    private static MediaSourceProfile Remote(MediaSourceKind kind, string displayName, Uri endpoint)
        => new(kind, RequireDisplayName(displayName), RequireEndpoint(endpoint), RequiresBundledBackend: false);

    private static string RequireDisplayName(string displayName)
    {
        if (string.IsNullOrWhiteSpace(displayName))
        {
            throw new ArgumentException("Media source display name is required.", nameof(displayName));
        }

        return displayName.Trim();
    }

    private static Uri RequireEndpoint(Uri endpoint)
        => endpoint ?? throw new ArgumentNullException(nameof(endpoint));
}
