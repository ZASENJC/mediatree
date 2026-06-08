using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace MediaTree.Windows.Services;

public sealed record PlayerTrack(
    int Id,
    string Type,
    string Title,
    string Language,
    string Codec,
    bool External)
{
    public string DisplayName
    {
        get
        {
            var label = FirstNonEmpty(Title, Language, Codec, $"{Type} {Id}");
            var details = new List<string>();
            if (!string.IsNullOrWhiteSpace(Language) && !label.Contains(Language, StringComparison.OrdinalIgnoreCase))
            {
                details.Add(Language.ToUpperInvariant());
            }

            if (!string.IsNullOrWhiteSpace(Codec) && !label.Contains(Codec, StringComparison.OrdinalIgnoreCase))
            {
                details.Add(Codec.ToUpperInvariant());
            }

            if (External)
            {
                details.Add("外部");
            }

            return details.Count == 0 ? label : $"{label} ({string.Join(" · ", details)})";
        }
    }

    private static string FirstNonEmpty(params string[] values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
            {
                return value;
            }
        }

        return "轨道";
    }
}

public sealed record PlayerStateSnapshot
{
    public PlayerStateSnapshot(
        double position,
        double duration,
        bool paused,
        double volume = 80,
        double speed = 1,
        int subtitleId = 0,
        int audioId = 0,
        IReadOnlyList<PlayerTrack>? tracks = null)
    {
        Position = position;
        Duration = duration;
        Paused = paused;
        Volume = volume;
        Speed = speed;
        SubtitleId = subtitleId;
        AudioId = audioId;
        Tracks = tracks ?? Array.Empty<PlayerTrack>();
    }

    public double Position { get; init; }
    public double Duration { get; init; }
    public bool Paused { get; init; }
    public double Volume { get; init; }
    public double Speed { get; init; }
    public int SubtitleId { get; init; }
    public int AudioId { get; init; }
    public IReadOnlyList<PlayerTrack> Tracks { get; init; }
}

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
    Task ShowTextAsync(string text, int durationMilliseconds = 1200, CancellationToken cancellationToken = default);
    Task StopAsync(CancellationToken cancellationToken = default);

    PlayerStateSnapshot CurrentState { get; }
}
