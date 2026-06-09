using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using MediaTree.Windows.Models;
using MediaTree.Windows.Services;
using MediaTree.Windows.Styles;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Windows.Storage.Pickers;
using WinRT.Interop;

namespace MediaTree.Windows.Views;

public sealed partial class SettingsPage : Page
{
    private sealed record ScraperOption(string Value, string Label, string Description, bool HasKey);

    private sealed record LibrarySettingsRowContext(string MediaRoot, string TmdbKey, ComboBox ScraperBox, PasswordBox PasswordBox);

    private static readonly IReadOnlyList<ScraperOption> ScraperOptions =
    [
        new("tmdb_movie", "TMDB 电影", "适合电影库；tmdbid 调用 /movie 精确刮削", true),
        new("tmdb_tv", "TMDB 剧集/番剧", "适合剧集、番剧、电视剧库；tmdbid 调用 /tv 精确刮削", true),
        new("bangumi", "Bangumi", "适合番剧、动画、二次元条目，数据可能不全", false),
        new("javdatabase", "Javdatabase", "适合 JAV 番号识别和刮削", false),
        new("auto", "自动", "自动判断刮削源，但可能效果不好", true),
        new("none", "不刮削", "只扫描本地文件，不联网刮削元数据", false),
    ];

    private readonly TextBlock _authStatusText;
    private readonly TextBlock _globalStatusText;
    private readonly CheckBox _hideHomeTitleTextBox;
    private readonly PasswordBox _newPasswordBox;
    private readonly TextBox _newUsernameBox;
    private readonly PasswordBox _oldPasswordBox;
    private readonly TextBox _oldUsernameBox;
    private readonly CheckBox _showSourceNameBox;
    private readonly TextBlock _backupStatusText;
    private readonly TextBox _bangumiCacheHoursBox;
    private readonly TextBox _javdbCacheHoursBox;
    private readonly TextBox _javdbRequestIntervalBox;
    private readonly ListView _librarySettingsList;
    private readonly TextBlock _libraryStatusText;
    private readonly TextBox _tmdbApiKeyBox;
    private readonly TextBox _tmdbCacheHoursBox;
    private readonly PasswordBox _tmdbTokenBox;
    private readonly TextBlock _tmdbTokenStatusText;
    private readonly TextBlock _updateStatusText;
    private readonly TextBlock _versionText;
    private ConfigDto _loadedConfig = new();
    private bool _suppressUiPreferenceSave;

    public SettingsPage()
    {
        (
            _globalStatusText,
            _hideHomeTitleTextBox,
            _showSourceNameBox,
            _oldUsernameBox,
            _oldPasswordBox,
            _newUsernameBox,
            _newPasswordBox,
            _authStatusText,
            _librarySettingsList,
            _libraryStatusText,
            _javdbCacheHoursBox,
            _tmdbCacheHoursBox,
            _bangumiCacheHoursBox,
            _javdbRequestIntervalBox,
            _tmdbApiKeyBox,
            _tmdbTokenBox,
            _tmdbTokenStatusText,
            _backupStatusText,
            _versionText,
            _updateStatusText
        ) = BuildContent();
        Loaded += OnLoaded;
    }

