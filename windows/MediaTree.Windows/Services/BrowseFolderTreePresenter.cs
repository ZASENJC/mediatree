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
    {
        var items = new List<BrowseFolderTreeItem>();
        foreach (var folder in Order(folders, orderFolders))
        {
            AddFolder(items, folder, 0, orderFolders);
        }

        return items;
    }

    private static void AddFolder(
        List<BrowseFolderTreeItem> items,
        FolderNodeDto folder,
        int depth,
        Func<IEnumerable<FolderNodeDto>, IEnumerable<FolderNodeDto>>? orderFolders)
    {
        items.Add(new BrowseFolderTreeItem(folder, depth));
        foreach (var child in Order(folder.Children, orderFolders))
        {
            AddFolder(items, child, depth + 1, orderFolders);
        }
    }

    private static IEnumerable<FolderNodeDto> Order(
        IEnumerable<FolderNodeDto> folders,
        Func<IEnumerable<FolderNodeDto>, IEnumerable<FolderNodeDto>>? orderFolders)
        => orderFolders is null ? folders : orderFolders(folders);
}
