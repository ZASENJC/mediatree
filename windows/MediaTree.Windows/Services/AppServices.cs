using System;
using MediaTree.Windows.Providers;

namespace MediaTree.Windows.Services;

public static class AppServices
{
    public static MainWindow? MainWindow { get; set; }
    public static IMediaProvider ActiveProvider { get; private set; } = null!;
    public static IMediaTreeProvider? ActiveMediaTreeProvider { get; private set; }
    public static BackendProcessService Backend { get; private set; } = null!;
    public static MediaTreeServices Media { get; private set; } = null!;

    public static bool IsReady => Media != null && ActiveProvider != null;

    public static bool IsLocalMediaTreeActive
        => ActiveProvider?.Profile.Kind == MediaSourceKind.LocalMediaTree;

    public static bool SupportsMediaTreeLibraryManagement
        => ActiveProvider?.Profile.Kind is MediaSourceKind.LocalMediaTree or MediaSourceKind.RemoteMediaTree;

    public static void Initialize(
        BackendProcessService backend,
        IMediaProvider provider)
    {
        Backend = backend ?? throw new ArgumentNullException(nameof(backend));
        ActiveProvider = provider ?? throw new ArgumentNullException(nameof(provider));
        ActiveMediaTreeProvider = provider as IMediaTreeProvider;
        Media = provider.Services;
    }

    public static void Dispose()
    {
        try
        {
            Media?.Api.Dispose();
        }
        catch
        {
            // Best-effort cleanup during app shutdown.
        }
    }

    public static void RequireReady()
    {
        if (!IsReady)
        {
            throw new InvalidOperationException("MediaTree Windows services are not initialized.");
        }
    }
}