    private (TextBlock globalStatusText, CheckBox hideHomeTitleTextBox, CheckBox showSourceNameBox, TextBox oldUsernameBox, PasswordBox oldPasswordBox, TextBox newUsernameBox, PasswordBox newPasswordBox, TextBlock authStatusText, ListView librarySettingsList, TextBlock libraryStatusText, TextBox javdbCacheHoursBox, TextBox tmdbCacheHoursBox, TextBox bangumiCacheHoursBox, TextBox javdbRequestIntervalBox, TextBox tmdbApiKeyBox, PasswordBox tmdbTokenBox, TextBlock tmdbTokenStatusText, TextBlock backupStatusText, TextBlock versionText, TextBlock updateStatusText) BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "SettingsPage");

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
        root.Children.Add(FluentTheme.Card(headerGrid, new Thickness(18)));

        var globalStatusText = StatusText("SettingsGlobalStatusText");
        root.Children.Add(globalStatusText);

        var columns = new Grid { ColumnSpacing = 20, RowSpacing = 20 };
        columns.HorizontalAlignment = HorizontalAlignment.Stretch;
        columns.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        columns.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        columns.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        columns.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });

        var leftColumn = new StackPanel { Spacing = 20, HorizontalAlignment = HorizontalAlignment.Stretch };
        var rightColumn = new StackPanel { Spacing = 20, HorizontalAlignment = HorizontalAlignment.Stretch };
        Grid.SetColumn(rightColumn, 1);
        columns.Children.Add(leftColumn);
        columns.Children.Add(rightColumn);
        root.Children.Add(columns);

        var uiPrefsStack = new StackPanel { Spacing = 12 };
        uiPrefsStack.Children.Add(SectionTitle("界面偏好", "SettingsUiPrefsCard"));
        var hideHomeTitleTextBox = new CheckBox
        {
            Content = WrapText("无字模式：首页仅展示影片封面图，隐藏卡片上的标题文字和目录数量。"),
        };
        AutomationProperties.SetAutomationId(hideHomeTitleTextBox, "SettingsHideHomeTitleText");
        hideHomeTitleTextBox.Checked += OnUiPreferenceChanged;
        hideHomeTitleTextBox.Unchecked += OnUiPreferenceChanged;
        uiPrefsStack.Children.Add(hideHomeTitleTextBox);
        var showSourceNameBox = new CheckBox
        {
            Content = WrapText("使用源文件名称：首页媒体库卡片显示源文件夹名称。"),
        };
        AutomationProperties.SetAutomationId(showSourceNameBox, "SettingsShowSourceName");
        showSourceNameBox.Checked += OnUiPreferenceChanged;
        showSourceNameBox.Unchecked += OnUiPreferenceChanged;
        uiPrefsStack.Children.Add(showSourceNameBox);
        leftColumn.Children.Add(SectionCard(uiPrefsStack, "SettingsUiPrefsCard"));

        var authStack = new StackPanel { Spacing = 12 };
        authStack.Children.Add(SectionTitle("账号安全", "SettingsAuthCard"));
        var oldUsernameBox = TextInput("当前用户名", "SettingsOldUsername");
        var oldPasswordBox = PasswordInput("当前密码", "SettingsOldPassword");
        var newUsernameBox = TextInput("新用户名", "SettingsNewUsername");
        var newPasswordBox = PasswordInput("新密码", "SettingsNewPassword");
        authStack.Children.Add(TwoColumnRow(oldUsernameBox, oldPasswordBox));
        authStack.Children.Add(TwoColumnRow(newUsernameBox, newPasswordBox));
        var changePasswordButton = FluentTheme.ApplyButton(new Button
        {
            Content = "修改用户名/密码",
            HorizontalAlignment = HorizontalAlignment.Left,
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(changePasswordButton, "SettingsChangePassword");
        changePasswordButton.Click += OnChangePasswordClicked;
        authStack.Children.Add(changePasswordButton);
        var authStatusText = StatusText("SettingsAuthStatusText");
        authStack.Children.Add(authStatusText);
        leftColumn.Children.Add(SectionCard(authStack, "SettingsAuthCard"));

        var libraryStack = new StackPanel { Spacing = 12 };
        var libraryHeader = new Grid { ColumnSpacing = 12, RowSpacing = 10 };
        libraryHeader.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        libraryHeader.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        libraryHeader.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        libraryHeader.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });
        libraryHeader.Children.Add(SectionTitle("媒体库", "SettingsLibraryCard"));
        var addLibraryButton = FluentTheme.ApplyButton(new Button
        {
            Content = "添加本机目录",
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(addLibraryButton, "SettingsAddLibrary");
        addLibraryButton.Click += OnAddLibraryClicked;
        Grid.SetColumn(addLibraryButton, 1);
        libraryHeader.Children.Add(addLibraryButton);
        libraryHeader.SizeChanged += (_, args) => ApplyHeaderActionLayout(args.NewSize.Width, libraryHeader, addLibraryButton);
        libraryStack.Children.Add(libraryHeader);
        libraryStack.Children.Add(FluentTheme.Body("Windows 桌面版可直接选择本机文件夹作为媒体库。", 13));
        var librarySettingsList = new ListView
        {
            SelectionMode = ListViewSelectionMode.None,
            IsItemClickEnabled = false,
            Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent),
            HorizontalAlignment = HorizontalAlignment.Stretch,
            Padding = new Thickness(0),
        };
        AutomationProperties.SetAutomationId(librarySettingsList, "SettingsLibrarySettingsList");
        libraryStack.Children.Add(librarySettingsList);
        var libraryStatusText = StatusText("SettingsLibraryStatusText", visible: true);
        libraryStatusText.Text = "正在加载媒体库设置...";
        libraryStack.Children.Add(libraryStatusText);
        leftColumn.Children.Add(SectionCard(libraryStack, "SettingsLibraryCard"));

        var scraperStack = new StackPanel { Spacing = 12 };
        scraperStack.Children.Add(SectionTitle("刮削器", "SettingsScraperCard"));
        var javdbCacheHoursBox = TextInput("Javdatabase 缓存（小时）", "SettingsJavdbCacheHours", "24");
        var tmdbCacheHoursBox = TextInput("TMDB 缓存（小时）", "SettingsTmdbCacheHours", "168");
        var bangumiCacheHoursBox = TextInput("Bangumi 缓存（小时）", "SettingsBangumiCacheHours", "168");
        scraperStack.Children.Add(ThreeColumnRow(javdbCacheHoursBox, tmdbCacheHoursBox, bangumiCacheHoursBox));
        var javdbRequestIntervalBox = TextInput("请求间隔（秒）", "SettingsJavdbRequestInterval", "3");
        scraperStack.Children.Add(javdbRequestIntervalBox);
        var tmdbApiKeyBox = TextInput("TMDB API Key", "SettingsTmdbApiKey");
        tmdbApiKeyBox.PlaceholderText = "去 themoviedb.org 免费申请";
        scraperStack.Children.Add(tmdbApiKeyBox);
        var tmdbTokenBox = PasswordInput("TMDB 读访问令牌（推荐，优先使用）", "SettingsTmdbAccessToken");
        tmdbTokenBox.PlaceholderText = "Bearer Token";
        scraperStack.Children.Add(tmdbTokenBox);
        var tmdbTokenStatusText = StatusText("SettingsTmdbTokenStatusText");
        scraperStack.Children.Add(tmdbTokenStatusText);
        scraperStack.Children.Add(ScraperDescriptionGrid());
        rightColumn.Children.Add(SectionCard(scraperStack, "SettingsScraperCard"));

        var backupStack = new StackPanel { Spacing = 12 };
        backupStack.Children.Add(SectionTitle("数据备份与恢复", "SettingsBackupCard"));
        var backupActions = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 10,
        };
        var backupCoreButton = FluentTheme.ApplyButton(new Button { Content = "下载数据库备份" }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(backupCoreButton, "SettingsBackupCore");
        backupCoreButton.Click += (_, _) => OpenBackup("core");
        backupActions.Children.Add(backupCoreButton);
        var backupFullButton = FluentTheme.ApplyButton(new Button { Content = "下载完整备份 (含封面图)" }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(backupFullButton, "SettingsBackupFull");
        backupFullButton.Click += (_, _) => OpenBackup("full");
        backupActions.Children.Add(backupFullButton);
        var restoreBackupButton = FluentTheme.ApplyButton(new Button { Content = "选择备份恢复" });
        AutomationProperties.SetAutomationId(restoreBackupButton, "SettingsRestoreBackup");
        restoreBackupButton.Click += OnRestoreBackupClicked;
        backupActions.Children.Add(restoreBackupButton);
        backupActions.SizeChanged += (_, args) => ApplyActionStackLayout(args.NewSize.Width, backupActions);
        backupStack.Children.Add(backupActions);
        backupStack.Children.Add(FluentTheme.Body("完整备份包含数据库和所有封面图片缓存。恢复会覆盖当前数据。", 13));
        var backupStatusText = StatusText("SettingsBackupStatusText");
        backupStack.Children.Add(backupStatusText);
        rightColumn.Children.Add(SectionCard(backupStack, "SettingsBackupCard"));

        var updateStack = new StackPanel { Spacing = 12 };
        var updateHeader = new Grid { ColumnSpacing = 12, RowSpacing = 10 };
        updateHeader.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        updateHeader.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        updateHeader.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        updateHeader.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });
        updateHeader.Children.Add(SectionTitle("更新", "SettingsUpdateCard"));
        var checkButton = FluentTheme.ApplyButton(new Button { Content = "检查更新" });
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
        var updateStatusText = StatusText("SettingsUpdateStatusText");
        updateStack.Children.Add(updateStatusText);
        var logsButton = FluentTheme.ApplyButton(new Button
        {
            Content = "打开问题日志",
            HorizontalAlignment = HorizontalAlignment.Left,
        });
        AutomationProperties.SetAutomationId(logsButton, "SettingsOpenLogs");
        logsButton.Click += OnOpenLogsClicked;
        updateStack.Children.Add(logsButton);
        rightColumn.Children.Add(SectionCard(updateStack, "SettingsUpdateCard"));

        scrollViewer.SizeChanged += (_, args) => ApplySettingsViewportLayout(
            args.NewSize.Width,
            root,
            columns,
            rightColumn);

        scrollViewer.Content = root;
        Content = scrollViewer;
        return (
            globalStatusText,
            hideHomeTitleTextBox,
            showSourceNameBox,
            oldUsernameBox,
            oldPasswordBox,
            newUsernameBox,
            newPasswordBox,
            authStatusText,
            librarySettingsList,
            libraryStatusText,
            javdbCacheHoursBox,
            tmdbCacheHoursBox,
            bangumiCacheHoursBox,
            javdbRequestIntervalBox,
            tmdbApiKeyBox,
            tmdbTokenBox,
            tmdbTokenStatusText,
            backupStatusText,
            versionText,
            updateStatusText
        );
    }

    private async void OnLoaded(object sender, RoutedEventArgs args)
    {
        LoadUiPreferences();
        await LoadVersionAsync();
        await LoadTmdbConfigAsync();
        await LoadLibrarySettingsAsync();
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

    private async System.Threading.Tasks.Task LoadVersionAsync()
    {
        try
        {
            var version = await AppServices.Updates.GetVersionAsync();
            var source = version.CurrentSource == "app-package" ? "应用包" : "安装包内置";
            _versionText.Text = $"当前版本：{version.Version}    运行来源：Windows · {source}    镜像内置版本：{version.BaseVersion}";
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
            var config = await AppServices.Api.GetConfigAsync();
            _loadedConfig = config;
            _javdbCacheHoursBox.Text = config.JavdbCacheHours.ToString();
            _tmdbCacheHoursBox.Text = config.TmdbCacheHours.ToString();
            _bangumiCacheHoursBox.Text = config.BangumiCacheHours.ToString();
            _javdbRequestIntervalBox.Text = config.JavdbRequestInterval.ToString();
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
            ShowTmdbStatus("TMDB 设置已保存。", false);
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
        await AppServices.Api.SaveGlobalConfigAsync(new ConfigDto
        {
            JavdbEnabled = _loadedConfig.JavdbEnabled,
            JavdbCacheHours = ReadInt(_javdbCacheHoursBox.Text, 24),
            TmdbCacheHours = ReadInt(_tmdbCacheHoursBox.Text, 168),
            BangumiCacheHours = ReadInt(_bangumiCacheHoursBox.Text, 168),
            JavdbRequestInterval = ReadInt(_javdbRequestIntervalBox.Text, 3),
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

    private async void OnChangePasswordClicked(object sender, RoutedEventArgs args)
    {
        if (sender is not Button button)
        {
            return;
        }

        try
        {
            button.IsEnabled = false;
            ShowAuthStatus("正在更新账号...", false);
            await AppServices.Api.ChangePasswordAsync(_oldUsernameBox.Text, _oldPasswordBox.Password, _newUsernameBox.Text, _newPasswordBox.Password);
            _oldUsernameBox.Text = "";
            _oldPasswordBox.Password = "";
            _newUsernameBox.Text = "";
            _newPasswordBox.Password = "";
            ShowAuthStatus("密码已更新。", false);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to change native account password.");
            ShowAuthStatus($"更新失败：{ex.Message}", true);
        }
        finally
        {
            button.IsEnabled = true;
        }
    }

    private async System.Threading.Tasks.Task LoadLibrarySettingsAsync()
    {
        try
        {
            _libraryStatusText.Foreground = FluentTheme.TextSecondary;
            _libraryStatusText.Text = "正在加载媒体库设置...";
            _librarySettingsList.Items.Clear();

            var roots = await AppServices.Library.GetMediaRootsAsync();
            var settings = await AppServices.Library.GetLibrarySettingsAsync();
            var settingMap = settings.ToDictionary(s => s.MediaRoot, StringComparer.OrdinalIgnoreCase);
            var orderedRoots = roots.Items
                .OrderBy(root => string.IsNullOrWhiteSpace(root.Label) ? root.Path : root.Label, StringComparer.CurrentCultureIgnoreCase)
                .ToList();

            if (orderedRoots.Count == 0)
            {
                _libraryStatusText.Text = "还没有媒体库。先添加影片文件夹后，再设置刮削器。";
                return;
            }

            for (var i = 0; i < orderedRoots.Count; i++)
            {
                var root = orderedRoots[i];
                settingMap.TryGetValue(root.Path, out var setting);
                _librarySettingsList.Items.Add(CreateLibrarySettingsRow(root, setting, i));
            }

            _libraryStatusText.Text = "选择刮削器后点击保存。需要重新整理时可直接重新扫描。";
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load native library scraper settings.");
            _librarySettingsList.Items.Clear();
            _libraryStatusText.Foreground = FluentTheme.Error;
            _libraryStatusText.Text = $"加载媒体库设置失败：{ex.Message}";
        }
    }

    private UIElement CreateLibrarySettingsRow(MediaRootDto root, LibrarySettingDto? setting, int index)
    {
        var row = new Border
        {
            Padding = new Thickness(14),
            CornerRadius = FluentTheme.CardCornerRadius,
            Background = FluentTheme.LayerAlt,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(1),
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };

        var grid = new Grid { ColumnSpacing = 12, HorizontalAlignment = HorizontalAlignment.Stretch };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });
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

        var selectedScraper = NormalizeScraper(setting?.Scraper ?? root.Scraper);
        var scraperStack = new StackPanel
        {
            Spacing = 6,
            Width = 230,
        };
        var scraperBox = new ComboBox
        {
            Header = "资料来源",
            MinWidth = 0,
        };
        AutomationProperties.SetAutomationId(scraperBox, $"SettingsLibraryScraper_{index}");
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
            Text = GetScraperDescription(GetSelectedScraper(scraperBox)),
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        scraperBox.SelectionChanged += (_, _) =>
        {
            descriptionText.Text = GetScraperDescription(GetSelectedScraper(scraperBox));
        };
        scraperStack.Children.Add(scraperBox);
        scraperStack.Children.Add(descriptionText);
        Grid.SetColumn(scraperStack, 1);
        grid.Children.Add(scraperStack);

        var passwordBox = new PasswordBox
        {
            Header = "密码",
            PlaceholderText = "可选",
            Width = 120,
        };
        AutomationProperties.SetAutomationId(passwordBox, $"SettingsLibraryPassword_{index}");
        Grid.SetColumn(passwordBox, 2);
        grid.Children.Add(passwordBox);

        var actions = new StackPanel { Spacing = 8 };
        var saveButton = FluentTheme.ApplyButton(new Button
        {
            Content = "保存",
            Tag = new LibrarySettingsRowContext(root.Path, setting?.TmdbKey ?? "", scraperBox, passwordBox),
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(saveButton, $"SettingsSaveLibrary_{index}");
        saveButton.Click += OnSaveLibrarySettingClicked;
        actions.Children.Add(saveButton);

        var scanButton = FluentTheme.ApplyButton(new Button
        {
            Content = "重新扫描",
            Tag = new LibrarySettingsRowContext(root.Path, setting?.TmdbKey ?? "", scraperBox, passwordBox),
        });
        AutomationProperties.SetAutomationId(scanButton, $"SettingsScanLibrary_{index}");
        scanButton.Click += OnScanLibraryClicked;
        actions.Children.Add(scanButton);
        Grid.SetColumn(actions, 3);
        grid.Children.Add(actions);

        row.SizeChanged += (_, args) => ApplyLibrarySettingsRowLayout(
            args.NewSize.Width,
            grid,
            info,
            scraperStack,
            passwordBox,
            actions);

        row.Child = grid;
        return row;
    }

    private async void OnSaveLibrarySettingClicked(object sender, RoutedEventArgs args)
    {
        if (sender is not Button button || button.Tag is not LibrarySettingsRowContext context)
        {
            return;
        }

        try
        {
            button.IsEnabled = false;
            _libraryStatusText.Foreground = FluentTheme.TextSecondary;
            _libraryStatusText.Text = "正在保存媒体库设置...";
            await SaveLibrarySettingAsync(context);

            _libraryStatusText.Foreground = FluentTheme.Accent;
            _libraryStatusText.Text = "媒体库设置已保存。";
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to save native library scraper setting.");
            _libraryStatusText.Foreground = FluentTheme.Error;
            _libraryStatusText.Text = $"保存媒体库设置失败：{ex.Message}";
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
            button.IsEnabled = false;
            _libraryStatusText.Foreground = FluentTheme.TextSecondary;
            _libraryStatusText.Text = "正在保存刮削器设置并重新扫描...";
            await SaveLibrarySettingAsync(context);
            await AppServices.Library.ClearLibraryAsync(context.MediaRoot);
            await AppServices.Library.ScanAsync(context.MediaRoot);
            _libraryStatusText.Foreground = FluentTheme.Accent;
            _libraryStatusText.Text = "已开始重新扫描。你可以继续使用应用。";
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to rescan native library from settings.");
            _libraryStatusText.Foreground = FluentTheme.Error;
            _libraryStatusText.Text = $"重新扫描失败：{ex.Message}";
        }
        finally
        {
            button.IsEnabled = true;
        }
    }

    private async System.Threading.Tasks.Task SaveLibrarySettingAsync(LibrarySettingsRowContext context)
    {
        await AppServices.Library.SaveLibrarySettingAsync(new LibrarySettingDto
        {
            MediaRoot = context.MediaRoot,
            Scraper = GetSelectedScraper(context.ScraperBox),
            TmdbKey = context.TmdbKey,
            Enabled = 1,
        });
        if (!string.IsNullOrWhiteSpace(context.PasswordBox.Password))
        {
            await AppServices.Library.SetLibraryPasswordAsync(context.MediaRoot, context.PasswordBox.Password);
            context.PasswordBox.Password = "";
        }
    }

    private void OpenBackup(string backupType)
    {
        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = AppServices.Api.BuildBackupUri(backupType).ToString(),
                UseShellExecute = true,
            });
            ShowBackupStatus("已打开备份下载。", false);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to open native backup URL.");
            ShowBackupStatus($"打开备份失败：{ex.Message}", true);
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
            await AppServices.Api.RestoreBackupAsync(file.Path);
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
        try
        {
            var result = await AppServices.Updates.CheckForUpdatesAsync();
            if (!result.HasUpdate)
            {
                ShowUpdateStatus("当前已经是最新版本。", false);
            }
            else
            {
                var next = result.Versions.Count > 0 ? result.Versions[0] : null;
                var message = next?.RequiresWindowsBaseUpdate == true
                    ? $"发现新版本 {next.DisplayVersion}。这次更新需要安装新的 Windows 桌面版安装包。{next.WindowsReason}"
                    : $"发现新版本 {next?.DisplayVersion}。可以直接在应用内更新。";
                ShowUpdateStatus(message, false);
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to check native Windows updates.");
            ShowUpdateStatus($"检查更新失败：{ex.Message}", true);
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

    private void OnAddLibraryClicked(object sender, RoutedEventArgs args)
    {
        ShellPage.Current?.NavigateToSetup();
    }

    private void ShowGlobalStatus(string message, bool isError)
    {
        _globalStatusText.Text = message;
        _globalStatusText.Foreground = isError ? FluentTheme.Error : FluentTheme.Accent;
        _globalStatusText.Visibility = Visibility.Visible;
    }

    private void ShowAuthStatus(string message, bool isError)
    {
        _authStatusText.Text = message;
        _authStatusText.Foreground = isError ? FluentTheme.Error : FluentTheme.Accent;
        _authStatusText.Visibility = Visibility.Visible;
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

    private static ContentControl SectionCard(UIElement child, string automationId)
    {
        var wrapper = new ContentControl
        {
            Content = FluentTheme.Card(child, new Thickness(22)),
            HorizontalAlignment = HorizontalAlignment.Stretch,
            IsTabStop = false,
        };
        AutomationProperties.SetAutomationId(wrapper, automationId);
        return wrapper;
    }

    private static void ApplySettingsViewportLayout(double viewportWidth, StackPanel root, Grid columns, StackPanel rightColumn)
    {
        var compact = viewportWidth < FluentTheme.MediumBreakpoint;
        root.Width = Math.Max(0, viewportWidth);
        root.Padding = FluentTheme.SpaciousPagePadding(viewportWidth);
        var contentWidth = Math.Max(0, viewportWidth - root.Padding.Left - root.Padding.Right);
        columns.Width = contentWidth;
        columns.ColumnDefinitions[1].Width = compact ? new GridLength(0) : new GridLength(1, GridUnitType.Star);
        columns.RowDefinitions[1].Height = compact ? GridLength.Auto : new GridLength(0);
        columns.ColumnSpacing = compact ? 0 : 20;
        Grid.SetColumn(rightColumn, compact ? 0 : 1);
        Grid.SetRow(rightColumn, compact ? 1 : 0);
    }

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

    private static void ApplyLibrarySettingsRowLayout(
        double width,
        Grid grid,
        FrameworkElement info,
        StackPanel scraperStack,
        PasswordBox passwordBox,
        StackPanel actions)
    {
        var compact = width < 720;
        grid.RowSpacing = compact ? 12 : 0;
        grid.ColumnDefinitions[1].Width = compact ? new GridLength(0) : GridLength.Auto;
        grid.ColumnDefinitions[2].Width = compact ? new GridLength(0) : GridLength.Auto;
        grid.ColumnDefinitions[3].Width = compact ? new GridLength(0) : GridLength.Auto;
        for (var i = 1; i < grid.RowDefinitions.Count; i++)
        {
            grid.RowDefinitions[i].Height = compact ? GridLength.Auto : new GridLength(0);
        }

        Grid.SetColumn(info, 0);
        Grid.SetRow(info, 0);
        Grid.SetColumn(scraperStack, compact ? 0 : 1);
        Grid.SetRow(scraperStack, compact ? 1 : 0);
        Grid.SetColumn(passwordBox, compact ? 0 : 2);
        Grid.SetRow(passwordBox, compact ? 2 : 0);
        Grid.SetColumn(actions, compact ? 0 : 3);
        Grid.SetRow(actions, compact ? 3 : 0);

        info.MinWidth = compact ? 0 : 220;
        scraperStack.Width = compact ? double.NaN : 230;
        passwordBox.Width = compact ? double.NaN : 120;
        scraperStack.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Left;
        passwordBox.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Left;
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
        var box = new TextBox
        {
            Header = header,
            Text = value,
            MinWidth = 0,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };
        AutomationProperties.SetAutomationId(box, automationId);
        return box;
    }

    private static PasswordBox PasswordInput(string header, string automationId)
    {
        var box = new PasswordBox
        {
            Header = header,
            MinWidth = 0,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };
        AutomationProperties.SetAutomationId(box, automationId);
        return box;
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
                Grid.SetColumn(child, i % columns);
                Grid.SetRow(child, i / columns);
            }
        }
    }

    private static int ReadInt(string value, int fallback)
    {
        return int.TryParse(value, out var parsed) && parsed > 0 ? parsed : fallback;
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
