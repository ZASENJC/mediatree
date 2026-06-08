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

namespace MediaTree.Windows.Views;

public sealed partial class SettingsPage : Page
{
    private sealed record ScraperOption(string Value, string Label, string Description, bool HasKey);

    private sealed record LibrarySettingsRowContext(string MediaRoot, string TmdbKey, ComboBox ScraperBox);

    private static readonly IReadOnlyList<ScraperOption> ScraperOptions =
    [
        new("tmdb_movie", "TMDB 电影", "适合电影库；tmdbid 调用 /movie 精确刮削", true),
        new("tmdb_tv", "TMDB 剧集/番剧", "适合剧集、番剧、电视剧库；tmdbid 调用 /tv 精确刮削", true),
        new("bangumi", "Bangumi", "适合番剧、动画、二次元条目，数据可能不全", false),
        new("javdatabase", "Javdatabase", "适合 JAV 番号识别和刮削", false),
        new("auto", "自动", "自动判断刮削源，但可能效果不好", true),
        new("none", "不刮削", "只扫描本地文件，不联网刮削元数据", false),
    ];

    private readonly ListView _librarySettingsList;
    private readonly TextBlock _libraryStatusText;
    private readonly PasswordBox _tmdbTokenBox;
    private readonly TextBlock _tmdbTokenStatusText;
    private readonly TextBlock _updateStatusText;
    private readonly TextBlock _versionText;

    public SettingsPage()
    {
        (_versionText, _updateStatusText, _tmdbTokenBox, _tmdbTokenStatusText, _librarySettingsList, _libraryStatusText) = BuildContent();
        Loaded += OnLoaded;
    }

