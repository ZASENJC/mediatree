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
    private readonly Button _homeButton;
    private readonly Button _libraryButton;
    private readonly Button _recentButton;
    private readonly Button _settingsButton;

    public ShellPage()
    {
        (_contentFrame, _homeButton, _libraryButton, _recentButton, _settingsButton) = BuildContent();
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
        _ = NavigateToLibraryAsync();
    }

    public void NavigateToMovie(int movieId)
    {
        _contentFrame.Navigate(typeof(MovieDetailPage), new MovieNavigationParameter(movieId));
    }

    public void NavigateToPlayer(int movieId)
    {
        _contentFrame.Navigate(typeof(PlayerPage), new PlayerNavigationParameter(movieId));
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

            NavigateToPage(typeof(HomePage), _homeButton);
        }
        catch
        {
            NavigateToPage(typeof(HomePage), _homeButton);
        }
    }

    private (Frame contentFrame, Button homeButton, Button libraryButton, Button recentButton, Button settingsButton) BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "ShellPage");

        var root = new Grid
        {
            Background = FluentTheme.Canvas,
            RequestedTheme = ElementTheme.Light,
        };
        root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(248) });
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
        homeButton.Click += (_, _) => NavigateToPage(typeof(HomePage), homeButton);
        navigation.Children.Add(homeButton);

        var libraryButton = CreateNavigationButton("媒体库", "NavLibrary");
        libraryButton.Click += (_, _) => _ = NavigateToLibraryAsync();
        navigation.Children.Add(libraryButton);

        var recentButton = CreateNavigationButton("最近观看", "NavRecent");
        recentButton.Click += (_, _) => _ = NavigateToRecentAsync();
        navigation.Children.Add(recentButton);

        var settingsButton = CreateNavigationButton("设置", "NavSettings");
        settingsButton.Click += (_, _) => NavigateToPage(typeof(SettingsPage), settingsButton);
        navigation.Children.Add(settingsButton);

        navigationHost.Child = navigation;
        root.Children.Add(navigationHost);

        var contentFrame = new Frame();
        AutomationProperties.SetAutomationId(contentFrame, "ContentFrame");
        Grid.SetColumn(contentFrame, 1);
        root.Children.Add(contentFrame);

        Content = root;
        return (contentFrame, homeButton, libraryButton, recentButton, settingsButton);
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

    private async System.Threading.Tasks.Task NavigateToLibraryAsync()
    {
        if (!await HasLibraryAsync())
        {
            NavigateToPage(typeof(SetupRequiredPage), _libraryButton);
            return;
        }

        NavigateToPage(typeof(LibraryPage), _libraryButton);
    }

    private async System.Threading.Tasks.Task NavigateToRecentAsync()
    {
        if (!await HasLibraryAsync())
        {
            NavigateToPage(typeof(SetupRequiredPage), _recentButton);
            return;
        }

        NavigateToPage(typeof(RecentPage), _recentButton);
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
        foreach (var button in new[] { _homeButton, _libraryButton, _recentButton, _settingsButton })
        {
            var selected = button == selectedButton;
            button.Background = selected ? FluentTheme.AccentSoft : new SolidColorBrush(Microsoft.UI.Colors.Transparent);
            button.BorderBrush = selected ? FluentTheme.AccentSoft : new SolidColorBrush(Microsoft.UI.Colors.Transparent);
        }
    }
}
