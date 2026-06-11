using System;
using System.Collections.Generic;
using MediaTree.Windows.Services;
using MediaTree.Windows.Styles;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Windows.Storage.Pickers;
using WinRT.Interop;

namespace MediaTree.Windows.Views;

public sealed partial class SetupPage : Page
{
    private sealed record SetupScraperOption(string Value, string Label, string Description, string AutomationId);

    private static readonly IReadOnlyList<SetupScraperOption> ScraperOptions =
    [
        new("tmdb_movie", "TMDB 电影", "电影库；tmdbid 调用 /movie 精确刮削", "SetupScraperTmdbMovie"),
        new("tmdb_tv", "TMDB 剧集/番剧", "剧集、番剧、电视剧库；tmdbid 调用 /tv 精确刮削", "SetupScraperTmdbTv"),
        new("tmdb_collection", "TMDB 合集", "电影合集库；复用 TMDB collection 元数据", "SetupScraperTmdbCollection"),
        new("bangumi", "Bangumi", "番剧、动画、二次元条目", "SetupScraperBangumi"),
        new("javdatabase", "Javdatabase", "JAV 番号识别和刮削", "SetupScraperJavdatabase"),
        new("auto", "自动", "自动判断，可能效果不好", "SetupScraperAuto"),
        new("none", "不刮削", "只扫描本地文件", "SetupScraperNone"),
    ];

    private readonly List<(Button Button, string Value)> _scraperButtons = [];
    private readonly Button _addLibraryButton;
    private readonly PasswordBox _libraryPasswordBox;
    private readonly TextBlock _selectedFolderText;
    private readonly TextBlock _statusText;
    private readonly PasswordBox _tmdbTokenBox;
    private readonly StackPanel _tmdbTokenSection;
    private string _selectedScraper = "auto";
    private string _selectedFolder = "";

    public SetupPage()
    {
        (_addLibraryButton, _selectedFolderText, _statusText, _tmdbTokenSection, _tmdbTokenBox, _libraryPasswordBox) = BuildContent();
        UpdateScraperSelection();
    }