    private (TextBlock versionText, TextBlock updateStatusText, PasswordBox tmdbTokenBox, TextBlock tmdbTokenStatusText, ListView librarySettingsList, TextBlock libraryStatusText) BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "SettingsPage");

        var scrollViewer = new ScrollViewer();
        var root = new StackPanel
        {
            Padding = new Thickness(40),
            Spacing = 22,
            Background = FluentTheme.Canvas,
            RequestedTheme = ElementTheme.Light,
        };
        root.Children.Add(FluentTheme.Title("设置", 34));

        var card = new Border
        {
            Padding = new Thickness(22),
            CornerRadius = new CornerRadius(16),
            Background = FluentTheme.Layer,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(1),
        };
        var stack = new StackPanel { Spacing = 12 };
        stack.Children.Add(new TextBlock
        {
            Text = "版本与更新",
            FontSize = 20,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
        });

        var versionText = new TextBlock
        {
            Foreground = FluentTheme.TextSecondary,
        };
        AutomationProperties.SetAutomationId(versionText, "SettingsVersion");
        stack.Children.Add(versionText);

        var updateStatusText = new TextBlock
        {
            Text = "",
            Visibility = Visibility.Collapsed,
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(updateStatusText, "SettingsUpdateStatusText");
        stack.Children.Add(updateStatusText);

        var actions = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 10,
        };
        var checkButton = FluentTheme.ApplyButton(new Button
        {
            Content = "检查更新",
        });
        AutomationProperties.SetAutomationId(checkButton, "SettingsCheckUpdates");
        checkButton.Click += OnCheckUpdatesClicked;
        actions.Children.Add(checkButton);

        var logsButton = FluentTheme.ApplyButton(new Button
        {
            Content = "打开问题日志",
        });
        AutomationProperties.SetAutomationId(logsButton, "SettingsOpenLogs");
        logsButton.Click += OnOpenLogsClicked;
        actions.Children.Add(logsButton);

        var addLibraryButton = FluentTheme.ApplyButton(new Button
        {
            Content = "添加影片文件夹",
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(addLibraryButton, "SettingsAddLibrary");
        addLibraryButton.Click += OnAddLibraryClicked;
        actions.Children.Add(addLibraryButton);

        stack.Children.Add(actions);
        card.Child = stack;
        root.Children.Add(card);

        var libraryStack = new StackPanel { Spacing = 12 };
        libraryStack.Children.Add(new TextBlock
        {
            Text = "刮削器设置",
            FontSize = 20,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
        });
        libraryStack.Children.Add(new TextBlock
        {
            Text = "为每个媒体库选择资料来源。保存后重新整理媒体库时会按这里的设置刮削。",
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        });

        var tmdbConfig = new Grid
        {
            ColumnSpacing = 10,
        };
        tmdbConfig.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        tmdbConfig.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        var tmdbTokenBox = new PasswordBox
        {
            Header = "TMDB 读访问令牌（推荐，优先使用）",
            PlaceholderText = "Bearer Token",
            MinWidth = 360,
        };
        AutomationProperties.SetAutomationId(tmdbTokenBox, "SettingsTmdbAccessToken");
        tmdbConfig.Children.Add(tmdbTokenBox);

        var saveTmdbButton = FluentTheme.ApplyButton(new Button
        {
            Content = "保存令牌",
            VerticalAlignment = VerticalAlignment.Bottom,
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(saveTmdbButton, "SettingsSaveTmdbToken");
        saveTmdbButton.Click += OnSaveTmdbTokenClicked;
        Grid.SetColumn(saveTmdbButton, 1);
        tmdbConfig.Children.Add(saveTmdbButton);
        libraryStack.Children.Add(tmdbConfig);

        var tmdbTokenStatusText = new TextBlock
        {
            Text = "",
            Visibility = Visibility.Collapsed,
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(tmdbTokenStatusText, "SettingsTmdbTokenStatusText");
        libraryStack.Children.Add(tmdbTokenStatusText);

        var librarySettingsList = new ListView
        {
            SelectionMode = ListViewSelectionMode.None,
            IsItemClickEnabled = false,
            Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent),
            Padding = new Thickness(0),
        };
        AutomationProperties.SetAutomationId(librarySettingsList, "SettingsLibrarySettingsList");
        libraryStack.Children.Add(librarySettingsList);

        var libraryStatusText = new TextBlock
        {
            Text = "正在加载媒体库设置...",
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(libraryStatusText, "SettingsLibraryStatusText");
        libraryStack.Children.Add(libraryStatusText);

        root.Children.Add(FluentTheme.Card(libraryStack, new Thickness(22)));
        scrollViewer.Content = root;
        Content = scrollViewer;
        return (versionText, updateStatusText, tmdbTokenBox, tmdbTokenStatusText, librarySettingsList, libraryStatusText);
    }

    private async void OnLoaded(object sender, RoutedEventArgs args)
    {
        await LoadVersionAsync();
        await LoadTmdbConfigAsync();
        await LoadLibrarySettingsAsync();
    }

    private async System.Threading.Tasks.Task LoadVersionAsync()
    {
        try
        {
            var version = await AppServices.Updates.GetVersionAsync();
            var source = version.CurrentSource == "app-package" ? "已更新的应用包" : "安装包内置版本";
            _versionText.Text = $"当前版本：{version.Version}    来源：{source}";
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
            _tmdbTokenBox.Password = config.TmdbAccessToken ?? "";
            if (config.TmdbConfigured)
            {
                ShowTmdbStatus("TMDB 已配置。输入新令牌后保存即可替换。", false);
            }
            else
            {
                ShowTmdbStatus("未配置 TMDB 令牌。选择 TMDB 刮削器前建议先填写。", false);
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load native TMDB config.");
            ShowTmdbStatus($"读取 TMDB 配置失败：{ex.Message}", true);
        }
    }

    private async void OnSaveTmdbTokenClicked(object sender, RoutedEventArgs args)
    {
        if (sender is not Button button)
        {
            return;
        }

        try
        {
            button.IsEnabled = false;
            ShowTmdbStatus("正在保存 TMDB 令牌...", false);
            await AppServices.Api.SaveTmdbConfigAsync(_tmdbTokenBox.Password);
            ShowTmdbStatus("TMDB 令牌已保存。", false);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to save native TMDB token.");
            ShowTmdbStatus($"保存 TMDB 令牌失败：{ex.Message}", true);
        }
        finally
        {
            button.IsEnabled = true;
        }
    }

    private void ShowTmdbStatus(string message, bool isError)
    {
        _tmdbTokenStatusText.Text = message;
        _tmdbTokenStatusText.Foreground = isError ? FluentTheme.Error : FluentTheme.TextSecondary;
        _tmdbTokenStatusText.Visibility = Visibility.Visible;
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

            _libraryStatusText.Text = "选择刮削器后点击保存。TMDB 相关选项会使用全局 TMDB 配置。";
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
            CornerRadius = new CornerRadius(10),
            Background = FluentTheme.LayerAlt,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(1),
        };

        var grid = new Grid { ColumnSpacing = 12 };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        var info = new StackPanel { Spacing = 4, MinWidth = 240 };
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
            Width = 280,
        };
        var scraperBox = new ComboBox
        {
            Header = "资料来源",
            MinWidth = 240,
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

        var saveButton = FluentTheme.ApplyButton(new Button
        {
            Content = "保存",
            VerticalAlignment = VerticalAlignment.Top,
            Tag = new LibrarySettingsRowContext(root.Path, setting?.TmdbKey ?? "", scraperBox),
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(saveButton, $"SettingsSaveLibrary_{index}");
        saveButton.Click += OnSaveLibrarySettingClicked;
        Grid.SetColumn(saveButton, 2);
        grid.Children.Add(saveButton);

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
            await AppServices.Library.SaveLibrarySettingAsync(new LibrarySettingDto
            {
                MediaRoot = context.MediaRoot,
                Scraper = GetSelectedScraper(context.ScraperBox),
                TmdbKey = context.TmdbKey,
                Enabled = 1,
            });
            _libraryStatusText.Foreground = FluentTheme.Accent;
            _libraryStatusText.Text = "媒体库刮削器设置已保存。";
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

    private void ShowUpdateStatus(string message, bool isError)
    {
        _updateStatusText.Text = message;
        _updateStatusText.Foreground = isError ? FluentTheme.Error : FluentTheme.TextSecondary;
        _updateStatusText.Visibility = Visibility.Visible;
    }

}
