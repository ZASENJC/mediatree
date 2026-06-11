using System;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using MediaTree.Windows.Providers;

namespace MediaTree.Windows.Services;

public sealed record MediaSourceConnectionTestResult(bool Succeeded, string Message);

public sealed class MediaSourceConnectionTester : IDisposable
{
    private readonly HttpClient _httpClient;
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
    };

    public MediaSourceConnectionTester()
    {
        _httpClient = new HttpClient
        {
            Timeout = TimeSpan.FromSeconds(15),
        };
    }

    public async Task<MediaSourceConnectionTestResult> TestAsync(
        MediaSourceKind kind,
        Uri endpoint,
        MediaSourceCredentials credentials,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(endpoint);
        ArgumentNullException.ThrowIfNull(credentials);
        if (string.IsNullOrWhiteSpace(credentials.Username) || string.IsNullOrEmpty(credentials.Secret))
        {
            return new MediaSourceConnectionTestResult(false, "用户名和密码 / token 需要一起填写。");
        }

        try
        {
            return kind switch
            {
                MediaSourceKind.RemoteMediaTree => await TestRemoteMediaTreeAsync(endpoint, credentials, cancellationToken),
                MediaSourceKind.Jellyfin or MediaSourceKind.Emby => await TestJellyfinCompatibleAsync(endpoint, credentials, cancellationToken),
                _ => new MediaSourceConnectionTestResult(false, "本机目录不需要远程连接测试。"),
            };
        }
        catch (OperationCanceledException)
        {
            return new MediaSourceConnectionTestResult(false, "连接测试已取消或超时。");
        }
        catch (HttpRequestException ex)
        {
            return new MediaSourceConnectionTestResult(false, $"连接失败：{ex.Message}");
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Media source connection test failed.");
            return new MediaSourceConnectionTestResult(false, $"连接测试失败：{ex.Message}");
        }
    }

    public async Task<MediaSourceConnectionTestResult> TestRemoteMediaTreeAsync(
        Uri endpoint,
        MediaSourceCredentials credentials,
        CancellationToken cancellationToken = default)
    {
        using var healthRequest = new HttpRequestMessage(HttpMethod.Get, Resolve(endpoint, "/api/health"));
        using var healthResponse = await _httpClient.SendAsync(healthRequest, cancellationToken);
        if (!healthResponse.IsSuccessStatusCode)
        {
            return new MediaSourceConnectionTestResult(false, $"MediaTree 健康检查失败：HTTP {(int)healthResponse.StatusCode}");
        }

        using var loginRequest = new HttpRequestMessage(HttpMethod.Post, Resolve(endpoint, "/api/auth/login"))
        {
            Content = JsonBody(new
            {
                username = credentials.Username,
                password = credentials.Secret,
            }),
        };
        using var loginResponse = await _httpClient.SendAsync(loginRequest, cancellationToken);
        if (loginResponse.StatusCode == HttpStatusCode.Unauthorized)
        {
            return new MediaSourceConnectionTestResult(false, "MediaTree 登录失败：账号或密码不正确。");
        }

        if (!loginResponse.IsSuccessStatusCode)
        {
            return new MediaSourceConnectionTestResult(false, $"MediaTree 登录失败：HTTP {(int)loginResponse.StatusCode}");
        }

        var auth = await ReadJsonAsync<MediaTreeLoginResponse>(loginResponse, cancellationToken);
        return string.IsNullOrWhiteSpace(auth.Token)
            ? new MediaSourceConnectionTestResult(false, "MediaTree 登录响应缺少 token。")
            : new MediaSourceConnectionTestResult(true, "MediaTree 远程连接测试通过。");
    }

    public async Task<MediaSourceConnectionTestResult> TestJellyfinCompatibleAsync(
        Uri endpoint,
        MediaSourceCredentials credentials,
        CancellationToken cancellationToken = default)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, Resolve(endpoint, "/Users/AuthenticateByName"))
        {
            Content = JsonBody(new
            {
                Username = credentials.Username,
                Pw = credentials.Secret,
            }),
        };
        using var response = await _httpClient.SendAsync(request, cancellationToken);
        if (response.StatusCode == HttpStatusCode.Unauthorized)
        {
            return new MediaSourceConnectionTestResult(false, "媒体库登录失败：账号或密码不正确。");
        }

        if (!response.IsSuccessStatusCode)
        {
            return new MediaSourceConnectionTestResult(false, $"媒体库登录失败：HTTP {(int)response.StatusCode}");
        }

        var auth = await ReadJsonAsync<JellyfinCompatibleLoginResponse>(response, cancellationToken);
        return string.IsNullOrWhiteSpace(auth.AccessToken)
            ? new MediaSourceConnectionTestResult(false, "媒体库登录响应缺少 AccessToken。")
            : new MediaSourceConnectionTestResult(true, "媒体库连接测试通过。");
    }

    private async Task<T> ReadJsonAsync<T>(HttpResponseMessage response, CancellationToken cancellationToken)
    {
        var result = await response.Content.ReadFromJsonAsync<T>(_jsonOptions, cancellationToken);
        return result ?? throw new InvalidDataException($"Media source returned an empty {typeof(T).Name} response.");
    }

    private static Uri Resolve(Uri endpoint, string relativePath)
    {
        var baseText = endpoint.ToString();
        if (!baseText.EndsWith("/", StringComparison.Ordinal))
        {
            baseText += "/";
        }

        return new Uri(new Uri(baseText), relativePath.TrimStart('/'));
    }

    private StringContent JsonBody(object body)
        => new(JsonSerializer.Serialize(body, _jsonOptions), Encoding.UTF8, "application/json");

    public void Dispose()
    {
        _httpClient.Dispose();
    }

    private sealed class MediaTreeLoginResponse
    {
        public string Token { get; set; } = "";
    }

    private sealed class JellyfinCompatibleLoginResponse
    {
        public string AccessToken { get; set; } = "";
    }
}
