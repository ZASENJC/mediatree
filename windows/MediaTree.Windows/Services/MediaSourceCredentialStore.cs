using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace MediaTree.Windows.Services;

public sealed record MediaSourceCredentials(string Username, string Secret);

public static class MediaSourceCredentialStore
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
    };

    public static MediaSourceCredentials? Load(string sourceId)
        => Load(sourceId, CredentialsFilePath);

    public static MediaSourceCredentials? Load(string sourceId, string filePath)
    {
        RequireSourceId(sourceId);
        try
        {
            var state = LoadState(filePath);
            var entry = state.Sources.FirstOrDefault(source => string.Equals(source.SourceId, sourceId, StringComparison.OrdinalIgnoreCase));
            if (entry is null || string.IsNullOrWhiteSpace(entry.Payload))
            {
                return null;
            }

            var protectedBytes = Convert.FromBase64String(entry.Payload);
            var bytes = ProtectedData.Unprotect(protectedBytes, null, DataProtectionScope.CurrentUser);
            return JsonSerializer.Deserialize<MediaSourceCredentials>(Encoding.UTF8.GetString(bytes));
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load protected media source credentials.");
            return null;
        }
    }

    public static void Save(string sourceId, MediaSourceCredentials credentials)
        => Save(sourceId, credentials, CredentialsFilePath);

    public static void Save(string sourceId, MediaSourceCredentials credentials, string filePath)
    {
        RequireSourceId(sourceId);
        ArgumentNullException.ThrowIfNull(credentials);
        if (string.IsNullOrWhiteSpace(credentials.Username))
        {
            throw new ArgumentException("Media source username is required.", nameof(credentials));
        }

        if (string.IsNullOrEmpty(credentials.Secret))
        {
            throw new ArgumentException("Media source secret is required.", nameof(credentials));
        }

        var state = LoadState(filePath);
        state.Sources.RemoveAll(source => string.Equals(source.SourceId, sourceId, StringComparison.OrdinalIgnoreCase));
        var bytes = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(credentials));
        var protectedBytes = ProtectedData.Protect(bytes, null, DataProtectionScope.CurrentUser);
        state.Sources.Add(new ProtectedMediaSourceCredentials(sourceId, Convert.ToBase64String(protectedBytes)));
        SaveState(state, filePath);
    }

    public static void Clear(string sourceId)
        => Clear(sourceId, CredentialsFilePath);

    public static void Clear(string sourceId, string filePath)
    {
        RequireSourceId(sourceId);
        var state = LoadState(filePath);
        state.Sources.RemoveAll(source => string.Equals(source.SourceId, sourceId, StringComparison.OrdinalIgnoreCase));
        SaveState(state, filePath);
    }

    private static void RequireSourceId(string sourceId)
    {
        if (string.IsNullOrWhiteSpace(sourceId))
        {
            throw new ArgumentException("Media source id is required.", nameof(sourceId));
        }
    }

    private static MediaSourceCredentialState LoadState(string filePath)
    {
        try
        {
            if (!File.Exists(filePath))
            {
                return new MediaSourceCredentialState([]);
            }

            var state = JsonSerializer.Deserialize<MediaSourceCredentialState>(File.ReadAllText(filePath, Encoding.UTF8), JsonOptions);
            return new MediaSourceCredentialState((state?.Sources ?? [])
                .Where(source => source is not null)
                .Where(source => !string.IsNullOrWhiteSpace(source.SourceId))
                .GroupBy(source => source.SourceId, StringComparer.OrdinalIgnoreCase)
                .Select(group => group.Last())
                .ToList());
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load media source credential state.");
            return new MediaSourceCredentialState([]);
        }
    }

    private static void SaveState(MediaSourceCredentialState state, string filePath)
    {
        var directory = Path.GetDirectoryName(filePath);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        File.WriteAllText(filePath, JsonSerializer.Serialize(state, JsonOptions), Encoding.UTF8);
    }

    private static string CredentialsFilePath => Path.Combine(AppPaths.WindowsStateDirectory, "media-source-credentials.dpapi.json");

    private sealed record MediaSourceCredentialState(List<ProtectedMediaSourceCredentials> Sources);

    private sealed record ProtectedMediaSourceCredentials(string SourceId, string Payload);
}
