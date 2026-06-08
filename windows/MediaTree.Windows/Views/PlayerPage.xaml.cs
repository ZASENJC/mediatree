using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using MediaTree.Windows.Controls;
using MediaTree.Windows.Models;
using MediaTree.Windows.Services;
using MediaTree.Windows.Styles;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Navigation;
using Windows.System;

namespace MediaTree.Windows.Views;

public sealed partial class PlayerPage : Page
{
    private const double SeekStepSeconds = 5;

    private sealed record PlayerUi(
        Grid Root,
        MpvPlayerControl PlayerHost,
        Border TopChrome,
        Button SubtitleButton,
        Button AudioButton,
        Button EpisodeButton,
        Button FullScreenButton,
        ComboBox SpeedBox,
        TextBlock TitleText,
        TextBlock TrackSummaryText,
        TextBlock StatusText,
        Border ResumePrompt,
        TextBlock ResumeText,
        Border EpisodePanel,
        TextBlock EpisodeCountText,
        StackPanel EpisodeItems);

    private readonly DispatcherTimer _chromeTimer = new() { Interval = TimeSpan.FromSeconds(3) };
    private readonly DispatcherTimer _saveTimer = new() { Interval = TimeSpan.FromSeconds(5) };
    private readonly Button _audioButton;
    private readonly Button _episodeButton;
    private readonly TextBlock _episodeCountText;
    private readonly StackPanel _episodeItems;
    private readonly Border _episodePanel;
    private readonly Button _fullScreenButton;
    private readonly MpvPlayerControl _playerHost;
    private readonly TextBlock _resumeText;
    private readonly Border _resumePrompt;
    private readonly Grid _root;
    private readonly ComboBox _speedBox;
    private readonly TextBlock _statusText;
    private readonly Button _subtitleButton;
    private readonly TextBlock _titleText;
    private readonly Border _topChrome;
    private readonly TextBlock _trackSummaryText;
    private readonly List<MovieDto> _episodes = [];
    private IMpvPlayerService? _player;
    private MovieDto? _movie;
    private PlayerStateSnapshot _state = new(0, 0, true);
    private int _movieId;
    private bool _controlsVisible = true;
    private bool _episodePanelOpen;
    private bool _fullScreenMode;
    private bool _ignoreSpeed;
    private bool _muted;
    private bool _playbackStarted;
    private double _duration;
    private double _lastKnownVolume = 80;
    private double _resumePosition;

    public PlayerPage()
    {
        var ui = BuildContent();
        _root = ui.Root;
        _playerHost = ui.PlayerHost;
        _topChrome = ui.TopChrome;
        _subtitleButton = ui.SubtitleButton;
        _audioButton = ui.AudioButton;
        _episodeButton = ui.EpisodeButton;
        _fullScreenButton = ui.FullScreenButton;
        _speedBox = ui.SpeedBox;
        _titleText = ui.TitleText;
        _trackSummaryText = ui.TrackSummaryText;
        _statusText = ui.StatusText;
        _resumePrompt = ui.ResumePrompt;
        _resumeText = ui.ResumeText;
        _episodePanel = ui.EpisodePanel;
        _episodeCountText = ui.EpisodeCountText;
        _episodeItems = ui.EpisodeItems;

        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
        _chromeTimer.Tick += OnChromeTimerTick;
        _saveTimer.Tick += OnSaveTimerTick;
    }

