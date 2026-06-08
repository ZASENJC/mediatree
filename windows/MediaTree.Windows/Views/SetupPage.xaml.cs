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
    private readonly List<(Button Button, string Value)> _scraperButtons = [];
    private readonly Button _addLibraryButton;
    private readonly TextBlock _selectedFolderText;
    private readonly TextBlock _statusText;
    private string _selectedScraper = "auto";
    private string _selectedFolder = "";

    public SetupPage()
    {
        (_addLibraryButton, _selectedFolderText, _statusText) = BuildContent();
    }

    private (Button addLibraryButton, TextBlock selectedFolderText, TextBlock statusText) BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "SetupPage");

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

        var header = new StackPanel { Spacing = 8, MaxWidth = 760 };
        header.Children.Add(FluentTheme.Title("添加你的影片文件夹", 34));
        header.Children.Add(FluentTheme.Body("选择一个存放影片或剧集的本机文件夹。MediaTree 会自动扫描里面的视频，并整理成方便浏览的媒体库。", 15));
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

        var scraperButtons = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 8,
        };
        scraperButtons.Children.Add(CreateScraperButton("自动识别（推荐）", "auto", "SetupScraperAuto"));
        scraperButtons.Children.Add(CreateScraperButton("TMDB", "tmdb", "SetupScraperTmdb"));
        scraperButtons.Children.Add(CreateScraperButton("Bangumi", "bangumi", "SetupScraperBangumi"));
        scraperButtons.Children.Add(CreateScraperButton("先不识别资料", "none", "SetupScraperNone"));
        form.Children.Add(scraperButtons);
        UpdateScraperSelection();

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
            Content = "添加并开始整理",
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

        Content = root;
        return (addLibraryButton, selectedFolderText, statusText);
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
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Folder picker failed.");
            _selectedFolder = "";
            _selectedFolderText.Text = "还没有选择文件夹";
            _statusText.Foreground = FluentTheme.Error;
            _statusText.Text = $"选择文件夹失败：{ex.Message}";
            _addLibraryButton.IsEnabled = false;
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
            _statusText.Text = "正在添加文件夹并开始整理，请稍候...";

            await AppServices.Library.AddLibraryAsync(_selectedFolder, _selectedScraper);

            _statusText.Foreground = FluentTheme.Accent;
            _statusText.Text = "文件夹已添加，MediaTree 正在整理里面的视频。";
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

    private Button CreateScraperButton(string label, string value, string automationId)
    {
        var button = FluentTheme.ApplyButton(new Button
        {
            Content = label,
        }, FluentButtonStyle.Subtle);
        AutomationProperties.SetAutomationId(button, automationId);
        button.Click += (_, _) =>
        {
            _selectedScraper = value;
            UpdateScraperSelection();
        };
        _scraperButtons.Add((button, value));
        return button;
    }

    private void UpdateScraperSelection()
    {
        foreach (var (button, value) in _scraperButtons)
        {
            var selected = value == _selectedScraper;
            button.Background = selected ? FluentTheme.AccentSoft : new SolidColorBrush(Microsoft.UI.Colors.Transparent);
            button.BorderBrush = selected ? FluentTheme.AccentSoft : new SolidColorBrush(Microsoft.UI.Colors.Transparent);
        }
    }
}
