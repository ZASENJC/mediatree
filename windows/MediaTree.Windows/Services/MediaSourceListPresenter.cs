using System;
using System.Collections.Generic;
using System.Linq;
using MediaTree.Windows.Providers;

namespace MediaTree.Windows.Services;

public sealed record MediaSourceListItem(
    string Id,
    MediaSourceKind Kind,
    string DisplayName,
    string Endpoint,
    bool RequiresBundledBackend,
    bool IsActive);

public sealed record MediaSourceGroupState(
    MediaSourceKind Kind,
    string Title,
    IReadOnlyList<MediaSourceListItem> Sources);

public static class MediaSourceListPresenter
{
    private static readonly IReadOnlyList<(MediaSourceKind Kind, string Title)> GroupOrder =
    [
        (MediaSourceKind.LocalMediaTree, "本机 MediaTree"),
        (MediaSourceKind.RemoteMediaTree, "MediaTree 远程"),
        (MediaSourceKind.Jellyfin, "Jellyfin"),
        (MediaSourceKind.Emby, "Emby"),
    ];

    public static IReadOnlyList<MediaSourceGroupState> BuildGroups(MediaSourceProfileState state)
    {
        ArgumentNullException.ThrowIfNull(state);
        var sources = BuildItems(state);
        return GroupOrder
            .Select(group => new MediaSourceGroupState(
                group.Kind,
                group.Title,
                sources
                    .Where(source => source.Kind == group.Kind)
                    .ToList()))
            .Where(group => group.Sources.Count > 0)
            .ToList();
    }

    public static IReadOnlyList<MediaSourceListItem> BuildItems(MediaSourceProfileState state)
    {
        ArgumentNullException.ThrowIfNull(state);
        var sources = state.Sources ?? [];
        return sources
            .Select(source => new MediaSourceListItem(
                source.Id,
                source.Kind,
                source.DisplayName,
                source.Endpoint,
                source.RequiresBundledBackend,
                string.Equals(source.Id, state.ActiveSourceId, StringComparison.OrdinalIgnoreCase)))
            .OrderBy(source => GroupIndex(source.Kind))
            .ThenBy(source => source.DisplayName, StringComparer.CurrentCultureIgnoreCase)
            .ThenBy(source => source.Endpoint, StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    private static int GroupIndex(MediaSourceKind kind)
    {
        for (var index = 0; index < GroupOrder.Count; index++)
        {
            if (GroupOrder[index].Kind == kind)
            {
                return index;
            }
        }

        return GroupOrder.Count;
    }
}
