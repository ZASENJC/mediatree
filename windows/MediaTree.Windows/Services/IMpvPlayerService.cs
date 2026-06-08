using System;
using System.Threading;
using System.Threading.Tasks;

namespace MediaTree.Windows.Services;

public sealed record PlayerStateSnapshot(double Position, double Duration, bool Paused);

public interface IMpvPlayerService : IDisposable
{
    event EventHandler<IntPtr>? DisplaySwapchainChanged;
    event EventHandler<PlayerStateSnapshot>? StateChanged;

    Task LoadAsync(string source, CancellationToken cancellationToken = default);
    Task PlayPauseAsync(CancellationToken cancellationToken = default);
    Task SeekAsync(double seconds, CancellationToken cancellationToken = default);
    Task SetVolumeAsync(double volume, CancellationToken cancellationToken = default);
    Task SetSpeedAsync(double speed, CancellationToken cancellationToken = default);
    Task SelectSubtitleAsync(int subtitleId, CancellationToken cancellationToken = default);
    Task SelectAudioAsync(int audioId, CancellationToken cancellationToken = default);
    Task StopAsync(CancellationToken cancellationToken = default);

    PlayerStateSnapshot CurrentState { get; }
}

