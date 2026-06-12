using System;
using MediaTree.Windows.Providers;

namespace MediaTree.Windows.Services;

public static class AppServices
{
    public static MainWindow? MainWindow { get; set; }
    public static IMediaProvider ActiveProvider { get; private set; } = null!;
    public static IMediaTreeProvider LocalMediaTreeProvider { get; private set; } = null!;
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
        var activeProvider = provider ?? throw new ArgumentNullException(nameof(provider));
        var localProvider = activeProvider.Profile.Kind == MediaSourceKind.LocalMediaTree
            ? activeProvider as IMediaTreeProvider
            : null;
        if (localProvider is null)
        {
            LocalMediaTreeProvider = null!;
        }

        SetActiveProvider(activeProvider, localProvider, disposePrevious: false);
    }

    public static void Initialize(
        BackendProcessService backend,
        IMediaProvider provider,
        IMediaTreeProvider localProvider)
    {
        Backend = backend ?? throw new ArgumentNullException(nameof(backend));
        ArgumentNullException.ThrowIfNull(localProvider);
        SetActiveProvider(provider ?? throw new ArgumentNullException(nameof(provider)), localProvider, disposePrevious: false);
    }

    public static void SwitchProvider(IMediaProvider provider)
        => SetActiveProvider(provider ?? throw new ArgumentNullException(nameof(provider)), localProvider: null, disposePrevious: true);

    public static void SwitchToLocalMediaTree()
    {
        if (LocalMediaTreeProvider is null)
        {
            throw new InvalidOperationException("Local MediaTree provider is not initialized.");
        }

        SetActiveProvider(LocalMediaTreeProvider, localProvider: LocalMediaTreeProvider, disposePrevious: true);
    }

    private static void SetActiveProvider(IMediaProvider provider, IMediaTreeProvider? localProvider, bool disposePrevious)
    {
        var previousApi = Media?.Api;
        if (provider.Profile.Kind == MediaSourceKind.LocalMediaTree)
        {
            LocalMediaTreeProvider = localProvider
                ?? provider as IMediaTreeProvider
                ?? throw new ArgumentException("Local MediaTree provider must implement IMediaTreeProvider.", nameof(provider));
        }
        else if (localProvider is not null)
        {
            LocalMediaTreeProvider = localProvider;
        }

        ActiveProvider = provider;
        ActiveMediaTreeProvider = provider as IMediaTreeProvider;
        Media = provider.Services;
        if (disposePrevious
            && previousApi is not null
            && !ReferenceEquals(previousApi, provider.Services.Api)
            && !ReferenceEquals(previousApi, LocalMediaTreeProvider?.Services.Api))
        {
            previousApi.Dispose();
        }
    }

    public static void Dispose()
    {
        try
        {
            Media?.Api.Dispose();
            if (LocalMediaTreeProvider is not null && !ReferenceEquals(LocalMediaTreeProvider.Services.Api, Media?.Api))
            {
                LocalMediaTreeProvider.Services.Api.Dispose();
            }
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
