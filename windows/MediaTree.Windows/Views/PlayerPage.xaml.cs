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
using MediaTree.Windows.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Controls.Primitives;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;
using Microsoft.UI.Xaml.Navigation;
using Windows.System;

namespace MediaTree.Windows.Views;

public sealed partial class PlayerPage : Page
{
    private const double SeekStepSeconds = 5;

    private sealed record PlayerUi(
        Grid Root,
        Border PlayerFrame,
        MpvPlayerControl PlayerHost,
        Border TopChrome,
        Border BottomChrome,
        Button PlayPauseButton,
        Button SubtitleButton,
        Button AudioButton,
        Button EpisodeButton,
        Button VolumeButton,
        Button VolumeMuteButton,
        Button FullScreenButton,
        Slider ProgressSlider,
        Slider VolumeSlider,
        FrameworkElement VolumePanel,
        Flyout VolumeFlyout,
        ComboBox SpeedBox,
        TextBlock TitleText,
        TextBlock TrackSummaryText,
        TextBlock TimeText,
        TextBlock StatusText,
        Border ResumePrompt,
        TextBlock ResumeText,
        Border EpisodePanel,
        TextBlock EpisodeCountText,
        StackPanel EpisodeItems,
        StackPanel DetailHost,
        TextBlock DetailTitleText,
        TextBlock DetailOriginalTitleText,
        TextBlock DetailMetaText,
        TextBlock DetailProgressText,
        StackPanel DetailActions,
        Button FavoriteButton,
        Button WantButton,
        Button WatchedButton,
        Button DetailMoreButton,
        TextBlock DetailOverviewText,
        TextBlock DetailEpisodeOverviewText,
        TextBlock DetailPathText,
        TextBlock DetailStaffText,
        TextBlock DetailStatusText,
        Border DetailEpisodesCard,
        TextBlock DetailEpisodesTitleText,
        GridView DetailEpisodesGrid,
        Border SpecialsCard,
        TextBlock SpecialsTitleText,
        Button SpecialsToggleButton,
        GridView SpecialsGrid,
        Border ThumbnailsCard,
        TextBlock ThumbnailsTitleText,
        GridView ThumbnailsGrid);

    private readonly DispatcherTimer _chromeTimer = new() { Interval = TimeSpan.FromSeconds(3) };
    private readonly DispatcherTimer _resumePromptTimer = new() { Interval = TimeSpan.FromSeconds(5) };
    private readonly DispatcherTimer _saveTimer = new() { Interval = TimeSpan.FromSeconds(5) };
    private readonly Button _audioButton;
    private readonly Border _bottomChrome;
    private readonly Button _episodeButton;
    private readonly TextBlock _episodeCountText;
    private readonly StackPanel _episodeItems;
    private readonly Border _episodePanel;
    private readonly Button _fullScreenButton;
    private readonly Button _playPauseButton;
    private readonly MpvPlayerControl _playerHost;
    private readonly Slider _progressSlider;
    private readonly TextBlock _resumeText;
    private readonly Border _resumePrompt;
    private readonly Grid _root;
    private readonly ComboBox _speedBox;
    private readonly TextBlock _statusText;
    private readonly Button _subtitleButton;
    private readonly TextBlock _timeText;
    private readonly TextBlock _titleText;
    private readonly Border _topChrome;
    private readonly TextBlock _trackSummaryText;
    private readonly Button _volumeButton;
    private readonly Button _volumeMuteButton;
    private readonly Slider _volumeSlider;
    private readonly FrameworkElement _volumePanel;
    private readonly Flyout _volumeFlyout;
    private readonly List<MovieDto> _episodes = [];
    private readonly List<MovieDto> _specialMovies = [];
    private readonly StackPanel _detailHost;
    private readonly TextBlock _detailTitleText;
    private readonly TextBlock _detailOriginalTitleText;
    private readonly TextBlock _detailMetaText;
    private readonly TextBlock _detailProgressText;
    private readonly StackPanel _detailActions;
    private readonly Button _favoriteButton;
    private readonly Button _wantButton;
    private readonly Button _watchedButton;
    private readonly Button _detailMoreButton;
    private readonly TextBlock _detailOverviewText;
    private readonly TextBlock _detailEpisodeOverviewText;
    private readonly TextBlock _detailPathText;
    private readonly TextBlock _detailStaffText;
    private readonly TextBlock _detailStatusText;
    private readonly Border _detailEpisodesCard;
    private readonly TextBlock _detailEpisodesTitleText;
    private readonly GridView _detailEpisodesGrid;
    private readonly Border _specialsCard;
    private readonly TextBlock _specialsTitleText;
    private readonly Button _specialsToggleButton;
    private readonly GridView _specialsGrid;
    private readonly Border _thumbnailsCard;
    private readonly TextBlock _thumbnailsTitleText;
    private readonly GridView _thumbnailsGrid;
    private IMpvPlayerService? _player;
    private MovieDto? _movie;
    private PlayerStateSnapshot _state = new(0, 0, true);
    private int _movieId;
    private bool _controlsVisible = true;
    private bool _episodePanelOpen;
    private bool _fullScreenMode;
    private bool _ignoreProgress;
    private bool _ignoreSpeed;
    private bool _ignoreVolume;
    private bool _muted;
    private bool _playbackStarted;
    private bool _resumePromptAutoHideScheduled;
    private bool _specialsExpanded;
    private bool _volumePanelOpen;
    private double _duration;
    private double _lastKnownVolume = 80;
    private double _resumePosition;

    public PlayerPage()
    {
        var ui = BuildContent();
        _root = ui.Root;
        _playerHost = ui.PlayerHost;
        _topChrome = ui.TopChrome;
        _bottomChrome = ui.BottomChrome;
        _playPauseButton = ui.PlayPauseButton;
        _subtitleButton = ui.SubtitleButton;
        _audioButton = ui.AudioButton;
        _episodeButton = ui.EpisodeButton;
        _volumeButton = ui.VolumeButton;
        _volumeMuteButton = ui.VolumeMuteButton;
        _fullScreenButton = ui.FullScreenButton;
        _progressSlider = ui.ProgressSlider;
        _volumeSlider = ui.VolumeSlider;
        _volumePanel = ui.VolumePanel;
        _volumeFlyout = ui.VolumeFlyout;
        _speedBox = ui.SpeedBox;
        _titleText = ui.TitleText;
        _trackSummaryText = ui.TrackSummaryText;
        _timeText = ui.TimeText;
        _statusText = ui.StatusText;
        _resumePrompt = ui.ResumePrompt;
        _resumeText = ui.ResumeText;
        _episodePanel = ui.EpisodePanel;
        _episodeCountText = ui.EpisodeCountText;
        _episodeItems = ui.EpisodeItems;
        _detailHost = ui.DetailHost;
        _detailTitleText = ui.DetailTitleText;
        _detailOriginalTitleText = ui.DetailOriginalTitleText;
        _detailMetaText = ui.DetailMetaText;
        _detailProgressText = ui.DetailProgressText;
        _detailActions = ui.DetailActions;
        _favoriteButton = ui.FavoriteButton;
        _wantButton = ui.WantButton;
        _watchedButton = ui.WatchedButton;
        _detailMoreButton = ui.DetailMoreButton;
        _detailOverviewText = ui.DetailOverviewText;
        _detailEpisodeOverviewText = ui.DetailEpisodeOverviewText;
        _detailPathText = ui.DetailPathText;
        _detailStaffText = ui.DetailStaffText;
        _detailStatusText = ui.DetailStatusText;
        _detailEpisodesCard = ui.DetailEpisodesCard;
        _detailEpisodesTitleText = ui.DetailEpisodesTitleText;
        _detailEpisodesGrid = ui.DetailEpisodesGrid;
        _specialsCard = ui.SpecialsCard;
        _specialsTitleText = ui.SpecialsTitleText;
        _specialsToggleButton = ui.SpecialsToggleButton;
        _specialsGrid = ui.SpecialsGrid;
        _thumbnailsCard = ui.ThumbnailsCard;
        _thumbnailsTitleText = ui.ThumbnailsTitleText;
        _thumbnailsGrid = ui.ThumbnailsGrid;

        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
        _chromeTimer.Tick += OnChromeTimerTick;
        _resumePromptTimer.Tick += OnResumePromptTimerTick;
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
        AddPlaybackKeyboardAccelerators(root);
        root.PointerMoved += OnUserPointerMoved;
        root.PointerPressed += OnUserPointerPressed;
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
            RequestedTheme = ElementTheme.Dark,
        };
        AutomationProperties.SetAutomationId(topChrome, "PlayerTopChrome");

