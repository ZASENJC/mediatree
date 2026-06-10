using System;
using System.Collections.Generic;
using System.Linq;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.Services;

public sealed record BrowseFolderTreeItem(FolderNodeDto Folder, int Depth);
public sealed record BrowseFolderTreeNodeState(FolderNodeDto Folder, int Depth, bool IsExpanded, bool IsIncluded);

public static class BrowseFolderTreePresenter
{
    public const int DefaultExpandedDepth = 2;

    public static IReadOnlyList<BrowseFolderTreeItem> FlattenAll(
        IEnumerable<FolderNodeDto> folders,
        Func<IEnumerable<FolderNodeDto>, IEnumerable<FolderNodeDto>>? orderFolders = null)
        => FlattenAll(folders, "", orderFolders);

    public static IReadOnlyList<BrowseFolderTreeItem> FlattenForMediaRoot(
        string mediaRoot,
        IEnumerable<FolderNodeDto> folders,
        Func<IEnumerable<FolderNodeDto>, IEnumerable<FolderNodeDto>>? orderFolders = null)
        => FlattenAll(folders, mediaRoot, orderFolders);

    public static IReadOnlyList<BrowseFolderTreeNodeState> VisibleNodeStatesForMediaRoot(
        string mediaRoot,
        IEnumerable<FolderNodeDto> folders,
        ISet<string> excludedPaths,
        ISet<string> expandedKeys,
        ISet<string> collapsedKeys,
        Func<IEnumerable<FolderNodeDto>, IEnumerable<FolderNodeDto>>? orderFolders = null)
    {
        var items = new List<BrowseFolderTreeNodeState>();
        foreach (var folder in Order(folders, orderFolders))
        {
            AddVisibleNode(items, folder, mediaRoot, 0, excludedPaths, expandedKeys, collapsedKeys, orderFolders);
        }

        return items;
    }

    private static IReadOnlyList<BrowseFolderTreeItem> FlattenAll(
        IEnumerable<FolderNodeDto> folders,
        string fallbackMediaRoot,
        Func<IEnumerable<FolderNodeDto>, IEnumerable<FolderNodeDto>>? orderFolders)
    {
        var items = new List<BrowseFolderTreeItem>();
        foreach (var folder in Order(folders, orderFolders))
        {
            AddFolder(items, folder, fallbackMediaRoot, 0, orderFolders);
        }

        return items;
    }

    private static void AddFolder(
        List<BrowseFolderTreeItem> items,
        FolderNodeDto folder,
        string fallbackMediaRoot,
        int depth,
        Func<IEnumerable<FolderNodeDto>, IEnumerable<FolderNodeDto>>? orderFolders)
    {
        if (string.IsNullOrWhiteSpace(folder.MediaRoot))
        {
            folder.MediaRoot = fallbackMediaRoot;
        }

        items.Add(new BrowseFolderTreeItem(folder, depth));
        foreach (var child in Order(folder.Children, orderFolders))
        {
            AddFolder(items, child, fallbackMediaRoot, depth + 1, orderFolders);
        }
    }

    private static IEnumerable<FolderNodeDto> Order(
        IEnumerable<FolderNodeDto> folders,
        Func<IEnumerable<FolderNodeDto>, IEnumerable<FolderNodeDto>>? orderFolders)
        => orderFolders is null ? folders : orderFolders(folders);

    public static BrowseFolderTreeNodeState CreateNodeState(
        BrowseFolderTreeItem item,
        ISet<string> excludedPaths,
        ISet<string> expandedKeys,
        ISet<string>? collapsedKeys = null)
    {
        var key = FolderKey(item.Folder);
        var collapsed = collapsedKeys?.Contains(key) == true;
        return new BrowseFolderTreeNodeState(
            item.Folder,
            item.Depth,
            !collapsed && (expandedKeys.Contains(key) || item.Depth < DefaultExpandedDepth),
            !BrowseLibraryPresenter.IsFolderPathExcluded(item.Folder.Path, excludedPaths));
    }

    public static void ToggleExpanded(ISet<string> expandedKeys, FolderNodeDto folder)
    {
        var key = FolderKey(folder);
        if (!expandedKeys.Add(key))
        {
            expandedKeys.Remove(key);
        }
    }

    public static void ToggleExpanded(
        ISet<string> expandedKeys,
        ISet<string> collapsedKeys,
        FolderNodeDto folder,
        int depth)
    {
        var key = FolderKey(folder);
        var defaultExpanded = depth < DefaultExpandedDepth;
        if (defaultExpanded)
        {
            if (!collapsedKeys.Add(key))
            {
                collapsedKeys.Remove(key);
            }

            return;
        }

        collapsedKeys.Remove(key);
        ToggleExpanded(expandedKeys, folder);
    }

    public static void ToggleIncluded(ISet<string> excludedPaths, string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return;
        }

        if (!excludedPaths.Add(path))
        {
            excludedPaths.Remove(path);
        }
    }

    public static void SetIncluded(ISet<string> excludedPaths, string path, bool included)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return;
        }

        if (included)
        {
            excludedPaths.Remove(path);
            return;
        }

        excludedPaths.Add(path);
    }

    public static bool HasChildren(FolderNodeDto folder)
        => folder.Children.Any();

    public static string FolderKey(FolderNodeDto folder)
        => $"{folder.MediaRoot}::{folder.Path}";

    private static void AddVisibleNode(
        List<BrowseFolderTreeNodeState> items,
        FolderNodeDto folder,
        string fallbackMediaRoot,
        int depth,
        ISet<string> excludedPaths,
        ISet<string> expandedKeys,
        ISet<string> collapsedKeys,
        Func<IEnumerable<FolderNodeDto>, IEnumerable<FolderNodeDto>>? orderFolders)
    {
        if (string.IsNullOrWhiteSpace(folder.MediaRoot))
        {
            folder.MediaRoot = fallbackMediaRoot;
        }

        var state = CreateNodeState(new BrowseFolderTreeItem(folder, depth), excludedPaths, expandedKeys, collapsedKeys);
        items.Add(state);
        if (!state.IsExpanded)
        {
            return;
        }

        foreach (var child in Order(folder.Children, orderFolders))
        {
            AddVisibleNode(items, child, fallbackMediaRoot, depth + 1, excludedPaths, expandedKeys, collapsedKeys, orderFolders);
        }
    }
}