    private (Button addLibraryButton, TextBlock selectedFolderText, TextBlock statusText, StackPanel tmdbTokenSection, PasswordBox tmdbTokenBox, PasswordBox libraryPasswordBox) BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "SetupPage");

        var scrollViewer = new ScrollViewer();
        var root = new Grid
        {
            Padding = new Thickness(40),
            RowSpacing = 24,
            Background = FluentTheme.Canvas,
            RequestedTheme = ElementTheme.Light,
        };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

        var header = new StackPanel
        {
            Spacing = 8,
            MaxWidth = 760,
            HorizontalAlignment = HorizontalAlignment.Left,
        };
        header.Children.Add(FluentTheme.Title("添加你的影片文件夹", 34));
        header.Children.Add(FluentTheme.Body("选择一个存放影片或剧集的本机文件夹。MediaTree 会自动扫描里面的视频，并刮削成方便浏览的媒体库。", 15));
        root.Children.Add(header);

        var form = new StackPanel
        {
            Spacing = 18,
            MaxWidth = 760,
            HorizontalAlignment = HorizontalAlignment.Left,
        };
        Grid.SetRow(form, 1);
        var pickFolderButton = FluentTheme.ApplyButton(new Button
        {
            Content = "选择文件夹",
        });
        AutomationProperties.SetAutomationId(pickFolderButton, "PickLibraryFolder");
        pickFolderButton.Click += OnPickFolderClicked;
        form.Children.Add(pickFolderButton);

        var selectedFolderText = new TextBlock
        {
            Text = "还没有选择文件夹",
            TextWrapping = TextWrapping.WrapWholeWords,
            Foreground = FluentTheme.TextSecondary,
        };
        AutomationProperties.SetAutomationId(selectedFolderText, "SelectedLibraryFolder");
        form.Children.Add(selectedFolderText);

        form.Children.Add(new TextBlock
        {
            Text = "资料识别方式",
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
        });

        var scraperButtons = new Grid
        {
            ColumnSpacing = 10,
            RowSpacing = 10,
        };
        scraperButtons.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        scraperButtons.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        for (var i = 0; i < ScraperOptions.Count; i++)
        {
            if (i % 2 == 0)
            {
                scraperButtons.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            }

            var option = ScraperOptions[i];
            var button = CreateScraperButton(option);
            Grid.SetRow(button, i / 2);
            Grid.SetColumn(button, i % 2);
            scraperButtons.Children.Add(button);
        }
        scraperButtons.SizeChanged += (_, args) => ApplyScraperButtonsLayout(scraperButtons, args.NewSize.Width);

        form.Children.Add(scraperButtons);

        var tmdbTokenSection = new StackPanel { Spacing = 6 };
        var tmdbTokenBox = FluentTheme.ApplyPasswordInput(new PasswordBox
        {
            Header = "TMDB 读访问令牌（可选）",
            PlaceholderText = "以 eyJ 开头的 Read Access Token",
            MinWidth = 0,
        });
        AutomationProperties.SetAutomationId(tmdbTokenBox, "SetupTmdbAccessToken");
        tmdbTokenSection.Children.Add(tmdbTokenBox);
        tmdbTokenSection.Children.Add(FluentTheme.Body("选择 TMDB 电影、TMDB 剧集/番剧、TMDB 合集或自动时可填写；也可以之后在设置页补充。", 13));
        form.Children.Add(tmdbTokenSection);

        var libraryPasswordBox = FluentTheme.ApplyPasswordInput(new PasswordBox
        {
            Header = "媒体库密码（可选）",
            PlaceholderText = "留空则不设密码",
            MinWidth = 0,
        });
        AutomationProperties.SetAutomationId(libraryPasswordBox, "SetupLibraryPassword");
        form.Children.Add(libraryPasswordBox);

        var statusText = new TextBlock
        {
            Text = "选择文件夹后，就可以开始建立媒体库。",
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(statusText, "SetupStatus");
        form.Children.Add(statusText);

        var addLibraryButton = FluentTheme.ApplyButton(new Button
        {
            Content = "添加并开始刮削",
            IsEnabled = false,
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(addLibraryButton, "AddLibraryButton");
        addLibraryButton.Click += OnAddLibraryClicked;
        form.Children.Add(addLibraryButton);

        root.Children.Add(form);

        var backButton = FluentTheme.ApplyButton(new Button
        {
            Content = "返回媒体库",
        });
        AutomationProperties.SetAutomationId(backButton, "SetupBackToLibrary");
        backButton.Click += OnBackToLibraryClicked;
        Grid.SetRow(backButton, 2);
        root.Children.Add(backButton);

        root.SizeChanged += (_, args) => root.Padding = FluentTheme.SpaciousPagePadding(args.NewSize.Width);
        scrollViewer.Content = root;
        Content = scrollViewer;
        return (addLibraryButton, selectedFolderText, statusText, tmdbTokenSection, tmdbTokenBox, libraryPasswordBox);
    }

    private static void ApplyScraperButtonsLayout(Grid scraperButtons, double width)
    {
        var compact = width < 560;
        var columns = compact ? 1 : 2;
        scraperButtons.ColumnDefinitions[1].Width = compact ? new GridLength(0) : new GridLength(1, GridUnitType.Star);
        var rowsNeeded = (int)Math.Ceiling(scraperButtons.Children.Count / (double)columns);
        while (scraperButtons.RowDefinitions.Count < rowsNeeded)
        {
            scraperButtons.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        }

        for (var i = 0; i < scraperButtons.Children.Count; i++)
        {
            if (scraperButtons.Children[i] is FrameworkElement child)
            {
                Grid.SetColumn(child, i % columns);
                Grid.SetRow(child, i / columns);
            }
        }
    }

    private async void OnPickFolderClicked(object sender, RoutedEventArgs args)
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
            _selectedFolder = folder?.Path ?? "";
            _selectedFolderText.Text = string.IsNullOrWhiteSpace(_selectedFolder) ? "还没有选择文件夹" : $"已选择：{_selectedFolder}";
            _statusText.Foreground = FluentTheme.TextSecondary;
            _statusText.Text = string.IsNullOrWhiteSpace(_selectedFolder) ? "选择文件夹后，就可以开始建立媒体库。" : "文件夹已选择，可以开始建立媒体库。";
            _addLibraryButton.IsEnabled = !string.IsNullOrWhiteSpace(_selectedFolder);
            if (_addLibraryButton.IsEnabled)
            {
                _addLibraryButton.Focus(FocusState.Programmatic);
            }
            else if (sender is Button button)
            {
                button.Focus(FocusState.Programmatic);
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Folder picker failed.");
            _selectedFolder = "";
            _selectedFolderText.Text = "还没有选择文件夹";
            _statusText.Foreground = FluentTheme.Error;
            _statusText.Text = $"选择文件夹失败：{ex.Message}";
            _addLibraryButton.IsEnabled = false;
            if (sender is Button button)
            {
                button.Focus(FocusState.Programmatic);
            }
        }
    }

    private async void OnAddLibraryClicked(object sender, RoutedEventArgs args)
    {
        if (string.IsNullOrWhiteSpace(_selectedFolder))
        {
            return;
        }

        try
        {
            _addLibraryButton.IsEnabled = false;
            _statusText.Foreground = FluentTheme.TextSecondary;
            _statusText.Text = "正在添加文件夹并开始刮削，请稍候...";

            await AppServices.Library.AddLibraryAsync(
                _selectedFolder,
                _selectedScraper,
                _libraryPasswordBox.Password,
                _tmdbTokenBox.Password);

            _statusText.Foreground = FluentTheme.Accent;
            _statusText.Text = "文件夹已添加，MediaTree 正在刮削里面的视频。";
            ShellPage.Current?.NavigateToLibrary();
        }
        catch (Exception ex)
        {
            _statusText.Foreground = FluentTheme.Error;
            _statusText.Text = $"添加失败：{ex.Message}";
        }
        finally
        {
            _addLibraryButton.IsEnabled = true;
        }
    }

    private void OnBackToLibraryClicked(object sender, RoutedEventArgs args)
    {
        ShellPage.Current?.NavigateToLibrary();
    }

    private Button CreateScraperButton(SetupScraperOption option)
    {
        var content = new StackPanel { Spacing = 4 };
        content.Children.Add(new TextBlock
        {
            Text = option.Label,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
            TextWrapping = TextWrapping.WrapWholeWords,
        });
        content.Children.Add(new TextBlock
        {
            Text = option.Description,
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        });

        var button = FluentTheme.ApplyButton(new Button
        {
            Content = content,
            MinHeight = 76,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            HorizontalContentAlignment = HorizontalAlignment.Stretch,
        }, FluentButtonStyle.Subtle);
        AutomationProperties.SetAutomationId(button, option.AutomationId);
        button.Click += (_, _) =>
        {
            _selectedScraper = option.Value;
            UpdateScraperSelection();
        };
        _scraperButtons.Add((button, option.Value));
        return button;
    }

    private void UpdateScraperSelection()
    {
        _tmdbTokenSection.Visibility = RequiresTmdbToken(_selectedScraper) ? Visibility.Visible : Visibility.Collapsed;
        foreach (var (button, value) in _scraperButtons)
        {
            var selected = value == _selectedScraper;
            button.Background = selected ? FluentTheme.AccentSoft : new SolidColorBrush(Microsoft.UI.Colors.Transparent);
            button.BorderBrush = selected ? FluentTheme.AccentSoft : new SolidColorBrush(Microsoft.UI.Colors.Transparent);
        }
    }

    private static bool RequiresTmdbToken(string scraper)
        => scraper is "tmdb_movie" or "tmdb_tv" or "tmdb_collection" or "auto";
}
