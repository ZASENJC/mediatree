using System;
using MediaTree.Windows.Models;
using MediaTree.Windows.Styles;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;

namespace MediaTree.Windows.Views;

public sealed partial class ShellPage : Page
{
    public static ShellPage? Current { get; private set; }

    private readonly Frame _contentFrame;
    private readonly Button _browseButton;
    private readonly Button _favoritesButton;
    private readonly Button _homeButton;
    private readonly Border _navigationHost;
    private readonly ColumnDefinition _navigationColumn;
    private readonly Button _settingsButton;
    private bool _isCompactNavigation;
    private bool _navigationChromeVisible = true;

    public ShellPage()
    {
        (_contentFrame, _homeButton, _browseButton, _favoritesButton, _settingsButton, _navigationHost, _navigationColumn) = BuildContent();
        Current = this;
        Loaded += OnLoaded;
    }

    public void NavigateToSetup()
    {
        Services.ShellLogger.Info("Navigating shell content to setup page.");
        _contentFrame.Navigate(typeof(SetupPage));
        Services.ShellLogger.Info("Setup page navigation requested.");
    }

    public void NavigateToLibrary()
    {
        _ = NavigateToHomeAsync();
    }

    public void NavigateToMovie(int movieId)
    {
        NavigateToPlayer(movieId);
    }

    public void NavigateToPlayer(int movieId)
    {
        _contentFrame.Navigate(typeof(PlayerPage), new PlayerNavigationParameter(movieId));
    }

    public void NavigateToFolder(string folderPath, string mediaRoot, string title)
    {
        _contentFrame.Navigate(typeof(FolderPage), new FolderNavigationParameter(folderPath, mediaRoot, title));
    }

    public void GoBackOrLibrary()
    {
        RemoveTopPlayerPagesFromBackStack();

        if (_contentFrame.CanGoBack)
        {
            _contentFrame.GoBack();
            return;
        }

        NavigateToLibrary();
    }

    public void SetNavigationChromeVisible(bool visible)
    {
        _navigationChromeVisible = visible;
        _navigationHost.Visibility = visible ? Visibility.Visible : Visibility.Collapsed;
        _navigationColumn.Width = visible ? new GridLength(_isCompactNavigation ? 88 : 248) : new GridLength(0);
    }

    private void RemoveTopPlayerPagesFromBackStack()
    {
        while (_contentFrame.BackStack.Count > 0)
        {
            var lastIndex = _contentFrame.BackStack.Count - 1;
            if (_contentFrame.BackStack[lastIndex].SourcePageType != typeof(PlayerPage))
            {
                return;
            }

            _contentFrame.BackStack.RemoveAt(lastIndex);
        }
    }

    private async void OnLoaded(object sender, RoutedEventArgs args)
    {
        try
        {
            var setup = await Services.AppServices.Library.GetSetupStatusAsync();
            if (setup.NeedsSetup)
            {
                NavigateToSetup();
                return;
            }

            await NavigateToHomeAsync();
        }
        catch
        {
            NavigateToPage(typeof(LibraryPage), _homeButton);
        }
    }

