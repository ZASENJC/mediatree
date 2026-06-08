using MediaTree.Windows.Styles;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;

namespace MediaTree.Windows.Views;

public sealed partial class HomePage : Page
{
    public HomePage()
    {
        BuildContent();
    }

    private void BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "HomePage");

        var root = new Grid
        {
            Padding = new Thickness(40),
            RowSpacing = 24,
            RequestedTheme = ElementTheme.Light,
            Background = FluentTheme.Canvas,
        };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

        var header = new StackPanel { Spacing = 8 };
        header.Children.Add(FluentTheme.Title("MediaTree", 36));
        header.Children.Add(FluentTheme.Body("把电脑里的影片和剧集整理成一个本地媒体库。", 16));
        root.Children.Add(header);

        var cards = new Grid { ColumnSpacing = 16, RowSpacing = 16 };
        cards.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        cards.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        cards.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        cards.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        Grid.SetRow(cards, 1);

        var openLibrary = CreateActionButton("打开媒体库", "查看已经整理好的影片和剧集", "HomeOpenLibrary");
        openLibrary.Click += OnOpenLibraryClicked;
        cards.Children.Add(openLibrary);

        var addLibrary = CreateActionButton("添加文件夹", "选择本机视频目录开始整理", "HomeAddLibrary");
        addLibrary.Click += OnAddLibraryClicked;
        Grid.SetColumn(addLibrary, 1);
        cards.Children.Add(addLibrary);

        root.SizeChanged += (_, args) =>
        {
            var compact = args.NewSize.Width < FluentTheme.CompactBreakpoint;
            root.Padding = FluentTheme.SpaciousPagePadding(args.NewSize.Width);
            cards.ColumnDefinitions[1].Width = compact ? new GridLength(0) : new GridLength(1, GridUnitType.Star);
            Grid.SetColumn(addLibrary, compact ? 0 : 1);
            Grid.SetRow(addLibrary, compact ? 1 : 0);
        };

        root.Children.Add(cards);
        Content = root;
    }

    private static Button CreateActionButton(string title, string subtitle, string automationId)
    {
        var content = new StackPanel();
        content.Children.Add(new TextBlock
        {
            Text = title,
            FontSize = 20,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
            TextWrapping = TextWrapping.WrapWholeWords,
        });
        content.Children.Add(new TextBlock
        {
            Text = subtitle,
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        });

        var button = FluentTheme.ApplyButton(new Button
        {
            Content = content,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            MinHeight = 96,
        });
        AutomationProperties.SetAutomationId(button, automationId);
        return button;
    }

    private void OnOpenLibraryClicked(object sender, RoutedEventArgs args)
    {
        ShellPage.Current?.NavigateToLibrary();
    }

    private void OnAddLibraryClicked(object sender, RoutedEventArgs args)
    {
        ShellPage.Current?.NavigateToSetup();
    }

}
