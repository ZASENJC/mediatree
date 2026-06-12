using System;
using System.Collections.Generic;

namespace MediaTree.Windows.Services;

public sealed class MediaPlaybackSource
{
    public MediaPlaybackSource(string uri, IReadOnlyDictionary<string, string>? headers = null)
    {
        if (string.IsNullOrWhiteSpace(uri))
        {
            throw new ArgumentException("Playback source URI is required.", nameof(uri));
        }

        Uri = uri;
        Headers = headers ?? new Dictionary<string, string>();
    }

    public string Uri { get; }

    public IReadOnlyDictionary<string, string> Headers { get; }
}
