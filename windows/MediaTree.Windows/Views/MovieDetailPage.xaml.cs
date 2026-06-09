using System;
using System.Collections.Generic;
using System.Linq;
using MediaTree.Windows.Models;
using MediaTree.Windows.Services;
using MediaTree.Windows.Styles;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;
using Microsoft.UI.Xaml.Navigation;

namespace MediaTree.Windows.Views;

public sealed partial class MovieDetailPage : Page
{
    private readonly TextBlock _metaText;
    private readonly TextBlock _overviewText;
    private readonly TextBlock _pathText;
    private readonly Button _playButton;
    private readonly Image _posterImage;
    private readonly TextBlock _progressText;
    private readonly Button _scrapeButton;
    private readonly Border _specialsCard;
    private readonly GridView _specialsGrid;
    private readonly StackPanel _specialsSection;
    private readonly Button _specialsToggleButton;
    private readonly TextBlock _specialsTitleText;
    private readonly TextBlock _statusText;
    private readonly TextBlock _titleText;
    private int _movieId;
    private MovieDto? _loadedMovie;
    private bool _specialsExpanded;
    private List<MovieDto> _specialMovies = [];

    public MovieDetailPage()
    {
        (_posterImage, _titleText, _metaText, _progressText, _playButton, _scrapeButton, _statusText, _specialsCard, _specialsSection, _specialsTitleText, _specialsToggleButton, _specialsGrid, _overviewText, _pathText) = BuildContent();
    }

