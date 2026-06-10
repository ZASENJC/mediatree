using System;
using System.Collections.Generic;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.Services;

public sealed record BrowseFolderTreeItem(FolderNodeDto Folder, int Depth);

public static class BrowseFolderTreePresenter
{
    public static IReadOnlyList<BrowseFolderTreeItem> FlattenAll(
        IEnumerable<FolderNodeDto> folders,
        Func<IEnumerable<FolderNodeDto>, IEnumerable<FolderNodeDto>>? orderFolders = null)
        => FlattenAll(folders, "", orderFolders);

    public static IReadOnlyList<BrowseFolderTreeItem> FlattenForMediaRoot(
        string mediaRoot,
        IEnumerable<FolderNodeDto> folders,
        Func<IEnumerable<FolderNodeDto>, IEnumerable<FolderNodeDto>>? orderFolders = null)
        => FlattenAll(folders, mediaRoot, orderFolders);

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
}
