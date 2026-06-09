using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using MediaTree.Windows.Models;
using MediaTree.Windows.Services;
using MediaTree.Windows.Styles;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Navigation;

namespace MediaTree.Windows.Views;

public sealed partial class FolderPage : Page
{
    private sealed record SeasonTab(string Name, string Path, int Count);

    private readonly TextBlock _headerSubtitleText;
    private readonly TextBlock _headerTitleText;
    private readonly TextBlock _loadingText;
    private readonly GridView _moviesGrid;
    private readonly StackPanel _seasonTabs;
    private readonly ComboBox _sortBox;
    private readonly TextBlock _statusText;
    private List<MovieDto> _allMovies = [];
    private List<MovieDto> _specialMovies = [];
    private string _folderPath = "";
    private string _mediaRoot = "";
    private string _seasonFilter = "";
    private string _title = "";
    private bool _showSpecials;
    private bool _specialsSelected;
    private int _specialCount;
    private int _loadGeneration;

    public FolderPage()
    {
        (_headerTitleText, _headerSubtitleText, _seasonTabs, _sortBox, _moviesGrid, _loadingText, _statusText) = BuildContent();
    }

    private (TextBlock headerTitleText, TextBlock headerSubtitleText, StackPanel seasonTabs, ComboBox sortBox, GridView moviesGrid, TextBlock loadingText, TextBlock statusText) BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "FolderPage");

        var root = new Grid
        {
            Padding = new Thickness(28),
            RowSpacing = 16,
            Background = FluentTheme.Canvas,
            RequestedTheme = ElementTheme.Light,
        };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

        var headerStack = new StackPanel { Spacing = 14 };
        var header = new Grid { ColumnSpacing = 16, RowSpacing = 12 };
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        header.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        header.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });
        header.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });

        var backButton = FluentTheme.ApplyButton(new Button
        {
            Content = "返回首页",
            VerticalAlignment = VerticalAlignment.Center,
        });
        AutomationProperties.SetAutomationId(backButton, "FolderBackHome");
        backButton.Click += (_, _) => ShellPage.Current?.NavigateToLibrary();
        header.Children.Add(backButton);

        var titleStack = new StackPanel { Spacing = 4 };
        Grid.SetColumn(titleStack, 1);
        titleStack.Children.Add(new TextBlock
        {
            Text = "Folder",
            FontSize = 12,
            Foreground = FluentTheme.Accent,
        });
        var headerTitleText = new TextBlock
        {
            Text = "目录",
            FontSize = 28,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(headerTitleText, "FolderHeaderTitle");
        titleStack.Children.Add(headerTitleText);
        var headerSubtitleText = new TextBlock
        {
            Text = "",
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(headerSubtitleText, "FolderHeaderSubtitle");
        titleStack.Children.Add(headerSubtitleText);
        header.Children.Add(titleStack);

        var sortBox = new ComboBox
        {
            Header = "排序",
            MinWidth = 160,
            VerticalAlignment = VerticalAlignment.Bottom,
        };
        AutomationProperties.SetAutomationId(sortBox, "FolderSort");
        BrowsePage.AddSortOptions(sortBox, browseLabels: false);
        sortBox.SelectedIndex = 0;
        sortBox.SelectionChanged += OnSortChanged;
        Grid.SetColumn(sortBox, 2);
        header.Children.Add(sortBox);
        headerStack.Children.Add(header);

        var seasonScroll = new ScrollViewer
        {
            HorizontalScrollBarVisibility = ScrollBarVisibility.Auto,
            HorizontalScrollMode = ScrollMode.Auto,
            VerticalScrollBarVisibility = ScrollBarVisibility.Disabled,
            VerticalScrollMode = ScrollMode.Disabled,
        };
        var seasonTabs = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 8,
        };
        AutomationProperties.SetAutomationId(seasonTabs, "FolderSeasonTabs");
        seasonScroll.Content = seasonTabs;
        headerStack.Children.Add(seasonScroll);

        root.Children.Add(FluentTheme.Card(headerStack, new Thickness(16)));

        root.SizeChanged += (_, args) => ApplyFolderResponsiveLayout(
            args.NewSize.Width,
            root,
            header,
            backButton,
            titleStack,
            sortBox);

        var statusText = new TextBlock
        {
            Text = "",
            Visibility = Visibility.Collapsed,
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(statusText, "FolderStatusText");
        Grid.SetRow(statusText, 1);
        root.Children.Add(statusText);

        var content = new Grid();
        Grid.SetRow(content, 2);
        var moviesGrid = new GridView
        {
            IsItemClickEnabled = false,
            SelectionMode = ListViewSelectionMode.None,
            Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent),
        };
        AutomationProperties.SetAutomationId(moviesGrid, "FolderMoviesGrid");
        content.Children.Add(moviesGrid);

        var loadingText = new TextBlock
        {
            Text = "正在加载...",
            Visibility = Visibility.Collapsed,
            Margin = new Thickness(12),
            Foreground = FluentTheme.TextSecondary,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
        };
        AutomationProperties.SetAutomationId(loadingText, "FolderLoadingText");
        content.Children.Add(loadingText);
        root.Children.Add(content);

        Content = root;
        return (headerTitleText, headerSubtitleText, seasonTabs, sortBox, moviesGrid, loadingText, statusText);
    }

    private static void ApplyFolderResponsiveLayout(
        double width,
        Grid root,
        Grid header,
        Button backButton,
        StackPanel titleStack,
        ComboBox sortBox)
    {
        var compact = width < FluentTheme.CompactBreakpoint;
        root.Padding = FluentTheme.PagePadding(width);
        header.ColumnDefinitions[0].Width = compact ? new GridLength(1, GridUnitType.Star) : GridLength.Auto;
        header.ColumnDefinitions[1].Width = compact ? new GridLength(0) : new GridLength(1, GridUnitType.Star);
        header.ColumnDefinitions[2].Width = compact ? new GridLength(0) : GridLength.Auto;
        header.RowDefinitions[1].Height = compact ? GridLength.Auto : new GridLength(0);
        header.RowDefinitions[2].Height = compact ? GridLength.Auto : new GridLength(0);

        Grid.SetColumn(backButton, 0);
        Grid.SetRow(backButton, 0);
        Grid.SetColumn(titleStack, compact ? 0 : 1);
        Grid.SetRow(titleStack, compact ? 1 : 0);
        Grid.SetColumn(sortBox, compact ? 0 : 2);
        Grid.SetRow(sortBox, compact ? 2 : 0);
        backButton.HorizontalAlignment = compact ? HorizontalAlignment.Left : HorizontalAlignment.Left;
        sortBox.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Left;
        sortBox.MinWidth = compact ? 0 : 160;
    }

    protected override async void OnNavigatedTo(NavigationEventArgs args)
    {
        base.OnNavigatedTo(args);
        if (args.Parameter is FolderNavigationParameter parameter)
        {
            _folderPath = parameter.FolderPath;
            _mediaRoot = parameter.MediaRoot;
            _title = parameter.Title;
        }

        await LoadAsync();
    }

    private async System.Threading.Tasks.Task LoadAsync()
    {
        var generation = ++_loadGeneration;
        try
        {
            SetLoading(true);
            _statusText.Visibility = Visibility.Collapsed;
            _moviesGrid.Items.Clear();
            _seasonTabs.Children.Clear();
            _seasonFilter = "";
            _specialsSelected = false;
            _specialMovies = [];
            _specialCount = 0;
            _showSpecials = false;

            var sort = CurrentSort();
            var response = await AppServices.Movie.GetMoviesAsync(_mediaRoot, _folderPath, "", sort, 2000, 0);
            var specials = string.IsNullOrWhiteSpace(_folderPath)
                ? new FolderSpecialsResponseDto()
                : await AppServices.Movie.GetFolderSpecialsAsync(_folderPath, _mediaRoot, includeMovies: true);
            if (generation != _loadGeneration)
            {
                return;
            }

            _allMovies = SortMovies(response.Movies, sort).ToList();
            _showSpecials = specials.ShowSpecials;
            _specialCount = specials.SpecialCount;
            _specialMovies = SortMovies(specials.Movies, sort).ToList();
            _headerTitleText.Text = string.IsNullOrWhiteSpace(_title) ? FolderTitleFromPath(_folderPath) : _title;
            RenderSeasonTabs();
            RenderMovies();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load native folder page.");
            ShowStatus($"加载目录失败：{ex.Message}", true);
        }
        finally
        {
            if (generation == _loadGeneration)
            {
                SetLoading(false);
            }
        }
    }

    private void RenderSeasonTabs()
    {
        _seasonTabs.Children.Clear();
        var tabs = BuildSeasonTabs().ToList();
        if (tabs.Count == 0 && _specialCount <= 0)
        {
            _seasonTabs.Visibility = Visibility.Collapsed;
            return;
        }

        _seasonTabs.Visibility = Visibility.Visible;
        _seasonTabs.Children.Add(CreateSeasonButton($"全部 ({_allMovies.Count})", ""));
        foreach (var tab in tabs)
        {
            _seasonTabs.Children.Add(CreateSeasonButton($"{tab.Name} ({tab.Count})", tab.Path));
        }

        if (_specialCount > 0)
        {
            _seasonTabs.Children.Add(CreateSpecialsButton($"花絮 ({_specialCount})"));
        }
    }

    private Button CreateSeasonButton(string label, string path)
    {
        var button = FluentTheme.ApplyButton(new Button
        {
            Content = label,
            Tag = path,
        }, path == _seasonFilter ? FluentButtonStyle.Accent : FluentButtonStyle.Standard);
        AutomationProperties.SetAutomationId(button, string.IsNullOrWhiteSpace(path) ? "FolderSeason_All" : $"FolderSeason_{SanitizeAutomationId(path)}");
        button.Click += (_, _) =>
        {
            _specialsSelected = false;
            _seasonFilter = path;
            RenderSeasonTabs();
            RenderMovies();
        };
        return button;
    }

    private Button CreateSpecialsButton(string label)
    {
        var button = FluentTheme.ApplyButton(new Button
        {
            Content = label,
        }, _specialsSelected ? FluentButtonStyle.Accent : FluentButtonStyle.Standard);
        AutomationProperties.SetAutomationId(button, "FolderSeason_Specials");
        button.Click += async (_, _) => await SelectSpecialsAsync();
        return button;
    }

    private async System.Threading.Tasks.Task SelectSpecialsAsync()
    {
        try
        {
            if (!_showSpecials && !string.IsNullOrWhiteSpace(_folderPath))
            {
                await AppServices.Movie.SetFolderSpecialsAsync(_folderPath, _mediaRoot, true);
                var specials = await AppServices.Movie.GetFolderSpecialsAsync(_folderPath, _mediaRoot, includeMovies: true);
                _showSpecials = specials.ShowSpecials;
                _specialCount = specials.SpecialCount;
                _specialMovies = SortMovies(specials.Movies, CurrentSort()).ToList();
            }

            _specialsSelected = true;
            _seasonFilter = "";
            RenderSeasonTabs();
            RenderMovies();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to show native folder specials.");
            ShowStatus($"花絮加载失败：{ex.Message}", true);
        }
    }

    private void RenderMovies()
    {
        _moviesGrid.Items.Clear();
        var movies = _specialsSelected
            ? _specialMovies
            : string.IsNullOrWhiteSpace(_seasonFilter)
            ? _allMovies
            : _allMovies.Where(movie => IsInSeason(movie, _seasonFilter)).ToList();

        foreach (var movie in movies)
        {
            _moviesGrid.Items.Add(CreateEpisodeCardAsync(movie));
        }

        _headerSubtitleText.Text = _specialsSelected ? $"{movies.Count} 个花絮" : $"{movies.Count} 部影片";
        if (movies.Count == 0)
        {
            ShowStatus(_specialsSelected ? "此文件夹下没有花絮" : "此文件夹下没有影片", false);
        }
        else
        {
            _statusText.Visibility = Visibility.Collapsed;
        }
    }

    private UIElement CreateEpisodeCardAsync(MovieDto movie)
    {
        var stack = new StackPanel
        {
            Width = 184,
            Margin = new Thickness(6),
            Spacing = 8,
        };

        var cardHost = new Grid();
        var placeholder = new TextBlock
        {
            Text = "正在加载封面...",
            Height = HasEpisodeStill(movie) ? 100 : 252,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Foreground = FluentTheme.TextTertiary,
        };
        cardHost.Children.Add(placeholder);
        stack.Children.Add(cardHost);

        _ = LoadEpisodeCardAsync(movie, cardHost);
        return stack;
    }

    private async System.Threading.Tasks.Task LoadEpisodeCardAsync(MovieDto movie, Grid cardHost)
    {
        var card = BrowsePage.CreateMovieCard(await BrowsePage.CreateMovieCardItemAsync(movie, "folder"));
        AutomationProperties.SetAutomationId(card, $"FolderMovieCard_{movie.Id}");
        cardHost.Children.Clear();
        cardHost.Children.Add(card);
    }

    private IEnumerable<SeasonTab> BuildSeasonTabs()
    {
        var tabs = new Dictionary<string, SeasonTab>(StringComparer.OrdinalIgnoreCase);
        foreach (var movie in _allMovies)
        {
            var levels = movie.FolderLevels ?? "";
            if (string.IsNullOrWhiteSpace(levels) || string.Equals(levels, _folderPath, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var relative = levels.StartsWith(_folderPath + "/", StringComparison.OrdinalIgnoreCase)
                ? levels[(_folderPath.Length + 1)..]
                : "";
            var top = relative.Split('/', StringSplitOptions.RemoveEmptyEntries).FirstOrDefault();
            if (string.IsNullOrWhiteSpace(top))
            {
                continue;
            }

            var path = $"{_folderPath}/{top}";
            if (!tabs.ContainsKey(path))
            {
                tabs[path] = new SeasonTab(top, path, 0);
            }

            var current = tabs[path];
            tabs[path] = current with { Count = current.Count + 1 };
        }

        return tabs.Values.OrderBy(tab => SeasonSortKey(tab.Name)).ThenBy(tab => tab.Name, StringComparer.CurrentCultureIgnoreCase);
    }

    private static bool IsInSeason(MovieDto movie, string seasonPath)
    {
        var levels = movie.FolderLevels ?? "";
        return string.Equals(levels, seasonPath, StringComparison.OrdinalIgnoreCase)
            || levels.StartsWith(seasonPath + "/", StringComparison.OrdinalIgnoreCase);
    }

    private static bool HasEpisodeStill(MovieDto movie)
        => string.Equals(movie.TmdbType, "tv", StringComparison.OrdinalIgnoreCase)
            && movie.TmdbEpisode.HasValue
            && !string.IsNullOrWhiteSpace(movie.EpisodeStill);

    private IEnumerable<MovieDto> SortMovies(IEnumerable<MovieDto> movies, string sort)
        => sort switch
        {
            "name" => movies.OrderBy(EpisodeSortKey).ThenBy(movie => movie.BestTitle, StringComparer.CurrentCultureIgnoreCase),
            "release_date_desc" => movies.OrderByDescending(movie => movie.ReleaseDate ?? "").ThenBy(EpisodeSortKey),
            "release_date_asc" => movies.OrderBy(movie => movie.ReleaseDate ?? "").ThenBy(EpisodeSortKey),
            "created_asc" => movies,
            "random" => movies.OrderBy(_ => Guid.NewGuid()),
            _ => movies,
        };

    private static int EpisodeSortKey(MovieDto movie)
    {
        if (movie.TmdbEpisode is > 0)
        {
            return movie.TmdbEpisode.Value;
        }

        if (movie.EpisodeNumber is > 0)
        {
            return movie.EpisodeNumber.Value;
        }

        var text = string.Join(" ", new[] { movie.DisplayTitle, movie.EpisodeTitle, movie.Code, movie.Path }.Where(value => !string.IsNullOrWhiteSpace(value)));
        var match = Regex.Match(text, @"[Ss]\d{1,2}\s*[Ee](\d{1,4})|(?:EP?|第)\s*0*(\d{1,4})\s*(?:集|話|话)?", RegexOptions.IgnoreCase);
        if (match.Success && int.TryParse(string.IsNullOrWhiteSpace(match.Groups[1].Value) ? match.Groups[2].Value : match.Groups[1].Value, out var value))
        {
            return value;
        }

        return int.MaxValue;
    }

    private static int SeasonSortKey(string label)
    {
        var match = Regex.Match(label, @"(?:S|Season\s*|第)\s*0*(\d{1,3})", RegexOptions.IgnoreCase);
        return match.Success && int.TryParse(match.Groups[1].Value, out var value) ? value : int.MaxValue;
    }

    private async void OnSortChanged(object sender, SelectionChangedEventArgs args)
    {
        if (IsLoaded)
        {
            await LoadAsync();
        }
    }

    private string CurrentSort()
        => (_sortBox.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "created_desc";

    private void SetLoading(bool isLoading)
    {
        _loadingText.Visibility = isLoading ? Visibility.Visible : Visibility.Collapsed;
    }

    private void ShowStatus(string message, bool isError)
    {
        _statusText.Text = message;
        _statusText.Foreground = isError ? FluentTheme.Error : FluentTheme.TextSecondary;
        _statusText.Visibility = Visibility.Visible;
    }

    private static string FolderTitleFromPath(string folderPath)
    {
        if (string.IsNullOrWhiteSpace(folderPath))
        {
            return "目录";
        }

        var normalized = folderPath.Replace("\\", "/").TrimEnd('/');
        var index = normalized.LastIndexOf("/", StringComparison.Ordinal);
        return index >= 0 ? normalized[(index + 1)..] : normalized;
    }

    private static string SanitizeAutomationId(string value)
        => value.Replace("\\", "_").Replace("/", "_").Replace(":", "_");
}