    private (Image posterImage, TextBlock titleText, TextBlock metaText, TextBlock progressText, Button playButton, Button scrapeButton, TextBlock statusText, Border specialsCard, StackPanel specialsSection, TextBlock specialsTitleText, Button specialsToggleButton, GridView specialsGrid, TextBlock overviewText, TextBlock pathText) BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "MovieDetailPage");

        var scrollViewer = new ScrollViewer();
        var root = new Grid
        {
            Padding = new Thickness(32),
            ColumnSpacing = 28,
            Background = FluentTheme.Canvas,
            RequestedTheme = ElementTheme.Light,
        };
        root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(280) });
        root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });

        var posterImage = new Image { Stretch = Stretch.UniformToFill };
        posterImage.ImageFailed += (_, _) => posterImage.Source = null;
        AutomationProperties.SetAutomationId(posterImage, "DetailPoster");
        var posterCard = new Border
        {
            CornerRadius = FluentTheme.MediaCornerRadius,
            Background = FluentTheme.LayerAlt,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(1),
            Height = 420,
            VerticalAlignment = VerticalAlignment.Top,
            Child = posterImage,
        };
        root.Children.Add(posterCard);

        var detail = new StackPanel { Spacing = 16 };
        Grid.SetColumn(detail, 1);

        var backButton = FluentTheme.ApplyButton(new Button
        {
            Content = "返回媒体库",
            HorizontalAlignment = HorizontalAlignment.Left,
        });
        AutomationProperties.SetAutomationId(backButton, "DetailBackButton");
        backButton.Click += OnBackClicked;
        detail.Children.Add(backButton);

        var titleText = new TextBlock
        {
            FontSize = 34,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(titleText, "DetailTitle");
        detail.Children.Add(titleText);

        var metaText = new TextBlock
        {
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(metaText, "DetailMeta");
        detail.Children.Add(metaText);

        var progressText = new TextBlock
        {
            Text = "",
            Foreground = FluentTheme.Accent,
            FontSize = 13,
        };
        AutomationProperties.SetAutomationId(progressText, "DetailProgressText");
        detail.Children.Add(progressText);

        var actionRow = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 10,
        };

        var playButton = FluentTheme.ApplyButton(new Button
        {
            Content = "播放",
            MinWidth = 120,
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(playButton, "DetailPlayButton");
        playButton.Click += OnPlayClicked;
        actionRow.Children.Add(playButton);

        var scrapeButton = FluentTheme.ApplyButton(new Button
        {
            Content = "手动刮削",
        });
        AutomationProperties.SetAutomationId(scrapeButton, "DetailManualScrapeButton");
        scrapeButton.Click += OnManualScrapeClicked;
        actionRow.Children.Add(scrapeButton);
        actionRow.SizeChanged += (_, args) => ApplyDetailActionLayout(args.NewSize.Width, actionRow);
        detail.Children.Add(actionRow);

        var statusText = new TextBlock
        {
            Text = "",
            Visibility = Visibility.Collapsed,
            Foreground = FluentTheme.Error,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(statusText, "DetailStatusText");
        detail.Children.Add(statusText);

        var specialsSection = new StackPanel
        {
            Spacing = 10,
            Visibility = Visibility.Collapsed,
        };
        AutomationProperties.SetAutomationId(specialsSection, "DetailSpecialsSection");
        var specialsHeader = new Grid { ColumnSpacing = 12 };
        specialsHeader.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        specialsHeader.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var specialsTitleText = new TextBlock
        {
            Text = "花絮",
            FontSize = 20,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
            TextWrapping = TextWrapping.WrapWholeWords,
            VerticalAlignment = VerticalAlignment.Center,
        };
        AutomationProperties.SetAutomationId(specialsTitleText, "DetailSpecialsTitle");
        specialsHeader.Children.Add(specialsTitleText);
        var specialsToggleButton = FluentTheme.ApplyButton(new Button
        {
            Content = "展开",
        });
        AutomationProperties.SetAutomationId(specialsToggleButton, "DetailSpecialsToggle");
        specialsToggleButton.Click += OnSpecialsToggleClicked;
        Grid.SetColumn(specialsToggleButton, 1);
        specialsHeader.Children.Add(specialsToggleButton);
        specialsSection.Children.Add(specialsHeader);

        var specialsGrid = FluentTheme.ApplyGridView(new GridView
        {
            IsItemClickEnabled = false,
            SelectionMode = ListViewSelectionMode.None,
            Visibility = Visibility.Collapsed,
        });
        AutomationProperties.SetAutomationId(specialsGrid, "DetailSpecialsGrid");
        specialsSection.Children.Add(specialsGrid);
        var specialsCard = FluentTheme.Card(specialsSection, new Thickness(16));
        specialsCard.Visibility = Visibility.Collapsed;
        detail.Children.Add(specialsCard);

        detail.Children.Add(new TextBlock
        {
            Text = "简介",
            FontSize = 20,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
        });

        var overviewText = new TextBlock
        {
            TextWrapping = TextWrapping.WrapWholeWords,
            MaxWidth = 760,
            Foreground = FluentTheme.TextPrimary,
        };
        AutomationProperties.SetAutomationId(overviewText, "DetailOverview");
        detail.Children.Add(overviewText);

        var pathText = new TextBlock
        {
            Foreground = FluentTheme.TextTertiary,
            FontSize = 12,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(pathText, "DetailPath");
        detail.Children.Add(pathText);

        root.Children.Add(detail);
        root.SizeChanged += (_, args) => ApplyDetailResponsiveLayout(args.NewSize.Width, root, posterCard, detail);
        scrollViewer.Content = root;
        Content = scrollViewer;
        return (posterImage, titleText, metaText, progressText, playButton, scrapeButton, statusText, specialsCard, specialsSection, specialsTitleText, specialsToggleButton, specialsGrid, overviewText, pathText);
    }

    private static void ApplyDetailActionLayout(double width, StackPanel actions)
    {
        var compact = width < 420;
        actions.Orientation = compact ? Orientation.Vertical : Orientation.Horizontal;
        foreach (var child in actions.Children.OfType<FrameworkElement>())
        {
            child.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Left;
        }
    }

    private static void ApplyDetailResponsiveLayout(double width, Grid root, Border posterCard, StackPanel detail)
    {
        var compact = width < FluentTheme.CompactBreakpoint;
        root.Padding = FluentTheme.PagePadding(width);
        root.RowSpacing = compact ? 20 : 0;
        root.ColumnDefinitions[0].Width = compact ? new GridLength(1, GridUnitType.Star) : new GridLength(280);
        root.ColumnDefinitions[1].Width = compact ? new GridLength(0) : new GridLength(1, GridUnitType.Star);
        root.RowDefinitions[1].Height = compact ? GridLength.Auto : new GridLength(0);

        Grid.SetColumn(posterCard, 0);
        Grid.SetRow(posterCard, 0);
        Grid.SetColumn(detail, compact ? 0 : 1);
        Grid.SetRow(detail, compact ? 1 : 0);

        posterCard.Height = compact ? Math.Min(420, Math.Max(260, width * 1.05)) : 420;
        posterCard.MaxWidth = compact ? 340 : double.PositiveInfinity;
        posterCard.HorizontalAlignment = compact ? HorizontalAlignment.Left : HorizontalAlignment.Stretch;
    }

    protected override async void OnNavigatedTo(NavigationEventArgs args)
    {
        base.OnNavigatedTo(args);
        if (args.Parameter is MovieNavigationParameter parameter)
        {
            _movieId = parameter.MovieId;
        }
        else if (args.Parameter is int id)
        {
            _movieId = id;
        }

        try
        {
            if (_movieId <= 0)
            {
                ShowDetailError("没有找到要打开的影片。");
                return;
            }

            await LoadAsync();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load native movie detail.");
            ShowDetailError($"打开影片失败：{ex.Message}");
        }
    }

    private async System.Threading.Tasks.Task LoadAsync()
    {
        var movie = await AppServices.Movie.GetMovieDetailAsync(_movieId);
        var progress = await AppServices.Movie.GetProgressAsync(_movieId);
        _loadedMovie = movie;
        _titleText.Text = movie.BestTitle;
        _metaText.Text = $"{movie.ReleaseDate}  {movie.Genre}  {FormatDuration(movie.Duration)}".Trim();
        _overviewText.Text = string.IsNullOrWhiteSpace(movie.Overview) ? "还没有简介。" : movie.Overview;
        _pathText.Text = movie.Path;
        _progressText.Text = progress.ProgressPercent > 0 ? $"已观看 {progress.ProgressPercent:0}%" : "";
        _playButton.Content = progress.Position > 5 ? $"继续播放 {FormatDuration(progress.Position)}" : "播放";
        _playButton.IsEnabled = true;
        _scrapeButton.IsEnabled = !movie.IsSpecial;
        _statusText.Visibility = Visibility.Collapsed;
        await LoadSpecialsAsync(movie);

        try
        {
            var cover = await AppServices.Api.BuildCoverUrlAsync(movie.Id);
            _posterImage.Source = Uri.TryCreate(cover, UriKind.Absolute, out var coverUri) ? new BitmapImage(coverUri) : null;
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Failed to load native movie cover for {movie.Id}.");
            _posterImage.Source = null;
        }
    }

    private async System.Threading.Tasks.Task LoadSpecialsAsync(MovieDto movie)
    {
        _specialsExpanded = false;
        _specialMovies = [];
        _specialsGrid.Items.Clear();
        _specialsGrid.Visibility = Visibility.Collapsed;
        _specialsCard.Visibility = Visibility.Collapsed;
        _specialsSection.Visibility = Visibility.Visible;
        _specialsToggleButton.Content = "展开";

        var folder = movie.FolderForSpecials;
        if (string.IsNullOrWhiteSpace(folder))
        {
            return;
        }

        try
        {
            var data = await AppServices.Movie.GetFolderSpecialsAsync(folder, movie.MediaRoot, includeMovies: true);
            _specialMovies = data.Movies
                .OrderBy(item => item.FolderLevels, StringComparer.CurrentCultureIgnoreCase)
                .ThenBy(item => item.BestTitle, StringComparer.CurrentCultureIgnoreCase)
                .ToList();
            if (data.SpecialCount <= 0)
            {
                return;
            }

            _specialsTitleText.Text = $"花絮 ({data.SpecialCount})";
            _specialsCard.Visibility = Visibility.Visible;
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load native detail specials.");
        }
    }

    private async void OnSpecialsToggleClicked(object sender, RoutedEventArgs args)
    {
        _specialsExpanded = !_specialsExpanded;
        _specialsToggleButton.Content = _specialsExpanded ? "收起" : "展开";
        _specialsGrid.Visibility = _specialsExpanded ? Visibility.Visible : Visibility.Collapsed;
        if (!_specialsExpanded || _specialsGrid.Items.Count > 0)
        {
            return;
        }

        foreach (var special in _specialMovies)
        {
            var card = BrowsePage.CreateMovieCard(await BrowsePage.CreateMovieCardItemAsync(special, "detail-specials"));
            AutomationProperties.SetAutomationId(card, $"DetailSpecialCard_{special.Id}");
            _specialsGrid.Items.Add(card);
        }
    }

    private void OnBackClicked(object sender, RoutedEventArgs args)
    {
        ShellPage.Current?.NavigateToLibrary();
    }

    private void OnPlayClicked(object sender, RoutedEventArgs args)
    {
        try
        {
            if (_movieId <= 0)
            {
                ShowDetailError("没有找到要播放的影片。");
                return;
            }

            ShellPage.Current?.NavigateToPlayer(_movieId);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to navigate native movie player.");
            ShowDetailError($"打开播放器失败：{ex.Message}");
        }
    }

    private async void OnManualScrapeClicked(object sender, RoutedEventArgs args)
    {
        if (_loadedMovie is null || _loadedMovie.IsSpecial)
        {
            return;
        }

        await ShowManualScrapeDialogAsync(_loadedMovie);
    }

    private async System.Threading.Tasks.Task ShowManualScrapeDialogAsync(MovieDto movie)
    {
        var queryBox = FluentTheme.ApplyTextInput(new TextBox
        {
            Header = "搜索关键词",
            Text = movie.BestTitle,
            PlaceholderText = "输入片名、原名或编号",
            MinWidth = 0,
        });
        AutomationProperties.SetAutomationId(queryBox, "ManualScrapeQuery");

        var scraperBox = FluentTheme.ApplyComboBox(new ComboBox
        {
            Header = "刮削器",
            MinWidth = 0,
        });
        AddScraperOption(scraperBox, "auto", "自动");
        AddScraperOption(scraperBox, "tmdb_movie", "TMDB 电影");
        AddScraperOption(scraperBox, "tmdb_tv", "TMDB 剧集/番剧");
        AddScraperOption(scraperBox, "tmdb_collection", "TMDB 合集");
        AddScraperOption(scraperBox, "bangumi", "Bangumi");
        AddScraperOption(scraperBox, "javdatabase", "Javdatabase");
        scraperBox.SelectedIndex = 0;
        AutomationProperties.SetAutomationId(scraperBox, "ManualScrapeScraper");

        var resultList = FluentTheme.ApplyListView(new ListView
        {
            SelectionMode = ListViewSelectionMode.Single,
            IsItemClickEnabled = true,
            MaxHeight = 420,
        });
        AutomationProperties.SetAutomationId(resultList, "ManualScrapeResults");

        var statusText = new TextBlock
        {
            Text = "输入关键词后搜索，选择一个结果应用到当前影片。",
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };

        var searchButton = FluentTheme.ApplyButton(new Button
        {
            Content = "搜索",
            HorizontalAlignment = HorizontalAlignment.Left,
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(searchButton, "ManualScrapeSearch");
        searchButton.Click += async (_, _) =>
        {
            var query = queryBox.Text.Trim();
            if (string.IsNullOrWhiteSpace(query))
            {
                statusText.Foreground = FluentTheme.Error;
                statusText.Text = "请先输入搜索关键词。";
                return;
            }

            try
            {
                searchButton.IsEnabled = false;
                statusText.Foreground = FluentTheme.TextSecondary;
                statusText.Text = "正在搜索候选结果...";
                resultList.Items.Clear();
                var scraper = SelectedScraper(scraperBox);
                var response = await AppServices.Movie.SearchScrapeAsync(query, scraper, movie.MediaRoot);
                foreach (var result in response.Results.Select(result => NormalizeScrapeResult(result, scraper)))
                {
                    resultList.Items.Add(CreateScrapeResultRow(result));
                }

                statusText.Text = response.Results.Count == 0 ? "没有找到匹配结果。" : $"找到 {response.Results.Count} 个候选结果。";
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, "Failed to search native manual scrape candidates.");
                statusText.Foreground = FluentTheme.Error;
                statusText.Text = $"搜索失败：{ex.Message}";
            }
            finally
            {
                searchButton.IsEnabled = true;
            }
        };

        var form = new StackPanel { Spacing = 12 };
        form.Children.Add(queryBox);
        form.Children.Add(scraperBox);
        form.Children.Add(searchButton);
        form.Children.Add(statusText);
        form.Children.Add(resultList);

        var dialog = FluentTheme.ApplyContentDialog(new ContentDialog
        {
            Title = "手动刮削",
            Content = new ScrollViewer { Content = form },
            PrimaryButtonText = "应用所选结果",
            CloseButtonText = "取消",
            DefaultButton = ContentDialogButton.Primary,
            XamlRoot = XamlRoot,
        });

        dialog.PrimaryButtonClick += async (_, eventArgs) =>
        {
            if (resultList.SelectedItem is not FrameworkElement { Tag: ScrapeSearchResultDto selected })
            {
                eventArgs.Cancel = true;
                statusText.Foreground = FluentTheme.Error;
                statusText.Text = "请先选择一个候选结果。";
                return;
            }

            eventArgs.Cancel = true;
            try
            {
                dialog.IsPrimaryButtonEnabled = false;
                statusText.Foreground = FluentTheme.TextSecondary;
                statusText.Text = "正在应用刮削结果...";
                var scraper = string.IsNullOrWhiteSpace(selected.Scraper) ? SelectedScraper(scraperBox) : selected.Scraper;
                await AppServices.Movie.ManualScrapeMovieAsync(movie.Id, selected.Title, selected.SourceId, selected.MediaType, scraper);
                dialog.Hide();
                await LoadAsync();
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, "Failed to apply native manual scrape candidate.");
                statusText.Foreground = FluentTheme.Error;
                statusText.Text = $"应用失败：{ex.Message}";
                dialog.IsPrimaryButtonEnabled = true;
            }
        };

        await dialog.ShowAsync();
    }

    private static void AddScraperOption(ComboBox box, string value, string label)
    {
        box.Items.Add(new ComboBoxItem
        {
            Content = label,
            Tag = value,
        });
    }

    private static string SelectedScraper(ComboBox box)
        => box.SelectedItem is ComboBoxItem { Tag: string value } ? value : "auto";

    private static ScrapeSearchResultDto NormalizeScrapeResult(ScrapeSearchResultDto result, string fallbackScraper)
    {
        if (string.IsNullOrWhiteSpace(result.Scraper))
        {
            result.Scraper = fallbackScraper;
        }

        return result;
    }

    private static FrameworkElement CreateScrapeResultRow(ScrapeSearchResultDto result)
    {
        var stack = new StackPanel
        {
            Padding = new Thickness(10),
            Spacing = 4,
        };
        stack.Children.Add(new TextBlock
        {
            Text = string.IsNullOrWhiteSpace(result.Title) ? result.SourceId : result.Title,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
            TextWrapping = TextWrapping.WrapWholeWords,
        });

        var meta = new List<string>();
        if (!string.IsNullOrWhiteSpace(result.Source))
        {
            meta.Add(result.Source);
        }

        if (!string.IsNullOrWhiteSpace(result.MediaType))
        {
            meta.Add(result.MediaType);
        }

        if (!string.IsNullOrWhiteSpace(result.Year))
        {
            meta.Add(result.Year);
        }

        if (!string.IsNullOrWhiteSpace(result.OriginalTitle))
        {
            meta.Add(result.OriginalTitle);
        }

        stack.Children.Add(new TextBlock
        {
            Text = string.Join(" · ", meta),
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        });
        if (!string.IsNullOrWhiteSpace(result.Overview))
        {
            stack.Children.Add(new TextBlock
            {
                Text = result.Overview,
                MaxLines = 3,
                Foreground = FluentTheme.TextTertiary,
                TextWrapping = TextWrapping.WrapWholeWords,
            });
        }

        return new Border
        {
            CornerRadius = FluentTheme.CardCornerRadius,
            Background = FluentTheme.LayerAlt,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(1),
            Margin = new Thickness(0, 0, 0, 8),
            Child = stack,
            Tag = result,
        };
    }

    private void ShowDetailError(string message)
    {
        _statusText.Text = message;
        _statusText.Visibility = Visibility.Visible;
        _playButton.IsEnabled = false;
    }

    private static string FormatDuration(double seconds)
    {
        if (seconds <= 0)
        {
            return "";
        }

        var span = TimeSpan.FromSeconds(seconds);
        return span.TotalHours >= 1 ? $"{(int)span.TotalHours}:{span.Minutes:00}:{span.Seconds:00}" : $"{span.Minutes}:{span.Seconds:00}";
    }

}
