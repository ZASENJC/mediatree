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
    public static MediaTreeApiClient Api { get; private set; } = null!;
    public static AuthSessionService Auth { get; private set; } = null!;
    public static LibraryService Library { get; private set; } = null!;
    public static MovieService Movie { get; private set; } = null!;
    public static UpdateService Updates { get; private set; } = null!;
    public static PlaybackProgressService PlaybackProgress { get; private set; } = null!;

    public static bool IsReady => Api != null && ActiveProvider != null;

    public static void Initialize(
        BackendProcessService backend,
        IMediaTreeProvider provider)
    {
        Backend = backend ?? throw new ArgumentNullException(nameof(backend));
        ActiveProvider = provider ?? throw new ArgumentNullException(nameof(provider));
        ActiveMediaTreeProvider = provider;
        MediaTree = provider.Services;
        Api = MediaTree.Api;
        Auth = MediaTree.Auth;
        Library = MediaTree.Library;
        Movie = MediaTree.Movie;
        Updates = MediaTree.Updates;
        PlaybackProgress = MediaTree.PlaybackProgress;
    }

    public static void Dispose()
    {
        try
        {
            Api?.Dispose();
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
