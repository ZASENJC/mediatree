namespace MediaTree.Windows.Models;

public sealed record MovieNavigationParameter(int MovieId);

public sealed record PlayerNavigationParameter(int MovieId);

public sealed record FolderNavigationParameter(string FolderPath, string MediaRoot, string Title);
