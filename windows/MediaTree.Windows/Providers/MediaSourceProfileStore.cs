using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace MediaTree.Windows.Providers;

public sealed record MediaSourceProfileState(
    string ActiveSourceId,
    List<MediaSourceProfileRecord> Sources);

public sealed record MediaSourceProfileRecord(
    string Id,
    MediaSourceKind Kind,
    string DisplayName,
    string Endpoint,
    bool RequiresBundledBackend);

public static class MediaSourceProfileStore
{
    public const string LocalSourceId = "local-mediatree";

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        Converters = { new JsonStringEnumConverter() },
    };

    public static MediaSourceProfileState Load()
        => Load(SourcesFilePath);

    public static MediaSourceProfileState Load(string filePath)
    {
        try
        {
            if (!File.Exists(filePath))
            {
                return DefaultState();
            }

            var json = File.ReadAllText(filePath);
            var state = JsonSerializer.Deserialize<MediaSourceProfileState>(json, JsonOptions);
            return NormalizeState(state);
        }
        catch
        {
            return DefaultState();
        }
    }

    public static MediaSourceProfileRecord UpsertExternalSource(
        MediaSourceKind kind,
        string displayName,
        Uri endpoint)
        => UpsertExternalSource(kind, displayName, endpoint, SourcesFilePath);

    public static MediaSourceProfileRecord UpsertExternalSource(
        MediaSourceKind kind,
        string displayName,
        Uri endpoint,
        string filePath)
    {
        if (kind == MediaSourceKind.LocalMediaTree)
        {
            throw new ArgumentException("Local MediaTree is managed by the bundled backend source.", nameof(kind));
        }

        var profile = kind switch
        {
            MediaSourceKind.RemoteMediaTree => MediaSourceProfile.RemoteMediaTree(displayName, endpoint),
            MediaSourceKind.Jellyfin => MediaSourceProfile.Jellyfin(displayName, endpoint),
            MediaSourceKind.Emby => MediaSourceProfile.Emby(displayName, endpoint),
            _ => throw new NotSupportedException($"Media source kind {kind} is not supported."),
        };
        var record = ToRecord(profile);
        var state = Load(filePath);
        state.Sources.RemoveAll(source => source.Id == record.Id);
        state.Sources.Add(record);
        Save(state, filePath);
        return record;
    }

    public static MediaSourceProfileState SetActiveSource(string sourceId)
        => SetActiveSource(sourceId, SourcesFilePath);

    public static MediaSourceProfileState SetActiveSource(string sourceId, string filePath)
    {
        if (string.IsNullOrWhiteSpace(sourceId))
        {
            throw new ArgumentException("Media source id is required.", nameof(sourceId));
        }

        var state = Load(filePath);
        var active = state.Sources.FirstOrDefault(source => string.Equals(source.Id, sourceId, StringComparison.OrdinalIgnoreCase))
            ?? throw new ArgumentException("Media source must be saved before it can be activated.", nameof(sourceId));
        var next = new MediaSourceProfileState(active.Id, state.Sources);
        Save(next, filePath);
        return Load(filePath);
    }

    public static MediaSourceProfileState RemoveSource(string sourceId)
        => RemoveSource(sourceId, SourcesFilePath);

    public static MediaSourceProfileState RemoveSource(string sourceId, string filePath)
    {
        if (string.IsNullOrWhiteSpace(sourceId))
        {
            throw new ArgumentException("Media source id is required.", nameof(sourceId));
        }

        if (string.Equals(sourceId, LocalSourceId, StringComparison.OrdinalIgnoreCase))
        {
            throw new ArgumentException("The bundled local MediaTree source cannot be removed.", nameof(sourceId));
        }

        var state = Load(filePath);
        var removed = state.Sources.RemoveAll(source => string.Equals(source.Id, sourceId, StringComparison.OrdinalIgnoreCase));
        if (removed == 0)
        {
            throw new ArgumentException("Media source does not exist.", nameof(sourceId));
        }

        var activeSourceId = string.Equals(state.ActiveSourceId, sourceId, StringComparison.OrdinalIgnoreCase)
            ? LocalSourceId
            : state.ActiveSourceId;
        Save(new MediaSourceProfileState(activeSourceId, state.Sources), filePath);
        return Load(filePath);
    }

    private static void Save(MediaSourceProfileState state, string filePath)
    {
        var directory = Path.GetDirectoryName(filePath);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        File.WriteAllText(filePath, JsonSerializer.Serialize(NormalizeState(state), JsonOptions));
    }

    private static MediaSourceProfileState NormalizeState(MediaSourceProfileState? state)
    {
        var sources = state?.Sources ?? [];
        var normalized = sources
            .Where(source => source is not null)
            .Where(source => !string.IsNullOrWhiteSpace(source.Id))
            .GroupBy(source => source.Id, StringComparer.OrdinalIgnoreCase)
            .Select(group => group.Last())
            .ToList();
        if (normalized.All(source => source.Id != LocalSourceId))
        {
            normalized.Insert(0, LocalRecord());
        }

        var activeSourceId = string.IsNullOrWhiteSpace(state?.ActiveSourceId)
            ? LocalSourceId
            : state.ActiveSourceId;
        if (normalized.All(source => !string.Equals(source.Id, activeSourceId, StringComparison.OrdinalIgnoreCase)))
        {
            activeSourceId = LocalSourceId;
        }

        return new MediaSourceProfileState(activeSourceId, normalized);
    }

    private static MediaSourceProfileState DefaultState()
        => new(LocalSourceId, [LocalRecord()]);

    private static MediaSourceProfileRecord LocalRecord()
        => new(LocalSourceId, MediaSourceKind.LocalMediaTree, "本机 MediaTree", "", RequiresBundledBackend: true);

    private static MediaSourceProfileRecord ToRecord(MediaSourceProfile profile)
        => new(
            IdFor(profile.Kind, profile.Endpoint),
            profile.Kind,
            profile.DisplayName,
            profile.Endpoint?.ToString() ?? "",
            profile.RequiresBundledBackend);

    private static string IdFor(MediaSourceKind kind, Uri? endpoint)
        => $"{kind}:{endpoint?.ToString().Trim().ToLowerInvariant()}";

    private static string SourcesFilePath => Path.Combine(AppPaths.WindowsStateDirectory, "media-sources.json");
}
