using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using MediaTree.Windows.Models;
using MediaTree.Windows.Providers;
using MediaTree.Windows.Services;
using MediaTree.Windows.Styles;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using Windows.Storage;
using Windows.Storage.Pickers;
using WinRT.Interop;

namespace MediaTree.Windows.Views;

public sealed partial class SettingsPage : Page
{
    public const string AddLibraryButtonText = "添加";
    public const string SwitchToLocalMediaTreeButtonText = "切回本机";
    public const string SwitchMediaSourceButtonText = "切换";
    public const string DeleteLibraryButtonText = "删除";
    public const string LibraryScraperHeader = "刮削器";
    public const string RemoteAccessTitle = "移动端访问";
    public const string RemoteLoginUsernameHeader = "登录用户名";
    public const string RemoteLoginPasswordHeader = "登录密码";
    public const string SaveRemoteAccessButtonText = "保存账号并重启本机服务";
    public const string LocalMediaTreeOnlyMessage = "当前媒体源不是本机 MediaTree，此操作不可用。";
    public const string ExternalLibraryReadOnlyMessage = "当前媒体源由外部服务端管理，MediaTree 刮削、扫描和删除操作不可用。";
    public static readonly IReadOnlyList<string> AddLibrarySourceOptions =
    [
        "本地目录",
        "MediaTree 远程",
        "Jellyfin",
        "Emby",
    ];

    private const double SettingsColumnPreferredWidth = 400;
    private const double SettingsColumnMinWidth = 340;
    private const double SettingsColumnSpacing = 18;

    private sealed record ScraperOption(string Value, string Label, string Description, bool HasKey);

    private sealed record LibrarySettingsRowContext(string SourceId, string MediaRoot, string TmdbKey, ComboBox ScraperBox, PasswordBox PasswordBox, TextBlock StatusText, TextBlock LogText);

    private sealed record LibraryScanRowUi(string SourceId, string MediaRoot, TextBlock StatusText, TextBlock LogText, Button ScanButton);

    private sealed record MediaSourceRowContext(MediaSourceListItem Source, TextBlock StatusText);

    private sealed record DeleteLibraryContext(string SourceId, string MediaRoot);

    private sealed class MediaServicesLease(MediaTreeServices services, IDisposable? disposable = null) : IDisposable
    {
        public MediaTreeServices Services { get; } = services;

        public void Dispose()
            => disposable?.Dispose();
    }

    private sealed class MediaSourceLibraryPanelState
    {
        public bool IsLoading { get; init; }
        public bool IsLoaded { get; init; }
        public bool IsError { get; init; }
        public string Message { get; init; } = "";
        public List<MediaRootDto> Roots { get; init; } = [];
        public Dictionary<string, LibrarySettingDto> Settings { get; init; } = new(StringComparer.OrdinalIgnoreCase);
        public List<string> RemovableRoots { get; init; } = [];
    }

    private static readonly IReadOnlyList<ScraperOption> ScraperOptions =
    [
        new("tmdb_movie", "TMDB 电影", "适合电影库；tmdbid 调用 /movie 精确刮削", true),
        new("tmdb_tv", "TMDB 剧集/番剧", "适合剧集、番剧、电视剧库；tmdbid 调用 /tv 精确刮削", true),
        new("tmdb_collection", "TMDB 合集", "适合电影合集库；按合集条目刮削系列电影元数据", true),
        new("bangumi", "Bangumi", "适合番剧、动画、二次元条目，数据可能不全", false),
        new("javdatabase", "Javdatabase", "适合 JAV 番号识别和刮削", false),
        new("auto", "自动", "自动判断刮削源，但可能效果不好", true),
        new("none", "不刮削", "只扫描本地文件，不联网刮削元数据", false),
    ];

    private readonly TextBlock _globalStatusText;
    private readonly CheckBox _hideHomeTitleTextBox;
    private readonly CheckBox _allowRemoteBackendBox;
    private readonly TextBox _remoteBackendPortBox;
    private readonly TextBlock _remoteBackendUrlText;
    private readonly TextBlock _remoteBackendStatusText;
    private readonly TextBox _remoteLoginUsernameBox;
    private readonly PasswordBox _remoteLoginPasswordBox;
    private readonly CheckBox _showSourceNameBox;
    private readonly TextBlock _backupStatusText;
    private readonly StackPanel _mediaSourceGroupsStack;
    private readonly TextBlock _libraryStatusText;
    private readonly TextBox _tmdbApiKeyBox;
    private readonly PasswordBox _tmdbTokenBox;
    private readonly TextBlock _tmdbTokenStatusText;
    private readonly DispatcherTimer _scanStatusTimer = new() { Interval = TimeSpan.FromSeconds(2) };
    private readonly Dictionary<string, int> _scanPollCounts = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, LibraryScanRowUi> _scanRows = new(StringComparer.OrdinalIgnoreCase);
    private readonly HashSet<string> _activeScanRoots = new(StringComparer.OrdinalIgnoreCase);
    private readonly HashSet<string> _expandedMediaSources = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, MediaSourceLibraryPanelState> _mediaSourceLibraryStates = new(StringComparer.OrdinalIgnoreCase);
    private readonly List<FrameworkElement> _librarySettingRows = [];
    private readonly DispatcherTimer _updateStatusTimer = new() { Interval = TimeSpan.FromSeconds(2) };
    private readonly TextBlock _updateProgressText;
    private readonly TextBlock _updateStatusText;
    private readonly StackPanel _updateVersionsStack;
    private readonly TextBlock _versionText;
    private readonly List<FrameworkElement> _settingsCards = [];
    private double _settingsColumnWidth;
    private ConfigDto _loadedConfig = new();
    private UpdateCheckResultDto? _lastUpdateResult;
    private UpdateStatusDto? _lastUpdateStatus;
    private bool _isSwitchingMediaSource;
    private bool _suppressUiPreferenceSave;

    private static MediaSourceKind ActiveSourceKind => AppServices.ActiveProvider?.Profile.Kind ?? MediaSourceKind.LocalMediaTree;
    private static bool IsLocalMediaTreeActive => ActiveSourceKind == MediaSourceKind.LocalMediaTree;
    private static bool SupportsMediaTreeLibraryManagement => AppServices.SupportsMediaTreeLibraryManagement;

    public SettingsPage()
    {
        (
            _globalStatusText,
            _hideHomeTitleTextBox,
            _allowRemoteBackendBox,
            _remoteBackendPortBox,
            _remoteBackendUrlText,
            _remoteBackendStatusText,
            _showSourceNameBox,
            _remoteLoginUsernameBox,
            _remoteLoginPasswordBox,
            _mediaSourceGroupsStack,
            _libraryStatusText,
            _tmdbApiKeyBox,
            _tmdbTokenBox,
            _tmdbTokenStatusText,
            _backupStatusText,
            _versionText,
            _updateProgressText,
            _updateStatusText,
            _updateVersionsStack
        ) = BuildContent();
        _scanStatusTimer.Tick += OnScanStatusTimerTick;
        _updateStatusTimer.Tick += OnUpdateStatusTimerTick;
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
    }

