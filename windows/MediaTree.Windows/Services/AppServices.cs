using System;

namespace MediaTree.Windows.Services;

public static class AppServices
{
    public static MainWindow? MainWindow { get; set; }
    public static BackendProcessService Backend { get; private set; } = null!;
    public static MediaTreeApiClient Api { get; private set; } = null!;
    public static AuthSessionService Auth { get; private set; } = null!;
    public static LibraryService Library { get; private set; } = null!;
    public static MovieService Movie { get; private set; } = null!;
    public static UpdateService Updates { get; private set; } = null!;
    public static PlaybackProgressService PlaybackProgress { get; private set; } = null!;

    public static bool IsReady => Api != null;

    public static void Initialize(
        BackendProcessService backend,
        MediaTreeApiClient api,
        AuthSessionService auth,
        LibraryService library,
        MovieService movie,
        UpdateService updates,
        PlaybackProgressService playbackProgress)
    {
        Backend = backend;
        Api = api;
        Auth = auth;
        Library = library;
        Movie = movie;
        Updates = updates;
        PlaybackProgress = playbackProgress;
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

