using System;
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
        MpvNative.Command(_handle, "seek", seconds.ToString(System.Globalization.CultureInfo.InvariantCulture), "absolute");
        PollState();
        return Task.CompletedTask;
    }

    public Task SetVolumeAsync(double volume, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        MpvNative.Command(_handle, "set", "volume", Math.Clamp(volume, 0, 100).ToString(System.Globalization.CultureInfo.InvariantCulture));
        return Task.CompletedTask;
    }

    public Task SetSpeedAsync(double speed, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        MpvNative.Command(_handle, "set", "speed", Math.Clamp(speed, 0.25, 4).ToString(System.Globalization.CultureInfo.InvariantCulture));
        return Task.CompletedTask;
    }

    public Task SelectSubtitleAsync(int subtitleId, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        MpvNative.Command(_handle, "set", "sid", subtitleId <= 0 ? "no" : subtitleId.ToString(System.Globalization.CultureInfo.InvariantCulture));
        return Task.CompletedTask;
    }

    public Task SelectAudioAsync(int audioId, CancellationToken cancellationToken = default)
    {
        EnsureInitialized();
        MpvNative.Command(_handle, "set", "aid", audioId <= 0 ? "auto" : audioId.ToString(System.Globalization.CultureInfo.InvariantCulture));
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
        if (_handle != IntPtr.Zero)
        {
            MpvNative.SetD3D11CompositionSize(_handle, width, height);
        }
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
        _pollTimer = new Timer(_ => PollState(), null, TimeSpan.Zero, TimeSpan.FromMilliseconds(750));
    }

    private void PollState()
    {
        try
        {
            if (_handle == IntPtr.Zero || _disposed)
            {
                return;
            }

            var next = new PlayerStateSnapshot(
                MpvNative.GetDouble(_handle, "time-pos"),
                MpvNative.GetDouble(_handle, "duration"),
                MpvNative.GetFlag(_handle, "pause"));
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
