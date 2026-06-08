using System;
using System.Globalization;
using System.IO;
using System.Threading.Tasks;
using MediaTree.Windows.Controls;
using MediaTree.Windows.Models;
using MediaTree.Windows.Services;
using MediaTree.Windows.Styles;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Navigation;

namespace MediaTree.Windows.Views;

public sealed partial class PlayerPage : Page
{
    private readonly DispatcherTimer _saveTimer = new() { Interval = TimeSpan.FromSeconds(5) };
    private readonly Button _playPauseButton;
    private readonly MpvPlayerControl _playerHost;
    private readonly Slider _progressSlider;
    private readonly ComboBox _speedBox;
    private readonly TextBlock _statusText;
    private readonly TextBlock _timeText;
    private readonly TextBlock _titleText;
    private readonly Slider _volumeSlider;
    private IMpvPlayerService? _player;
    private int _movieId;
    private bool _ignoreSlider;
    private double _duration;

    public PlayerPage()
    {
        (_titleText, _playerHost, _playPauseButton, _progressSlider, _timeText, _volumeSlider, _speedBox, _statusText) = BuildContent();
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
        _saveTimer.Tick += OnSaveTimerTick;
    }

    private (TextBlock titleText, MpvPlayerControl playerHost, Button playPauseButton, Slider progressSlider, TextBlock timeText, Slider volumeSlider, ComboBox speedBox, TextBlock statusText) BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "PlayerPage");

        var root = new Grid
        {
            Background = new SolidColorBrush(Microsoft.UI.Colors.Black),
            RowSpacing = 0,
        };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

        var topBar = new Grid
        {
            Padding = new Thickness(16),
            Background = Brush(0x10, 0x13, 0x18, 0xCC),
        };
        topBar.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        topBar.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

        var backButton = FluentTheme.ApplyButton(new Button { Content = "返回" }, FluentButtonStyle.Overlay);
        AutomationProperties.SetAutomationId(backButton, "PlayerBackButton");
        backButton.Click += OnBackClicked;
        topBar.Children.Add(backButton);

        var titleText = new TextBlock
        {
            Margin = new Thickness(14, 0, 0, 0),
            VerticalAlignment = VerticalAlignment.Center,
            Foreground = new SolidColorBrush(Microsoft.UI.Colors.White),
            FontSize = 18,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            TextTrimming = TextTrimming.CharacterEllipsis,
        };
        AutomationProperties.SetAutomationId(titleText, "PlayerTitle");
        Grid.SetColumn(titleText, 1);
        topBar.Children.Add(titleText);
        root.Children.Add(topBar);

        var playerHost = new MpvPlayerControl();
        AutomationProperties.SetAutomationId(playerHost, "PlayerHost");
        Grid.SetRow(playerHost, 1);
        root.Children.Add(playerHost);

        var statusText = new TextBlock
        {
            Text = "",
            Visibility = Visibility.Collapsed,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Foreground = new SolidColorBrush(Microsoft.UI.Colors.White),
            TextWrapping = TextWrapping.WrapWholeWords,
            MaxWidth = 560,
            Margin = new Thickness(24),
        };
        AutomationProperties.SetAutomationId(statusText, "PlayerStatusText");
        Grid.SetRow(statusText, 1);
        root.Children.Add(statusText);

        var controls = new Grid
        {
            Padding = new Thickness(18),
            Background = Brush(0, 0, 0, 0xE6),
            ColumnSpacing = 12,
        };
        controls.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        controls.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        controls.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        controls.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(120) });
        controls.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        Grid.SetRow(controls, 2);

        var playPauseButton = FluentTheme.ApplyButton(new Button { Content = "暂停" }, FluentButtonStyle.Overlay);
        AutomationProperties.SetAutomationId(playPauseButton, "PlayerPlayPause");
        playPauseButton.Click += OnPlayPauseClicked;
        controls.Children.Add(playPauseButton);

        var progressSlider = new Slider
        {
            Minimum = 0,
            Maximum = 1,
        };
        AutomationProperties.SetAutomationId(progressSlider, "PlayerProgressSlider");
        progressSlider.ValueChanged += OnProgressSliderChanged;
        Grid.SetColumn(progressSlider, 1);
        controls.Children.Add(progressSlider);

        var timeText = new TextBlock
        {
            Foreground = new SolidColorBrush(Microsoft.UI.Colors.White),
            VerticalAlignment = VerticalAlignment.Center,
            Text = "0:00 / 0:00",
        };
        AutomationProperties.SetAutomationId(timeText, "PlayerTime");
        Grid.SetColumn(timeText, 2);
        controls.Children.Add(timeText);

        var volumeSlider = new Slider
        {
            Minimum = 0,
            Maximum = 100,
            Value = 80,
        };
        AutomationProperties.SetAutomationId(volumeSlider, "PlayerVolumeSlider");
        volumeSlider.ValueChanged += OnVolumeChanged;
        Grid.SetColumn(volumeSlider, 3);
        controls.Children.Add(volumeSlider);

        var speedBox = new ComboBox();
        AutomationProperties.SetAutomationId(speedBox, "PlayerSpeed");
        speedBox.Items.Add(new ComboBoxItem { Content = "0.75x", Tag = "0.75" });
        speedBox.Items.Add(new ComboBoxItem { Content = "1.0x", Tag = "1" });
        speedBox.Items.Add(new ComboBoxItem { Content = "1.25x", Tag = "1.25" });
        speedBox.Items.Add(new ComboBoxItem { Content = "1.5x", Tag = "1.5" });
        speedBox.Items.Add(new ComboBoxItem { Content = "2.0x", Tag = "2" });
        speedBox.SelectedIndex = 1;
        speedBox.SelectionChanged += OnSpeedChanged;
        Grid.SetColumn(speedBox, 4);
        controls.Children.Add(speedBox);

        root.Children.Add(controls);
        Content = root;
        return (titleText, playerHost, playPauseButton, progressSlider, timeText, volumeSlider, speedBox, statusText);
    }

    protected override void OnNavigatedTo(NavigationEventArgs args)
    {
        base.OnNavigatedTo(args);
        _movieId = args.Parameter switch
        {
            PlayerNavigationParameter parameter => parameter.MovieId,
            int id => id,
            _ => 0,
        };
    }

    private async void OnLoaded(object sender, RoutedEventArgs args)
    {
        try
        {
            await StartPlaybackAsync();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to start native playback.");
            ShowPlaybackError($"打开视频失败：{ex.Message}");
        }
    }

    private async Task StartPlaybackAsync()
    {
        var movie = await AppServices.Movie.GetMovieDetailAsync(_movieId);
        var progress = await AppServices.Movie.GetProgressAsync(_movieId);
        _titleText.Text = movie.BestTitle;
        _statusText.Visibility = Visibility.Collapsed;

        _player = new LibMpvPlayerService();
        _player.StateChanged += OnPlayerStateChanged;
        _playerHost.AttachService(_player);

        var source = File.Exists(movie.Path) ? movie.Path : await AppServices.Api.BuildStreamUrlAsync(movie.Id);
        await _player.LoadAsync(source);
        await _player.SetVolumeAsync(_volumeSlider.Value);
        if (progress.Position > 5)
        {
            try
            {
                await _player.SeekAsync(progress.Position);
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, "Failed to resume native playback position.");
            }
        }

        _saveTimer.Start();
    }

    private void OnPlayerStateChanged(object? sender, PlayerStateSnapshot state)
    {
        DispatcherQueue.TryEnqueue(() =>
        {
            _duration = state.Duration;
            _ignoreSlider = true;
            _progressSlider.Maximum = Math.Max(1, state.Duration);
            _progressSlider.Value = Math.Clamp(state.Position, 0, _progressSlider.Maximum);
            _ignoreSlider = false;
            _playPauseButton.Content = state.Paused ? "播放" : "暂停";
            _timeText.Text = $"{FormatTime(state.Position)} / {FormatTime(state.Duration)}";
        });
    }

    private async void OnPlayPauseClicked(object sender, RoutedEventArgs args)
    {
        try
        {
            if (_player is not null)
            {
                await _player.PlayPauseAsync();
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to toggle native playback.");
            ShowPlaybackError($"播放控制失败：{ex.Message}");
        }
    }

    private async void OnProgressSliderChanged(object sender, Microsoft.UI.Xaml.Controls.Primitives.RangeBaseValueChangedEventArgs args)
    {
        if (_ignoreSlider || _player is null || Math.Abs(args.NewValue - _player.CurrentState.Position) < 1)
        {
            return;
        }

        try
        {
            await _player.SeekAsync(args.NewValue);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to seek native playback.");
            ShowPlaybackError($"跳转失败：{ex.Message}");
        }
    }

    private async void OnVolumeChanged(object sender, Microsoft.UI.Xaml.Controls.Primitives.RangeBaseValueChangedEventArgs args)
    {
        try
        {
            if (_player is not null)
            {
                await _player.SetVolumeAsync(args.NewValue);
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to set native playback volume.");
            ShowPlaybackError($"音量设置失败：{ex.Message}");
        }
    }

    private async void OnSpeedChanged(object sender, SelectionChangedEventArgs args)
    {
        if (_player is null || _speedBox.SelectedItem is not ComboBoxItem item)
        {
            return;
        }

        if (double.TryParse(item.Tag?.ToString(), NumberStyles.Float, CultureInfo.InvariantCulture, out var speed))
        {
            try
            {
                await _player.SetSpeedAsync(speed);
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, "Failed to set native playback speed.");
                ShowPlaybackError($"倍速设置失败：{ex.Message}");
            }
        }
    }

    private async void OnBackClicked(object sender, RoutedEventArgs args)
    {
        try
        {
            await SaveProgressAsync(true);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to save native playback before back navigation.");
        }

        ShellPage.Current?.GoBackOrLibrary();
    }

    private async void OnSaveTimerTick(object? sender, object args)
    {
        try
        {
            await SaveProgressAsync(false);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to save native playback progress.");
        }
    }

    private async void OnUnloaded(object sender, RoutedEventArgs args)
    {
        try
        {
            _saveTimer.Stop();
            await SaveProgressAsync(true);
            if (_player is not null)
            {
                await _player.StopAsync();
                _player.Dispose();
                _player = null;
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to unload native player page.");
        }
    }

    private async Task SaveProgressAsync(bool stopped)
    {
        if (_player is null || _movieId <= 0)
        {
            return;
        }

        var state = _player.CurrentState;
        await AppServices.PlaybackProgress.SaveAsync(_movieId, state.Position, _duration > 0 ? _duration : state.Duration, stopped);
    }

    private static string FormatTime(double seconds)
    {
        if (seconds <= 0 || double.IsNaN(seconds))
        {
            return "0:00";
        }

        var span = TimeSpan.FromSeconds(seconds);
        return span.TotalHours >= 1 ? $"{(int)span.TotalHours}:{span.Minutes:00}:{span.Seconds:00}" : $"{span.Minutes}:{span.Seconds:00}";
    }

    private static SolidColorBrush Brush(byte r, byte g, byte b, byte a = 0xFF)
    {
        return new SolidColorBrush(Microsoft.UI.ColorHelper.FromArgb(a, r, g, b));
    }

    private void ShowPlaybackError(string message)
    {
        _statusText.Text = message;
        _statusText.Visibility = Visibility.Visible;
        _playPauseButton.IsEnabled = false;
        _progressSlider.IsEnabled = false;
        _volumeSlider.IsEnabled = false;
        _speedBox.IsEnabled = false;
    }
}
