using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.Services;

public sealed partial class MediaTreeApiClient
{
    public async Task<string> EnsureMediaTokenAsync(CancellationToken cancellationToken = default)
    {
        var now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        if (!string.IsNullOrWhiteSpace(_mediaToken) && _mediaTokenExpiresAt > now + 60)
        {
            return _mediaToken;
        }

        var response = await PostJsonAsync<MediaTokenResponseDto>("/media-token", new { }, cancellationToken);
        _mediaToken = response.Token;
        _mediaTokenExpiresAt = response.ExpiresAt;
        return _mediaToken;
    }

    public async Task<string> BuildCoverUrlAsync(int movieId, CancellationToken cancellationToken = default)
    {
        var token = await EnsureMediaTokenAsync(cancellationToken);
        return new Uri(BackendUri, $"api/cover/{movieId}?token={Uri.EscapeDataString(token)}").ToString();
    }

    public async Task<string> BuildEpisodeStillUrlAsync(int movieId, CancellationToken cancellationToken = default)
    {
        var token = await EnsureMediaTokenAsync(cancellationToken);
        return new Uri(BackendUri, $"api/episode-still/{movieId}?token={Uri.EscapeDataString(token)}").ToString();
    }

    public async Task<string> BuildMediaAssetUrlAsync(string source, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(source))
        {
            return "";
        }

        if (Uri.TryCreate(source, UriKind.Absolute, out var absoluteUri))
        {
            return absoluteUri.ToString();
        }

        if (source.StartsWith("/api/", StringComparison.OrdinalIgnoreCase))
        {
            var token = await EnsureMediaTokenAsync(cancellationToken);
            var separator = source.Contains('?') ? "&" : "?";
            return new Uri(BackendUri, $"{source.TrimStart('/')}{separator}token={Uri.EscapeDataString(token)}").ToString();
        }

        var tokenForMedia = await EnsureMediaTokenAsync(cancellationToken);
        var normalized = source.Replace("\\", "/").TrimStart('/');
        var encoded = string.Join("/", normalized.Split('/').Select(Uri.EscapeDataString));
        return new Uri(BackendUri, $"api/media/{encoded}?token={Uri.EscapeDataString(tokenForMedia)}").ToString();
    }

    public async Task<string> BuildStreamUrlAsync(int movieId, CancellationToken cancellationToken = default)
    {
        var token = await EnsureMediaTokenAsync(cancellationToken);
        return new Uri(BackendUri, $"api/stream/{movieId}?token={Uri.EscapeDataString(token)}").ToString();
    }

    public async Task<MediaPlaybackSource> BuildPlaybackSourceAsync(int movieId, CancellationToken cancellationToken = default)
        => new(await BuildStreamUrlAsync(movieId, cancellationToken));
}