    private (Frame contentFrame, Button homeButton, Button browseButton, Button favoritesButton, Button settingsButton, Border navigationHost, ColumnDefinition navigationColumn) BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "ShellPage");

        var root = new Grid
        {
            Background = FluentTheme.Canvas,
            RequestedTheme = ElementTheme.Light,
        };
        var navigationColumn = new ColumnDefinition { Width = new GridLength(248) };
        root.ColumnDefinitions.Add(navigationColumn);
        root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

        var navigationHost = new Border
        {
            Background = FluentTheme.Layer,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(0, 0, 1, 0),
            Padding = new Thickness(18, 22, 18, 18),
        };
        AutomationProperties.SetAutomationId(navigationHost, "ShellNavigation");

        var navigation = new StackPanel { Spacing = 8 };
        navigation.Children.Add(new TextBlock
        {
            Text = "MediaTree",
            FontSize = 24,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
            Margin = new Thickness(8, 0, 8, 2),
        });
        navigation.Children.Add(new TextBlock
        {
            Text = "本机媒体库",
            FontSize = 13,
            Foreground = FluentTheme.TextSecondary,
            Margin = new Thickness(8, 0, 8, 18),
        });

        var homeButton = CreateNavigationButton("首页", "NavHome");
        homeButton.Click += (_, _) => _ = NavigateToHomeAsync();
        navigation.Children.Add(homeButton);

        var browseButton = CreateNavigationButton("浏览", "NavBrowse");
        browseButton.Click += (_, _) => _ = NavigateToBrowseAsync();
        navigation.Children.Add(browseButton);

        var favoritesButton = CreateNavigationButton("收藏", "NavFavorites");
        favoritesButton.Click += (_, _) => _ = NavigateToFavoritesAsync();
        navigation.Children.Add(favoritesButton);

        var settingsButton = CreateNavigationButton("设置", "NavSettings");
        settingsButton.Click += (_, _) => NavigateToPage(typeof(SettingsPage), settingsButton);
        navigation.Children.Add(settingsButton);

        navigationHost.Child = navigation;
        root.Children.Add(navigationHost);

        var contentFrame = new Frame();
        AutomationProperties.SetAutomationId(contentFrame, "ContentFrame");
        Grid.SetColumn(contentFrame, 1);
        root.Children.Add(contentFrame);

        root.SizeChanged += (_, args) =>
        {
            _isCompactNavigation = args.NewSize.Width < 900;
            navigationHost.Padding = _isCompactNavigation ? new Thickness(10, 18, 10, 14) : new Thickness(18, 22, 18, 18);
            if (_navigationChromeVisible)
            {
                navigationColumn.Width = new GridLength(_isCompactNavigation ? 88 : 248);
            }
        };

        Content = root;
        return (contentFrame, homeButton, browseButton, favoritesButton, settingsButton, navigationHost, navigationColumn);
    }

    private static Button CreateNavigationButton(string label, string automationId)
    {
        var labelBlock = new TextBlock
        {
            Text = label,
            VerticalAlignment = VerticalAlignment.Center,
            Foreground = FluentTheme.TextPrimary,
        };

        var button = new Button
        {
            Content = labelBlock,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            HorizontalContentAlignment = HorizontalAlignment.Left,
        };
        FluentTheme.ApplyButton(button, FluentButtonStyle.Subtle);
        AutomationProperties.SetAutomationId(button, automationId);
        return button;
    }

    private async System.Threading.Tasks.Task NavigateToHomeAsync()
    {
        if (!await HasLibraryAsync())
        {
            NavigateToPage(typeof(SetupRequiredPage), _homeButton);
            return;
        }

        NavigateToPage(typeof(LibraryPage), _homeButton);
    }

    private async System.Threading.Tasks.Task NavigateToBrowseAsync()
    {
        if (!await HasLibraryAsync())
        {
            NavigateToPage(typeof(SetupRequiredPage), _browseButton);
            return;
        }

        NavigateToPage(typeof(BrowsePage), _browseButton);
    }

    private async System.Threading.Tasks.Task NavigateToFavoritesAsync()
    {
        if (!await HasLibraryAsync())
        {
            NavigateToPage(typeof(SetupRequiredPage), _favoritesButton);
            return;
        }

        NavigateToPage(typeof(FavoritesPage), _favoritesButton);
    }

    private static async System.Threading.Tasks.Task<bool> HasLibraryAsync()
    {
        try
        {
            var setup = await Services.AppServices.Library.GetSetupStatusAsync();
            return !setup.NeedsSetup;
        }
        catch
        {
            return false;
        }
    }

    private void NavigateToPage(Type page, Button selectedButton)
    {
        SelectButton(selectedButton);
        if (_contentFrame.CurrentSourcePageType != page)
        {
            _contentFrame.Navigate(page);
        }
    }

    private void SelectButton(Button selectedButton)
    {
        foreach (var button in new[] { _homeButton, _browseButton, _favoritesButton, _settingsButton })
        {
            var selected = button == selectedButton;
            button.Background = selected ? FluentTheme.AccentSoft : new SolidColorBrush(Microsoft.UI.Colors.Transparent);
            button.BorderBrush = selected ? FluentTheme.AccentSoft : new SolidColorBrush(Microsoft.UI.Colors.Transparent);
        }
    }
}
