using System;
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
    private readonly TextBlock _statusText;
    private readonly TextBlock _titleText;
    private int _movieId;

    public MovieDetailPage()
    {
        (_posterImage, _titleText, _metaText, _progressText, _playButton, _statusText, _overviewText, _pathText) = BuildContent();
    }

    private (Image posterImage, TextBlock titleText, TextBlock metaText, TextBlock progressText, Button playButton, TextBlock statusText, TextBlock overviewText, TextBlock pathText) BuildContent()
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

        var posterImage = new Image { Stretch = Stretch.UniformToFill };
        posterImage.ImageFailed += (_, _) => posterImage.Source = null;
        AutomationProperties.SetAutomationId(posterImage, "DetailPoster");
        var posterCard = new Border
        {
            CornerRadius = new CornerRadius(18),
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

        var playButton = FluentTheme.ApplyButton(new Button
        {
            Content = "播放",
            MinWidth = 120,
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(playButton, "DetailPlayButton");
        playButton.Click += OnPlayClicked;
        detail.Children.Add(playButton);

        var statusText = new TextBlock
        {
            Text = "",
            Visibility = Visibility.Collapsed,
            Foreground = FluentTheme.Error,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(statusText, "DetailStatusText");
        detail.Children.Add(statusText);

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
        scrollViewer.Content = root;
        Content = scrollViewer;
        return (posterImage, titleText, metaText, progressText, playButton, statusText, overviewText, pathText);
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
        _titleText.Text = movie.BestTitle;
        _metaText.Text = $"{movie.ReleaseDate}  {movie.Genre}  {FormatDuration(movie.Duration)}".Trim();
        _overviewText.Text = string.IsNullOrWhiteSpace(movie.Overview) ? "还没有简介。" : movie.Overview;
        _pathText.Text = movie.Path;
        _progressText.Text = progress.ProgressPercent > 0 ? $"已观看 {progress.ProgressPercent:0}%" : "";
        _playButton.Content = progress.Position > 5 ? $"继续播放 {FormatDuration(progress.Position)}" : "播放";
        _playButton.IsEnabled = true;
        _statusText.Visibility = Visibility.Collapsed;

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
