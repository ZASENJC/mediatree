using System;
using System.Collections.Generic;
using System.Globalization;
using System.Threading;
using System.Threading.Tasks;
using MediaTree.Windows.Interop;

namespace MediaTree.Windows.Services;

public sealed class LibMpvPlayerService : IMpvPlayerService
{
    private readonly object _sync = new();
    private IntPtr _handle;
    private Timer? _pollTimer;
    private bool _disposed;
    private double _compositionWidth;
    private double _compositionHeight;
    private PlayerStateSnapshot _currentState = new(0, 0, true);

    public event EventHandler<IntPtr>? DisplaySwapchainChanged;
    public event EventHandler<PlayerStateSnapshot>? StateChanged;

    public PlayerStateSnapshot CurrentState
    {
        get
        {
            lock (_sync)
            {
                return _currentState;
            }
        }
    }

    public Task LoadAsync(string source, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        ApplyCompositionSize();
        MpvNative.Command(_handle, "loadfile", source);
        UpdateSwapchain();
        return Task.CompletedTask;
    }

    public Task PlayPauseAsync(CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        MpvNative.Command(_handle, "cycle", "pause");
        PollState();
        return Task.CompletedTask;
    }

    public Task SeekAsync(double seconds, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        MpvNative.Command(_handle, "seek", seconds.ToString(CultureInfo.InvariantCulture), "absolute");
        PollState();
        return Task.CompletedTask;
    }

    public Task SetVolumeAsync(double volume, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        MpvNative.Command(_handle, "set", "volume", Math.Clamp(volume, 0, 100).ToString(CultureInfo.InvariantCulture));
        PollState();
        return Task.CompletedTask;
    }

    public Task SetSpeedAsync(double speed, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        MpvNative.Command(_handle, "set", "speed", Math.Clamp(speed, 0.25, 4).ToString(CultureInfo.InvariantCulture));
        PollState();
        return Task.CompletedTask;
    }

    public Task SelectSubtitleAsync(int subtitleId, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        MpvNative.Command(_handle, "set", "sid", subtitleId <= 0 ? "no" : subtitleId.ToString(CultureInfo.InvariantCulture));
        PollState();
        return Task.CompletedTask;
    }

    public Task SelectAudioAsync(int audioId, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        MpvNative.Command(_handle, "set", "aid", audioId <= 0 ? "auto" : audioId.ToString(CultureInfo.InvariantCulture));
        PollState();
        return Task.CompletedTask;
    }

    public Task StopAsync(CancellationToken cancellationToken = default)
    {
        if (_handle != IntPtr.Zero)
        {
            MpvNative.Command(_handle, "stop");
            PollState();
        }

        return Task.CompletedTask;
    }

    public void UpdateCompositionSize(double width, double height)
    {
        if (width <= 0 || height <= 0)
        {
            return;
        }

        lock (_sync)
        {
            _compositionWidth = width;
            _compositionHeight = height;
        }

        ApplyCompositionSize();
    }

    private void EnsureInitialized()
    {
        if (_disposed)
        {
            throw new ObjectDisposedException(nameof(LibMpvPlayerService));
        }

        if (_handle != IntPtr.Zero)
        {
            return;
        }

        _handle = MpvNative.Create();
        MpvNative.InitializeForD3D11Composition(_handle);
        ApplyCompositionSize();
        _pollTimer = new Timer(_ => PollState(), null, TimeSpan.Zero, TimeSpan.FromMilliseconds(750));
    }

    private void ApplyCompositionSize()
    {
        if (_handle == IntPtr.Zero)
        {
            return;
        }

        double width;
        double height;
        lock (_sync)
        {
            width = _compositionWidth;
            height = _compositionHeight;
        }

        MpvNative.SetD3D11CompositionSize(_handle, width, height);
    }

    private void PollState()
    {
        try
        {
            if (_handle == IntPtr.Zero || _disposed)
            {
                return;
            }

            var next = BuildSnapshot(_handle);
            lock (_sync)
            {
                _currentState = next;
            }

            StateChanged?.Invoke(this, next);
            UpdateSwapchain();
            _ = MpvNative.ReadEvent(_handle, 0);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to poll libmpv state.");
        }
    }

    private static PlayerStateSnapshot BuildSnapshot(IntPtr handle)
    {
        var speed = MpvNative.GetDouble(handle, "speed");
        if (speed <= 0)
        {
            speed = 1;
        }

        return new PlayerStateSnapshot(
            MpvNative.GetDouble(handle, "time-pos"),
            MpvNative.GetDouble(handle, "duration"),
            MpvNative.GetFlag(handle, "pause"),
            Math.Clamp(MpvNative.GetDouble(handle, "volume"), 0, 100),
            speed,
            ReadSelectedTrackId(handle, "sid"),
            ReadSelectedTrackId(handle, "aid"),
            ReadTracks(handle));
    }

    private static IReadOnlyList<PlayerTrack> ReadTracks(IntPtr handle)
    {
        var count = (int)Math.Clamp(MpvNative.GetInt64(handle, "track-list/count"), 0, 256);
        if (count == 0)
        {
            return Array.Empty<PlayerTrack>();
        }

        var tracks = new List<PlayerTrack>(count);
        for (var index = 0; index < count; index++)
        {
            var prefix = $"track-list/{index}";
            var id = (int)MpvNative.GetInt64(handle, $"{prefix}/id");
            var type = MpvNative.GetString(handle, $"{prefix}/type");
            if (id <= 0 || string.IsNullOrWhiteSpace(type))
            {
                continue;
            }

            tracks.Add(new PlayerTrack(
                id,
                type,
                MpvNative.GetString(handle, $"{prefix}/title"),
                MpvNative.GetString(handle, $"{prefix}/lang"),
                MpvNative.GetString(handle, $"{prefix}/codec"),
                MpvNative.GetFlag(handle, $"{prefix}/external")));
        }

        return tracks;
    }

    private static int ReadSelectedTrackId(IntPtr handle, string propertyName)
    {
        var value = MpvNative.GetString(handle, propertyName);
        return int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var id) ? id : 0;
    }

    private void UpdateSwapchain()
    {
        try
        {
            var swapchain = MpvNative.GetDisplaySwapchain(_handle);
            if (swapchain != IntPtr.Zero)
            {
                DisplaySwapchainChanged?.Invoke(this, swapchain);
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to read libmpv display-swapchain.");
        }
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        _pollTimer?.Dispose();
        if (_handle != IntPtr.Zero)
        {
            try
            {
                MpvNative.Terminate(_handle);
            }
            finally
            {
                _handle = IntPtr.Zero;
            }
        }
    }
}
