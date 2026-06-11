using System;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace MediaTree.Windows.Services;

public sealed partial class MediaTreeApiClient
{
    public Uri BuildBackupUri(string backupType)
        => new(BackendUri, $"api/backup?backup_type={Uri.EscapeDataString(backupType)}");

    public async Task<byte[]> DownloadBackupAsync(string backupType, CancellationToken cancellationToken = default)
    {
        using var request = CreateRequest(HttpMethod.Get, $"/backup?backup_type={Uri.EscapeDataString(backupType)}");
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

        return await response.Content.ReadAsByteArrayAsync(cancellationToken);
    }

    public async Task RestoreBackupAsync(string filePath, CancellationToken cancellationToken = default)
    {
        await using var stream = File.OpenRead(filePath);
        using var request = CreateRequest(HttpMethod.Post, "/restore/upload");
        using var content = new MultipartFormDataContent();
        content.Add(new StreamContent(stream), "file", Path.GetFileName(filePath));
        request.Content = content;
        await SendAsync<JsonElement>(request, cancellationToken);
    }
}