    private (TextBlock globalStatusText, CheckBox hideHomeTitleTextBox, CheckBox allowRemoteBackendBox, TextBox remoteBackendPortBox, TextBlock remoteBackendUrlText, TextBlock remoteBackendStatusText, CheckBox showSourceNameBox, TextBox remoteLoginUsernameBox, PasswordBox remoteLoginPasswordBox, StackPanel mediaSourceGroupsStack, TextBlock libraryStatusText, TextBox tmdbApiKeyBox, PasswordBox tmdbTokenBox, TextBlock tmdbTokenStatusText, TextBlock backupStatusText, TextBlock versionText, TextBlock updateProgressText, TextBlock updateStatusText, StackPanel updateVersionsStack) BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "SettingsPage");
        var isLocalMediaTreeActive = IsLocalMediaTreeActive;
        var supportsMediaTreeLibraryManagement = SupportsMediaTreeLibraryManagement;

        var scrollViewer = new ScrollViewer
        {
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
            HorizontalScrollMode = ScrollMode.Disabled,
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            VerticalScrollMode = ScrollMode.Auto,
        };
        var root = new StackPanel
        {
            Padding = new Thickness(40),
            Spacing = 22,
            Background = FluentTheme.Canvas,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            RequestedTheme = ElementTheme.Light,
        };

        var headerGrid = new Grid { ColumnSpacing = 16, RowSpacing = 12 };
        headerGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        headerGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        headerGrid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        headerGrid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });

        var titleStack = new StackPanel { Spacing = 4 };
        titleStack.Children.Add(new TextBlock
        {
            Text = "MediaTree",
            FontSize = 12,
            Foreground = FluentTheme.Accent,
        });
        titleStack.Children.Add(FluentTheme.Title("设置", 34));
        headerGrid.Children.Add(titleStack);

        var saveGlobalButton = FluentTheme.ApplyButton(new Button
        {
            Content = "保存全局设置",
            VerticalAlignment = VerticalAlignment.Center,
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(saveGlobalButton, "SettingsSaveGlobal");
        saveGlobalButton.Click += OnSaveGlobalClicked;
        Grid.SetColumn(saveGlobalButton, 1);
        headerGrid.Children.Add(saveGlobalButton);
        headerGrid.SizeChanged += (_, args) => ApplyHeaderActionLayout(args.NewSize.Width, headerGrid, saveGlobalButton);
        root.Children.Add(SectionCard(headerGrid, "SettingsHeaderCard", new Thickness(18)));

        var globalStatusText = StatusText("SettingsGlobalStatusText");
        root.Children.Add(globalStatusText);

        var settingsGrid = new Grid
        {
            ColumnSpacing = SettingsColumnSpacing,
            HorizontalAlignment = HorizontalAlignment.Center,
        };
        root.Children.Add(settingsGrid);
        _settingsCards.Clear();

        var uiPrefsStack = new StackPanel { Spacing = 12 };
        uiPrefsStack.Children.Add(SectionTitle("界面偏好", "SettingsUiPrefsCard"));
        var hideHomeTitleTextBox = FluentTheme.ApplyCheckBox(new CheckBox
        {
            Content = WrapText("无字模式：首页仅展示影片封面图，隐藏卡片上的标题文字和目录数量。"),
        });
        AutomationProperties.SetAutomationId(hideHomeTitleTextBox, "SettingsHideHomeTitleText");
        hideHomeTitleTextBox.Checked += OnUiPreferenceChanged;
        hideHomeTitleTextBox.Unchecked += OnUiPreferenceChanged;
        uiPrefsStack.Children.Add(hideHomeTitleTextBox);
        var showSourceNameBox = FluentTheme.ApplyCheckBox(new CheckBox
        {
            Content = WrapText("使用源文件名称：首页媒体库卡片显示源文件夹名称。"),
        });
        AutomationProperties.SetAutomationId(showSourceNameBox, "SettingsShowSourceName");
        showSourceNameBox.Checked += OnUiPreferenceChanged;
        showSourceNameBox.Unchecked += OnUiPreferenceChanged;
        uiPrefsStack.Children.Add(showSourceNameBox);
        _settingsCards.Add(SectionCard(uiPrefsStack, "SettingsUiPrefsCard"));

        var remoteStack = new StackPanel { Spacing = 12 };
        remoteStack.Children.Add(SectionTitle(RemoteAccessTitle, "SettingsRemoteBackendCard"));
        var allowRemoteBackendBox = FluentTheme.ApplyCheckBox(new CheckBox
        {
            Content = WrapText("开放本机后端给局域网设备连接。"),
            IsEnabled = isLocalMediaTreeActive,
        });
        AutomationProperties.SetAutomationId(allowRemoteBackendBox, "SettingsAllowRemoteBackend");
        remoteStack.Children.Add(allowRemoteBackendBox);
        var remoteAccessContent = new StackPanel
        {
            Spacing = 12,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };
        AutomationProperties.SetAutomationId(remoteAccessContent, "SettingsRemoteAccessContent");
        var remoteBackendPortBox = TextInput("端口", "SettingsRemoteBackendPort", BackendAccessSettings.DefaultRemotePort.ToString());
        remoteBackendPortBox.InputScope = NumberInputScope();
        remoteBackendPortBox.IsEnabled = isLocalMediaTreeActive;
        remoteAccessContent.Children.Add(remoteBackendPortBox);
        var remoteLoginUsernameBox = TextInput(RemoteLoginUsernameHeader, "SettingsRemoteLoginUsername");
        var remoteLoginPasswordBox = PasswordInput(RemoteLoginPasswordHeader, "SettingsRemoteLoginPassword");
        remoteLoginUsernameBox.IsEnabled = isLocalMediaTreeActive;
        remoteLoginPasswordBox.IsEnabled = isLocalMediaTreeActive;
        remoteAccessContent.Children.Add(remoteLoginUsernameBox);
        remoteAccessContent.Children.Add(remoteLoginPasswordBox);
        remoteStack.Children.Add(remoteAccessContent);
        remoteStack.Children.Add(FluentTheme.Body("保存后会重启本机后端。然后在 mediatree-app 里选择 MediaTree，填入下面地址，并用这里设置的账号登录。", 13));
        if (!isLocalMediaTreeActive)
        {
            remoteStack.Children.Add(FluentTheme.Body("当前媒体源不是本机 MediaTree，本机后端移动端访问设置不可用。", 13));
        }
        var remoteBackendUrlText = new TextBlock
        {
            TextWrapping = TextWrapping.WrapWholeWords,
            FontFamily = new FontFamily("Consolas"),
            Foreground = FluentTheme.TextPrimary,
        };
        AutomationProperties.SetAutomationId(remoteBackendUrlText, "SettingsRemoteBackendUrl");
        remoteStack.Children.Add(remoteBackendUrlText);
        var remoteActions = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 10,
        };
        var saveRemoteBackendButton = FluentTheme.ApplyButton(new Button
        {
            Content = SaveRemoteAccessButtonText,
            IsEnabled = isLocalMediaTreeActive,
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(saveRemoteBackendButton, "SettingsSaveRemoteBackend");
        saveRemoteBackendButton.Click += OnSaveRemoteBackendClicked;
        remoteActions.Children.Add(saveRemoteBackendButton);
        remoteActions.SizeChanged += (_, args) => ApplyActionStackLayout(args.NewSize.Width, remoteActions);
        remoteStack.Children.Add(remoteActions);
        var remoteBackendStatusText = StatusText("SettingsRemoteBackendStatusText", visible: true);
        remoteStack.Children.Add(remoteBackendStatusText);
        _settingsCards.Add(SectionCard(remoteStack, "SettingsRemoteBackendCard"));

        var libraryStack = new StackPanel { Spacing = 12 };
        var libraryHeader = new Grid { ColumnSpacing = 12, RowSpacing = 10 };
        libraryHeader.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        libraryHeader.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        libraryHeader.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        libraryHeader.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });
        libraryHeader.Children.Add(SectionTitle("媒体库", "SettingsLibraryCard"));
        var addLibraryButton = FluentTheme.ApplyButton(new Button
        {
            Content = AddLibraryButtonText,
            HorizontalAlignment = HorizontalAlignment.Right,
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(addLibraryButton, "SettingsAddLibrary");
        addLibraryButton.Click += OnAddLibraryClicked;
        Grid.SetColumn(addLibraryButton, 1);
        libraryHeader.Children.Add(addLibraryButton);
        libraryStack.Children.Add(libraryHeader);
        var mediaSourceGroupsStack = new StackPanel
        {
            Spacing = 8,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };
        AutomationProperties.SetAutomationId(mediaSourceGroupsStack, "SettingsMediaSourceGroups");
        libraryStack.Children.Add(mediaSourceGroupsStack);
        libraryStack.Children.Add(FluentTheme.Body(
            supportsMediaTreeLibraryManagement
                ? "可添加本机目录，也可以先保存远程 MediaTree、Jellyfin 或 Emby 的连接配置。"
                : "当前媒体源由外部服务端管理；这里可查看媒体库，也可以添加或切换连接配置。",
            13));
        var libraryStatusText = StatusText("SettingsLibraryStatusText", visible: true);
        libraryStatusText.Text = "正在加载媒体库设置...";
        libraryStack.Children.Add(libraryStatusText);
        _settingsCards.Add(SectionCard(libraryStack, "SettingsLibraryCard"));

        var scraperStack = new StackPanel { Spacing = 12 };
        scraperStack.Children.Add(SectionTitle("刮削器", "SettingsScraperCard"));
        var scraperContent = new StackPanel
        {
            Spacing = 12,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };
        AutomationProperties.SetAutomationId(scraperContent, "SettingsScraperContent");
        var tmdbApiKeyBox = TextInput("TMDB API Key", "SettingsTmdbApiKey");
        tmdbApiKeyBox.PlaceholderText = "去 themoviedb.org 免费申请";
        tmdbApiKeyBox.IsEnabled = supportsMediaTreeLibraryManagement;
        scraperContent.Children.Add(tmdbApiKeyBox);
        var tmdbTokenBox = PasswordInput("TMDB 读访问令牌（推荐，优先使用）", "SettingsTmdbAccessToken");
        tmdbTokenBox.PlaceholderText = "Bearer Token";
        tmdbTokenBox.IsEnabled = supportsMediaTreeLibraryManagement;
        scraperContent.Children.Add(tmdbTokenBox);
        var tmdbTokenStatusText = StatusText("SettingsTmdbTokenStatusText");
        scraperContent.Children.Add(tmdbTokenStatusText);
        scraperContent.Children.Add(ScraperDescriptionGrid());
        scraperStack.Children.Add(scraperContent);
        _settingsCards.Add(SectionCard(scraperStack, "SettingsScraperCard"));

        var backupStack = new StackPanel { Spacing = 12 };
        backupStack.Children.Add(SectionTitle("数据备份与恢复", "SettingsBackupCard"));
        var backupActions = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 10,
        };
        var backupCoreButton = FluentTheme.ApplyButton(new Button { Content = "下载数据库备份" }, FluentButtonStyle.Accent);
        backupCoreButton.IsEnabled = isLocalMediaTreeActive;
        AutomationProperties.SetAutomationId(backupCoreButton, "SettingsBackupCore");
        backupCoreButton.Click += async (sender, _) => await SaveBackupAsync("core", sender as Button);
        backupActions.Children.Add(backupCoreButton);
        var backupFullButton = FluentTheme.ApplyButton(new Button { Content = "下载完整备份 (含封面图)" }, FluentButtonStyle.Accent);
        backupFullButton.IsEnabled = isLocalMediaTreeActive;
        AutomationProperties.SetAutomationId(backupFullButton, "SettingsBackupFull");
        backupFullButton.Click += async (sender, _) => await SaveBackupAsync("full", sender as Button);
        backupActions.Children.Add(backupFullButton);
        var restoreBackupButton = FluentTheme.ApplyButton(new Button { Content = "选择备份恢复" });
        restoreBackupButton.IsEnabled = isLocalMediaTreeActive;
        AutomationProperties.SetAutomationId(restoreBackupButton, "SettingsRestoreBackup");
        restoreBackupButton.Click += OnRestoreBackupClicked;
        backupActions.Children.Add(restoreBackupButton);
        backupActions.SizeChanged += (_, args) => ApplyActionStackLayout(args.NewSize.Width, backupActions);
        backupStack.Children.Add(backupActions);
        backupStack.Children.Add(FluentTheme.Body("完整备份包含数据库和所有封面图片缓存。恢复会覆盖当前数据。", 13));
        if (!isLocalMediaTreeActive)
        {
            backupStack.Children.Add(FluentTheme.Body("当前媒体源不是本机 MediaTree，备份与恢复不可用。", 13));
        }
        var backupStatusText = StatusText("SettingsBackupStatusText");
        backupStack.Children.Add(backupStatusText);
        _settingsCards.Add(SectionCard(backupStack, "SettingsBackupCard"));

        var updateStack = new StackPanel { Spacing = 12 };
        var updateHeader = new Grid { ColumnSpacing = 12, RowSpacing = 10 };
        updateHeader.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        updateHeader.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        updateHeader.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        updateHeader.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });
        updateHeader.Children.Add(SectionTitle("更新", "SettingsUpdateCard"));
        var checkButton = FluentTheme.ApplyButton(new Button { Content = "检查更新", IsEnabled = isLocalMediaTreeActive });
        AutomationProperties.SetAutomationId(checkButton, "SettingsCheckUpdates");
        checkButton.Click += OnCheckUpdatesClicked;
        Grid.SetColumn(checkButton, 1);
        updateHeader.Children.Add(checkButton);
        updateHeader.SizeChanged += (_, args) => ApplyHeaderActionLayout(args.NewSize.Width, updateHeader, checkButton);
        updateStack.Children.Add(updateHeader);
        var versionText = new TextBlock
        {
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(versionText, "SettingsVersion");
        updateStack.Children.Add(versionText);
        var updateProgressText = StatusText("SettingsUpdateProgressText");
        updateStack.Children.Add(updateProgressText);
        var updateStatusText = StatusText("SettingsUpdateStatusText");
        updateStack.Children.Add(updateStatusText);
        var updateVersionsStack = new StackPanel { Spacing = 10 };
        AutomationProperties.SetAutomationId(updateVersionsStack, "SettingsUpdateVersions");
        updateStack.Children.Add(updateVersionsStack);
        if (!isLocalMediaTreeActive)
        {
            updateStack.Children.Add(FluentTheme.Body("当前媒体源不是本机 MediaTree，Windows 应用包更新不可用。", 13));
        }
        var logsButton = FluentTheme.ApplyButton(new Button
        {
            Content = "打开问题日志",
            HorizontalAlignment = HorizontalAlignment.Left,
        });
        AutomationProperties.SetAutomationId(logsButton, "SettingsOpenLogs");
        logsButton.Click += OnOpenLogsClicked;
        updateStack.Children.Add(logsButton);
        _settingsCards.Add(SectionCard(updateStack, "SettingsUpdateCard"));

        scrollViewer.SizeChanged += (_, args) => ApplySettingsViewportLayout(
            args.NewSize.Width,
            root,
            settingsGrid);

        scrollViewer.Content = root;
        Content = scrollViewer;
        return (
            globalStatusText,
            hideHomeTitleTextBox,
            allowRemoteBackendBox,
            remoteBackendPortBox,
            remoteBackendUrlText,
            remoteBackendStatusText,
            showSourceNameBox,
            remoteLoginUsernameBox,
            remoteLoginPasswordBox,
            mediaSourceGroupsStack,
            libraryStatusText,
            tmdbApiKeyBox,
            tmdbTokenBox,
            tmdbTokenStatusText,
            backupStatusText,
            versionText,
            updateProgressText,
            updateStatusText,
            updateVersionsStack
        );
    }

    private async void OnLoaded(object sender, RoutedEventArgs args)
    {
        LoadUiPreferences();
        LoadBackendAccessSettings();
        LoadMediaSourceGroups();
        await LoadVersionAsync();
        if (_isSwitchingMediaSource)
        {
            return;
        }

        await LoadTmdbConfigAsync();
        if (_isSwitchingMediaSource)
        {
            return;
        }

        await LoadLibrarySettingsAsync();
        if (_isSwitchingMediaSource)
        {
            return;
        }

        await LoadUpdateStatusAsync();
        if (_isSwitchingMediaSource)
        {
            return;
        }

        await CheckUpdatesOnLoadAsync();
    }

    private void OnUnloaded(object sender, RoutedEventArgs args)
        => StopBackgroundTimers();

    private void StopBackgroundTimers()
    {
        _scanStatusTimer.Stop();
        _updateStatusTimer.Stop();
    }

    private void LoadUiPreferences()
    {
        _suppressUiPreferenceSave = true;
        try
        {
            var preferences = UiPreferenceStore.Load();
            _hideHomeTitleTextBox.IsChecked = preferences.HideHomeTitleText;
            _showSourceNameBox.IsChecked = preferences.ShowSourceName;
        }
        finally
        {
            _suppressUiPreferenceSave = false;
        }
    }

    private void LoadBackendAccessSettings()
    {
        var settings = BackendAccessSettingsStore.Load();
        _allowRemoteBackendBox.IsChecked = settings.AllowRemoteAccess;
        _remoteBackendPortBox.Text = BackendAccessSettings.NormalizePort(settings.RemotePort).ToString();
        ShowRemoteBackendSettings(
            settings,
            IsLocalMediaTreeActive ? $"当前为{settings.AccessModeLabel}。" : LocalMediaTreeOnlyMessage,
            false);
    }

    private void LoadMediaSourceGroups()
    {
        _mediaSourceGroupsStack.Children.Clear();
        _librarySettingRows.Clear();
        var state = MediaSourceProfileStore.Load();
        foreach (var source in MediaSourceListPresenter.BuildItems(state))
        {
            _mediaSourceGroupsStack.Children.Add(CreateMediaSourceCard(source));
        }
    }

    private UIElement CreateMediaSourceCard(MediaSourceListItem source)
    {
        var expanded = _expandedMediaSources.Contains(source.Id);
        var state = GetLibraryPanelState(source);
        var automationSuffix = SanitizeAutomationId(source.Id);
        var row = new Border
        {
            Padding = new Thickness(12),
            CornerRadius = FluentTheme.CardCornerRadius,
            Background = FluentTheme.LayerAlt,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(1),
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };
        AutomationProperties.SetAutomationId(row, $"SettingsMediaSource_{automationSuffix}");

        var stack = new StackPanel
        {
            Spacing = 10,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };
        var header = new Grid
        {
            ColumnSpacing = 12,
            RowSpacing = 10,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        header.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        header.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });

        var info = new StackPanel
        {
            Spacing = 4,
            MinWidth = 220,
        };
        info.Children.Add(new TextBlock
        {
            Text = source.DisplayName,
            FontSize = 15,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
            TextWrapping = TextWrapping.WrapWholeWords,
        });
        info.Children.Add(new TextBlock
        {
            Text = $"{DisplaySourceKind(source.Kind)} · {FormatMediaSourceEndpoint(source)}",
            Foreground = FluentTheme.TextTertiary,
            TextWrapping = TextWrapping.WrapWholeWords,
            FontFamily = new FontFamily("Consolas"),
            FontSize = 12,
        });
        info.Children.Add(new TextBlock
        {
            Text = FormatMediaSourceSummary(source, state),
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        });
        header.Children.Add(info);

        var actions = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 8,
        };
        var statusText = StatusText($"SettingsMediaSourceStatus_{automationSuffix}");
        var toggleButton = FluentTheme.ApplyButton(new Button
        {
            Content = expanded ? "收起媒体库" : "查看媒体库",
            Tag = source,
            HorizontalAlignment = HorizontalAlignment.Left,
        });
        AutomationProperties.SetAutomationId(toggleButton, $"SettingsToggleMediaSource_{automationSuffix}");
        toggleButton.Click += OnToggleMediaSourceClicked;
        actions.Children.Add(toggleButton);

        if (!source.IsActive)
        {
            var switchButton = FluentTheme.ApplyButton(new Button
            {
                Content = source.Kind == MediaSourceKind.LocalMediaTree ? SwitchToLocalMediaTreeButtonText : SwitchMediaSourceButtonText,
                Tag = new MediaSourceRowContext(source, statusText),
                HorizontalAlignment = HorizontalAlignment.Left,
            }, FluentButtonStyle.Accent);
            AutomationProperties.SetAutomationId(switchButton, $"SettingsSwitchMediaSource_{automationSuffix}");
            switchButton.Click += OnSwitchMediaSourceClicked;
            actions.Children.Add(switchButton);
        }

        if (source.Kind != MediaSourceKind.LocalMediaTree)
        {
            var deleteButton = FluentTheme.ApplyButton(new Button
            {
                Content = DeleteLibraryButtonText,
                Tag = new MediaSourceRowContext(source, statusText),
                HorizontalAlignment = HorizontalAlignment.Left,
            }, FluentButtonStyle.Danger);
            AutomationProperties.SetAutomationId(deleteButton, $"SettingsDeleteMediaSource_{automationSuffix}");
            deleteButton.Click += OnDeleteMediaSourceClicked;
            actions.Children.Add(deleteButton);
        }

        Grid.SetColumn(actions, 1);
        header.Children.Add(actions);
        header.SizeChanged += (_, args) => ApplyMediaSourceRowLayout(args.NewSize.Width, header, info, actions);
        stack.Children.Add(header);
        stack.Children.Add(statusText);

        var libraryStack = new StackPanel
        {
            Spacing = 8,
            Visibility = expanded ? Visibility.Visible : Visibility.Collapsed,
        };
        AutomationProperties.SetAutomationId(libraryStack, $"SettingsMediaSourceLibraries_{automationSuffix}");
        if (expanded)
        {
            RenderMediaSourceLibraries(source, state, libraryStack);
        }

        stack.Children.Add(libraryStack);
        row.Child = stack;
        return row;
    }

    private MediaSourceLibraryPanelState GetLibraryPanelState(MediaSourceListItem source)
    {
        if (_mediaSourceLibraryStates.TryGetValue(source.Id, out var state))
        {
            return state;
        }

        return new MediaSourceLibraryPanelState
        {
            Message = source.IsActive ? "正在加载媒体库..." : "展开后加载该后端媒体库。"
        };
    }

    private void RenderMediaSourceLibraries(MediaSourceListItem source, MediaSourceLibraryPanelState state, StackPanel libraryStack)
    {
        if (state.IsLoading || !state.IsLoaded)
        {
            libraryStack.Children.Add(FluentTheme.Body(state.Message, 13));
            return;
        }

        if (state.IsError || state.Roots.Count == 0)
        {
            libraryStack.Children.Add(FluentTheme.Body(state.Message, 13));
            return;
        }

        for (var i = 0; i < state.Roots.Count; i++)
        {
            var root = state.Roots[i];
            state.Settings.TryGetValue(root.Path, out var setting);
            var canDelete = CanManageLibraries(source)
                && state.RemovableRoots.Any(extraRoot => LibraryService.RootsMatch(extraRoot, root.Path));
            libraryStack.Children.Add(CreateLibrarySettingsRow(source, root, setting, i, canDelete));
        }
    }

    private async void OnToggleMediaSourceClicked(object sender, RoutedEventArgs args)
    {
        if (sender is not Button { Tag: MediaSourceListItem source })
        {
            return;
        }

        if (!_expandedMediaSources.Add(source.Id))
        {
            _expandedMediaSources.Remove(source.Id);
            LoadMediaSourceGroups();
            return;
        }

        LoadMediaSourceGroups();
        await LoadMediaSourceLibrariesAsync(source);
    }

    private async System.Threading.Tasks.Task LoadLibrarySettingsAsync()
    {
        var state = MediaSourceProfileStore.Load();
        var active = MediaSourceListPresenter.BuildItems(state).FirstOrDefault(source => source.IsActive);
        if (active is null)
        {
            _libraryStatusText.Foreground = FluentTheme.Error;
            _libraryStatusText.Text = "当前媒体源配置不存在。";
            return;
        }

        _expandedMediaSources.Add(active.Id);
        LoadMediaSourceGroups();
        await LoadMediaSourceLibrariesAsync(active);
    }

    private async System.Threading.Tasks.Task LoadMediaSourceLibrariesAsync(MediaSourceListItem source)
    {
        _mediaSourceLibraryStates[source.Id] = new MediaSourceLibraryPanelState
        {
            IsLoading = true,
            Message = $"正在加载 {source.DisplayName} 的媒体库...",
        };
        LoadMediaSourceGroups();

        try
        {
            _libraryStatusText.Foreground = FluentTheme.TextSecondary;
            _libraryStatusText.Text = $"正在加载 {source.DisplayName} 的媒体库...";
            using var lease = await OpenMediaServicesAsync(source);
            var canManageLibraries = CanManageLibraries(source);
            var roots = await lease.Services.Library.GetMediaRootsAsync();
            var librarySettings = await lease.Services.Library.GetLibrarySettingsAsync();
            var config = canManageLibraries ? await lease.Services.Api.GetConfigAsync() : new ConfigDto();
            var orderedRoots = roots.Items
                .OrderBy(root => string.IsNullOrWhiteSpace(root.Label) ? root.Path : root.Label, StringComparer.CurrentCultureIgnoreCase)
                .ToList();
            var message = orderedRoots.Count == 0
                ? canManageLibraries
                    ? "还没有媒体库。先添加影片文件夹后，再设置刮削器。"
                    : "当前外部媒体源没有返回可显示的媒体库。"
                : canManageLibraries
                    ? "选择刮削器后点击保存。需要重新刮削时可直接重新扫描。"
                    : ExternalLibraryReadOnlyMessage;

            _mediaSourceLibraryStates[source.Id] = new MediaSourceLibraryPanelState
            {
                IsLoaded = true,
                Message = message,
                Roots = orderedRoots,
                Settings = librarySettings.ToDictionary(s => s.MediaRoot, StringComparer.OrdinalIgnoreCase),
                RemovableRoots = config.ExtraMediaRoots ?? [],
            };
            _libraryStatusText.Foreground = canManageLibraries || orderedRoots.Count > 0 ? FluentTheme.TextSecondary : FluentTheme.Error;
            _libraryStatusText.Text = message;
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load media source library settings.");
            _mediaSourceLibraryStates[source.Id] = new MediaSourceLibraryPanelState
            {
                IsLoaded = true,
                IsError = true,
                Message = $"加载媒体库设置失败：{ex.Message}",
            };
            _libraryStatusText.Foreground = FluentTheme.Error;
            _libraryStatusText.Text = $"加载 {source.DisplayName} 媒体库失败：{ex.Message}";
        }
        finally
        {
            LoadMediaSourceGroups();
        }
    }

    private async System.Threading.Tasks.Task<MediaServicesLease> OpenMediaServicesAsync(MediaSourceListItem source)
    {
        if (source.Kind == MediaSourceKind.LocalMediaTree)
        {
            return new MediaServicesLease(AppServices.LocalMediaTreeProvider.Services);
        }

        if (source.IsActive)
        {
            return new MediaServicesLease(AppServices.Media);
        }

        var record = MediaSourceProfileStore.Load().Sources.FirstOrDefault(item => string.Equals(item.Id, source.Id, StringComparison.OrdinalIgnoreCase))
            ?? throw new InvalidOperationException("媒体源配置不存在。");
        var provider = await MediaSourceActivator.CreateProviderAsync(record);
        return new MediaServicesLease(provider.Services, provider.Services.Api);
    }

    private async System.Threading.Tasks.Task<MediaServicesLease> OpenMediaServicesAsync(string sourceId)
    {
        var source = MediaSourceListPresenter.BuildItems(MediaSourceProfileStore.Load())
            .FirstOrDefault(item => string.Equals(item.Id, sourceId, StringComparison.OrdinalIgnoreCase))
            ?? throw new InvalidOperationException("媒体源配置不存在。");
        return await OpenMediaServicesAsync(source);
    }

    private static bool CanManageLibraries(MediaSourceListItem source)
        => source.Kind is MediaSourceKind.LocalMediaTree or MediaSourceKind.RemoteMediaTree;

    private static string FormatMediaSourceEndpoint(MediaSourceListItem source)
        => string.IsNullOrWhiteSpace(source.Endpoint) ? "内置本机后端" : source.Endpoint;

    private static string FormatMediaSourceSummary(MediaSourceListItem source, MediaSourceLibraryPanelState state)
    {
        var status = source.IsActive ? "当前" : "已保存";
        if (state.IsLoaded && !state.IsError)
        {
            return $"{status} · {state.Roots.Count} 个媒体库";
        }

        return string.IsNullOrWhiteSpace(state.Message) ? status : $"{status} · {state.Message}";
    }

    private static MediaSourceListItem FindMediaSource(string sourceId)
        => MediaSourceListPresenter.BuildItems(MediaSourceProfileStore.Load())
            .FirstOrDefault(item => string.Equals(item.Id, sourceId, StringComparison.OrdinalIgnoreCase))
            ?? throw new InvalidOperationException("媒体源配置不存在。");

    private static string ScanKey(string sourceId, string mediaRoot)
        => $"{sourceId}\n{mediaRoot}";

    private async void OnDeleteMediaSourceClicked(object sender, RoutedEventArgs args)
    {
        if (sender is not Button button || button.Tag is not MediaSourceRowContext context)
        {
            return;
        }

        await ShowDeleteMediaSourceDialogAsync(context.Source, context.StatusText);
    }

    private async System.Threading.Tasks.Task ShowDeleteMediaSourceDialogAsync(MediaSourceListItem source, TextBlock rowStatusText)
    {
        if (source.Kind == MediaSourceKind.LocalMediaTree)
        {
            ShowRowStatus(rowStatusText, "本机 MediaTree 不能删除。", true);
            return;
        }

        var statusText = StatusText("SettingsDeleteMediaSourceDialogStatus", visible: true);
        statusText.Text = source.IsActive
            ? "此后端当前正在使用。删除后会自动切回本机 MediaTree。"
            : "删除后只移除此连接配置和本机保存的凭据，不会删除服务端媒体库。";
        statusText.Foreground = FluentTheme.TextSecondary;

        var content = new StackPanel { Spacing = 12 };
        content.Children.Add(WrapText("确定要删除这个已连接后端吗？"));
        content.Children.Add(new TextBlock
        {
            Text = source.DisplayName,
            Foreground = FluentTheme.TextPrimary,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            TextWrapping = TextWrapping.WrapWholeWords,
        });
        content.Children.Add(new TextBlock
        {
            Text = FormatMediaSourceEndpoint(source),
            Foreground = FluentTheme.TextTertiary,
            TextWrapping = TextWrapping.WrapWholeWords,
            FontFamily = new FontFamily("Consolas"),
        });
        content.Children.Add(statusText);

        var dialog = new WindowModalDialog("删除后端", content, "删除", "取消")
        {
            MaxWidth = 560,
            ContentMaxWidth = 500,
        };
        dialog.PrimaryActionAsync = async () =>
        {
            try
            {
                statusText.Foreground = FluentTheme.TextSecondary;
                statusText.Text = "正在删除后端连接...";
                MediaSourceProfileStore.RemoveSource(source.Id);
                MediaSourceCredentialStore.Clear(source.Id);
                _expandedMediaSources.Remove(source.Id);
                _mediaSourceLibraryStates.Remove(source.Id);
                RemoveScanRowsForSource(source.Id);

                if (source.IsActive)
                {
                    await SwitchToSavedMediaSourceAsync(new MediaSourceListItem(
                        MediaSourceProfileStore.LocalSourceId,
                        MediaSourceKind.LocalMediaTree,
                        "本机 MediaTree",
                        "",
                        RequiresBundledBackend: true,
                        IsActive: false));
                }
                else
                {
                    LoadMediaSourceGroups();
                }

                _libraryStatusText.Foreground = FluentTheme.Accent;
                _libraryStatusText.Text = "后端连接已删除。";
                ShowRowStatus(rowStatusText, "已删除。", false);
                ShellPage.Current?.ReloadActiveMediaSource();
                return true;
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, "Failed to delete saved media source.");
                statusText.Foreground = FluentTheme.Error;
                statusText.Text = $"删除失败：{ex.Message}";
                ShowRowStatus(rowStatusText, $"删除失败：{ex.Message}", true);
                return false;
            }
        };

        await dialog.ShowAsync();
    }

    private void RemoveScanRowsForSource(string sourceId)
    {
        foreach (var scanKey in _scanRows
            .Where(pair => string.Equals(pair.Value.SourceId, sourceId, StringComparison.OrdinalIgnoreCase))
            .Select(pair => pair.Key)
            .ToList())
        {
            _scanRows.Remove(scanKey);
            _activeScanRoots.Remove(scanKey);
            _scanPollCounts.Remove(scanKey);
        }
    }

    private async void OnSaveRemoteBackendClicked(object sender, RoutedEventArgs args)
    {
        if (sender is not Button button)
        {
            return;
        }

        try
        {
            if (!IsLocalMediaTreeActive)
            {
                ShowRemoteBackendSettings(BackendAccessSettingsStore.Load(), LocalMediaTreeOnlyMessage, true);
                return;
            }

            button.IsEnabled = false;
            var settings = ReadBackendAccessSettingsFromUi();
            if (HasRemoteLoginInput())
            {
                ValidateRemoteLoginInput();
                ShowRemoteBackendSettings(settings, "正在更新移动端登录账号...", false);
                await AppServices.Media.Auth.ChangeStoredSessionCredentialsAsync(
                    _remoteLoginUsernameBox.Text.Trim(),
                    _remoteLoginPasswordBox.Password);
                _remoteLoginUsernameBox.Text = "";
                _remoteLoginPasswordBox.Password = "";
            }

            BackendAccessSettingsStore.Save(settings);
            ShowRemoteBackendSettings(settings, "正在重启本机后端...", false);
            var backendUri = await AppServices.Backend.RestartAsync();
            if (IsLocalMediaTreeActive)
            {
                AppServices.Media.Api.SetBackendUri(backendUri);
            }
            ShowRemoteBackendSettings(BackendAccessSettingsStore.Load(), "已保存账号并重启本机后端。", false);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to save native backend access settings.");
            ShowRemoteBackendSettings(ReadBackendAccessSettingsFromUi(), $"保存失败：{ex.Message}", true);
        }
        finally
        {
            button.IsEnabled = true;
        }
    }

    private bool HasRemoteLoginInput()
        => !string.IsNullOrWhiteSpace(_remoteLoginUsernameBox.Text) || !string.IsNullOrEmpty(_remoteLoginPasswordBox.Password);

    private void ValidateRemoteLoginInput()
    {
        if (string.IsNullOrWhiteSpace(_remoteLoginUsernameBox.Text) || string.IsNullOrEmpty(_remoteLoginPasswordBox.Password))
        {
            throw new InvalidOperationException("登录用户名和登录密码需要一起填写。");
        }
    }

    private BackendAccessSettings ReadBackendAccessSettingsFromUi()
    {
        var port = int.TryParse(_remoteBackendPortBox.Text.Trim(), out var parsedPort)
            ? BackendAccessSettings.NormalizePort(parsedPort)
            : BackendAccessSettings.DefaultRemotePort;
        _remoteBackendPortBox.Text = port.ToString();
        return new BackendAccessSettings
        {
            AllowRemoteAccess = _allowRemoteBackendBox.IsChecked == true,
            RemotePort = port,
        };
    }

    private void ShowRemoteBackendSettings(BackendAccessSettings settings, string message, bool isError)
    {
        _remoteBackendUrlText.Text = settings.AllowRemoteAccess
            ? settings.DisplayUrl(BackendProcessService.GetPreferredLanAddress())
            : $"局域网未开放；开启后地址：{settings.DisplayUrl("此电脑IP")}";
        _remoteBackendStatusText.Text = settings.AllowRemoteAccess
            ? $"{message} Windows 防火墙若弹出提示，需要允许专用网络访问。"
            : message;
        _remoteBackendStatusText.Foreground = isError ? FluentTheme.Error : FluentTheme.TextSecondary;
        _remoteBackendStatusText.Visibility = Visibility.Visible;
    }

    private async System.Threading.Tasks.Task LoadVersionAsync()
    {
        try
        {
            if (!IsLocalMediaTreeActive)
            {
                _versionText.Text = $"当前媒体源：{DisplaySourceKind(ActiveSourceKind)}    由外部服务端管理。";
                return;
            }

            var version = await AppServices.Media.Updates.GetVersionAsync();
            _versionText.Text = FormatVersionLine(
                version.Version,
                version.CurrentSource,
                version.BaseVersion,
                version.StatusNote);
        }
        catch (Exception ex)
        {
            _versionText.Text = $"暂时无法读取版本信息：{ex.Message}";
        }
    }

    private async System.Threading.Tasks.Task LoadTmdbConfigAsync()
    {
        try
        {
            if (!SupportsMediaTreeLibraryManagement)
            {
                _loadedConfig = new ConfigDto();
                _tmdbApiKeyBox.Text = "";
                _tmdbTokenBox.Password = "";
                ShowTmdbStatus(ExternalLibraryReadOnlyMessage, false);
                return;
            }

            var config = await AppServices.Media.Api.GetConfigAsync();
            _loadedConfig = config;
            _tmdbApiKeyBox.Text = config.TmdbApiKey ?? "";
            _tmdbTokenBox.Password = config.TmdbAccessToken ?? "";
            ShowTmdbStatus(config.TmdbConfigured ? "TMDB 已配置。保存全局设置即可替换令牌。" : "未配置 TMDB 令牌。选择 TMDB 刮削器前建议先填写。", false);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load native TMDB config.");
            ShowTmdbStatus($"读取 TMDB 配置失败：{ex.Message}", true);
        }
    }

    private async void OnSaveGlobalClicked(object sender, RoutedEventArgs args)
    {
        if (sender is not Button button)
        {
            return;
        }

        try
        {
            button.IsEnabled = false;
            ShowGlobalStatus("正在保存全局设置...", false);
            SaveUiPreferences();
            await SaveGlobalConfigAsync();
            ShowGlobalStatus("已保存", false);
            ShowTmdbStatus(SupportsMediaTreeLibraryManagement ? "TMDB 设置已保存。" : ExternalLibraryReadOnlyMessage, false);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to save native global settings.");
            ShowGlobalStatus($"保存失败：{ex.Message}", true);
        }
        finally
        {
            button.IsEnabled = true;
        }
    }

    private async System.Threading.Tasks.Task SaveGlobalConfigAsync()
    {
        if (!SupportsMediaTreeLibraryManagement)
        {
            return;
        }

        await AppServices.Media.Api.SaveGlobalConfigAsync(new ConfigDto
        {
            JavdbEnabled = _loadedConfig.JavdbEnabled,
            TmdbApiKey = _tmdbApiKeyBox.Text.Trim(),
            TmdbAccessToken = _tmdbTokenBox.Password,
            UpdateCheckEnabled = _loadedConfig.UpdateCheckEnabled,
            UpdateCheckIntervalHours = _loadedConfig.UpdateCheckIntervalHours,
        });
    }

    private void OnUiPreferenceChanged(object sender, RoutedEventArgs args)
    {
        if (_suppressUiPreferenceSave)
        {
            return;
        }

        SaveUiPreferences();
    }

    private void SaveUiPreferences()
    {
        UiPreferenceStore.Save(new UiPreferenceState
        {
            HideHomeTitleText = _hideHomeTitleTextBox.IsChecked == true,
            ShowSourceName = _showSourceNameBox.IsChecked == true,
        });
    }

    private UIElement CreateLibrarySettingsRow(MediaSourceListItem source, MediaRootDto root, LibrarySettingDto? setting, int index, bool canDelete)
    {
        var rowSuffix = $"{SanitizeAutomationId(source.Id)}_{index}";
        var row = new Border
        {
            Padding = new Thickness(14),
            CornerRadius = FluentTheme.CardCornerRadius,
            Background = FluentTheme.LayerAlt,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(1),
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };
        if (_settingsColumnWidth > 0)
        {
            row.Width = CalculateLibraryRowWidth(_settingsColumnWidth);
        }
        _librarySettingRows.Add(row);

        var grid = new Grid { ColumnSpacing = 12, HorizontalAlignment = HorizontalAlignment.Stretch };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });
        grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });

        var info = new StackPanel { Spacing = 4, MinWidth = 220 };
        info.Children.Add(new TextBlock
        {
            Text = string.IsNullOrWhiteSpace(root.Label) ? root.Path : root.Label,
            FontSize = 16,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
            TextTrimming = TextTrimming.CharacterEllipsis,
        });
        info.Children.Add(new TextBlock
        {
            Text = root.Path,
            Foreground = FluentTheme.TextTertiary,
            TextWrapping = TextWrapping.WrapWholeWords,
        });
        info.Children.Add(new TextBlock
        {
            Text = $"{root.MovieCount} 部",
            Foreground = FluentTheme.TextSecondary,
        });
        grid.Children.Add(info);

        var canManageLibraries = CanManageLibraries(source);
        var selectedScraper = NormalizeScraper(setting?.Scraper ?? root.Scraper);
        var scraperStack = new StackPanel
        {
            Spacing = 6,
        };
        var inputGrid = new Grid
        {
            ColumnSpacing = 10,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };
        inputGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        inputGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        var scraperBox = FluentTheme.ApplyComboBox(new ComboBox
        {
            Header = LibraryScraperHeader,
            MinWidth = 0,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            IsEnabled = canManageLibraries,
        });
        AutomationProperties.SetAutomationId(scraperBox, $"SettingsLibraryScraper_{rowSuffix}");
        foreach (var option in ScraperOptions)
        {
            scraperBox.Items.Add(new ComboBoxItem
            {
                Content = option.Label,
                Tag = option.Value,
            });
        }

        SelectScraper(scraperBox, selectedScraper);
        var descriptionText = new TextBlock
        {
            Text = canManageLibraries ? GetScraperDescription(GetSelectedScraper(scraperBox)) : ExternalLibraryReadOnlyMessage,
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        scraperBox.SelectionChanged += (_, _) =>
        {
            descriptionText.Text = canManageLibraries ? GetScraperDescription(GetSelectedScraper(scraperBox)) : ExternalLibraryReadOnlyMessage;
        };

        var passwordBox = FluentTheme.ApplyPasswordInput(new PasswordBox
        {
            Header = "密码",
            PlaceholderText = "可选",
            MinWidth = 0,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            IsEnabled = canManageLibraries,
        });
        AutomationProperties.SetAutomationId(passwordBox, $"SettingsLibraryPassword_{rowSuffix}");
        inputGrid.Children.Add(scraperBox);
        Grid.SetColumn(passwordBox, 1);
        inputGrid.Children.Add(passwordBox);
        scraperStack.Children.Add(inputGrid);
        scraperStack.Children.Add(descriptionText);
        Grid.SetColumn(scraperStack, 1);
        grid.Children.Add(scraperStack);

        var actions = new StackPanel { Spacing = 8 };
        var rowStatusText = StatusText($"SettingsLibraryRowStatus_{rowSuffix}");
        var rowLogText = new TextBlock
        {
            Foreground = FluentTheme.TextTertiary,
            TextWrapping = TextWrapping.WrapWholeWords,
            FontFamily = new FontFamily("Consolas"),
            FontSize = 11,
            Visibility = Visibility.Collapsed,
        };
        AutomationProperties.SetAutomationId(rowLogText, $"SettingsLibraryScanLog_{rowSuffix}");
        if (canManageLibraries)
        {
            var saveButton = FluentTheme.ApplyButton(new Button
            {
                Content = "保存",
                Tag = new LibrarySettingsRowContext(source.Id, root.Path, setting?.TmdbKey ?? "", scraperBox, passwordBox, rowStatusText, rowLogText),
            }, FluentButtonStyle.Accent);
            AutomationProperties.SetAutomationId(saveButton, $"SettingsSaveLibrary_{rowSuffix}");
            saveButton.Click += OnSaveLibrarySettingClicked;
            actions.Children.Add(saveButton);

            var scanButton = FluentTheme.ApplyButton(new Button
            {
                Content = "重新扫描",
                Tag = new LibrarySettingsRowContext(source.Id, root.Path, setting?.TmdbKey ?? "", scraperBox, passwordBox, rowStatusText, rowLogText),
            });
            AutomationProperties.SetAutomationId(scanButton, $"SettingsScanLibrary_{rowSuffix}");
            scanButton.Click += OnScanLibraryClicked;
            actions.Children.Add(scanButton);

            if (canDelete)
            {
                var deleteButton = FluentTheme.ApplyButton(new Button
                {
                    Content = DeleteLibraryButtonText,
                    Tag = new DeleteLibraryContext(source.Id, root.Path),
                }, FluentButtonStyle.Danger);
                AutomationProperties.SetAutomationId(deleteButton, $"SettingsDeleteLibrary_{rowSuffix}");
                deleteButton.Click += OnDeleteLibraryClicked;
                actions.Children.Add(deleteButton);
            }

            _scanRows[ScanKey(source.Id, root.Path)] = new LibraryScanRowUi(source.Id, root.Path, rowStatusText, rowLogText, scanButton);
        }
        else
        {
            actions.Children.Add(new TextBlock
            {
                Text = "只读",
                Foreground = FluentTheme.TextSecondary,
                TextWrapping = TextWrapping.WrapWholeWords,
            });
        }
        Grid.SetColumn(actions, 2);
        grid.Children.Add(actions);

        row.SizeChanged += (_, args) => ApplyLibrarySettingsRowLayout(
            args.NewSize.Width,
            grid,
            info,
            scraperStack,
            inputGrid,
            actions);

        row.Child = grid;
        var rowStack = new StackPanel { Spacing = 10 };
        rowStack.Children.Add(row);
        rowStack.Children.Add(rowStatusText);
        rowStack.Children.Add(rowLogText);
        return rowStack;
    }

    private async void OnSaveLibrarySettingClicked(object sender, RoutedEventArgs args)
    {
        if (sender is not Button button || button.Tag is not LibrarySettingsRowContext context)
        {
            return;
        }

        try
        {
            var source = FindMediaSource(context.SourceId);
            if (!CanManageLibraries(source))
            {
                ShowRowStatus(context.StatusText, ExternalLibraryReadOnlyMessage, true);
                return;
            }

            button.IsEnabled = false;
            _libraryStatusText.Foreground = FluentTheme.TextSecondary;
            _libraryStatusText.Text = "正在保存媒体库设置...";
            ShowRowStatus(context.StatusText, "正在保存媒体库设置...", false);
            await SaveLibrarySettingAsync(context);

            _libraryStatusText.Foreground = FluentTheme.Accent;
            _libraryStatusText.Text = "媒体库设置已保存。";
            ShowRowStatus(context.StatusText, "已保存。", false);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to save native library scraper setting.");
            _libraryStatusText.Foreground = FluentTheme.Error;
            _libraryStatusText.Text = $"保存媒体库设置失败：{ex.Message}";
            ShowRowStatus(context.StatusText, $"保存失败：{ex.Message}", true);
        }
        finally
        {
            button.IsEnabled = true;
        }
    }

    private async void OnScanLibraryClicked(object sender, RoutedEventArgs args)
    {
        if (sender is not Button button || button.Tag is not LibrarySettingsRowContext context || string.IsNullOrWhiteSpace(context.MediaRoot))
        {
            return;
        }

        try
        {
            var source = FindMediaSource(context.SourceId);
            if (!CanManageLibraries(source))
            {
                ShowRowStatus(context.StatusText, ExternalLibraryReadOnlyMessage, true);
                return;
            }

            button.IsEnabled = false;
            _libraryStatusText.Foreground = FluentTheme.TextSecondary;
            _libraryStatusText.Text = "正在保存刮削器设置并重新扫描...";
            ShowRowStatus(context.StatusText, "正在保存刮削器设置并重新扫描...", false);
            context.LogText.Visibility = Visibility.Collapsed;
            context.LogText.Text = "";
            await SaveLibrarySettingAsync(context);
            using (var lease = await OpenMediaServicesAsync(context.SourceId))
            {
                await lease.Services.Library.ClearLibraryAsync(context.MediaRoot);
            }

            var scanKey = ScanKey(context.SourceId, context.MediaRoot);
            _ = StartLibraryScanInBackgroundAsync(context.SourceId, context.MediaRoot);
            _activeScanRoots.Add(scanKey);
            _scanPollCounts[scanKey] = 0;
            _scanStatusTimer.Start();
            _libraryStatusText.Foreground = FluentTheme.Accent;
            _libraryStatusText.Text = "已开始重新扫描。你可以继续使用应用。";
            ShowRowStatus(context.StatusText, "已开始重新扫描。", false);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to rescan native library from settings.");
            _libraryStatusText.Foreground = FluentTheme.Error;
            _libraryStatusText.Text = $"重新扫描失败：{ex.Message}";
            ShowRowStatus(context.StatusText, $"重新扫描失败：{ex.Message}", true);
        }
        finally
        {
            button.IsEnabled = !_activeScanRoots.Contains(ScanKey(context.SourceId, context.MediaRoot));
        }
    }

    private async void OnDeleteLibraryClicked(object sender, RoutedEventArgs args)
    {
        if (sender is not Button button || button.Tag is not DeleteLibraryContext context || string.IsNullOrWhiteSpace(context.MediaRoot))
        {
            return;
        }

        var statusText = StatusText("SettingsDeleteLibraryDialogStatus", visible: true);
        var source = FindMediaSource(context.SourceId);
        if (!CanManageLibraries(source))
        {
            _libraryStatusText.Foreground = FluentTheme.Error;
            _libraryStatusText.Text = ExternalLibraryReadOnlyMessage;
            return;
        }

        statusText.Text = "此操作只会从 Windows 桌面版的已添加本机目录列表移除此媒体库，不会删除本机文件夹或影片文件。";
        statusText.Foreground = FluentTheme.TextSecondary;

        var content = new StackPanel { Spacing = 12 };
        content.Children.Add(WrapText("确定要删除这个本机媒体库目录吗？"));
        content.Children.Add(new TextBlock
        {
            Text = context.MediaRoot,
            Foreground = FluentTheme.TextPrimary,
            TextWrapping = TextWrapping.WrapWholeWords,
            FontFamily = new FontFamily("Consolas"),
        });
        content.Children.Add(statusText);

        var dialog = new WindowModalDialog("删除媒体库", content, "删除", "取消")
        {
            MaxWidth = 560,
            ContentMaxWidth = 500,
        };
        dialog.PrimaryActionAsync = async () =>
        {
            try
            {
                statusText.Foreground = FluentTheme.TextSecondary;
                statusText.Text = "正在删除媒体库...";
                using var lease = await OpenMediaServicesAsync(context.SourceId);
                await lease.Services.Library.DeleteLibraryAsync(context.MediaRoot);
                var scanKey = ScanKey(context.SourceId, context.MediaRoot);
                _activeScanRoots.Remove(scanKey);
                _scanPollCounts.Remove(scanKey);
                _scanRows.Remove(scanKey);
                _libraryStatusText.Foreground = FluentTheme.Accent;
                _libraryStatusText.Text = "媒体库已从已添加目录中移除。";
                await LoadMediaSourceLibrariesAsync(source);
                return true;
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, "Failed to delete native library.");
                statusText.Foreground = FluentTheme.Error;
                statusText.Text = $"删除失败：{ex.Message}";
                return false;
            }
        };

        await dialog.ShowAsync();
    }

    private async System.Threading.Tasks.Task SaveLibrarySettingAsync(LibrarySettingsRowContext context)
    {
        var source = FindMediaSource(context.SourceId);
        if (!CanManageLibraries(source))
        {
            throw new InvalidOperationException(ExternalLibraryReadOnlyMessage);
        }

        using var lease = await OpenMediaServicesAsync(context.SourceId);
        await lease.Services.Library.SaveLibrarySettingAsync(new LibrarySettingDto
        {
            MediaRoot = context.MediaRoot,
            Scraper = GetSelectedScraper(context.ScraperBox),
            TmdbKey = context.TmdbKey,
            Enabled = 1,
        });
        if (!string.IsNullOrWhiteSpace(context.PasswordBox.Password))
        {
            await lease.Services.Library.SetLibraryPasswordAsync(context.MediaRoot, context.PasswordBox.Password);
            context.PasswordBox.Password = "";
        }
    }

    private async System.Threading.Tasks.Task SaveBackupAsync(string backupType, Button? button)
    {
        try
        {
            if (!IsLocalMediaTreeActive)
            {
                ShowBackupStatus(LocalMediaTreeOnlyMessage, true);
                return;
            }

            if (button is not null)
            {
                button.IsEnabled = false;
            }

            ShowBackupStatus("正在准备备份文件...", false);
            var picker = new FileSavePicker
            {
                SuggestedStartLocation = PickerLocationId.DocumentsLibrary,
                SuggestedFileName = backupType == "full" ? "mediatree_full_backup.tar.gz" : "mediatree_backup.db",
            };
            if (backupType == "full")
            {
                picker.FileTypeChoices.Add("MediaTree 完整备份", [".gz"]);
            }
            else
            {
                picker.FileTypeChoices.Add("MediaTree 数据库备份", [".db"]);
            }

            if (AppServices.MainWindow is not null)
            {
                InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(AppServices.MainWindow));
            }

            var file = await picker.PickSaveFileAsync();
            if (file is null)
            {
                ShowBackupStatus("已取消保存。", false);
                return;
            }

            var bytes = await AppServices.Media.Api.DownloadBackupAsync(backupType);
            CachedFileManager.DeferUpdates(file);
            await FileIO.WriteBytesAsync(file, bytes);
            await CachedFileManager.CompleteUpdatesAsync(file);
            ShowBackupStatus("备份已保存。", false);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to save native backup.");
            ShowBackupStatus($"保存备份失败：{ex.Message}", true);
        }
        finally
        {
            if (button is not null)
            {
                button.IsEnabled = true;
            }
        }
    }

    private async void OnRestoreBackupClicked(object sender, RoutedEventArgs args)
    {
        if (sender is not Button button)
        {
            return;
        }

        try
        {
            if (!IsLocalMediaTreeActive)
            {
                ShowBackupStatus(LocalMediaTreeOnlyMessage, true);
                return;
            }

            var picker = new FileOpenPicker
            {
                SuggestedStartLocation = PickerLocationId.DocumentsLibrary,
            };
            picker.FileTypeFilter.Add(".db");
            picker.FileTypeFilter.Add(".gz");
            if (AppServices.MainWindow is not null)
            {
                InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(AppServices.MainWindow));
            }

            var file = await picker.PickSingleFileAsync();
            if (file is null)
            {
                ShowBackupStatus("已取消选择。", false);
                return;
            }

            button.IsEnabled = false;
            ShowBackupStatus("正在恢复备份...", false);
            await AppServices.Media.Api.RestoreBackupAsync(file.Path);
            ShowBackupStatus("恢复成功。请重新打开应用查看最新数据。", false);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to restore native backup.");
            ShowBackupStatus($"恢复失败：{ex.Message}", true);
        }
        finally
        {
            button.IsEnabled = true;
        }
    }

    private async void OnCheckUpdatesClicked(object sender, RoutedEventArgs args)
    {
        var button = sender as Button;
        if (button is not null)
        {
            button.IsEnabled = false;
        }

        try
        {
            if (!IsLocalMediaTreeActive)
            {
                ShowUpdateStatus(LocalMediaTreeOnlyMessage, true);
                return;
            }

            ShowUpdateStatus("正在检查更新...", false);
            var result = await AppServices.Media.Updates.CheckForUpdatesAsync();
            _lastUpdateResult = result;
            await LoadUpdateStatusAsync();
            if (!result.HasUpdate)
            {
                ShowUpdateStatus("当前已经是最新版本。", false);
            }
            else
            {
                var next = result.Versions.Count > 0 ? result.Versions[0] : null;
                var nextDisplay = next is null ? "" : DisplayVersionOrVersion(next);
                var message = next?.RequiresFullUpdate == true
                    ? $"发现新版本 {nextDisplay}。该版本需要下载全量更新安装包。{next.FullUpdateReason}"
                    : $"发现新版本 {nextDisplay}。可以直接在应用内更新。";
                ShowUpdateStatus(message, false);
            }
            RenderUpdateVersions();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to check native Windows updates.");
            ShowUpdateStatus($"检查更新失败：{ex.Message}", true);
        }
        finally
        {
            if (button is not null)
            {
                button.IsEnabled = true;
            }
        }
    }

    private async System.Threading.Tasks.Task CheckUpdatesOnLoadAsync()
    {
        try
        {
            if (!IsLocalMediaTreeActive)
            {
                _lastUpdateResult = null;
                RenderUpdateVersions();
                ShowUpdateStatus(LocalMediaTreeOnlyMessage, false);
                return;
            }

            _lastUpdateResult = await AppServices.Media.Updates.CheckForUpdatesAsync();
            RenderUpdateVersions();
            if (_lastUpdateResult.HasUpdate)
            {
                var next = _lastUpdateResult.Versions.Count > 0 ? _lastUpdateResult.Versions[0] : null;
                ShowUpdateStatus($"发现新版本 {next?.DisplayVersion ?? next?.Version ?? ""}", false);
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to auto-check native Windows updates.");
        }
    }

    private async System.Threading.Tasks.Task StartLibraryScanInBackgroundAsync(string sourceId, string mediaRoot)
    {
        try
        {
            var source = FindMediaSource(sourceId);
            if (!CanManageLibraries(source))
            {
                return;
            }

            using var lease = await OpenMediaServicesAsync(sourceId);
            await lease.Services.Library.ScanAsync(mediaRoot);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Native library scan trigger failed or timed out.");
        }
    }

    private void OnOpenLogsClicked(object sender, RoutedEventArgs args)
    {
        try
        {
            AppPaths.EnsureLogsDirectory();
            Process.Start(new ProcessStartInfo
            {
                FileName = AppPaths.LogsDirectory,
                UseShellExecute = true,
            });
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to open native Windows logs directory.");
            ShowUpdateStatus($"打开日志失败：{ex.Message}", true);
        }
    }

    private async System.Threading.Tasks.Task LoadUpdateStatusAsync()
    {
        try
        {
            if (!IsLocalMediaTreeActive)
            {
                _lastUpdateStatus = new UpdateStatusDto
                {
                    Status = "disabled",
                    Message = LocalMediaTreeOnlyMessage,
                };
                RenderUpdateStatus(_lastUpdateStatus);
                RenderUpdateVersions();
                return;
            }

            _lastUpdateStatus = await AppServices.Media.Updates.GetStatusAsync();
            RenderUpdateStatus(_lastUpdateStatus);
            RenderUpdateVersions();
            if (IsUpdateBusy(_lastUpdateStatus))
            {
                _updateStatusTimer.Start();
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load native update status.");
        }
    }

    private async void OnUpdateStatusTimerTick(object? sender, object args)
    {
        await RefreshUpdateStatusAsync();
    }

    private async System.Threading.Tasks.Task RefreshUpdateStatusAsync()
    {
        try
        {
            if (!IsLocalMediaTreeActive)
            {
                _updateStatusTimer.Stop();
                return;
            }

            _lastUpdateStatus = await AppServices.Media.Updates.GetStatusAsync();
            RenderUpdateStatus(_lastUpdateStatus);
            RenderUpdateVersions();
            if (!IsUpdateBusy(_lastUpdateStatus))
            {
                _updateStatusTimer.Stop();
                if (_lastUpdateStatus.Status == "success")
                {
                    await LoadVersionAsync();
                }
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to refresh native update status.");
            ShowUpdateStatus("服务可能正在重启，请稍后刷新设置页查看最新版本。", false);
        }
    }

    private void RenderUpdateStatus(UpdateStatusDto status)
    {
        var label = StatusLabel(status.Status);
        var percent = status.Total > 0 ? $" · {Math.Min(100, (int)Math.Round(status.Downloaded * 100.0 / status.Total))}%" : "";
        var message = string.IsNullOrWhiteSpace(status.Message) ? "" : $" · {status.Message}";
        _updateProgressText.Text = $"更新状态：{label}{percent}{message}";
        _updateProgressText.Foreground = status.Status == "error" ? FluentTheme.Error : FluentTheme.TextSecondary;
        _updateProgressText.Visibility = status.Status == "idle" && string.IsNullOrWhiteSpace(status.Message)
            ? Visibility.Collapsed
            : Visibility.Visible;
    }

    private void RenderUpdateVersions()
    {
        _updateVersionsStack.Children.Clear();
        var versions = (_lastUpdateResult?.Versions ?? []).Take(3).ToList();
        foreach (var version in versions)
        {
            _updateVersionsStack.Children.Add(CreateUpdateVersionRow(version));
        }
    }

    private UIElement CreateUpdateVersionRow(VersionEntryDto version)
    {
        var row = new Border
        {
            Padding = new Thickness(12),
            CornerRadius = FluentTheme.CardCornerRadius,
            Background = FluentTheme.LayerAlt,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(1),
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };

        var stack = new StackPanel { Spacing = 8 };
        stack.Children.Add(new TextBlock
        {
            Text = DisplayVersionOrVersion(version),
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
            TextWrapping = TextWrapping.WrapWholeWords,
        });
        var typeText = version.RequiresFullUpdate ? "全量更新" : "应用包更新";
        var sizeText = version.RequiresFullUpdate ? "" : $" · {FormatSize(version.Size)}";
        var meta = new TextBlock
        {
            Text = $"{typeText}{sizeText}{FormatReason(version)}",
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        stack.Children.Add(meta);

        var actions = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 8,
        };
        var changelogButton = FluentTheme.ApplyButton(new Button { Content = "更新日志" });
        AutomationProperties.SetAutomationId(changelogButton, $"SettingsUpdateChangelog_{SanitizeAutomationId(version.Version)}");
        changelogButton.Click += (_, _) => _ = ShowChangelogAsync(version);
        actions.Children.Add(changelogButton);

        if (CanRollbackTo(version))
        {
            var rollbackButton = FluentTheme.ApplyButton(new Button { Content = "回滚此版本" });
            AutomationProperties.SetAutomationId(rollbackButton, $"SettingsRollbackUpdate_{SanitizeAutomationId(version.Version)}");
            rollbackButton.Click += (_, _) => _ = RollbackUpdateAsync(version);
            actions.Children.Add(rollbackButton);
        }
        else if (!IsCurrentVersion(version) && version.RequiresFullUpdate)
        {
            var downloadButton = FluentTheme.ApplyButton(new Button { Content = "下载全量更新" }, FluentButtonStyle.Accent);
            AutomationProperties.SetAutomationId(downloadButton, $"SettingsDownloadFullUpdate_{SanitizeAutomationId(version.Version)}");
            downloadButton.Click += (_, _) => OpenUrl(version.FullUpdateUrl);
            actions.Children.Add(downloadButton);
        }
        else if (!IsCurrentVersion(version))
        {
            var updateButton = FluentTheme.ApplyButton(new Button { Content = IsOlderVersion(version) ? "回滚此版本" : "下载并更新" }, FluentButtonStyle.Accent);
            AutomationProperties.SetAutomationId(updateButton, $"SettingsPerformUpdate_{SanitizeAutomationId(version.Version)}");
            updateButton.IsEnabled = !IsUpdateBusy(_lastUpdateStatus);
            updateButton.Click += (_, _) => _ = PerformUpdateAsync(version);
            actions.Children.Add(updateButton);
        }

        actions.SizeChanged += (_, args) => ApplyActionStackLayout(args.NewSize.Width, actions);
        stack.Children.Add(actions);
        row.Child = stack;
        return row;
    }

    private async System.Threading.Tasks.Task PerformUpdateAsync(VersionEntryDto version)
    {
        var isOlderVersion = IsOlderVersion(version);
        try
        {
            if (!IsLocalMediaTreeActive)
            {
                ShowUpdateStatus(LocalMediaTreeOnlyMessage, true);
                return;
            }

            ShowUpdateStatus(isOlderVersion ? "正在发起版本回滚..." : "正在发起应用包更新...", false);
            _lastUpdateStatus = new UpdateStatusDto
            {
                Status = "downloading",
                Version = version.Version,
                Message = isOlderVersion ? "正在发起版本回滚..." : "正在发起应用包更新...",
                UpdateType = "app-package",
            };
            RenderUpdateStatus(_lastUpdateStatus);
            RenderUpdateVersions();
            _updateStatusTimer.Start();
            var result = await AppServices.Media.Updates.PerformUpdateAsync(version.Version, "app-package");
            ShowUpdateStatus(string.IsNullOrWhiteSpace(result.Message) ? (isOlderVersion ? "回滚已触发。" : "更新已触发。") : result.Message, false);
            await RestartBackendAfterAppPackageUpdateAsync(
                isOlderVersion ? "已切换版本，正在重启本机服务..." : "应用包已安装，正在重启本机服务...",
                isOlderVersion ? "版本切换完成。" : "应用包更新完成。");
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to perform native Windows app update.");
            ShowUpdateStatus($"{(isOlderVersion ? "回滚" : "更新")}失败：{ex.Message}", true);
        }
        finally
        {
            RenderUpdateVersions();
        }
    }

    private async System.Threading.Tasks.Task RollbackUpdateAsync(VersionEntryDto version)
    {
        try
        {
            if (!IsLocalMediaTreeActive)
            {
                ShowUpdateStatus(LocalMediaTreeOnlyMessage, true);
                return;
            }

            ShowUpdateStatus("正在触发回滚...", false);
            _updateStatusTimer.Start();
            var result = await AppServices.Media.Updates.RollbackAsync();
            ShowUpdateStatus(string.IsNullOrWhiteSpace(result.Message) ? "已触发回滚。" : result.Message, false);
            await RestartBackendAfterAppPackageUpdateAsync("已切换版本，正在重启本机服务...", "版本切换完成。");
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to rollback native Windows app update.");
            ShowUpdateStatus($"回滚失败：{ex.Message}", true);
        }
        finally
        {
            RenderUpdateVersions();
        }
    }

    private async System.Threading.Tasks.Task RestartBackendAfterAppPackageUpdateAsync(string restartingMessage, string completedMessage)
    {
        if (!IsLocalMediaTreeActive)
        {
            ShowUpdateStatus(LocalMediaTreeOnlyMessage, true);
            return;
        }

        _updateStatusTimer.Stop();
        _lastUpdateStatus = new UpdateStatusDto
        {
            Status = "restarting",
            Message = restartingMessage,
            UpdateType = "app-package",
        };
        RenderUpdateStatus(_lastUpdateStatus);
        ShowUpdateStatus(restartingMessage, false);

        await System.Threading.Tasks.Task.Delay(TimeSpan.FromSeconds(1.5));
        var backendUri = await AppServices.Backend.RestartAsync();
        if (IsLocalMediaTreeActive)
        {
            AppServices.Media.Api.SetBackendUri(backendUri);
        }
        await LoadVersionAsync();
        await LoadUpdateStatusAsync();
        ShowUpdateStatus(completedMessage, false);
    }

    private async System.Threading.Tasks.Task ShowChangelogAsync(VersionEntryDto version)
    {
        try
        {
            var changelog = await AppServices.Media.Updates.GetChangelogAsync(version.Version);
            var text = FluentTheme.ApplyTextInput(new TextBox
            {
                Text = string.IsNullOrWhiteSpace(changelog.Body) ? "暂无更新日志" : changelog.Body,
                AcceptsReturn = true,
                IsReadOnly = true,
                TextWrapping = TextWrapping.Wrap,
                MinWidth = 520,
                MaxHeight = 480,
            });
            var dialog = FluentTheme.ApplyContentDialog(new ContentDialog
            {
                Title = $"更新日志 - {DisplayVersionOrVersion(version)}",
                Content = new ScrollViewer { Content = text },
                CloseButtonText = "关闭",
                XamlRoot = XamlRoot,
            });
            await dialog.ShowAsync();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load native update changelog.");
            ShowUpdateStatus($"读取更新日志失败：{ex.Message}", true);
        }
    }

    private static bool IsUpdateBusy(UpdateStatusDto? status)
        => status?.Status is "downloading" or "verifying" or "installing" or "restarting";

    private bool IsCurrentVersion(VersionEntryDto version)
        => CompareVersions(version.Version, _lastUpdateResult?.EffectiveVersion ?? _lastUpdateResult?.CurrentVersion) == 0;

    private bool IsOlderVersion(VersionEntryDto version)
        => CompareVersions(version.Version, _lastUpdateResult?.EffectiveVersion ?? _lastUpdateResult?.CurrentVersion) < 0;

    private bool CanRollbackTo(VersionEntryDto version)
        => _lastUpdateStatus?.CanRollback == true
            && !string.IsNullOrWhiteSpace(_lastUpdateStatus.RollbackVersion)
            && string.Equals(NormalizeVersion(_lastUpdateStatus.RollbackVersion), NormalizeVersion(version.Version), StringComparison.OrdinalIgnoreCase)
            && !IsCurrentVersion(version);

    private static string StatusLabel(string status)
        => status switch
        {
            "downloading" => "下载中",
            "verifying" => "校验中",
            "installing" => "安装中",
            "restarting" => "重启中",
            "success" => "完成",
            "error" => "失败",
            _ => "空闲",
        };

    private static string FormatVersionLine(string version, string currentSource, string baseVersion, string statusNote = "")
    {
        var source = currentSource == "app-package" ? "应用包" : "安装包内置";
        var note = string.IsNullOrWhiteSpace(statusNote) ? "" : $"    {statusNote}";
        return $"当前版本：{version}    运行来源：Windows · {source}    安装包内置版本：{baseVersion}{note}";
    }

    private static string NormalizeVersion(string? version)
        => (version ?? "").Trim().TrimStart('v', 'V');

    private static int CompareVersions(string? left, string? right)
    {
        var leftParts = NormalizeVersion(left).Split(['.', '-'], StringSplitOptions.RemoveEmptyEntries);
        var rightParts = NormalizeVersion(right).Split(['.', '-'], StringSplitOptions.RemoveEmptyEntries);
        var length = Math.Max(leftParts.Length, rightParts.Length);
        for (var i = 0; i < length; i++)
        {
            var leftPart = i < leftParts.Length && int.TryParse(leftParts[i], out var leftNumber) ? leftNumber : 0;
            var rightPart = i < rightParts.Length && int.TryParse(rightParts[i], out var rightNumber) ? rightNumber : 0;
            if (leftPart != rightPart)
            {
                return leftPart > rightPart ? 1 : -1;
            }
        }

        return 0;
    }

    private static string FormatSize(long size)
    {
        if (size <= 0)
        {
            return "大小未知";
        }

        return size < 1024 * 1024
            ? $"{size / 1024.0:F1} KB"
            : $"{size / 1024.0 / 1024.0:F1} MB";
    }

    private static string DisplayVersionOrVersion(VersionEntryDto version)
        => string.IsNullOrWhiteSpace(version.DisplayVersion) ? version.Version : version.DisplayVersion;

    private static string FormatReason(VersionEntryDto version)
    {
        var reason = version.RequiresFullUpdate ? version.FullUpdateReason : version.Reason;
        return string.IsNullOrWhiteSpace(reason) ? "" : $" · {reason}";
    }

    private static string SanitizeAutomationId(string value)
        => string.Join("_", (value ?? "").Where(char.IsLetterOrDigit));

    private static void OpenUrl(string url)
    {
        if (string.IsNullOrWhiteSpace(url))
        {
            return;
        }

        Process.Start(new ProcessStartInfo
        {
            FileName = url,
            UseShellExecute = true,
        });
    }

    private void OnAddLibraryClicked(object sender, RoutedEventArgs args)
    {
        if (sender is not Button button)
        {
            return;
        }

        var flyout = FluentTheme.ApplyMenuFlyout(new MenuFlyout());
        foreach (var option in AddLibrarySourceOptions)
        {
            var item = new MenuFlyoutItem
            {
                Text = option,
            };
            item.Click += (_, _) => _ = HandleAddLibrarySourceAsync(option);
            flyout.Items.Add(item);
        }

        flyout.ShowAt(button);
    }

    private async System.Threading.Tasks.Task HandleAddLibrarySourceAsync(string option)
    {
        switch (option)
        {
            case "本地目录":
                await AddLocalLibraryFromSettingsAsync();
                break;
            case "MediaTree 远程":
                await ShowExternalMediaSourceDialogAsync(MediaSourceKind.RemoteMediaTree);
                break;
            case "Jellyfin":
                await ShowExternalMediaSourceDialogAsync(MediaSourceKind.Jellyfin);
                break;
            case "Emby":
                await ShowExternalMediaSourceDialogAsync(MediaSourceKind.Emby);
                break;
        }
    }

    private async System.Threading.Tasks.Task AddLocalLibraryFromSettingsAsync()
    {
        try
        {
            var picker = new FolderPicker
            {
                SuggestedStartLocation = PickerLocationId.VideosLibrary,
            };
            picker.FileTypeFilter.Add("*");
            if (AppServices.MainWindow is not null)
            {
                InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(AppServices.MainWindow));
            }

            var folder = await picker.PickSingleFolderAsync();
            if (folder is null)
            {
                _libraryStatusText.Foreground = FluentTheme.TextSecondary;
                _libraryStatusText.Text = "已取消添加。";
                return;
            }

            _libraryStatusText.Foreground = FluentTheme.TextSecondary;
            _libraryStatusText.Text = "正在添加本机目录...";
            var localSource = FindMediaSource(MediaSourceProfileStore.LocalSourceId);
            using var lease = await OpenMediaServicesAsync(localSource);
            var added = await lease.Services.Library.AddLibraryRootAsync(folder.Path);
            _expandedMediaSources.Add(localSource.Id);
            _libraryStatusText.Foreground = FluentTheme.Accent;
            _libraryStatusText.Text = added ? "本机目录已添加。可在列表中设置刮削器并重新扫描。" : "该本机目录已存在。";
            await LoadMediaSourceLibrariesAsync(localSource);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to add native local library from settings.");
            _libraryStatusText.Foreground = FluentTheme.Error;
            _libraryStatusText.Text = $"添加本机目录失败：{ex.Message}";
        }
    }

    private async void OnSwitchToLocalMediaTreeClicked(object sender, RoutedEventArgs args)
    {
        if (sender is not Button button)
        {
            return;
        }

        try
        {
            button.IsEnabled = false;
            _libraryStatusText.Foreground = FluentTheme.TextSecondary;
            _libraryStatusText.Text = "正在切换到本机 MediaTree...";
            await SwitchToSavedMediaSourceAsync(new MediaSourceListItem(
                MediaSourceProfileStore.LocalSourceId,
                MediaSourceKind.LocalMediaTree,
                "本机 MediaTree",
                "",
                RequiresBundledBackend: true,
                IsActive: false));
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to switch back to local MediaTree from settings.");
            _libraryStatusText.Foreground = FluentTheme.Error;
            _libraryStatusText.Text = $"切换本机 MediaTree 失败：{ex.Message}";
        }
        finally
        {
            button.IsEnabled = true;
        }
    }

    private async void OnSwitchMediaSourceClicked(object sender, RoutedEventArgs args)
    {
        if (sender is not Button button || button.Tag is not MediaSourceRowContext context)
        {
            return;
        }

        try
        {
            button.IsEnabled = false;
            ShowRowStatus(context.StatusText, $"正在切换到：{context.Source.DisplayName}...", false);
            await SwitchToSavedMediaSourceAsync(context.Source);
            ShowRowStatus(context.StatusText, $"已切换到：{context.Source.DisplayName}。", false);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to switch saved media source from settings.");
            ShowRowStatus(context.StatusText, $"切换失败：{ex.Message}", true);
        }
        finally
        {
            button.IsEnabled = true;
        }
    }

    private async System.Threading.Tasks.Task SwitchToSavedMediaSourceAsync(MediaSourceListItem source)
    {
        if (source.Kind == MediaSourceKind.LocalMediaTree)
        {
            AppServices.SwitchToLocalMediaTree();
            MediaSourceProfileStore.SetActiveSource(MediaSourceProfileStore.LocalSourceId);
            var session = await AppServices.Media.Auth.EnsureLocalSessionAsync();
            if (session.State == AuthSessionState.NeedsUserLogin)
            {
                AppServices.MainWindow?.NavigateToLogin();
                return;
            }
        }
        else
        {
            var state = MediaSourceProfileStore.Load();
            var record = state.Sources.FirstOrDefault(item => string.Equals(item.Id, source.Id, StringComparison.OrdinalIgnoreCase))
                ?? throw new InvalidOperationException("媒体源配置不存在。");
            var provider = await MediaSourceActivator.CreateProviderAsync(record);
            AppServices.SwitchProvider(provider);
            MediaSourceProfileStore.SetActiveSource(record.Id);
        }

        _isSwitchingMediaSource = true;
        StopBackgroundTimers();
        _expandedMediaSources.Add(source.Id);
        LoadMediaSourceGroups();
        await LoadTmdbConfigAsync();
        await LoadVersionAsync();
        await LoadLibrarySettingsAsync();
        await LoadUpdateStatusAsync();
        _libraryStatusText.Foreground = FluentTheme.Accent;
        _libraryStatusText.Text = $"已切换到：{source.DisplayName}。";
        ShellPage.Current?.ReloadActiveMediaSource();
    }

    private async System.Threading.Tasks.Task ShowExternalMediaSourceDialogAsync(MediaSourceKind kind)
    {
        var sourceName = DisplaySourceKind(kind);
        var nameBox = TextInput("名称", $"SettingsSourceName_{kind}", sourceName);
        var endpointBox = TextInput("地址", $"SettingsSourceEndpoint_{kind}");
        endpointBox.PlaceholderText = kind == MediaSourceKind.RemoteMediaTree
            ? "http://192.168.1.10:27581"
            : "http://192.168.1.10:8096";
        var usernameBox = TextInput("用户名", $"SettingsSourceUsername_{kind}");
        var secretBox = PasswordInput("密码 / token", $"SettingsSourceSecret_{kind}");
        secretBox.PlaceholderText = "保存在当前 Windows 用户凭据中";
        var statusText = StatusText($"SettingsSourceStatus_{kind}", visible: true);
        statusText.Text = "凭据会使用 Windows DPAPI 保存。设为当前后会立即切换到该媒体源。";

        var testButton = FluentTheme.ApplyButton(new Button
        {
            Content = "测试连接",
            HorizontalAlignment = HorizontalAlignment.Left,
        });
        AutomationProperties.SetAutomationId(testButton, $"SettingsTestMediaSource_{kind}");
        testButton.Click += async (_, _) =>
        {
            try
            {
                testButton.IsEnabled = false;
                ShowSourceDialogStatus(statusText, "正在测试连接...", false);
                var endpoint = NormalizeEndpoint(endpointBox.Text);
                var credentials = ReadExternalSourceCredentials(usernameBox, secretBox);
                using var tester = new MediaSourceConnectionTester();
                var result = await tester.TestAsync(kind, endpoint, credentials);
                ShowSourceDialogStatus(statusText, result.Message, !result.Succeeded);
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, "Failed to test external media source from settings.");
                ShowSourceDialogStatus(statusText, $"测试失败：{ex.Message}", true);
            }
            finally
            {
                testButton.IsEnabled = true;
            }
        };

        WindowModalDialog? dialog = null;
        var activateButton = FluentTheme.ApplyButton(new Button
        {
            Content = "设为当前",
            HorizontalAlignment = HorizontalAlignment.Left,
        });
        AutomationProperties.SetAutomationId(activateButton, $"SettingsActivateMediaSource_{kind}");
        activateButton.Click += async (_, _) =>
        {
            try
            {
                activateButton.IsEnabled = false;
                ShowSourceDialogStatus(statusText, "正在保存并切换媒体源...", false);
                var saved = SaveExternalMediaSource(kind, nameBox, endpointBox, usernameBox, secretBox, activate: false);
                await SwitchToSavedMediaSourceAsync(new MediaSourceListItem(
                    saved.Id,
                    saved.Kind,
                    saved.DisplayName,
                    saved.Endpoint,
                    saved.RequiresBundledBackend,
                    IsActive: false));
                dialog?.Hide();
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, "Failed to activate external media source from settings.");
                ShowSourceDialogStatus(statusText, $"设为当前失败：{ex.Message}", true);
            }
            finally
            {
                activateButton.IsEnabled = true;
            }
        };

        var actions = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 10,
        };
        actions.Children.Add(testButton);
        actions.Children.Add(activateButton);
        actions.SizeChanged += (_, args) => ApplyActionStackLayout(args.NewSize.Width, actions);

        var content = new StackPanel { Spacing = 12 };
        content.Children.Add(nameBox);
        content.Children.Add(endpointBox);
        content.Children.Add(usernameBox);
        content.Children.Add(secretBox);
        content.Children.Add(actions);
        content.Children.Add(statusText);

        dialog = new WindowModalDialog($"添加{sourceName}", content, "保存", "取消")
        {
            MaxWidth = 560,
            ContentMaxWidth = 500,
        };
        dialog.PrimaryActionAsync = () =>
        {
            try
            {
                var saved = SaveExternalMediaSource(kind, nameBox, endpointBox, usernameBox, secretBox, activate: false);
                LoadMediaSourceGroups();
                _libraryStatusText.Foreground = FluentTheme.Accent;
                _libraryStatusText.Text = $"已保存 {saved.DisplayName}。";
                return System.Threading.Tasks.Task.FromResult(true);
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, "Failed to save external media source from settings.");
                ShowSourceDialogStatus(statusText, $"保存失败：{ex.Message}", true);
                return System.Threading.Tasks.Task.FromResult(false);
            }
        };

        await dialog.ShowAsync();
    }

    private static MediaSourceProfileRecord SaveExternalMediaSource(
        MediaSourceKind kind,
        TextBox nameBox,
        TextBox endpointBox,
        TextBox usernameBox,
        PasswordBox secretBox,
        bool activate)
    {
        var endpoint = NormalizeEndpoint(endpointBox.Text);
        var credentials = ReadExternalSourceCredentials(usernameBox, secretBox);
        var saved = MediaSourceProfileStore.UpsertExternalSource(kind, nameBox.Text, endpoint);
        MediaSourceCredentialStore.Save(saved.Id, credentials);
        if (activate)
        {
            MediaSourceProfileStore.SetActiveSource(saved.Id);
        }

        return saved;
    }

    private static MediaSourceCredentials ReadExternalSourceCredentials(TextBox usernameBox, PasswordBox secretBox)
    {
        var username = (usernameBox.Text ?? "").Trim();
        var secret = secretBox.Password ?? "";
        if (string.IsNullOrWhiteSpace(username) || string.IsNullOrEmpty(secret))
        {
            throw new ArgumentException("请填写用户名和密码 / token。");
        }

        return new MediaSourceCredentials(username, secret);
    }

    private static void ShowSourceDialogStatus(TextBlock statusText, string message, bool isError)
    {
        statusText.Text = message;
        statusText.Foreground = isError ? FluentTheme.Error : FluentTheme.TextSecondary;
        statusText.Visibility = Visibility.Visible;
    }

    private static Uri NormalizeEndpoint(string value)
    {
        var endpoint = (value ?? "").Trim();
        if (string.IsNullOrWhiteSpace(endpoint))
        {
            throw new ArgumentException("请填写地址。");
        }

        if (!endpoint.Contains("://", StringComparison.Ordinal))
        {
            endpoint = $"http://{endpoint}";
        }

        if (!Uri.TryCreate(endpoint, UriKind.Absolute, out var uri) || (uri.Scheme != "http" && uri.Scheme != "https"))
        {
            throw new ArgumentException("地址必须是 http 或 https。");
        }

        return uri;
    }

    private static string DisplaySourceKind(MediaSourceKind kind)
        => kind switch
        {
            MediaSourceKind.RemoteMediaTree => "MediaTree 远程",
            MediaSourceKind.Jellyfin => "Jellyfin",
            MediaSourceKind.Emby => "Emby",
            _ => "本地目录",
        };

    private void ShowGlobalStatus(string message, bool isError)
    {
        _globalStatusText.Text = message;
        _globalStatusText.Foreground = isError ? FluentTheme.Error : FluentTheme.Accent;
        _globalStatusText.Visibility = Visibility.Visible;
    }

    private void ShowTmdbStatus(string message, bool isError)
    {
        _tmdbTokenStatusText.Text = message;
        _tmdbTokenStatusText.Foreground = isError ? FluentTheme.Error : FluentTheme.TextSecondary;
        _tmdbTokenStatusText.Visibility = Visibility.Visible;
    }

    private void ShowBackupStatus(string message, bool isError)
    {
        _backupStatusText.Text = message;
        _backupStatusText.Foreground = isError ? FluentTheme.Error : FluentTheme.Accent;
        _backupStatusText.Visibility = Visibility.Visible;
    }

    private void ShowUpdateStatus(string message, bool isError)
    {
        _updateStatusText.Text = message;
        _updateStatusText.Foreground = isError ? FluentTheme.Error : FluentTheme.TextSecondary;
        _updateStatusText.Visibility = Visibility.Visible;
    }

    private static void ShowRowStatus(TextBlock textBlock, string message, bool isError)
    {
        textBlock.Text = message;
        textBlock.Foreground = isError ? FluentTheme.Error : FluentTheme.Accent;
        textBlock.Visibility = Visibility.Visible;
    }

    private async void OnScanStatusTimerTick(object? sender, object args)
    {
        if (_activeScanRoots.Count == 0)
        {
            _scanStatusTimer.Stop();
            return;
        }

        foreach (var scanKey in _activeScanRoots.ToList())
        {
            await RefreshScanRowAsync(scanKey);
        }
    }

    private async System.Threading.Tasks.Task RefreshScanRowAsync(string scanKey)
    {
        if (!_scanRows.TryGetValue(scanKey, out var row))
        {
            _activeScanRoots.Remove(scanKey);
            return;
        }

        _scanPollCounts[scanKey] = _scanPollCounts.TryGetValue(scanKey, out var count) ? count + 1 : 1;
        try
        {
            using var lease = await OpenMediaServicesAsync(row.SourceId);
            var status = await lease.Services.Library.GetScanStatusAsync(row.MediaRoot);
            var message = FormatScanStatus(status);
            row.StatusText.Text = message;
            row.StatusText.Foreground = status.Status == "done" ? FluentTheme.Accent : FluentTheme.TextSecondary;
            row.StatusText.Visibility = Visibility.Visible;

            var log = await lease.Services.Library.GetScanLogAsync(row.MediaRoot, 20);
            if (log.Lines.Count > 0)
            {
                row.LogText.Text = string.Join(Environment.NewLine, log.Lines);
                row.LogText.Visibility = Visibility.Visible;
            }

            if (status.Status is "done" or "disabled" or "not_found" || _scanPollCounts[scanKey] > 120)
            {
                _activeScanRoots.Remove(scanKey);
                _scanPollCounts.Remove(scanKey);
                row.ScanButton.IsEnabled = true;
                if (_activeScanRoots.Count == 0)
                {
                    _scanStatusTimer.Stop();
                }
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to refresh native scan status.");
            ShowRowStatus(row.StatusText, $"读取扫描进度失败：{ex.Message}", true);
            _activeScanRoots.Remove(scanKey);
            _scanPollCounts.Remove(scanKey);
            row.ScanButton.IsEnabled = true;
        }
    }

    private static string FormatScanStatus(ScanStatusDto status)
    {
        return status.Status switch
        {
            "scanning" => status.Total > 0 ? $"正在刮削：{status.Done}/{status.Total}" : "正在刮削...",
            "clearing" => "清除已有数据...",
            "done" => "刮削完成。",
            "disabled" => "媒体库已禁用。",
            "not_found" => "等待扫描进度...",
            _ => string.IsNullOrWhiteSpace(status.Status) ? "正在扫描..." : status.Status,
        };
    }

    private static Border SectionCard(UIElement child, string automationId, Thickness? padding = null)
    {
        var card = FluentTheme.Card(child, padding ?? new Thickness(22));
        card.HorizontalAlignment = HorizontalAlignment.Stretch;
        AutomationProperties.SetAutomationId(card, automationId);
        return card;
    }

    private void ApplySettingsViewportLayout(double viewportWidth, StackPanel root, Grid settingsGrid)
    {
        root.Width = Math.Max(0, viewportWidth);
        root.Padding = FluentTheme.SpaciousPagePadding(viewportWidth);
        var contentWidth = Math.Max(0, viewportWidth - root.Padding.Left - root.Padding.Right);
        var columnCount = CalculateSettingsColumnCount(contentWidth, _settingsCards.Count);
        var columnWidth = CalculateSettingsColumnWidth(contentWidth, columnCount);
        _settingsColumnWidth = columnWidth;
        var totalSpacing = (columnCount - 1) * SettingsColumnSpacing;
        var gridWidth = columnCount * columnWidth + totalSpacing;
        settingsGrid.Width = gridWidth;

        foreach (var card in root.Children.OfType<FrameworkElement>())
        {
            if (card == settingsGrid)
            {
                continue;
            }

            card.Width = contentWidth;
        }

        RenderSettingsCardColumns(settingsGrid, columnCount, columnWidth);
        ApplyLoadedLibraryRowWidths(columnWidth);
    }

    private void RenderSettingsCardColumns(Grid settingsGrid, int columnCount, double columnWidth)
    {
        foreach (var oldColumn in settingsGrid.Children.OfType<StackPanel>())
        {
            oldColumn.Children.Clear();
        }

        settingsGrid.Children.Clear();
        settingsGrid.ColumnDefinitions.Clear();
        settingsGrid.RowDefinitions.Clear();
        var columns = new List<StackPanel>();
        for (var column = 0; column < columnCount; column++)
        {
            settingsGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(columnWidth) });
            var columnStack = new StackPanel { Spacing = 20, Width = columnWidth, HorizontalAlignment = HorizontalAlignment.Stretch };
            Grid.SetColumn(columnStack, column);
            settingsGrid.Children.Add(columnStack);
            columns.Add(columnStack);
        }

        var rowsNeeded = (int)Math.Ceiling(_settingsCards.Count / (double)columnCount);
        for (var index = 0; index < _settingsCards.Count; index++)
        {
            var child = _settingsCards[index];
            child.Width = columnWidth;
            child.Height = double.NaN;
            child.VerticalAlignment = VerticalAlignment.Top;
            var column = Math.Min(columns.Count - 1, index / rowsNeeded);
            var columnStack = columns[column];
            columnStack.Children.Add(child);
        }
    }

    private static int CalculateSettingsColumnCount(double contentWidth, int itemCount)
    {
        var maxColumns = Math.Max(1, itemCount);
        if (contentWidth <= 0)
        {
            return 1;
        }

        var columnWithSpacing = SettingsColumnMinWidth + SettingsColumnSpacing;
        return Math.Min(maxColumns, Math.Max(1, (int)Math.Floor((contentWidth + SettingsColumnSpacing) / columnWithSpacing)));
    }

    private static double CalculateSettingsColumnWidth(double contentWidth, int columnCount)
    {
        if (contentWidth <= 0 || columnCount <= 0)
        {
            return 0;
        }

        var totalSpacing = (columnCount - 1) * SettingsColumnSpacing;
        var availableColumnWidth = Math.Max(0, (contentWidth - totalSpacing) / columnCount);
        return Math.Min(SettingsColumnPreferredWidth, availableColumnWidth);
    }

    private void ApplyLoadedLibraryRowWidths(double columnWidth)
    {
        if (columnWidth <= 0)
        {
            return;
        }

        var rowWidth = CalculateLibraryRowWidth(columnWidth);
        foreach (var row in _librarySettingRows)
        {
            row.Width = rowWidth;
        }
    }

    private static double CalculateLibraryRowWidth(double columnWidth)
        => Math.Max(0, columnWidth - 68);

    private static TextBlock WrapText(string text)
    {
        return new TextBlock
        {
            Text = text,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
    }

    private static void ApplyHeaderActionLayout(double width, Grid header, FrameworkElement action)
    {
        var compact = width < 560;
        header.ColumnDefinitions[1].Width = compact ? new GridLength(0) : GridLength.Auto;
        header.RowDefinitions[1].Height = compact ? GridLength.Auto : new GridLength(0);
        Grid.SetColumn(action, compact ? 0 : 1);
        Grid.SetRow(action, compact ? 1 : 0);
        action.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Left;
    }

    private static void ApplyActionStackLayout(double width, StackPanel actions)
    {
        var compact = width < 640;
        actions.Orientation = compact ? Orientation.Vertical : Orientation.Horizontal;
        foreach (var child in actions.Children.OfType<FrameworkElement>())
        {
            child.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Left;
        }
    }

    private static void ApplyMediaSourceRowLayout(double width, Grid grid, FrameworkElement info, StackPanel actions)
    {
        var compact = width < 520;
        grid.RowDefinitions[1].Height = compact ? GridLength.Auto : new GridLength(0);
        grid.ColumnDefinitions[1].Width = compact ? new GridLength(0) : GridLength.Auto;
        Grid.SetColumn(actions, compact ? 0 : 1);
        Grid.SetRow(actions, compact ? 1 : 0);
        info.MinWidth = compact ? 0 : 220;
        actions.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Left;
        foreach (var child in actions.Children.OfType<FrameworkElement>())
        {
            child.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Left;
        }
    }

    private static void ApplyLibrarySettingsRowLayout(
        double width,
        Grid grid,
        FrameworkElement info,
        StackPanel scraperStack,
        Grid inputGrid,
        StackPanel actions)
    {
        var compact = width < 720;
        grid.RowSpacing = compact ? 12 : 0;
        grid.ColumnDefinitions[1].Width = compact ? new GridLength(0) : GridLength.Auto;
        grid.ColumnDefinitions[2].Width = compact ? new GridLength(0) : GridLength.Auto;
        for (var i = 1; i < grid.RowDefinitions.Count; i++)
        {
            grid.RowDefinitions[i].Height = compact ? GridLength.Auto : new GridLength(0);
        }

        Grid.SetColumn(info, 0);
        Grid.SetRow(info, 0);
        Grid.SetColumn(scraperStack, compact ? 0 : 1);
        Grid.SetRow(scraperStack, compact ? 1 : 0);
        Grid.SetColumn(actions, compact ? 0 : 2);
        Grid.SetRow(actions, compact ? 2 : 0);

        info.MinWidth = compact ? 0 : 220;
        scraperStack.Width = compact ? double.NaN : 300;
        inputGrid.ColumnDefinitions[1].Width = new GridLength(1, GridUnitType.Star);
        scraperStack.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Left;
        actions.Orientation = compact && width >= 520 ? Orientation.Horizontal : Orientation.Vertical;
        foreach (var button in actions.Children.OfType<FrameworkElement>())
        {
            button.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Left;
        }
    }

    private static TextBlock SectionTitle(string text, string automationId = "")
    {
        var title = new TextBlock
        {
            Text = text,
            FontSize = 20,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
        };
        if (!string.IsNullOrWhiteSpace(automationId))
        {
            AutomationProperties.SetAutomationId(title, automationId);
        }

        return title;
    }

    private static TextBlock StatusText(string automationId, bool visible = false)
    {
        var text = new TextBlock
        {
            Text = "",
            Visibility = visible ? Visibility.Visible : Visibility.Collapsed,
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(text, automationId);
        return text;
    }

    private static TextBox TextInput(string header, string automationId, string value = "")
    {
        var box = FluentTheme.ApplyTextInput(new TextBox
        {
            Header = header,
            Text = value,
            Width = double.NaN,
            MaxWidth = double.PositiveInfinity,
            MinWidth = 0,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        });
        AutomationProperties.SetAutomationId(box, automationId);
        return box;
    }

    private static PasswordBox PasswordInput(string header, string automationId)
    {
        var box = FluentTheme.ApplyPasswordInput(new PasswordBox
        {
            Header = header,
            Width = double.NaN,
            MaxWidth = double.PositiveInfinity,
            MinWidth = 0,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        });
        AutomationProperties.SetAutomationId(box, automationId);
        return box;
    }

    private static InputScope NumberInputScope()
    {
        var scope = new InputScope();
        scope.Names.Add(new InputScopeName(InputScopeNameValue.Number));
        return scope;
    }

    private static Grid TwoColumnRow(FrameworkElement first, FrameworkElement second)
    {
        var row = new Grid { ColumnSpacing = 12 };
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        row.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        row.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });
        row.Children.Add(first);
        Grid.SetColumn(second, 1);
        row.Children.Add(second);
        row.SizeChanged += (_, args) =>
        {
            var compact = args.NewSize.Width < 560;
            row.RowSpacing = compact ? 12 : 0;
            row.ColumnDefinitions[1].Width = compact ? new GridLength(0) : new GridLength(1, GridUnitType.Star);
            row.RowDefinitions[1].Height = compact ? GridLength.Auto : new GridLength(0);
            Grid.SetColumn(second, compact ? 0 : 1);
            Grid.SetRow(second, compact ? 1 : 0);
        };
        return row;
    }

    private static Grid ThreeColumnRow(FrameworkElement first, FrameworkElement second, FrameworkElement third)
    {
        var row = new Grid { ColumnSpacing = 12 };
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        row.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        row.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });
        row.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });
        row.Children.Add(first);
        Grid.SetColumn(second, 1);
        row.Children.Add(second);
        Grid.SetColumn(third, 2);
        row.Children.Add(third);
        row.SizeChanged += (_, args) =>
        {
            var compact = args.NewSize.Width < 720;
            row.RowSpacing = compact ? 12 : 0;
            row.ColumnDefinitions[1].Width = compact ? new GridLength(0) : new GridLength(1, GridUnitType.Star);
            row.ColumnDefinitions[2].Width = compact ? new GridLength(0) : new GridLength(1, GridUnitType.Star);
            row.RowDefinitions[1].Height = compact ? GridLength.Auto : new GridLength(0);
            row.RowDefinitions[2].Height = compact ? GridLength.Auto : new GridLength(0);
            Grid.SetColumn(second, compact ? 0 : 1);
            Grid.SetRow(second, compact ? 1 : 0);
            Grid.SetColumn(third, compact ? 0 : 2);
            Grid.SetRow(third, compact ? 2 : 0);
        };
        return row;
    }

    private static Grid ScraperDescriptionGrid()
    {
        var grid = new Grid
        {
            ColumnSpacing = 10,
            RowSpacing = 10,
            Width = double.NaN,
            MaxWidth = double.PositiveInfinity,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

        var visibleOptions = ScraperOptions.Where(option => option.Value != "none").ToList();
        for (var i = 0; i < visibleOptions.Count; i++)
        {
            var option = visibleOptions[i];
            var stack = new StackPanel { Spacing = 4 };
            stack.Children.Add(new TextBlock
            {
                Text = option.Label,
                FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
                Foreground = FluentTheme.TextPrimary,
            });
            stack.Children.Add(new TextBlock
            {
                Text = option.Description,
                Foreground = FluentTheme.TextSecondary,
                TextWrapping = TextWrapping.WrapWholeWords,
            });
            var card = FluentTheme.Card(stack, new Thickness(12));
            card.Width = double.NaN;
            card.MaxWidth = double.PositiveInfinity;
            card.HorizontalAlignment = HorizontalAlignment.Stretch;
            Grid.SetColumn(card, i % 3);
            Grid.SetRow(card, i / 3);
            if (i % 3 == 0)
            {
                grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            }

            grid.Children.Add(card);
        }

        grid.SizeChanged += (_, args) => ApplyScraperDescriptionLayout(grid, args.NewSize.Width);
        return grid;
    }

    private static void ApplyScraperDescriptionLayout(Grid grid, double width)
    {
        var compact = width < 640;
        var columns = compact ? 1 : 3;
        grid.ColumnDefinitions[1].Width = compact ? new GridLength(0) : new GridLength(1, GridUnitType.Star);
        grid.ColumnDefinitions[2].Width = compact ? new GridLength(0) : new GridLength(1, GridUnitType.Star);
        var rowsNeeded = (int)Math.Ceiling(grid.Children.Count / (double)columns);
        while (grid.RowDefinitions.Count < rowsNeeded)
        {
            grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        }

        for (var i = 0; i < grid.Children.Count; i++)
        {
            if (grid.Children[i] is FrameworkElement child)
            {
                child.Width = double.NaN;
                child.MaxWidth = double.PositiveInfinity;
                child.HorizontalAlignment = HorizontalAlignment.Stretch;
                Grid.SetColumn(child, i % columns);
                Grid.SetRow(child, i / columns);
            }
        }
    }

    private static string NormalizeScraper(string? scraper)
    {
        var value = string.IsNullOrWhiteSpace(scraper) ? "auto" : scraper.Trim().ToLowerInvariant();
        return value == "tmdb" ? "tmdb_movie" : ScraperOptions.Any(option => option.Value == value) ? value : "auto";
    }

    private static void SelectScraper(ComboBox scraperBox, string value)
    {
        for (var i = 0; i < scraperBox.Items.Count; i++)
        {
            if (scraperBox.Items[i] is ComboBoxItem item && item.Tag as string == value)
            {
                scraperBox.SelectedIndex = i;
                return;
            }
        }

        scraperBox.SelectedIndex = ScraperOptions.ToList().FindIndex(option => option.Value == "auto");
    }

    private static string GetSelectedScraper(ComboBox scraperBox)
    {
        if (scraperBox.SelectedItem is ComboBoxItem item && item.Tag is string value)
        {
            return NormalizeScraper(value);
        }

        return "auto";
    }

    private static string GetScraperDescription(string value)
    {
        var option = ScraperOptions.FirstOrDefault(item => item.Value == NormalizeScraper(value));
        return option?.Description ?? "自动判断刮削源，但可能效果不好";
    }
}