    private PlayerUi BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "PlayerPage");

        var root = new Grid
        {
            Background = Brush(0, 0, 0),
            IsTabStop = true,
        };
        root.PointerMoved += OnUserActivity;
        root.PointerPressed += OnUserActivity;
        root.KeyDown += OnKeyDown;

        var playerHost = new MpvPlayerControl();
        AutomationProperties.SetAutomationId(playerHost, "PlayerHost");
        root.Children.Add(playerHost);

        var statusText = new TextBlock
        {
            Text = "正在打开视频...",
            Visibility = Visibility.Collapsed,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Foreground = Brush(0xFF, 0xFF, 0xFF),
            TextAlignment = TextAlignment.Center,
            TextWrapping = TextWrapping.WrapWholeWords,
            MaxWidth = 600,
            Margin = new Thickness(24),
        };
        AutomationProperties.SetAutomationId(statusText, "PlayerStatusText");
        root.Children.Add(statusText);

        var topChrome = new Border
        {
            Margin = new Thickness(16),
            Padding = new Thickness(0),
            Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent),
            BorderThickness = new Thickness(0),
            VerticalAlignment = VerticalAlignment.Top,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };
        AutomationProperties.SetAutomationId(topChrome, "PlayerTopChrome");

        var topGrid = new Grid { ColumnSpacing = 12 };
        topGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        topGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        topGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        topChrome.Child = topGrid;

        var backButton = OverlayButton("返回", "PlayerBackButton");
        backButton.Click += OnBackClicked;
        topGrid.Children.Add(backButton);

        var titleStack = new StackPanel { Spacing = 2 };
        Grid.SetColumn(titleStack, 1);
        var titleText = new TextBlock
        {
            Text = "",
            Foreground = Brush(0xFF, 0xFF, 0xFF),
            FontSize = 18,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            TextTrimming = TextTrimming.CharacterEllipsis,
        };
        AutomationProperties.SetAutomationId(titleText, "PlayerTitle");
        titleStack.Children.Add(titleText);

        var trackSummaryText = new TextBlock
        {
            Text = "内嵌 MPV 播放",
            Foreground = Brush(0xB8, 0xC0, 0xCC),
            FontSize = 12,
            TextTrimming = TextTrimming.CharacterEllipsis,
        };
        AutomationProperties.SetAutomationId(trackSummaryText, "PlayerTrackSummary");
        titleStack.Children.Add(trackSummaryText);
        topGrid.Children.Add(titleStack);

        var toolbarScroll = new ScrollViewer
        {
            HorizontalScrollBarVisibility = ScrollBarVisibility.Auto,
            HorizontalScrollMode = ScrollMode.Auto,
            VerticalScrollBarVisibility = ScrollBarVisibility.Disabled,
            VerticalScrollMode = ScrollMode.Disabled,
            VerticalAlignment = VerticalAlignment.Center,
        };
        var toolbar = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 8,
            VerticalAlignment = VerticalAlignment.Center,
        };
        toolbarScroll.Content = toolbar;

        var speedBox = new ComboBox
        {
            Width = 104,
            VerticalAlignment = VerticalAlignment.Center,
        };
        AutomationProperties.SetAutomationId(speedBox, "PlayerSpeed");
        AddSpeedOption(speedBox, "0.5x", 0.5);
        AddSpeedOption(speedBox, "0.75x", 0.75);
        AddSpeedOption(speedBox, "1.0x", 1);
        AddSpeedOption(speedBox, "1.25x", 1.25);
        AddSpeedOption(speedBox, "1.5x", 1.5);
        AddSpeedOption(speedBox, "2.0x", 2);
        speedBox.SelectedIndex = 2;
        speedBox.SelectionChanged += OnSpeedChanged;
        toolbar.Children.Add(speedBox);

        var subtitleButton = OverlayButton("字幕", "PlayerSubtitle");
        subtitleButton.Click += OnSubtitleClicked;
        toolbar.Children.Add(subtitleButton);

        var audioButton = OverlayButton("音轨", "PlayerAudio");
        audioButton.Click += OnAudioClicked;
        toolbar.Children.Add(audioButton);

        var episodeButton = OverlayButton("选集", "PlayerEpisodes");
        episodeButton.Visibility = Visibility.Collapsed;
        episodeButton.Click += OnEpisodeButtonClicked;
        toolbar.Children.Add(episodeButton);

        var fullScreenButton = OverlayButton("全屏", "PlayerFullScreen");
        fullScreenButton.Click += (_, _) => ToggleFullScreenMode();
        toolbar.Children.Add(fullScreenButton);

        Grid.SetColumn(toolbarScroll, 2);
        topGrid.Children.Add(toolbarScroll);
        root.Children.Add(topChrome);

        var episodePanel = new Border
        {
            Width = 332,
            MaxHeight = 500,
            Margin = new Thickness(0, 0, 16, 0),
            Padding = new Thickness(10),
            CornerRadius = new CornerRadius(8),
            Background = Brush(0x08, 0x0B, 0x12, 0xE8),
            BorderBrush = Brush(0xFF, 0xFF, 0xFF, 0x24),
            BorderThickness = new Thickness(1),
            HorizontalAlignment = HorizontalAlignment.Right,
            VerticalAlignment = VerticalAlignment.Center,
            Visibility = Visibility.Collapsed,
        };
        AutomationProperties.SetAutomationId(episodePanel, "PlayerEpisodePanel");

        var episodeStack = new StackPanel { Spacing = 8 };
        var episodeHeader = new Grid { ColumnSpacing = 8 };
        episodeHeader.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        episodeHeader.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        episodeHeader.Children.Add(new TextBlock
        {
            Text = "选集",
            Foreground = Brush(0xFF, 0xFF, 0xFF),
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            VerticalAlignment = VerticalAlignment.Center,
        });
        var episodeCountText = new TextBlock
        {
            Text = "0",
            Foreground = Brush(0xB8, 0xC0, 0xCC),
            FontSize = 12,
            VerticalAlignment = VerticalAlignment.Center,
        };
        AutomationProperties.SetAutomationId(episodeCountText, "PlayerEpisodeCount");
        Grid.SetColumn(episodeCountText, 1);
        episodeHeader.Children.Add(episodeCountText);
        episodeStack.Children.Add(episodeHeader);

        var episodeItems = new StackPanel { Spacing = 4 };
        AutomationProperties.SetAutomationId(episodeItems, "PlayerEpisodeItems");
        episodeStack.Children.Add(new ScrollViewer
        {
            MaxHeight = 440,
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            Content = episodeItems,
        });
        episodePanel.Child = episodeStack;
        root.Children.Add(episodePanel);

        var resumePrompt = new Border
        {
            Padding = new Thickness(4),
            CornerRadius = new CornerRadius(8),
            Background = Brush(0x00, 0x5F, 0xB8, 0xE8),
            BorderBrush = Brush(0xFF, 0xFF, 0xFF, 0x2E),
            BorderThickness = new Thickness(1),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Bottom,
            Margin = new Thickness(0, 0, 0, 132),
            Visibility = Visibility.Collapsed,
        };
        AutomationProperties.SetAutomationId(resumePrompt, "PlayerResumePrompt");

        var resumeActions = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 2,
        };
        var resumeText = new TextBlock { Text = "从上次位置继续", Foreground = Brush(0xFF, 0xFF, 0xFF) };
        var resumeButton = FluentTheme.ApplyButton(new Button
        {
            Content = resumeText,
            MinHeight = 36,
        }, FluentButtonStyle.Overlay);
        AutomationProperties.SetAutomationId(resumeButton, "PlayerResumeButton");
        resumeButton.Click += OnResumeClicked;
        resumeActions.Children.Add(resumeButton);

        var closeResumeButton = FluentTheme.ApplyButton(new Button
        {
            Content = "关闭",
            MinHeight = 36,
        }, FluentButtonStyle.Overlay);
        AutomationProperties.SetAutomationId(closeResumeButton, "PlayerResumeClose");
        closeResumeButton.Click += (_, _) => HideResumePrompt();
        resumeActions.Children.Add(closeResumeButton);
        resumePrompt.Child = resumeActions;
        root.Children.Add(resumePrompt);

        Content = root;
        return new PlayerUi(
            root,
            playerHost,
            topChrome,
            subtitleButton,
            audioButton,
            episodeButton,
            fullScreenButton,
            speedBox,
            titleText,
            trackSummaryText,
            statusText,
            resumePrompt,
            resumeText,
            episodePanel,
            episodeCountText,
            episodeItems);
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
        if (_playbackStarted)
        {
            return;
        }

        _playbackStarted = true;
        _root.Focus(FocusState.Programmatic);
        ShowChrome(true);

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
        _movie = movie;
        _titleText.Text = movie.BestTitle;
        _statusText.Visibility = Visibility.Collapsed;

        _player = new LibMpvPlayerService();
        _player.StateChanged += OnPlayerStateChanged;
        _playerHost.AttachService(_player);

        var source = File.Exists(movie.Path) ? movie.Path : await AppServices.Api.BuildStreamUrlAsync(movie.Id);
        await _player.LoadAsync(source);
        await SetVolumeAsync(_lastKnownVolume, showOsd: false);

        if (progress.Position > 5)
        {
            ShowResumePrompt(progress.Position);
        }

        _ = LoadEpisodesAsync(movie);
        _saveTimer.Start();
        ScheduleChromeHide();
    }

    private async Task LoadEpisodesAsync(MovieDto movie)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(movie.FolderLevels))
            {
                UpdateEpisodes([]);
                return;
            }

            var primary = await AppServices.Movie.GetMoviesAsync(movie.MediaRoot, movie.FolderLevels, "", "name", 2000, 0);
            var items = primary.Movies;
            var parent = ParentFolder(movie.FolderLevels);
            if (items.Count <= 1 && !string.IsNullOrWhiteSpace(parent))
            {
                var fallback = await AppServices.Movie.GetMoviesAsync(movie.MediaRoot, parent, "", "name", 2000, 0);
                if (fallback.Movies.Any(item => item.Id == movie.Id))
                {
                    items = fallback.Movies;
                }
            }

            UpdateEpisodes(SortEpisodes(items).ToList());
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load native player episode switcher.");
            UpdateEpisodes([]);
        }
    }

    private void UpdateEpisodes(IReadOnlyList<MovieDto> episodes)
    {
        DispatcherQueue.TryEnqueue(() =>
        {
            _episodes.Clear();
            _episodes.AddRange(episodes);
            _episodeButton.Visibility = _episodes.Count > 1 ? Visibility.Visible : Visibility.Collapsed;
            _episodePanelOpen = _episodePanelOpen && _episodes.Count > 1;
            RenderEpisodePanel();
            UpdateEpisodePanelVisibility();
        });
    }

    private void RenderEpisodePanel()
    {
        _episodeItems.Children.Clear();
        _episodeCountText.Text = _episodes.Count.ToString(CultureInfo.InvariantCulture);

        foreach (var episode in _episodes)
        {
            _episodeItems.Children.Add(CreateEpisodeButton(episode));
        }
    }

    private Button CreateEpisodeButton(MovieDto episode)
    {
        var active = episode.Id == _movieId;
        var button = FluentTheme.ApplyButton(new Button
        {
            HorizontalAlignment = HorizontalAlignment.Stretch,
            HorizontalContentAlignment = HorizontalAlignment.Stretch,
            Padding = new Thickness(10, 8, 10, 8),
        }, active ? FluentButtonStyle.Accent : FluentButtonStyle.Overlay);
        AutomationProperties.SetAutomationId(button, $"PlayerEpisode_{episode.Id}");
        button.Click += async (_, _) =>
        {
            if (episode.Id == _movieId)
            {
                return;
            }

            try
            {
                await SaveProgressAsync(true);
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, "Failed to save progress before native episode switch.");
            }

            ShellPage.Current?.NavigateToPlayer(episode.Id);
        };

        var row = new Grid { ColumnSpacing = 10 };
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

        row.Children.Add(new Border
        {
            Width = 8,
            Height = 8,
            CornerRadius = new CornerRadius(4),
            Background = active ? Brush(0xFF, 0xFF, 0xFF) : Brush(0xFF, 0xFF, 0xFF, 0x3D),
            VerticalAlignment = VerticalAlignment.Center,
        });

        var textStack = new StackPanel { Spacing = 2 };
        Grid.SetColumn(textStack, 1);
        textStack.Children.Add(new TextBlock
        {
            Text = EpisodeLabel(episode),
            Foreground = Brush(0xFF, 0xFF, 0xFF),
            FontSize = 13,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            TextTrimming = TextTrimming.CharacterEllipsis,
        });
        textStack.Children.Add(new TextBlock
        {
            Text = EpisodeMeta(episode),
            Foreground = Brush(0xB8, 0xC0, 0xCC),
            FontSize = 11,
            TextTrimming = TextTrimming.CharacterEllipsis,
        });
        row.Children.Add(textStack);
        button.Content = row;
        return button;
    }

    private void OnPlayerStateChanged(object? sender, PlayerStateSnapshot state)
    {
        DispatcherQueue.TryEnqueue(() =>
        {
            _state = state;
            _duration = state.Duration;

            if (state.Volume > 0)
            {
                _lastKnownVolume = state.Volume;
                _muted = false;
            }
            else
            {
                _muted = true;
            }

            SelectSpeedBox(state.Speed);
            UpdateTrackLabels(state);

            if (state.Paused)
            {
                ShowChrome(true);
            }
            else
            {
                ScheduleChromeHide();
            }
        });
    }

    private void UpdateTrackLabels(PlayerStateSnapshot state)
    {
        var subtitleTracks = SubtitleTracks(state).ToList();
        var audioTracks = AudioTracks(state).ToList();
        var selectedSubtitle = subtitleTracks.FirstOrDefault(track => track.Id == state.SubtitleId);
        var selectedAudio = audioTracks.FirstOrDefault(track => track.Id == state.AudioId);

        _subtitleButton.Content = subtitleTracks.Count == 0
            ? "字幕 无"
            : selectedSubtitle is null ? "字幕 关" : $"字幕 {ShortTrackName(selectedSubtitle)}";
        _subtitleButton.IsEnabled = subtitleTracks.Count > 0;

        _audioButton.Content = audioTracks.Count == 0
            ? "音轨 无"
            : selectedAudio is null ? "音轨 自动" : $"音轨 {ShortTrackName(selectedAudio)}";
        _audioButton.IsEnabled = audioTracks.Count > 0;

        var summary = new List<string>();
        if (selectedAudio is not null)
        {
            summary.Add($"音轨 {selectedAudio.DisplayName}");
        }

        summary.Add(selectedSubtitle is null ? "字幕关" : $"字幕 {selectedSubtitle.DisplayName}");
        _trackSummaryText.Text = string.Join("  ·  ", summary);
    }

    private async void OnPlayPauseClicked(object sender, RoutedEventArgs args)
    {
        await TogglePlayPauseAsync();
    }

    private async Task TogglePlayPauseAsync()
    {
        try
        {
            if (_player is not null)
            {
                await _player.PlayPauseAsync();
                ShowChrome(true);
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to toggle native playback.");
            ShowPlaybackError($"播放控制失败：{ex.Message}");
        }
    }

    private async Task SeekRelativeAsync(double seconds)
    {
        if (_player is null)
        {
            return;
        }

        try
        {
            var max = _duration > 0 ? _duration : Math.Max(_state.Duration, _state.Position + Math.Abs(seconds));
            var target = Math.Clamp(_state.Position + seconds, 0, Math.Max(1, max));
            await _player.SeekAsync(target);
            ShowSeekOsd(target - _state.Position, target);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to seek native playback.");
            ShowPlaybackError($"跳转失败：{ex.Message}");
        }
    }

    private async Task SetVolumeAsync(double volume, bool showOsd)
    {
        try
        {
            var value = Math.Clamp(volume, 0, 100);
            _muted = value <= 0;
            if (value > 0)
            {
                _lastKnownVolume = value;
            }

            if (_player is not null)
            {
                await _player.SetVolumeAsync(value);
            }

            if (showOsd)
            {
                ShowOsd($"音量 {Math.Round(value)}%");
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to set native playback volume.");
            ShowPlaybackError($"音量设置失败：{ex.Message}");
        }
    }

    private async Task ToggleMuteAsync()
    {
        await SetVolumeAsync(_muted ? Math.Max(20, _lastKnownVolume) : 0, showOsd: true);
    }

    private async Task ChangeVolumeAsync(double delta)
    {
        await SetVolumeAsync(Math.Clamp(_state.Volume + delta, 0, 100), showOsd: true);
    }

    private async void OnSpeedChanged(object sender, SelectionChangedEventArgs args)
    {
        if (_ignoreSpeed || _player is null || _speedBox.SelectedItem is not ComboBoxItem item)
        {
            return;
        }

        if (double.TryParse(item.Tag?.ToString(), NumberStyles.Float, CultureInfo.InvariantCulture, out var speed))
        {
            await SetSpeedAsync(speed, showOsd: true);
        }
    }

    private async Task SetSpeedAsync(double speed, bool showOsd)
    {
        try
        {
            if (_player is not null)
            {
                await _player.SetSpeedAsync(speed);
            }

            if (showOsd)
            {
                ShowOsd($"{speed:0.##}x");
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to set native playback speed.");
            ShowPlaybackError($"倍速设置失败：{ex.Message}");
        }
    }

    private void OnSubtitleClicked(object sender, RoutedEventArgs args)
    {
        var tracks = SubtitleTracks(_state).ToList();
        if (tracks.Count == 0)
        {
            return;
        }

        var flyout = new MenuFlyout();
        var off = new MenuFlyoutItem { Text = _state.SubtitleId <= 0 ? "* 关闭字幕" : "关闭字幕" };
        off.Click += async (_, _) => await SelectSubtitleAsync(0, "字幕已关闭");
        flyout.Items.Add(off);

        foreach (var track in tracks)
        {
            var item = new MenuFlyoutItem
            {
                Text = track.Id == _state.SubtitleId ? $"* {track.DisplayName}" : track.DisplayName,
            };
            item.Click += async (_, _) => await SelectSubtitleAsync(track.Id, $"字幕 {ShortTrackName(track)}");
            flyout.Items.Add(item);
        }

        flyout.ShowAt(_subtitleButton);
    }

    private async Task SelectSubtitleAsync(int subtitleId, string message)
    {
        try
        {
            if (_player is not null)
            {
                await _player.SelectSubtitleAsync(subtitleId);
                ShowOsd(message);
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to select native subtitle track.");
            ShowPlaybackError($"字幕切换失败：{ex.Message}");
        }
    }

    private void OnAudioClicked(object sender, RoutedEventArgs args)
    {
        var tracks = AudioTracks(_state).ToList();
        if (tracks.Count == 0)
        {
            return;
        }

        var flyout = new MenuFlyout();
        var auto = new MenuFlyoutItem { Text = _state.AudioId <= 0 ? "* 自动" : "自动" };
        auto.Click += async (_, _) => await SelectAudioAsync(0, "音轨 自动");
        flyout.Items.Add(auto);

        foreach (var track in tracks)
        {
            var item = new MenuFlyoutItem
            {
                Text = track.Id == _state.AudioId ? $"* {track.DisplayName}" : track.DisplayName,
            };
            item.Click += async (_, _) => await SelectAudioAsync(track.Id, $"音轨 {ShortTrackName(track)}");
            flyout.Items.Add(item);
        }

        flyout.ShowAt(_audioButton);
    }

    private async Task SelectAudioAsync(int audioId, string message)
    {
        try
        {
            if (_player is not null)
            {
                await _player.SelectAudioAsync(audioId);
                ShowOsd(message);
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to select native audio track.");
            ShowPlaybackError($"音轨切换失败：{ex.Message}");
        }
    }

    private void OnEpisodeButtonClicked(object sender, RoutedEventArgs args)
    {
        _episodePanelOpen = !_episodePanelOpen;
        UpdateEpisodePanelVisibility();
        ShowChrome(true);
    }

    private void UpdateEpisodePanelVisibility()
    {
        _episodePanel.Visibility = _episodePanelOpen && _episodes.Count > 1 ? Visibility.Visible : Visibility.Collapsed;
        ScheduleChromeHide();
    }

    private async void OnResumeClicked(object sender, RoutedEventArgs args)
    {
        if (_player is null || _resumePosition <= 0)
        {
            HideResumePrompt();
            return;
        }

        try
        {
            await _player.SeekAsync(_resumePosition);
            ShowOsd($"继续播放 {FormatTime(_resumePosition)}");
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to resume native playback position.");
            ShowPlaybackError($"继续播放失败：{ex.Message}");
        }
        finally
        {
            HideResumePrompt();
        }
    }

    private void ShowResumePrompt(double position)
    {
        _resumePosition = position;
        _resumeText.Text = $"从上次位置继续 ({FormatTime(position)})";
        _resumePrompt.Visibility = Visibility.Visible;
    }

    private void HideResumePrompt()
    {
        _resumePrompt.Visibility = Visibility.Collapsed;
        _resumePosition = 0;
    }

    private void ToggleFullScreenMode()
    {
        try
        {
            _fullScreenMode = !_fullScreenMode;
            AppServices.MainWindow?.SetFullScreen(_fullScreenMode);
            UpdateFullScreenChrome();
            ShowOsd(_fullScreenMode ? "全屏" : "退出全屏");
        }
        catch (Exception ex)
        {
            _fullScreenMode = false;
            ShellLogger.Error(ex, "Failed to toggle native full screen playback.");
            ShowPlaybackError($"全屏切换失败：{ex.Message}");
        }
    }

    private void UpdateFullScreenChrome()
    {
        ShellPage.Current?.SetNavigationChromeVisible(!_fullScreenMode);
        _fullScreenButton.Content = _fullScreenMode ? "退出全屏" : "全屏";
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
            _chromeTimer.Stop();
            _saveTimer.Stop();
            RestoreWindowChrome();
            await SaveProgressAsync(true);
            if (_player is not null)
            {
                _player.StateChanged -= OnPlayerStateChanged;
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

    private void RestoreWindowChrome()
    {
        try
        {
            if (_fullScreenMode)
            {
                AppServices.MainWindow?.SetFullScreen(false);
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to restore native player full screen state.");
        }

        _fullScreenMode = false;
        ShellPage.Current?.SetNavigationChromeVisible(true);
    }

    private async Task SaveProgressAsync(bool stopped)
    {
        if (_player is null || _movieId <= 0)
        {
            return;
        }

        if (_resumePosition > 0)
        {
            return;
        }

        var state = _player.CurrentState;
        await AppServices.PlaybackProgress.SaveAsync(_movieId, state.Position, _duration > 0 ? _duration : state.Duration, stopped);
    }

    private void OnUserActivity(object sender, PointerRoutedEventArgs args)
    {
        ShowChrome(true);
        ScheduleChromeHide();
    }

    private void OnChromeTimerTick(object? sender, object args)
    {
        if (!_state.Paused && !_episodePanelOpen)
        {
            ShowChrome(false);
        }
    }

    private void ShowChrome(bool visible)
    {
        _controlsVisible = visible;
        var opacity = visible ? 1 : 0;
        _topChrome.Opacity = opacity;
        _topChrome.IsHitTestVisible = visible;
    }

    private void ScheduleChromeHide()
    {
        _chromeTimer.Stop();
        if (_controlsVisible && !_state.Paused && !_episodePanelOpen)
        {
            _chromeTimer.Start();
        }
    }

    private void ShowSeekOsd(double delta, double target)
    {
        var sign = delta >= 0 ? "+" : "-";
        ShowOsd($"{sign}{FormatTime(Math.Abs(delta))}  {FormatTime(target)} / {FormatTime(_duration)}");
    }

    private void ShowOsd(string text)
    {
        try
        {
            _ = _player?.ShowTextAsync(text);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to show native mpv OSD text.");
        }

        ShowChrome(true);
    }

    private async void OnKeyDown(object sender, KeyRoutedEventArgs args)
    {
        switch (args.Key)
        {
            case VirtualKey.Space:
            case VirtualKey.K:
                args.Handled = true;
                await TogglePlayPauseAsync();
                break;
            case VirtualKey.Left:
                args.Handled = true;
                await SeekRelativeAsync(-SeekStepSeconds);
                break;
            case VirtualKey.Right:
                args.Handled = true;
                await SeekRelativeAsync(SeekStepSeconds);
                break;
            case VirtualKey.Up:
                args.Handled = true;
                await ChangeVolumeAsync(5);
                break;
            case VirtualKey.Down:
                args.Handled = true;
                await ChangeVolumeAsync(-5);
                break;
            case VirtualKey.F:
                args.Handled = true;
                ToggleFullScreenMode();
                break;
            case VirtualKey.M:
                args.Handled = true;
                await ToggleMuteAsync();
                break;
            case VirtualKey.Escape:
                args.Handled = true;
                HandleEscape();
                break;
        }
    }

    private void HandleEscape()
    {
        if (_episodePanelOpen)
        {
            _episodePanelOpen = false;
            UpdateEpisodePanelVisibility();
            return;
        }

        if (_fullScreenMode)
        {
            ToggleFullScreenMode();
            return;
        }

    }

    private void SelectSpeedBox(double speed)
    {
        _ignoreSpeed = true;
        for (var index = 0; index < _speedBox.Items.Count; index++)
        {
            if (_speedBox.Items[index] is ComboBoxItem item &&
                double.TryParse(item.Tag?.ToString(), NumberStyles.Float, CultureInfo.InvariantCulture, out var itemSpeed) &&
                Math.Abs(itemSpeed - speed) < 0.01)
            {
                _speedBox.SelectedIndex = index;
                _ignoreSpeed = false;
                return;
            }
        }

        _ignoreSpeed = false;
    }

    private static IEnumerable<PlayerTrack> SubtitleTracks(PlayerStateSnapshot state)
        => state.Tracks
            .Where(track => string.Equals(track.Type, "sub", StringComparison.OrdinalIgnoreCase))
            .OrderBy(track => track.External)
            .ThenBy(track => string.IsNullOrWhiteSpace(track.Language) ? "zz" : track.Language, StringComparer.OrdinalIgnoreCase)
            .ThenBy(track => track.Id);

    private static IEnumerable<PlayerTrack> AudioTracks(PlayerStateSnapshot state)
        => state.Tracks
            .Where(track => string.Equals(track.Type, "audio", StringComparison.OrdinalIgnoreCase))
            .OrderBy(track => track.Id);

    private static string ShortTrackName(PlayerTrack track)
    {
        var label = track.DisplayName;
        return label.Length <= 16 ? label : $"{label[..15]}...";
    }

    private static void AddSpeedOption(ComboBox box, string label, double value)
    {
        box.Items.Add(new ComboBoxItem
        {
            Content = label,
            Tag = value.ToString(CultureInfo.InvariantCulture),
        });
    }

    private static Button OverlayButton(string text, string automationId)
    {
        var button = FluentTheme.ApplyButton(new Button
        {
            Content = text,
            MinHeight = 34,
            MinWidth = 64,
            MaxWidth = 150,
        }, FluentButtonStyle.Overlay);
        button.Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent);
        button.BorderBrush = new SolidColorBrush(Microsoft.UI.Colors.Transparent);
        button.Foreground = Brush(0xFF, 0xFF, 0xFF);
        button.Padding = new Thickness(10, 6, 10, 6);
        AutomationProperties.SetAutomationId(button, automationId);
        return button;
    }

    private static IEnumerable<MovieDto> SortEpisodes(IEnumerable<MovieDto> movies)
        => movies
            .OrderBy(movie => movie.TmdbSeason ?? 0)
            .ThenBy(EpisodeSortKey)
            .ThenBy(movie => string.IsNullOrWhiteSpace(movie.Path) ? movie.Code : movie.Path, StringComparer.CurrentCultureIgnoreCase);

    private static int EpisodeSortKey(MovieDto movie)
    {
        if (movie.TmdbEpisode is > 0)
        {
            return movie.TmdbEpisode.Value;
        }

        if (movie.EpisodeNumber is > 0)
        {
            return movie.EpisodeNumber.Value;
        }

        var text = string.Join(" ", new[] { movie.DisplayTitle, movie.EpisodeTitle, movie.Code, Path.GetFileName(movie.Path) }.Where(value => !string.IsNullOrWhiteSpace(value)));
        var match = Regex.Match(text, @"[Ss]\d{1,2}\s*[Ee](\d{1,4})|(?:EP?|第)\s*0*(\d{1,4})\s*(?:集|話|话)?", RegexOptions.IgnoreCase);
        if (match.Success && int.TryParse(string.IsNullOrWhiteSpace(match.Groups[1].Value) ? match.Groups[2].Value : match.Groups[1].Value, out var value))
        {
            return value;
        }

        return int.MaxValue;
    }

    private static string EpisodeLabel(MovieDto movie)
    {
        var number = movie.TmdbEpisode ?? movie.EpisodeNumber;
        var prefix = number is not null
            ? $"{(movie.TmdbSeason is not null ? $"S{movie.TmdbSeason.Value:00}" : "")}E{number.Value:00}"
            : "";
        var title = FirstNonEmpty(movie.EpisodeTitle, movie.DisplayTitle, movie.Title, movie.Code, Path.GetFileNameWithoutExtension(movie.Path));
        if (string.IsNullOrWhiteSpace(prefix) || title.Contains(prefix, StringComparison.OrdinalIgnoreCase))
        {
            return title;
        }

        return $"{prefix} {title}";
    }

    private static string EpisodeMeta(MovieDto movie)
    {
        var parts = new List<string>();
        if (movie.Duration > 0)
        {
            parts.Add($"{movie.Duration}分");
        }
        else if (!string.IsNullOrWhiteSpace(movie.Code))
        {
            parts.Add(movie.Code);
        }

        var progress = Math.Clamp(movie.ProgressPercent, 0, 100);
        if (progress > 0 && progress < 90)
        {
            parts.Add($"{Math.Round(progress)}%");
        }

        return parts.Count == 0 ? "未播放" : string.Join(" · ", parts);
    }

    private static string ParentFolder(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || !path.Contains('/'))
        {
            return "";
        }

        var parts = path.Split('/', StringSplitOptions.RemoveEmptyEntries);
        return parts.Length <= 1 ? "" : string.Join("/", parts.Take(parts.Length - 1));
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

        return "未命名影片";
    }

    private static string FormatTime(double seconds)
    {
        if (seconds <= 0 || double.IsNaN(seconds) || double.IsInfinity(seconds))
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
        ShowChrome(true);
        _speedBox.IsEnabled = false;
        _subtitleButton.IsEnabled = false;
        _audioButton.IsEnabled = false;
        _episodeButton.IsEnabled = false;
    }
}
