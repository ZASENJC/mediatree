using System.Collections.ObjectModel;
using MediaTree.Windows.Services;
using MediaTree.Windows.Styles;
using MediaTree.Windows.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;

namespace MediaTree.Windows.Views;

public sealed partial class RecentPage : Page
{
    private readonly ObservableCollection<MovieCardItem> _items = [];
    private readonly GridView _recentGrid;

    public RecentPage()
    {
        _recentGrid = BuildContent();
        Loaded += async (_, _) => await LoadAsync();
    }

    private GridView BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "RecentPage");

        var root = new Grid
        {
            Padding = new Thickness(28),
            RowSpacing = 16,
            Background = FluentTheme.Canvas,
            RequestedTheme = ElementTheme.Light,
        };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

        var header = new Grid
        {
            ColumnSpacing = 12,
        };
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        header.Children.Add(new TextBlock
        {
            Text = "最近观看",
            FontSize = 30,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
            TextTrimming = TextTrimming.CharacterEllipsis,
        });

        var refreshButton = FluentTheme.ApplyButton(new Button
        {
            Content = "刷新",
        });
        AutomationProperties.SetAutomationId(refreshButton, "RecentRefreshButton");
        refreshButton.Click += OnRefreshClicked;
        Grid.SetColumn(refreshButton, 1);
        header.Children.Add(refreshButton);
        root.Children.Add(header);
        root.SizeChanged += (_, args) =>
        {
            root.Padding = FluentTheme.PagePadding(args.NewSize.Width);
        };

        var recentGrid = FluentTheme.ApplyGridView(new GridView
        {
            IsItemClickEnabled = true,
            SelectionMode = ListViewSelectionMode.None,
        });
        AutomationProperties.SetAutomationId(recentGrid, "RecentMoviesGrid");
        recentGrid.ItemClick += OnMovieItemClick;
        Grid.SetRow(recentGrid, 1);
        root.Children.Add(recentGrid);

        Content = root;
        return recentGrid;
    }

    private async System.Threading.Tasks.Task LoadAsync()
    {
        _items.Clear();
        _recentGrid.Items.Clear();
        var roots = await AppServices.Library.GetMediaRootsAsync();
        var mediaRoot = roots.Items.Count > 0 ? roots.Items[0].Path : "";
        var response = await AppServices.Movie.GetRecentWatchedAsync(mediaRoot, 80, 0);
        foreach (var movie in response.Movies)
        {
            var item = new MovieCardItem(movie, await AppServices.Api.BuildCoverUrlAsync(movie.Id));
            _items.Add(item);
            _recentGrid.Items.Add(CreateMovieCard(item));
        }
    }

    private async void OnRefreshClicked(object sender, RoutedEventArgs args)
    {
        await LoadAsync();
    }

    private void OnMovieItemClick(object sender, ItemClickEventArgs args)
    {
        if (args.ClickedItem is FrameworkElement { Tag: MovieCardItem item })
        {
            ShellPage.Current?.NavigateToMovie(item.Id);
        }
    }

    private static Border CreateMovieCard(MovieCardItem item)
    {
        var imageHost = new Grid
        {
            Height = 252,
            Background = FluentTheme.LayerAlt,
        };
        imageHost.Children.Add(new Image
        {
            Source = new BitmapImage(new System.Uri(item.CoverUrl)),
            Stretch = Stretch.UniformToFill,
        });

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
            Text = item.ProgressText,
            FontSize = 12,
            Foreground = FluentTheme.Accent,
        });

        var stack = new StackPanel();
        stack.Children.Add(imageHost);
        stack.Children.Add(textStack);

        var card = new Border
        {
            Width = 178,
            Margin = new Thickness(6),
            CornerRadius = FluentTheme.MediaCornerRadius,
            Background = FluentTheme.Layer,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(1),
            Child = stack,
            Tag = item,
        };
        AutomationProperties.SetAutomationId(card, $"RecentMovieCard_{item.Id}");
        return card;
    }

}
