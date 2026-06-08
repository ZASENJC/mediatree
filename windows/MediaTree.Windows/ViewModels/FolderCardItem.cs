using CommunityToolkit.Mvvm.ComponentModel;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.ViewModels;

public sealed partial class FolderCardItem : ObservableObject
{
    public FolderCardItem(FolderNodeDto folder, string coverUrl)
    {
        Folder = folder;
        CoverUrl = coverUrl;
    }

    public FolderNodeDto Folder { get; }
    public string Path => Folder.Path;
    public string MediaRoot => Folder.MediaRoot;
    public string Title => Folder.BestTitle;
    public string CoverUrl { get; }
    public string Subtitle => Folder.SpecialCount > 0 ? $"{Folder.MovieCount} 部 · {Folder.SpecialCount} 花絮" : $"{Folder.MovieCount} 部";
    public string ProgressText => Folder.ProgressPercent > 0 && !Folder.FolderWatched ? $"{Folder.ProgressPercent:0}%" : "";
}
