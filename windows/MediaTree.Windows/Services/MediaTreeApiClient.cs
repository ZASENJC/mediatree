using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace MediaTree.Windows.Services;

public sealed partial class MediaTreeApiClient : IDisposable
{
    private readonly HttpClient _httpClient;
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
    };
    private string _token = "";
    private string _mediaToken = "";
    private long _mediaTokenExpiresAt;

    public MediaTreeApiClient(Uri backendUri)
    {
        BackendUri = backendUri;
        _httpClient = new HttpClient
        {
            Timeout = TimeSpan.FromMinutes(10),
        };
    }

    public Uri BackendUri { get; private set; }

    public void SetBackendUri(Uri backendUri)
    {
        BackendUri = backendUri;
    }

    public void SetBearerToken(string token)
    {
        _token = token ?? "";
        _mediaToken = "";
        _mediaTokenExpiresAt = 0;
    }

    private async Task<T> GetAsync<T>(string path, CancellationToken cancellationToken)
    {
        using var request = CreateRequest(HttpMethod.Get, path);
        return await SendAsync<T>(request, cancellationToken);
    }

    private async Task<T> PostJsonAsync<T>(string path, object body, CancellationToken cancellationToken)
    {
        using var request = CreateRequest(HttpMethod.Post, path);
        request.Content = JsonContent.Create(body, options: _jsonOptions);
        return await SendAsync<T>(request, cancellationToken);
    }

    private async Task<T> PutJsonAsync<T>(string path, object body, CancellationToken cancellationToken)
    {
        using var request = CreateRequest(HttpMethod.Put, path);
        request.Content = JsonContent.Create(body, options: _jsonOptions);
        return await SendAsync<T>(request, cancellationToken);
    }

    private async Task<T> DeleteAsync<T>(string path, CancellationToken cancellationToken)
    {
        using var request = CreateRequest(HttpMethod.Delete, path);
        return await SendAsync<T>(request, cancellationToken);
    }

    private static string NormalizeTmdbAccessToken(string accessToken)
    {
        var value = (accessToken ?? "").Trim();
        return value.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase) ? value[7..].Trim() : value;
    }

    private static string NormalizeManualScraper(string scraper)
    {
        var value = (scraper ?? "").Trim().ToLowerInvariant();
        return value switch
        {
            "tmdb" => "tmdb_movie",
            "auto" or "tmdb_movie" or "tmdb_tv" or "tmdb_collection" or "bangumi" or "javdatabase" => value,
            _ => "auto",
        };
    }

    private static void PutIfNotNull(Dictionary<string, object?> body, string key, string value)
    {
        if (!string.IsNullOrWhiteSpace(value))
        {
            body[key] = value.Trim();
        }
    }

    private HttpRequestMessage CreateRequest(HttpMethod method, string path)
    {
        var normalized = path.TrimStart('/');
        var apiBase = new Uri(BackendUri, "api/");
        var request = new HttpRequestMessage(method, new Uri(apiBase, normalized));
        if (!string.IsNullOrWhiteSpace(_token))
        {
            request.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", _token);
        }

        return request;
    }

    private async Task<T> SendAsync<T>(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        using var response = await _httpClient.SendAsync(request, cancellationToken);
        if (response.StatusCode == HttpStatusCode.Unauthorized)
        {
            throw new UnauthorizedAccessException("MediaTree session is not authorized.");
        }

        if (!response.IsSuccessStatusCode)
        {
            var body = await response.Content.ReadAsStringAsync(cancellationToken);
            throw new InvalidOperationException($"MediaTree API failed ({(int)response.StatusCode}): {body}");
        }

        if (typeof(T) == typeof(JsonElement))
        {
            var element = await response.Content.ReadFromJsonAsync<JsonElement>(_jsonOptions, cancellationToken);
            return (T)(object)element;
        }

        var result = await response.Content.ReadFromJsonAsync<T>(_jsonOptions, cancellationToken);
        return result ?? throw new InvalidDataException($"MediaTree API returned an empty {typeof(T).Name} response.");
    }

    public void Dispose()
    {
        _httpClient.Dispose();
    }
}