        var topGrid = new Grid { ColumnSpacing = 12 };
        topGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        topGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        topGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        topChrome.Child = topGrid;

        var backButton = OverlayButton("返回", "PlayerBackButton");
        AttachPlaybackKeyHandler(backButton);
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
        var topToolbar = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 8,
            VerticalAlignment = VerticalAlignment.Center,
        };
        toolbarScroll.Content = topToolbar;

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
        AttachPlaybackKeyHandler(speedBox);
        speedBox.SelectionChanged += OnSpeedChanged;
        topToolbar.Children.Add(speedBox);

        var subtitleButton = OverlayButton("字幕", "PlayerSubtitle");
        AttachPlaybackKeyHandler(subtitleButton);
        subtitleButton.Click += OnSubtitleClicked;

        var audioButton = OverlayButton("音轨", "PlayerAudio");
        AttachPlaybackKeyHandler(audioButton);
        audioButton.Click += OnAudioClicked;

        var episodeButton = OverlayButton("选集", "PlayerEpisodes");
        episodeButton.Visibility = Visibility.Collapsed;
        AttachPlaybackKeyHandler(episodeButton);
        episodeButton.Click += OnEpisodeButtonClicked;
        topToolbar.Children.Add(episodeButton);

        var fullScreenButton = OverlayButton("全屏", "PlayerFullScreen");
        AttachPlaybackKeyHandler(fullScreenButton);
        fullScreenButton.Click += (_, _) => ToggleFullScreenMode();

        Grid.SetColumn(toolbarScroll, 2);
        topGrid.Children.Add(toolbarScroll);
        root.Children.Add(topChrome);

        var bottomChrome = new Border
        {
            Margin = new Thickness(16, 0, 16, 16),
            Padding = new Thickness(0),
            Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent),
            BorderThickness = new Thickness(0),
            VerticalAlignment = VerticalAlignment.Bottom,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            RequestedTheme = ElementTheme.Dark,
        };
        AutomationProperties.SetAutomationId(bottomChrome, "PlayerBottomChrome");

        var bottomStack = new StackPanel { Spacing = 6 };
        bottomChrome.Child = bottomStack;

        var progressSlider = new Slider
        {
            Minimum = 0,
            Maximum = 1,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            MinHeight = 28,
        };
        AutomationProperties.SetAutomationId(progressSlider, "PlayerProgressSlider");
        AttachPlaybackKeyHandler(progressSlider);
        progressSlider.ValueChanged += OnProgressSliderChanged;
        bottomStack.Children.Add(progressSlider);

        var controlGrid = new Grid { ColumnSpacing = 12 };
        controlGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        controlGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        var playbackControls = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 8,
            VerticalAlignment = VerticalAlignment.Center,
        };
        var playPauseButton = OverlayButton("暂停", "PlayerPlayPause");
        AttachPlaybackKeyHandler(playPauseButton);
        playPauseButton.Click += OnPlayPauseClicked;
        playbackControls.Children.Add(playPauseButton);

        var timeText = new TextBlock
        {
            Text = "0:00 / 0:00",
            Foreground = Brush(0xFF, 0xFF, 0xFF),
            FontSize = 13,
            MinWidth = 128,
            VerticalAlignment = VerticalAlignment.Center,
        };
        AutomationProperties.SetAutomationId(timeText, "PlayerTime");
        playbackControls.Children.Add(timeText);
        controlGrid.Children.Add(playbackControls);

        var bottomControlsScroll = new ScrollViewer
        {
            HorizontalScrollBarVisibility = ScrollBarVisibility.Auto,
            HorizontalScrollMode = ScrollMode.Auto,
            VerticalScrollBarVisibility = ScrollBarVisibility.Disabled,
            VerticalScrollMode = ScrollMode.Disabled,
            VerticalAlignment = VerticalAlignment.Center,
            HorizontalAlignment = HorizontalAlignment.Right,
            MaxWidth = 520,
        };
        var bottomControls = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 8,
            VerticalAlignment = VerticalAlignment.Center,
            HorizontalAlignment = HorizontalAlignment.Right,
        };
        bottomControlsScroll.Content = bottomControls;
        bottomControls.Children.Add(subtitleButton);
        bottomControls.Children.Add(audioButton);

        var volumeButton = OverlayButton("音量", "PlayerVolume");
        AttachPlaybackKeyHandler(volumeButton);
        volumeButton.Click += OnVolumeButtonClicked;
        bottomControls.Children.Add(volumeButton);
        bottomControls.Children.Add(fullScreenButton);

        Grid.SetColumn(bottomControlsScroll, 1);
        controlGrid.Children.Add(bottomControlsScroll);
        bottomStack.Children.Add(controlGrid);
        root.Children.Add(bottomChrome);

        var volumePanelStack = new StackPanel
        {
            Width = 220,
            Padding = new Thickness(12),
            Spacing = 10,
            RequestedTheme = ElementTheme.Dark,
        };
        AutomationProperties.SetAutomationId(volumePanelStack, "PlayerVolumePanel");
        volumePanelStack.Children.Add(new TextBlock
        {
            Text = "音量",
            Foreground = Brush(0xFF, 0xFF, 0xFF),
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
        });

        var volumeSlider = new Slider
        {
            Minimum = 0,
            Maximum = 100,
            Value = 80,
            Width = 196,
            VerticalAlignment = VerticalAlignment.Center,
        };
        AutomationProperties.SetAutomationId(volumeSlider, "PlayerVolumeSlider");
        AttachPlaybackKeyHandler(volumeSlider);
        volumeSlider.ValueChanged += OnVolumeChanged;
        volumePanelStack.Children.Add(volumeSlider);

        var volumeMuteButton = OverlayButton("静音", "PlayerMute");
        volumeMuteButton.HorizontalAlignment = HorizontalAlignment.Stretch;
        volumeMuteButton.MaxWidth = double.PositiveInfinity;
        AttachPlaybackKeyHandler(volumeMuteButton);
        volumeMuteButton.Click += async (_, _) => await ToggleMuteAsync();
        volumePanelStack.Children.Add(volumeMuteButton);
        volumePanelStack.PointerPressed += (_, args) => args.Handled = true;

        var volumeFlyout = new Flyout
        {
            Content = volumePanelStack,
            Placement = FlyoutPlacementMode.TopEdgeAlignedRight,
            ShouldConstrainToRootBounds = true,
        };
        volumeFlyout.Opened += (_, _) =>
        {
            _volumePanelOpen = true;
            ShowChrome(true);
        };
        volumeFlyout.Closed += (_, _) =>
        {
            _volumePanelOpen = false;
            ScheduleChromeHide();
        };
        FlyoutBase.SetAttachedFlyout(volumeButton, volumeFlyout);

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
            Padding = new Thickness(0),
            Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent),
            BorderThickness = new Thickness(0),
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
        AttachPlaybackKeyHandler(resumeButton);
        resumeButton.Click += OnResumeClicked;
        resumeActions.Children.Add(resumeButton);

        var closeResumeButton = FluentTheme.ApplyButton(new Button
        {
            Content = "关闭",
            MinHeight = 36,
        }, FluentButtonStyle.Overlay);
        AutomationProperties.SetAutomationId(closeResumeButton, "PlayerResumeClose");
        AttachPlaybackKeyHandler(closeResumeButton);
        closeResumeButton.Click += (_, _) => HideResumePrompt();
        resumeActions.Children.Add(closeResumeButton);
        resumePrompt.Child = resumeActions;
        root.Children.Add(resumePrompt);

        root.SizeChanged += (_, args) => ApplyPlayerResponsiveLayout(
            args.NewSize.Width,
            topChrome,
            bottomChrome,
            volumeSlider,
            volumePanelStack,
            timeText,
            episodePanel,
            resumePrompt);

        var playerFrame = new Border
        {
            Background = Brush(0, 0, 0),
            CornerRadius = FluentTheme.MediaCornerRadius,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(1),
            MinHeight = 320,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            Child = root,
        };
        AutomationProperties.SetAutomationId(playerFrame, "PlayerFrame");

        var detailHost = new StackPanel
        {
            Spacing = 16,
            MaxWidth = 1180,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };
        AutomationProperties.SetAutomationId(detailHost, "PlayerDetailHost");

        var detailHeader = new Grid { ColumnSpacing = 18 };
        detailHeader.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        detailHeader.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        var titleBlock = new StackPanel { Spacing = 8 };
        var detailTitleText = new TextBlock
        {
            FontSize = 28,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(detailTitleText, "PlayerDetailTitle");
        titleBlock.Children.Add(detailTitleText);

        var detailOriginalTitleText = new TextBlock
        {
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
            Visibility = Visibility.Collapsed,
        };
        AutomationProperties.SetAutomationId(detailOriginalTitleText, "PlayerDetailOriginalTitle");
        titleBlock.Children.Add(detailOriginalTitleText);

        var detailMetaText = new TextBlock
        {
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(detailMetaText, "PlayerDetailMeta");
        titleBlock.Children.Add(detailMetaText);

        var detailProgressText = new TextBlock
        {
            Foreground = FluentTheme.Accent,
            FontSize = 13,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(detailProgressText, "PlayerDetailProgress");
        titleBlock.Children.Add(detailProgressText);
        detailHeader.Children.Add(titleBlock);

        var detailActions = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 8,
            VerticalAlignment = VerticalAlignment.Bottom,
        };
        Grid.SetColumn(detailActions, 1);

        var favoriteButton = DetailActionButton("收藏", "PlayerDetailFavorite");
        favoriteButton.Click += async (_, _) => await ToggleTagAsync("favorite");
        detailActions.Children.Add(favoriteButton);

        var wantButton = DetailActionButton("想看", "PlayerDetailWant");
        wantButton.Click += async (_, _) => await ToggleTagAsync("want_to_watch");
        detailActions.Children.Add(wantButton);

        var watchedButton = DetailActionButton("标为已看", "PlayerDetailWatched");
        watchedButton.Click += async (_, _) => await ToggleTagAsync("watched");
        detailActions.Children.Add(watchedButton);

        var detailMoreButton = DetailActionButton("更多", "PlayerDetailMore");
        detailMoreButton.Click += OnDetailMoreClicked;
        detailActions.Children.Add(detailMoreButton);
        detailHeader.Children.Add(detailActions);

        var detailStatusText = new TextBlock
        {
            Foreground = FluentTheme.TextSecondary,
            Visibility = Visibility.Collapsed,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(detailStatusText, "PlayerDetailStatus");

        var heroStack = new StackPanel { Spacing = 14 };
        heroStack.Children.Add(detailHeader);
        heroStack.Children.Add(detailStatusText);
        detailHost.Children.Add(FluentTheme.Card(heroStack, new Thickness(20)));

        var detailEpisodesGrid = DetailGrid("PlayerDetailEpisodesGrid", 430);
        var detailEpisodesTitleText = SectionTitle("选集");
        AutomationProperties.SetAutomationId(detailEpisodesTitleText, "PlayerDetailEpisodesTitle");
        var detailEpisodesStack = SectionStack(detailEpisodesTitleText, detailEpisodesGrid);
        var detailEpisodesCard = FluentTheme.Card(detailEpisodesStack, new Thickness(16));
        detailEpisodesCard.Visibility = Visibility.Collapsed;
        AutomationProperties.SetAutomationId(detailEpisodesCard, "PlayerDetailEpisodesCard");
        detailHost.Children.Add(detailEpisodesCard);

        var specialsGrid = DetailGrid("PlayerDetailSpecialsGrid", 430);
        var specialsTitleText = SectionTitle("花絮");
        AutomationProperties.SetAutomationId(specialsTitleText, "PlayerDetailSpecialsTitle");
        var specialsToggleButton = FluentTheme.ApplyButton(new Button
        {
            Content = "展开",
            HorizontalAlignment = HorizontalAlignment.Right,
        });
        AutomationProperties.SetAutomationId(specialsToggleButton, "PlayerDetailSpecialsToggle");
        AttachPlaybackKeyHandler(specialsToggleButton);
        specialsToggleButton.Click += OnSpecialsToggleClicked;
        var specialsStack = SectionStack(specialsTitleText, specialsGrid, specialsToggleButton);
        specialsGrid.Visibility = Visibility.Collapsed;
        var specialsCard = FluentTheme.Card(specialsStack, new Thickness(16));
        specialsCard.Visibility = Visibility.Collapsed;
        AutomationProperties.SetAutomationId(specialsCard, "PlayerDetailSpecialsCard");
        detailHost.Children.Add(specialsCard);

        var thumbnailsGrid = DetailGrid("PlayerDetailThumbnailsGrid", 260);
        var thumbnailsTitleText = SectionTitle("缩略图");
        AutomationProperties.SetAutomationId(thumbnailsTitleText, "PlayerDetailThumbnailsTitle");
        var thumbnailsCard = FluentTheme.Card(SectionStack(thumbnailsTitleText, thumbnailsGrid), new Thickness(16));
        thumbnailsCard.Visibility = Visibility.Collapsed;
        AutomationProperties.SetAutomationId(thumbnailsCard, "PlayerDetailThumbnailsCard");
        detailHost.Children.Add(thumbnailsCard);

        var detailOverviewText = DetailBodyText("还没有简介。", "PlayerDetailOverview");
        var detailEpisodeOverviewText = DetailBodyText("", "PlayerDetailEpisodeOverview");
        detailEpisodeOverviewText.Visibility = Visibility.Collapsed;
        var detailStaffText = DetailBodyText("", "PlayerDetailStaff");
        detailStaffText.Visibility = Visibility.Collapsed;
        var detailPathText = DetailBodyText("", "PlayerDetailPath");
        detailPathText.Foreground = FluentTheme.TextTertiary;
        detailPathText.FontSize = 12;

        var infoStack = new StackPanel { Spacing = 12 };
        infoStack.Children.Add(SectionTitle("影片信息"));
        infoStack.Children.Add(detailOverviewText);
        infoStack.Children.Add(detailEpisodeOverviewText);
        infoStack.Children.Add(detailStaffText);
        infoStack.Children.Add(detailPathText);
        detailHost.Children.Add(FluentTheme.Card(infoStack, new Thickness(16)));

        var contentStack = new StackPanel { Spacing = 18 };
        contentStack.Children.Add(playerFrame);
        contentStack.Children.Add(detailHost);

        var pageRoot = new Grid
        {
            Background = FluentTheme.Canvas,
            Padding = FluentTheme.PagePadding(1200),
            IsTabStop = true,
        };
        pageRoot.KeyDown += OnKeyDown;
        pageRoot.Children.Add(contentStack);

        var scrollViewer = new ScrollViewer
        {
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
            HorizontalScrollMode = ScrollMode.Disabled,
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            VerticalScrollMode = ScrollMode.Auto,
            Content = pageRoot,
        };
        scrollViewer.KeyDown += OnKeyDown;
        scrollViewer.SizeChanged += (_, args) => ApplyPageResponsiveLayout(
            args.NewSize.Width,
            args.NewSize.Height,
            pageRoot,
            playerFrame,
            detailHeader,
            detailActions,
            detailHost);

        Content = scrollViewer;
        return new PlayerUi(
            root,
            playerFrame,
            playerHost,
            topChrome,
            bottomChrome,
            playPauseButton,
            subtitleButton,
            audioButton,
            episodeButton,
            volumeButton,
            volumeMuteButton,
            fullScreenButton,
            progressSlider,
            volumeSlider,
            volumePanelStack,
            volumeFlyout,
            speedBox,
            titleText,
            trackSummaryText,
            timeText,
            statusText,
            resumePrompt,
            resumeText,
            episodePanel,
            episodeCountText,
            episodeItems,
            detailHost,
            detailTitleText,
            detailOriginalTitleText,
            detailMetaText,
            detailProgressText,
            detailActions,
            favoriteButton,
            wantButton,
            watchedButton,
            detailMoreButton,
            detailOverviewText,
            detailEpisodeOverviewText,
            detailPathText,
            detailStaffText,
            detailStatusText,
            detailEpisodesCard,
            detailEpisodesTitleText,
            detailEpisodesGrid,
            specialsCard,
            specialsTitleText,
            specialsToggleButton,
            specialsGrid,
            thumbnailsCard,
            thumbnailsTitleText,
            thumbnailsGrid);
    }

    private static void ApplyPlayerResponsiveLayout(
        double width,
        Border topChrome,
        Border bottomChrome,
        Slider volumeSlider,
        FrameworkElement volumePanel,
        TextBlock timeText,
        Border episodePanel,
        Border resumePrompt)
    {
        var compact = width < FluentTheme.CompactBreakpoint;
        topChrome.Margin = compact ? new Thickness(10) : new Thickness(16);
        bottomChrome.Margin = compact ? new Thickness(10, 0, 10, 10) : new Thickness(16, 0, 16, 16);
        volumeSlider.Width = compact ? 168 : 196;
        volumePanel.Width = compact ? 192 : 220;
        timeText.MinWidth = compact ? 96 : 128;
        episodePanel.Width = Math.Min(332, Math.Max(220, width - 32));
        episodePanel.Margin = compact ? new Thickness(0, 0, 10, 0) : new Thickness(0, 0, 16, 0);
        resumePrompt.Margin = compact ? new Thickness(10, 0, 10, 104) : new Thickness(0, 0, 0, 132);
    }

    private static void ApplyPageResponsiveLayout(
        double width,
        double height,
        Grid pageRoot,
        Border playerFrame,
        Grid detailHeader,
        StackPanel detailActions,
        StackPanel detailHost)
    {
        var compact = width < FluentTheme.CompactBreakpoint;
        pageRoot.Padding = FluentTheme.PagePadding(width);
        detailHost.MaxWidth = compact ? double.PositiveInfinity : 1180;
        detailHost.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Center;

        if (detailHost.Visibility == Visibility.Collapsed)
        {
            pageRoot.Padding = new Thickness(0);
            playerFrame.Height = Math.Max(280, height);
        }
        else
        {
            playerFrame.Height = Math.Clamp(height * (compact ? 0.54 : 0.64), compact ? 280 : 420, compact ? 520 : 720);
        }

        detailHeader.ColumnDefinitions[0].Width = compact ? new GridLength(1, GridUnitType.Star) : new GridLength(1, GridUnitType.Star);
        detailHeader.ColumnDefinitions[1].Width = compact ? new GridLength(0) : GridLength.Auto;
        detailHeader.RowDefinitions.Clear();
        detailHeader.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        detailHeader.RowDefinitions.Add(new RowDefinition { Height = compact ? GridLength.Auto : new GridLength(0) });
        Grid.SetColumn(detailActions, compact ? 0 : 1);
        Grid.SetRow(detailActions, compact ? 1 : 0);
        detailActions.Margin = compact ? new Thickness(0, 8, 0, 0) : new Thickness(0);
        detailActions.Orientation = compact ? Orientation.Vertical : Orientation.Horizontal;
        detailActions.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Right;
        foreach (var child in detailActions.Children.OfType<FrameworkElement>())
        {
            child.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Left;
        }
    }

    private static TextBlock SectionTitle(string text)
        => new()
        {
            Text = text,
            FontSize = 18,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
            TextWrapping = TextWrapping.WrapWholeWords,
            VerticalAlignment = VerticalAlignment.Center,
        };

    private static TextBlock DetailBodyText(string text, string automationId)
    {
        var block = new TextBlock
        {
            Text = text,
            Foreground = FluentTheme.TextPrimary,
            TextWrapping = TextWrapping.WrapWholeWords,
            LineHeight = 20,
        };
        AutomationProperties.SetAutomationId(block, automationId);
        return block;
    }

    private static StackPanel SectionStack(TextBlock title, UIElement content, Button? action = null)
    {
        var stack = new StackPanel { Spacing = 12 };
        if (action is null)
        {
            stack.Children.Add(title);
        }
        else
        {
            var header = new Grid { ColumnSpacing = 12 };
            header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            header.Children.Add(title);
            Grid.SetColumn(action, 1);
            header.Children.Add(action);
            stack.Children.Add(header);
        }

        stack.Children.Add(content);
        return stack;
    }

    private static GridView DetailGrid(string automationId, double maxHeight)
    {
        var grid = new GridView
        {
            SelectionMode = ListViewSelectionMode.None,
            IsItemClickEnabled = false,
            MaxHeight = maxHeight,
            Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent),
        };
        AutomationProperties.SetAutomationId(grid, automationId);
        return grid;
    }

    private Button DetailActionButton(string text, string automationId)
    {
        var button = FluentTheme.ApplyButton(new Button
        {
            Content = text,
            MinWidth = 96,
        });
        AttachPlaybackKeyHandler(button);
        AutomationProperties.SetAutomationId(button, automationId);
        return button;
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
        UpdateDetail(movie, progress);

        _player = new LibMpvPlayerService();
        _player.StateChanged += OnPlayerStateChanged;
        _playerHost.AttachService(_player);

        var source = File.Exists(movie.Path) ? movie.Path : await AppServices.Api.BuildStreamUrlAsync(movie.Id);
        await _player.LoadAsync(source);
        await SetVolumeAsync(_volumeSlider.Value, showOsd: false);

        if (progress.Position > 5)
        {
            ShowResumePrompt(progress.Position);
        }

        _ = LoadEpisodesAsync(movie);
        _ = LoadSpecialsAsync(movie);
        _ = LoadThumbnailsAsync(movie);
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

            UpdateEpisodes(SortEpisodes(items.Where(item => !item.IsSpecial)).ToList());
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
            _ = RenderDetailEpisodesAsync();
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
        AttachPlaybackKeyHandler(button);
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

    private void UpdateDetail(MovieDto movie, ProgressDto progress)
    {
        _detailTitleText.Text = movie.IsSpecial ? SpecialMovieTitle(movie) : movie.BestTitle;
        var showOriginal = !movie.IsSpecial &&
            !string.IsNullOrWhiteSpace(movie.OriginalTitle) &&
            !string.Equals(movie.OriginalTitle, movie.BestTitle, StringComparison.OrdinalIgnoreCase);
        _detailOriginalTitleText.Text = movie.OriginalTitle;
        _detailOriginalTitleText.Visibility = showOriginal ? Visibility.Visible : Visibility.Collapsed;
        _detailMetaText.Text = string.Join(" · ", DetailMetaParts(movie));
        _detailProgressText.Text = progress.ProgressPercent > 0
            ? $"已观看 {progress.ProgressPercent:0}%"
            : movie.ProgressPercent > 0 ? $"已观看 {movie.ProgressPercent:0}%" : "";
        _detailOverviewText.Text = string.IsNullOrWhiteSpace(movie.Overview) ? "还没有简介。" : movie.Overview;
        _detailEpisodeOverviewText.Text = string.IsNullOrWhiteSpace(movie.EpisodeOverview) ? "" : $"集概述：{movie.EpisodeOverview}";
        _detailEpisodeOverviewText.Visibility = string.IsNullOrWhiteSpace(movie.EpisodeOverview) ? Visibility.Collapsed : Visibility.Visible;
        _detailPathText.Text = string.IsNullOrWhiteSpace(movie.Path) ? movie.FolderLevels : movie.Path;
        _detailStaffText.Text = BuildStaffSummary(movie);
        _detailStaffText.Visibility = string.IsNullOrWhiteSpace(_detailStaffText.Text) ? Visibility.Collapsed : Visibility.Visible;
        _detailMoreButton.IsEnabled = _movie is not null;
        UpdateTagButtons();
        ShowDetailStatus("", false, visible: false);
    }

    private IEnumerable<string> DetailMetaParts(MovieDto movie)
    {
        if (!string.IsNullOrWhiteSpace(movie.Code))
        {
            yield return movie.Code;
        }

        if (!movie.IsSpecial && !string.IsNullOrWhiteSpace(movie.ReleaseDate))
        {
            yield return movie.ReleaseDate;
        }

        if (movie.Duration > 0)
        {
            yield return $"{movie.Duration:0} 分钟";
        }

        if (!movie.IsSpecial && !string.IsNullOrWhiteSpace(movie.Genre))
        {
            yield return movie.Genre;
        }

        if (!movie.IsSpecial && !string.IsNullOrWhiteSpace(movie.ContentRating))
        {
            yield return movie.ContentRating;
        }

        if (!movie.IsSpecial && movie.TmdbType == "tv" && movie.TmdbSeason is not null)
        {
            var episode = movie.TmdbEpisode is null ? "" : $" · Episode {movie.TmdbEpisode.Value}";
            yield return $"Season {movie.TmdbSeason.Value}{episode}";
        }

        if (!movie.IsSpecial && movie.JavdbScore is > 0)
        {
            yield return $"评分 {movie.JavdbScore.Value:0.0}";
        }

        if (!movie.IsSpecial && movie.JavdbLikes is > 0)
        {
            yield return $"喜欢 {movie.JavdbLikes.Value:N0}";
        }
    }

    private static string BuildStaffSummary(MovieDto movie)
    {
        var lines = new List<string>();
        var castNames = movie.Cast
            .Where(item => !string.IsNullOrWhiteSpace(item.Name))
            .Select(item => string.IsNullOrWhiteSpace(item.Detail) ? item.Name : $"{item.Name} ({item.Detail})")
            .Take(8)
            .ToList();

        if (castNames.Count == 0 && !string.IsNullOrWhiteSpace(movie.Actress))
        {
            castNames = movie.Actress
                .Split([',', '，', '、'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Take(8)
                .ToList();
        }

        if (castNames.Count > 0)
        {
            lines.Add($"演员：{string.Join("、", castNames)}");
        }

        AddCrewLine(lines, "导演", movie.Crew, ["director", "导演"]);
        AddCrewLine(lines, "监督", movie.Crew, ["supervisor", "animation director", "series director", "监督"]);
        AddCrewLine(lines, "编剧", movie.Crew, ["writer", "脚本", "编剧"]);
        AddCrewLine(lines, "制作", movie.Crew, ["studio", "制作"]);
        return string.Join(Environment.NewLine, lines);
    }

    private static void AddCrewLine(List<string> lines, string label, IEnumerable<MovieStaffDto> crew, string[] jobs)
    {
        var names = crew
            .Where(item => !string.IsNullOrWhiteSpace(item.Name) && jobs.Any(job => (item.Job ?? "").Contains(job, StringComparison.OrdinalIgnoreCase)))
            .Select(item => item.Name)
            .Distinct(StringComparer.CurrentCultureIgnoreCase)
            .Take(6)
            .ToList();
        if (names.Count > 0)
        {
            lines.Add($"{label}：{string.Join("、", names)}");
        }
    }

    private void UpdateTagButtons()
    {
        UpdateTagButton(_favoriteButton, "favorite", "已收藏", "收藏");
        UpdateTagButton(_wantButton, "want_to_watch", "想看中", "想看");
        UpdateTagButton(_watchedButton, "watched", "已看", "标为已看");
    }

    private void UpdateTagButton(Button button, string tag, string selectedText, string normalText)
    {
        var selected = _movie?.Tags.Contains(tag) == true;
        button.Content = selected ? selectedText : normalText;
        FluentTheme.ApplyButton(button, selected ? FluentButtonStyle.Accent : FluentButtonStyle.Standard);
    }

    private async Task ToggleTagAsync(string tag)
    {
        if (_movie is null)
        {
            return;
        }

        try
        {
            SetTagButtonsEnabled(false);
            var hadTag = _movie.Tags.Contains(tag);
            if (hadTag)
            {
                await AppServices.Movie.RemoveTagAsync(_movie.Id, tag);
                _movie.Tags.RemoveAll(item => string.Equals(item, tag, StringComparison.OrdinalIgnoreCase));
            }
            else
            {
                await AppServices.Movie.AddTagAsync(_movie.Id, tag);
                _movie.Tags.Add(tag);
            }

            UpdateTagButtons();
            ShowDetailStatus(hadTag ? "标签已移除" : "标签已添加", false);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Failed to toggle native player detail tag: movie={_movie.Id} tag={tag}.");
            ShowDetailStatus($"标签更新失败：{ex.Message}", true);
        }
        finally
        {
            SetTagButtonsEnabled(true);
        }
    }

    private void SetTagButtonsEnabled(bool enabled)
    {
        _favoriteButton.IsEnabled = enabled;
        _wantButton.IsEnabled = enabled;
        _watchedButton.IsEnabled = enabled;
    }

    private void OnDetailMoreClicked(object sender, RoutedEventArgs args)
    {
        if (_movie is null)
        {
            return;
        }

        var item = new MovieCardItem(_movie, "")
        {
            FallbackCoverUrl = "",
        };
        var flyout = MediaContextMenuService.CreateMovieFlyout(item, CreateContextMenuHost(async () => await RefreshDetailAsync()));
        flyout.ShowAt(_detailMoreButton);
    }

    private async Task RefreshDetailAsync()
    {
        var movie = await AppServices.Movie.GetMovieDetailAsync(_movieId);
        var progress = await AppServices.Movie.GetProgressAsync(_movieId);
        _movie = movie;
        _titleText.Text = movie.BestTitle;
        UpdateDetail(movie, progress);
        _ = LoadEpisodesAsync(movie);
        _ = LoadSpecialsAsync(movie);
        _ = LoadThumbnailsAsync(movie);
    }

    private void ShowDetailStatus(string message, bool isError, bool visible = true)
    {
        _detailStatusText.Text = message;
        _detailStatusText.Foreground = isError ? FluentTheme.Error : FluentTheme.TextSecondary;
        _detailStatusText.Visibility = visible && !string.IsNullOrWhiteSpace(message) ? Visibility.Visible : Visibility.Collapsed;
    }

    private MediaContextMenuHost CreateContextMenuHost(Func<Task> refreshAsync)
        => new()
        {
            XamlRoot = XamlRoot,
            ShowStatus = (message, isError) => ShowDetailStatus(message, isError),
            RefreshAsync = refreshAsync,
        };

    private async Task RenderDetailEpisodesAsync()
    {
        var episodes = _episodes.ToList();
        if (episodes.Count <= 1)
        {
            _detailEpisodesGrid.Items.Clear();
            _detailEpisodesCard.Visibility = Visibility.Collapsed;
            return;
        }

        _detailEpisodesTitleText.Text = $"选集 ({episodes.Count})";
        _detailEpisodesCard.Visibility = Visibility.Visible;
        _detailEpisodesGrid.Items.Clear();

        foreach (var episode in episodes)
        {
            _detailEpisodesGrid.Items.Add(await CreateDetailMovieCardAsync(episode, "player-detail-episode"));
        }
    }

    private async Task LoadSpecialsAsync(MovieDto movie)
    {
        _specialsExpanded = false;
        _specialMovies.Clear();
        _specialsGrid.Items.Clear();
        _specialsGrid.Visibility = Visibility.Collapsed;
        _specialsToggleButton.Content = "展开";
        _specialsCard.Visibility = Visibility.Collapsed;

        var folder = movie.FolderForSpecials;
        if (string.IsNullOrWhiteSpace(folder))
        {
            return;
        }

        try
        {
            var data = await AppServices.Movie.GetFolderSpecialsAsync(folder, movie.MediaRoot, includeMovies: true);
            _specialMovies.AddRange(data.Movies
                .OrderBy(item => item.FolderLevels, StringComparer.CurrentCultureIgnoreCase)
                .ThenBy(item => item.BestTitle, StringComparer.CurrentCultureIgnoreCase));

            if (data.SpecialCount <= 0)
            {
                return;
            }

            _specialsTitleText.Text = $"花絮 ({data.SpecialCount})";
            _specialsCard.Visibility = Visibility.Visible;
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load native player detail specials.");
            ShowDetailStatus($"花絮加载失败：{ex.Message}", true);
        }
    }

    private async void OnSpecialsToggleClicked(object sender, RoutedEventArgs args)
    {
        _specialsExpanded = !_specialsExpanded;
        _specialsToggleButton.Content = _specialsExpanded ? "收起" : "展开";
        _specialsGrid.Visibility = _specialsExpanded ? Visibility.Visible : Visibility.Collapsed;
        if (!_specialsExpanded || _specialsGrid.Items.Count > 0)
        {
            return;
        }

        foreach (var special in _specialMovies)
        {
            _specialsGrid.Items.Add(await CreateDetailMovieCardAsync(special, "player-detail-special"));
        }
    }

    private async Task LoadThumbnailsAsync(MovieDto movie)
    {
        _thumbnailsGrid.Items.Clear();
        _thumbnailsCard.Visibility = Visibility.Collapsed;
        var sources = new List<(string Source, string Title)>();
        if (!string.IsNullOrWhiteSpace(movie.EpisodeStill))
        {
            try
            {
                sources.Add((await AppServices.Api.BuildEpisodeStillUrlAsync(movie.Id), "单集封面"));
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, $"Failed to build native detail episode still URL for movie {movie.Id}.");
            }
        }

        sources.AddRange(movie.JavdbThumbnails
            .Where(source => !string.IsNullOrWhiteSpace(source))
            .Take(12)
            .Select((source, index) => (source, $"缩略图 {index + 1}")));

        if (sources.Count == 0)
        {
            return;
        }

        _thumbnailsTitleText.Text = $"缩略图 ({sources.Count})";
        _thumbnailsCard.Visibility = Visibility.Visible;
        foreach (var (source, title) in sources)
        {
            _thumbnailsGrid.Items.Add(await CreateThumbnailCardAsync(source, title));
        }
    }

    private async Task<Button> CreateThumbnailCardAsync(string source, string title)
    {
        var imageHost = new Grid
        {
            Width = 188,
            Height = 106,
            Background = FluentTheme.LayerAlt,
        };
        try
        {
            var url = await AppServices.Api.BuildMediaAssetUrlAsync(source);
            if (Uri.TryCreate(url, UriKind.Absolute, out var uri))
            {
                var image = new Image
                {
                    Source = new BitmapImage(uri),
                    Stretch = Stretch.UniformToFill,
                };
                image.ImageFailed += (_, _) => image.Visibility = Visibility.Collapsed;
                imageHost.Children.Add(image);
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load native player detail thumbnail.");
        }

        var stack = new StackPanel();
        stack.Children.Add(imageHost);
        stack.Children.Add(new TextBlock
        {
            Text = title,
            Padding = new Thickness(10, 8, 10, 10),
            Foreground = FluentTheme.TextSecondary,
            FontSize = 12,
            TextTrimming = TextTrimming.CharacterEllipsis,
        });

        var card = new Button
        {
            Width = 188,
            Margin = new Thickness(6),
            CornerRadius = FluentTheme.MediaCornerRadius,
            Background = FluentTheme.Layer,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(1),
            Content = stack,
            Padding = new Thickness(0),
            HorizontalContentAlignment = HorizontalAlignment.Stretch,
            VerticalContentAlignment = VerticalAlignment.Stretch,
        };
        AttachPlaybackKeyHandler(card);
        return card;
    }

    private async Task<Button> CreateDetailMovieCardAsync(MovieDto movie, string logContext)
    {
        var item = await BrowsePage.CreateMovieCardItemAsync(movie, logContext);
        var card = CreateDetailMovieCard(item);
        AutomationProperties.SetAutomationId(card, $"PlayerDetailMovieCard_{movie.Id}");
        card.Click += async (_, _) =>
        {
            if (movie.Id == _movieId)
            {
                return;
            }

            try
            {
                await SaveProgressAsync(true);
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, "Failed to save progress before native detail card navigation.");
            }

            ShellPage.Current?.NavigateToPlayer(movie.Id);
        };
        return card;
    }

    private Button CreateDetailMovieCard(MovieCardItem item)
    {
        var imageHost = new Grid
        {
            Width = 178,
            Height = item.HasEpisodeStill ? 100 : 252,
            Background = FluentTheme.LayerAlt,
        };

        try
        {
            if (Uri.TryCreate(item.CoverUrl, UriKind.Absolute, out var coverUri))
            {
                var triedFallback = false;
                var image = new Image
                {
                    Source = new BitmapImage(coverUri),
                    Stretch = Stretch.UniformToFill,
                };
                image.ImageFailed += (_, _) =>
                {
                    if (item.HasEpisodeStill && !triedFallback && Uri.TryCreate(item.FallbackCoverUrl, UriKind.Absolute, out var fallbackUri))
                    {
                        triedFallback = true;
                        image.Source = new BitmapImage(fallbackUri);
                        return;
                    }

                    image.Visibility = Visibility.Collapsed;
                    imageHost.Children.Add(CoverFallbackText());
                };
                imageHost.Children.Add(image);
            }
            else
            {
                imageHost.Children.Add(CoverFallbackText());
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Failed to create native player detail cover image for movie {item.Id}.");
            imageHost.Children.Add(CoverFallbackText());
        }

        if (item.IsEpisode)
        {
            imageHost.Children.Add(new Border
            {
                Margin = new Thickness(8),
                Padding = new Thickness(8, 3, 8, 3),
                HorizontalAlignment = HorizontalAlignment.Left,
                VerticalAlignment = VerticalAlignment.Top,
                CornerRadius = FluentTheme.ControlCornerRadius,
                Background = FluentTheme.Accent,
                Child = new TextBlock
                {
                    Text = $"S{item.Movie.TmdbSeason?.ToString() ?? "-"}·E{item.Movie.TmdbEpisode?.ToString() ?? "-"}",
                    FontSize = 11,
                    FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
                    Foreground = new SolidColorBrush(Microsoft.UI.Colors.White),
                },
            });
        }

        var textStack = new StackPanel
        {
            Padding = new Thickness(12),
            Spacing = 4,
        };
        textStack.Children.Add(new TextBlock
        {
            Text = item.Title,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
            TextTrimming = TextTrimming.CharacterEllipsis,
        });
        textStack.Children.Add(new TextBlock
        {
            Text = item.Subtitle,
            FontSize = 12,
            Foreground = FluentTheme.TextSecondary,
            TextTrimming = TextTrimming.CharacterEllipsis,
        });
        if (!string.IsNullOrWhiteSpace(item.ProgressText))
        {
            textStack.Children.Add(new TextBlock
            {
                Text = item.ProgressText,
                FontSize = 12,
                Foreground = FluentTheme.Accent,
            });
        }

        var stack = new StackPanel();
        stack.Children.Add(imageHost);
        stack.Children.Add(textStack);

        var card = new Button
        {
            Width = 178,
            Margin = new Thickness(6),
            CornerRadius = FluentTheme.MediaCornerRadius,
            Background = FluentTheme.Layer,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(1),
            Content = stack,
            Padding = new Thickness(0),
            HorizontalContentAlignment = HorizontalAlignment.Stretch,
            VerticalContentAlignment = VerticalAlignment.Stretch,
            Tag = item,
            ContextFlyout = MediaContextMenuService.CreateMovieFlyout(item, CreateContextMenuHost(async () => await RefreshDetailAsync())),
        };
        AttachPlaybackKeyHandler(card);
        return card;
    }

    private static TextBlock CoverFallbackText()
        => new()
        {
            Text = "无封面",
            Foreground = FluentTheme.TextTertiary,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
        };

    private void OnPlayerStateChanged(object? sender, PlayerStateSnapshot state)
    {
        DispatcherQueue.TryEnqueue(() =>
        {
            _state = state;
            _duration = state.Duration;
            _ignoreProgress = true;
            _progressSlider.Maximum = Math.Max(1, state.Duration);
            _progressSlider.Value = Math.Clamp(state.Position, 0, _progressSlider.Maximum);
            _ignoreProgress = false;

            if (!_ignoreVolume)
            {
                _ignoreVolume = true;
                _volumeSlider.Value = Math.Clamp(state.Volume, 0, 100);
                _ignoreVolume = false;
            }

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
            UpdatePlaybackLabels(state);
            UpdateTrackLabels(state);
            ScheduleResumePromptAutoHide(state);

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

    private void UpdatePlaybackLabels(PlayerStateSnapshot state)
    {
        _playPauseButton.Content = state.Paused ? "播放" : "暂停";
        _volumeButton.Content = _muted ? "音量 0%" : $"音量 {Math.Round(state.Volume)}%";
        _volumeMuteButton.Content = _muted ? "取消静音" : "静音";
        _timeText.Text = $"{FormatTime(state.Position)} / {FormatTime(state.Duration)}";
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

    private async void OnProgressSliderChanged(object sender, RangeBaseValueChangedEventArgs args)
    {
        if (_ignoreProgress || _player is null || Math.Abs(args.NewValue - _state.Position) < 1)
        {
            return;
        }

        try
        {
            var target = Math.Clamp(args.NewValue, 0, Math.Max(1, _duration));
            var delta = target - _state.Position;
            await _player.SeekAsync(target);
            ShowSeekOsd(delta, target);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to seek native playback.");
            ShowPlaybackError($"跳转失败：{ex.Message}");
        }
    }

    private async void OnVolumeChanged(object sender, RangeBaseValueChangedEventArgs args)
    {
        if (_ignoreVolume)
        {
            return;
        }

        await SetVolumeAsync(args.NewValue, showOsd: true);
    }

    private void OnVolumeButtonClicked(object sender, RoutedEventArgs args)
    {
        if (_volumePanelOpen)
        {
            CloseVolumePanel();
        }
        else
        {
            CloseEpisodePanel();
            FlyoutBase.ShowAttachedFlyout(_volumeButton);
        }

        ShowChrome(true);
    }

    private void UpdateVolumePanelVisibility()
    {
        ScheduleChromeHide();
    }

    private void CloseVolumePanel()
    {
        if (!_volumePanelOpen)
        {
            return;
        }

        _volumePanelOpen = false;
        _volumeFlyout.Hide();
        ScheduleChromeHide();
    }

    private async Task SetVolumeAsync(double volume, bool showOsd)
    {
        try
        {
            var value = Math.Clamp(volume, 0, 100);
            _ignoreVolume = true;
            _volumeSlider.Value = value;
            _ignoreVolume = false;

            _muted = value <= 0;
            if (value > 0)
            {
                _lastKnownVolume = value;
            }

            if (_player is not null)
            {
                await _player.SetVolumeAsync(value);
            }

            _volumeButton.Content = _muted ? "音量 0%" : $"音量 {Math.Round(value)}%";
            _volumeMuteButton.Content = _muted ? "取消静音" : "静音";
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
        await SetVolumeAsync(Math.Clamp(_volumeSlider.Value + delta, 0, 100), showOsd: true);
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
        CloseVolumePanel();
        _episodePanelOpen = !_episodePanelOpen;
        UpdateEpisodePanelVisibility();
        ShowChrome(true);
    }

    private void UpdateEpisodePanelVisibility()
    {
        _episodePanel.Visibility = _episodePanelOpen && _episodes.Count > 1 ? Visibility.Visible : Visibility.Collapsed;
        ScheduleChromeHide();
    }

    private void CloseEpisodePanel()
    {
        if (!_episodePanelOpen)
        {
            return;
        }

        _episodePanelOpen = false;
        UpdateEpisodePanelVisibility();
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
        _resumePromptTimer.Stop();
        _resumePromptAutoHideScheduled = false;
        _resumePosition = position;
        _resumeText.Text = $"从上次位置继续 ({FormatTime(position)})";
        _resumePrompt.Visibility = Visibility.Visible;
        ScheduleResumePromptAutoHide(_state);
    }

    private void HideResumePrompt()
    {
        _resumePromptTimer.Stop();
        _resumePromptAutoHideScheduled = false;
        _resumePrompt.Visibility = Visibility.Collapsed;
        _resumePosition = 0;
    }

    private void ScheduleResumePromptAutoHide(PlayerStateSnapshot state)
    {
        if (_resumePromptAutoHideScheduled ||
            _resumePrompt.Visibility != Visibility.Visible ||
            _resumePosition <= 0 ||
            state.Paused)
        {
            return;
        }

        _resumePromptAutoHideScheduled = true;
        _resumePromptTimer.Stop();
        _resumePromptTimer.Start();
    }

    private void OnResumePromptTimerTick(object? sender, object args)
    {
        HideResumePrompt();
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
        _detailHost.Visibility = _fullScreenMode ? Visibility.Collapsed : Visibility.Visible;
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
            _resumePromptTimer.Stop();
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
        CloseVolumePanel();
        _detailHost.Visibility = Visibility.Visible;
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

    private void OnUserPointerMoved(object sender, PointerRoutedEventArgs args)
    {
        ShowChrome(true);
        ScheduleChromeHide();
    }

    private void OnUserPointerPressed(object sender, PointerRoutedEventArgs args)
    {
        if (args.OriginalSource is DependencyObject source)
        {
            if (!IsDescendantOf(source, _episodePanel) && !IsDescendantOf(source, _episodeButton))
            {
                CloseEpisodePanel();
            }

            if (!IsDescendantOf(source, _volumePanel) && !IsDescendantOf(source, _volumeButton))
            {
                CloseVolumePanel();
            }
        }
        else
        {
            CloseEpisodePanel();
            CloseVolumePanel();
        }

        ShowChrome(true);
        ScheduleChromeHide();
    }

    private void OnChromeTimerTick(object? sender, object args)
    {
        if (!_state.Paused && !_episodePanelOpen && !_volumePanelOpen)
        {
            ShowChrome(false);
        }
    }

    private void ShowChrome(bool visible)
    {
        _controlsVisible = visible;
        var opacity = visible ? 1 : 0;
        _topChrome.Opacity = opacity;
        _bottomChrome.Opacity = opacity;
        _topChrome.IsHitTestVisible = visible;
        _bottomChrome.IsHitTestVisible = visible;
        if (!visible)
        {
            CloseVolumePanel();
        }
    }

    private static bool IsDescendantOf(DependencyObject source, DependencyObject parent)
    {
        for (var current = source; current is not null; current = VisualTreeHelper.GetParent(current))
        {
            if (ReferenceEquals(current, parent))
            {
                return true;
            }
        }

        return false;
    }

    private void ScheduleChromeHide()
    {
        _chromeTimer.Stop();
        if (_controlsVisible && !_state.Paused && !_episodePanelOpen && !_volumePanelOpen)
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

    private void AttachPlaybackKeyHandler(UIElement element)
    {
        element.KeyDown += OnPlayerControlKeyDown;
        element.KeyUp += OnPlayerControlKeyUp;
    }

    private void AddPlaybackKeyboardAccelerators(UIElement element)
    {
        AddPlaybackKeyboardAccelerator(element, VirtualKey.Space, TogglePlayPauseAsync);
        AddPlaybackKeyboardAccelerator(element, VirtualKey.K, TogglePlayPauseAsync);
    }

    private static void AddPlaybackKeyboardAccelerator(UIElement element, VirtualKey key, Func<Task> action)
    {
        var accelerator = new KeyboardAccelerator { Key = key };
        accelerator.Invoked += async (_, args) =>
        {
            args.Handled = true;
            await action();
        };
        element.KeyboardAccelerators.Add(accelerator);
    }

    private async void OnPlayerControlKeyDown(object sender, KeyRoutedEventArgs args)
    {
        if (!IsPlayPauseKey(args.Key))
        {
            return;
        }

        args.Handled = true;
        await TogglePlayPauseAsync();
    }

    private void OnPlayerControlKeyUp(object sender, KeyRoutedEventArgs args)
    {
        if (IsPlayPauseKey(args.Key))
        {
            args.Handled = true;
        }
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

    private static bool IsPlayPauseKey(VirtualKey key)
        => key == VirtualKey.Space || key == VirtualKey.K;

    private void HandleEscape()
    {
        if (_volumePanelOpen)
        {
            CloseVolumePanel();
            return;
        }

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

    private static string SpecialMovieTitle(MovieDto movie)
        => FirstNonEmpty(
            Path.GetFileNameWithoutExtension(movie.Path),
            movie.DisplayTitle,
            movie.Title,
            movie.CleanTitle,
            movie.Code);

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
        _playPauseButton.IsEnabled = false;
        _progressSlider.IsEnabled = false;
        _volumeSlider.IsEnabled = false;
        _speedBox.IsEnabled = false;
        _subtitleButton.IsEnabled = false;
        _audioButton.IsEnabled = false;
        _episodeButton.IsEnabled = false;
    }
}
