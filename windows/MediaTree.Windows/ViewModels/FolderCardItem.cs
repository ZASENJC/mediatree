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
    public string SourceName => Folder.Name;
    public string CoverUrl { get; }
    public int DisplayVideoCount => Folder.VideoCount > 0 ? Folder.VideoCount : Folder.MovieCount;
    public string DisplayCountUnit => Folder.VideoCount > Folder.MovieCount ? "集" : "部";
    public string Subtitle => Folder.SpecialCount > 0 ? $"{DisplayVideoCount} {DisplayCountUnit} · {Folder.SpecialCount} 花絮" : $"{DisplayVideoCount} {DisplayCountUnit}";
    public string ProgressText => Folder.ProgressPercent > 0 && !Folder.FolderWatched ? $"{Folder.ProgressPercent:0}%" : "";
}
