using System;
using System.Collections.Generic;
using System.Linq;
using MediaTree.Windows.Models;
using MediaTree.Windows.Services;
using MediaTree.Windows.Styles;
using MediaTree.Windows.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;

namespace MediaTree.Windows.Views;

public sealed partial class FavoritesPage : Page
{
    private readonly ComboBox _libraryBox;
    private readonly GridView _moviesGrid;
    private readonly ComboBox _sortBox;
    private readonly TextBlock _statusText;
    private readonly TextBlock _subtitleText;
    private IReadOnlyList<MediaRootDto> _activeMediaRoots = [];
    private string _activeMediaRoot = "";
    private int _loadGeneration;
    private bool _hasLoadedLibraries;
    private bool _suppressLibrarySelectionChanged;

    public FavoritesPage()
    {
        NavigationCacheMode = Microsoft.UI.Xaml.Navigation.NavigationCacheMode.Enabled;
        (_libraryBox, _sortBox, _moviesGrid, _statusText, _subtitleText) = BuildContent();
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
    }

    private (ComboBox libraryBox, ComboBox sortBox, GridView moviesGrid, TextBlock statusText, TextBlock subtitleText) BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "FavoritesPage");

        var root = new Grid
        {
            Padding = new Thickness(28),
            RowSpacing = 16,
            Background = FluentTheme.Canvas,
            RequestedTheme = ElementTheme.Light,
        };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

        var header = new Grid { ColumnSpacing = 16, RowSpacing = 12 };
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        header.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        header.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });

        var titleStack = new StackPanel { Spacing = 4 };
        titleStack.Children.Add(new TextBlock
        {
            Text = "Library",
            FontSize = 12,
            Foreground = FluentTheme.Accent,
        });
        titleStack.Children.Add(new TextBlock
        {
            Text = "我的收藏",
            FontSize = 28,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
        });
        var subtitleText = new TextBlock
        {
            Text = "",
            Foreground = FluentTheme.TextSecondary,
        };
        AutomationProperties.SetAutomationId(subtitleText, "FavoritesHeaderSubtitle");
        titleStack.Children.Add(subtitleText);
        header.Children.Add(titleStack);

        var controls = new Grid
        {
            ColumnSpacing = 10,
            HorizontalAlignment = HorizontalAlignment.Right,
            VerticalAlignment = VerticalAlignment.Bottom,
        };
        controls.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        controls.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var libraryBox = FluentTheme.ApplyComboBox(new ComboBox
        {
            Header = "媒体库",
            MinWidth = 220,
        });
        AutomationProperties.SetAutomationId(libraryBox, "FavoritesLibrarySelector");
        libraryBox.SelectionChanged += OnLibraryChanged;
        controls.Children.Add(libraryBox);

        var sortBox = FluentTheme.ApplyComboBox(new ComboBox
        {
            Header = "排序",
            MinWidth = 160,
        });
        AutomationProperties.SetAutomationId(sortBox, "FavoritesSort");
        BrowsePage.AddSortOptions(sortBox, browseLabels: false);
        sortBox.SelectedIndex = 0;
        sortBox.SelectionChanged += OnSortChanged;
        Grid.SetColumn(sortBox, 1);
        controls.Children.Add(sortBox);

        Grid.SetColumn(controls, 1);
        header.Children.Add(controls);
        root.Children.Add(FluentTheme.Card(header, new Thickness(16)));

        root.SizeChanged += (_, args) => ApplyFavoritesResponsiveLayout(
            args.NewSize.Width,
            root,
            header,
            controls,
            libraryBox,
            sortBox);

        var content = new Grid();
        Grid.SetRow(content, 1);
        var moviesGrid = FluentTheme.ApplyGridView(new GridView
        {
            IsItemClickEnabled = false,
            SelectionMode = ListViewSelectionMode.None,
        });
        AutomationProperties.SetAutomationId(moviesGrid, "FavoritesMoviesGrid");
        content.Children.Add(moviesGrid);

        var statusText = new TextBlock
        {
            Text = "",
            Visibility = Visibility.Collapsed,
            Foreground = FluentTheme.TextSecondary,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(statusText, "FavoritesStatusText");
        content.Children.Add(statusText);
        root.Children.Add(content);

        Content = root;
        return (libraryBox, sortBox, moviesGrid, statusText, subtitleText);
    }

    private static void ApplyFavoritesResponsiveLayout(
        double width,
        Grid root,
        Grid header,
        Grid controls,
        ComboBox libraryBox,
        ComboBox sortBox)
    {
        var compact = width < FluentTheme.CompactBreakpoint;
        root.Padding = FluentTheme.PagePadding(width);
        header.ColumnDefinitions[1].Width = compact ? new GridLength(0) : GridLength.Auto;
        header.RowDefinitions[1].Height = compact ? GridLength.Auto : new GridLength(0);
        Grid.SetColumn(controls, compact ? 0 : 1);
        Grid.SetRow(controls, compact ? 1 : 0);
        controls.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Right;
        Grid.SetColumnSpan(controls, compact ? 2 : 1);
        controls.ColumnDefinitions[0].Width = compact ? new GridLength(1, GridUnitType.Star) : GridLength.Auto;
        controls.ColumnDefinitions[1].Width = compact ? new GridLength(0.72, GridUnitType.Star) : GridLength.Auto;
        libraryBox.MinWidth = compact ? 0 : 220;
        sortBox.MinWidth = compact ? 108 : 160;
        libraryBox.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Left;
        sortBox.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Left;
    }

    private async System.Threading.Tasks.Task LoadLibrariesAsync(bool forceRefresh = false)
    {
        if (_hasLoadedLibraries && !forceRefresh)
        {
            return;
        }

        var previousMediaRoot = _activeMediaRoot;
        _suppressLibrarySelectionChanged = true;
        try
        {
            _libraryBox.Items.Clear();
            _libraryBox.Items.Add(new ComboBoxItem { Content = "全部媒体库", Tag = "" });
            var roots = await AppServices.Media.Library.GetMediaRootsAsync();
            _activeMediaRoots = BrowseLibraryPresenter.DistinctMediaRoots(roots.Items);
            foreach (var root in _activeMediaRoots)
            {
                _libraryBox.Items.Add(new ComboBoxItem
                {
                    Content = string.IsNullOrWhiteSpace(root.Label) ? root.Path : root.Label,
                    Tag = root.Path,
                });
            }

            var selectedRoot = _activeMediaRoots.Any(root => LibraryService.RootsMatch(root.Path, previousMediaRoot))
                ? previousMediaRoot
                : "";
            var selectedIndex = 0;
            if (!string.IsNullOrWhiteSpace(selectedRoot))
            {
                selectedIndex = _activeMediaRoots
                    .Select((root, index) => new { root, index })
                    .First(item => LibraryService.RootsMatch(item.root.Path, selectedRoot))
                    .index + 1;
            }

            _libraryBox.SelectedIndex = selectedIndex;
            _activeMediaRoot = selectedRoot;
        }
        finally
        {
            _suppressLibrarySelectionChanged = false;
        }

        await LoadFavoritesAsync();
        _hasLoadedLibraries = true;
    }

    private async System.Threading.Tasks.Task LoadFavoritesAsync()
    {
        var generation = ++_loadGeneration;
        try
        {
            ShowStatus("正在加载...", false);
            _moviesGrid.Items.Clear();
            var sort = (_sortBox.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "created_desc";
            var response = await LoadActiveFavoritesAsync(sort, 200);
            if (generation != _loadGeneration)
            {
                return;
            }

            foreach (var movie in response.Movies)
            {
                var cover = "";
                try
                {
                    cover = await AppServices.Media.Api.BuildCoverUrlAsync(movie.Id);
                }
                catch (Exception ex)
                {
                    ShellLogger.Error(ex, $"Failed to build native favorite cover URL for movie {movie.Id}.");
                }

                _moviesGrid.Items.Add(CreateFavoriteMovieCard(new MovieCardItem(movie, cover)));
            }

            _subtitleText.Text = $"共 {response.Total} 部";
            _statusText.Visibility = response.Movies.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
            if (response.Movies.Count == 0)
            {
                _statusText.Text = "还没有收藏影片";
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load native favorites.");
            ShowStatus($"加载收藏失败：{ex.Message}", true);
        }
    }

    private async System.Threading.Tasks.Task<MoviesResponseDto> LoadActiveFavoritesAsync(string sort, int limit)
    {
        if (!string.IsNullOrWhiteSpace(_activeMediaRoot))
        {
            return await AppServices.Media.Movie.GetFavoritesAsync(_activeMediaRoot, sort, limit, 0);
        }

        var roots = _activeMediaRoots.ToList();
        if (roots.Count == 0)
        {
            return new MoviesResponseDto();
        }

        var responses = await System.Threading.Tasks.Task.WhenAll(roots.Select(root => AppServices.Media.Movie.GetFavoritesAsync(root.Path, sort, limit, 0)));
        return BrowseLibraryPresenter.MergeMovieResponses(responses, sort, limit);
    }

    private UIElement CreateFavoriteMovieCard(MovieCardItem item)
    {
        var card = BrowsePage.CreateMovieCard(item, CreateContextMenuHost(async () => await LoadFavoritesAsync()));
        AutomationProperties.SetAutomationId(card, $"FavoriteMovieCard_{item.Id}");

        var removeButton = FluentTheme.ApplyButton(new Button
        {
            Content = "取消收藏",
            HorizontalAlignment = HorizontalAlignment.Stretch,
            Margin = new Thickness(6, 0, 6, 6),
        });
        AutomationProperties.SetAutomationId(removeButton, $"FavoriteRemove_{item.Id}");
        removeButton.Click += async (_, _) => await RemoveFavoriteAsync(item.Id);

        var stack = new StackPanel();
        stack.Children.Add(card);
        stack.Children.Add(removeButton);
        return stack;
    }

    private async System.Threading.Tasks.Task RemoveFavoriteAsync(int movieId)
    {
        try
        {
            await AppServices.Media.Movie.RemoveTagAsync(movieId, "favorite");
            await LoadFavoritesAsync();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Failed to remove native favorite tag for movie {movieId}.");
            ShowStatus($"取消收藏失败：{ex.Message}", true);
        }
    }

    private async void OnLibraryChanged(object sender, SelectionChangedEventArgs args)
    {
        if (_suppressLibrarySelectionChanged)
        {
            return;
        }

        _activeMediaRoot = (_libraryBox.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "";
        await LoadFavoritesAsync();
    }

    private async void OnSortChanged(object sender, SelectionChangedEventArgs args)
    {
        if (IsLoaded)
        {
            await LoadFavoritesAsync();
        }
    }

    private void ShowStatus(string message, bool isError)
    {
        _statusText.Text = message;
        _statusText.Foreground = isError ? FluentTheme.Error : FluentTheme.TextSecondary;
        _statusText.Visibility = Visibility.Visible;
    }

    private async void OnLoaded(object sender, RoutedEventArgs args)
    {
        AppServices.Media.Library.LibrariesChanged -= OnLibrariesChanged;
        AppServices.Media.Library.LibrariesChanged += OnLibrariesChanged;
        await LoadLibrariesAsync();
    }

    private void OnUnloaded(object sender, RoutedEventArgs args)
    {
        AppServices.Media.Library.LibrariesChanged -= OnLibrariesChanged;
    }

    private void OnLibrariesChanged(object? sender, EventArgs args)
    {
        if (DispatcherQueue.HasThreadAccess)
        {
            _ = LoadLibrariesAsync(forceRefresh: true);
            return;
        }

        _ = DispatcherQueue.TryEnqueue(() => _ = LoadLibrariesAsync(forceRefresh: true));
    }

    private MediaContextMenuHost CreateContextMenuHost(Func<System.Threading.Tasks.Task> refreshAsync)
        => new()
        {
            XamlRoot = XamlRoot,
            ShowStatus = ShowStatus,
            RefreshAsync = refreshAsync,
        };
}
