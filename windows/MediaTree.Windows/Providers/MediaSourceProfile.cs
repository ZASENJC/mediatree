using System;

namespace MediaTree.Windows.Providers;

public sealed record MediaSourceProfile(
    MediaSourceKind Kind,
    string DisplayName,
    Uri? Endpoint,
    bool RequiresBundledBackend)
{
    public static MediaSourceProfile LocalMediaTree(Uri endpoint)
        => new(MediaSourceKind.LocalMediaTree, "本机 MediaTree", endpoint, RequiresBundledBackend: true);
}
