using System;
using MediaTree.Windows.Providers;

namespace MediaTree.Windows.Services;

public static class AppServices
{
    public static MainWindow? MainWindow { get; set; }
    public static IMediaProvider ActiveProvider { get; private set; } = null!;
    public static IMediaTreeProvider ActiveMediaTreeProvider { get; private set; } = null!;
    public static BackendProcessService Backend { get; private set; } = null!;
    public static MediaTreeServices MediaTree { get; private set; } = null!;

    public static bool IsReady => MediaTree != null && ActiveProvider != null;

    public static void Initialize(
        BackendProcessService backend,
        IMediaTreeProvider provider)
    {
        Backend = backend ?? throw new ArgumentNullException(nameof(backend));
        ActiveProvider = provider ?? throw new ArgumentNullException(nameof(provider));
        ActiveMediaTreeProvider = provider;
        MediaTree = provider.Services;
    }

    public static void Dispose()
    {
        try
        {
            MediaTree?.Api.Dispose();
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
