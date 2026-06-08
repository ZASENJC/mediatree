using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MediaTree.Windows.Models;
using MediaTree.Windows.Services;
using MediaTree.Windows.Styles;
using MediaTree.Windows.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;

namespace MediaTree.Windows.Views;

public sealed partial class BrowsePage : Page
{
    private readonly ComboBox _libraryBox;
    private readonly ListView _folderList;
    private readonly GridView _moviesGrid;
    private readonly TextBlock _statusText;
    private readonly TextBox _searchBox;
    private readonly ComboBox _sortBox;
    private readonly TextBlock _subtitleText;
    private readonly TextBlock _titleText;
    private string _activeFolderPath = "";
    private string _activeMediaRoot = "";
    private int _loadGeneration;
    private bool _suppressLibrarySelectionChanged;

    public BrowsePage()
    {
        (_libraryBox, _folderList, _moviesGrid, _statusText, _searchBox, _sortBox, _titleText, _subtitleText) = BuildContent();
        Loaded += async (_, _) => await LoadLibrariesAsync();
    }

    private (ComboBox libraryBox, ListView folderList, GridView moviesGrid, TextBlock statusText, TextBox searchBox, ComboBox sortBox, TextBlock titleText, TextBlock subtitleText) BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "BrowsePage");

        var root = new Grid
        {
            Padding = new Thickness(28),
            RowSpacing = 16,
            Background = FluentTheme.Canvas,
            RequestedTheme = ElementTheme.Light,
        };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

        var header = new Grid { ColumnSpacing = 16 };
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        var titleStack = new StackPanel { Spacing = 4 };
        titleStack.Children.Add(new TextBlock
        {
            Text = "Browse",
            FontSize = 12,
            Foreground = FluentTheme.Accent,
        });
        var titleText = new TextBlock
        {
            Text = "全部影片",
            FontSize = 28,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(titleText, "BrowseHeaderTitle");
        titleStack.Children.Add(titleText);
        var subtitleText = new TextBlock
        {
            Text = "",
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(subtitleText, "BrowseHeaderSubtitle");
        titleStack.Children.Add(subtitleText);
        header.Children.Add(titleStack);

        var controls = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 10,
            VerticalAlignment = VerticalAlignment.Bottom,
        };
        var libraryBox = new ComboBox
        {
            Header = "媒体库",
            MinWidth = 220,
        };
        AutomationProperties.SetAutomationId(libraryBox, "BrowseLibrarySelector");
        libraryBox.SelectionChanged += OnLibraryChanged;
        controls.Children.Add(libraryBox);

        var searchBox = new TextBox
        {
            Header = "搜索",
            PlaceholderText = "标题或关键字",
            MinWidth = 240,
        };
        AutomationProperties.SetAutomationId(searchBox, "BrowseSearchBox");
        searchBox.KeyDown += OnSearchKeyDown;
        controls.Children.Add(searchBox);

        var sortBox = new ComboBox
        {
            Header = "排序",
            MinWidth = 160,
        };
        AutomationProperties.SetAutomationId(sortBox, "BrowseSort");
        AddSortOptions(sortBox, browseLabels: true);
        sortBox.SelectedIndex = 0;
        sortBox.SelectionChanged += OnSortChanged;
        controls.Children.Add(sortBox);

        var searchButton = FluentTheme.ApplyButton(new Button
        {
            Content = "搜索",
            VerticalAlignment = VerticalAlignment.Bottom,
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(searchButton, "BrowseSearchButton");
        searchButton.Click += async (_, _) => await LoadMoviesAsync();
        controls.Children.Add(searchButton);

        Grid.SetColumn(controls, 1);
        header.Children.Add(controls);
        root.Children.Add(FluentTheme.Card(header, new Thickness(16)));

        var content = new Grid { ColumnSpacing = 16 };
        content.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(260) });
        content.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        Grid.SetRow(content, 1);

        var folderStack = new StackPanel { Spacing = 10 };
        folderStack.Children.Add(new TextBlock
        {
            Text = "文件夹",
            FontSize = 13,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextSecondary,
        });
        var folderList = new ListView
        {
            SelectionMode = ListViewSelectionMode.None,
            Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent),
            Padding = new Thickness(0),
        };
        AutomationProperties.SetAutomationId(folderList, "BrowseFoldersList");
        folderStack.Children.Add(folderList);
        content.Children.Add(FluentTheme.Card(folderStack, new Thickness(14)));

        var moviesHost = new Grid();
        Grid.SetColumn(moviesHost, 1);
        var moviesGrid = new GridView
        {
            IsItemClickEnabled = false,
            SelectionMode = ListViewSelectionMode.None,
            Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent),
        };
        AutomationProperties.SetAutomationId(moviesGrid, "BrowseMoviesGrid");
        moviesHost.Children.Add(moviesGrid);

        var statusText = new TextBlock
        {
            Text = "",
            Visibility = Visibility.Collapsed,
            Foreground = FluentTheme.TextSecondary,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            TextWrapping = TextWrapping.WrapWholeWords,
        };
        AutomationProperties.SetAutomationId(statusText, "BrowseStatusText");
        moviesHost.Children.Add(statusText);
        content.Children.Add(moviesHost);

        root.Children.Add(content);
        Content = root;
        return (libraryBox, folderList, moviesGrid, statusText, searchBox, sortBox, titleText, subtitleText);
    }

    private async Task LoadLibrariesAsync()
    {
        _suppressLibrarySelectionChanged = true;
        try
        {
            _libraryBox.Items.Clear();
            _libraryBox.Items.Add(new ComboBoxItem { Content = "全部媒体库", Tag = "" });
            var roots = await AppServices.Library.GetMediaRootsAsync();
            foreach (var root in roots.Items)
            {
                _libraryBox.Items.Add(new ComboBoxItem
                {
                    Content = string.IsNullOrWhiteSpace(root.Label) ? root.Path : root.Label,
                    Tag = root.Path,
                });
            }

            _libraryBox.SelectedIndex = 0;
            _activeMediaRoot = "";
        }
        finally
        {
            _suppressLibrarySelectionChanged = false;
        }

        await LoadFoldersAsync();
        await LoadMoviesAsync();
    }

    private async Task LoadFoldersAsync()
    {
        _folderList.Items.Clear();
        var allButton = CreateFolderButton("全部影片", "", 0);
        _folderList.Items.Add(allButton);

        try
        {
            var response = await AppServices.Library.GetFoldersAsync(_activeMediaRoot);
            foreach (var folder in SortFolders(response.Tree))
            {
                AddFolderButtons(folder, 0);
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load native browse folders.");
            ShowStatus($"加载文件夹失败：{ex.Message}", true);
        }
    }

    private async Task LoadMoviesAsync()
    {
        var generation = ++_loadGeneration;
        try
        {
            ShowStatus("正在加载...", false);
            _moviesGrid.Items.Clear();
            var sort = (_sortBox.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "created_desc";
            var response = await AppServices.Movie.GetMoviesAsync(_activeMediaRoot, _activeFolderPath, _searchBox.Text.Trim(), sort, 120, 0);
            if (generation != _loadGeneration)
            {
                return;
            }

            foreach (var movie in response.Movies)
            {
                var cover = "";
                try
                {
                    cover = await AppServices.Api.BuildCoverUrlAsync(movie.Id);
                }
                catch (Exception ex)
                {
                    ShellLogger.Error(ex, $"Failed to build native browse cover URL for movie {movie.Id}.");
                }

                _moviesGrid.Items.Add(CreateMovieCard(new MovieCardItem(movie, cover)));
            }

            _titleText.Text = string.IsNullOrWhiteSpace(_activeFolderPath) ? "全部影片" : $"浏览: {_activeFolderPath}";
            _subtitleText.Text = $"共 {response.Total} 部";
            _statusText.Visibility = response.Movies.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
            if (response.Movies.Count == 0)
            {
                _statusText.Text = "没有找到影片";
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load native browse movies.");
            ShowStatus($"加载影片失败：{ex.Message}", true);
        }
    }

    private void AddFolderButtons(FolderNodeDto folder, int depth)
    {
        if (folder.MovieCount > 0)
        {
            _folderList.Items.Add(CreateFolderButton(folder.Name, folder.Path, depth));
        }

        foreach (var child in SortFolders(folder.Children))
        {
            AddFolderButtons(child, depth + 1);
        }
    }

    private Button CreateFolderButton(string label, string path, int depth)
    {
        var text = new TextBlock
        {
            Text = label,
            Margin = new Thickness(depth * 14, 0, 0, 0),
            TextTrimming = TextTrimming.CharacterEllipsis,
            Foreground = FluentTheme.TextPrimary,
        };
        var button = FluentTheme.ApplyButton(new Button
        {
            Content = text,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            HorizontalContentAlignment = HorizontalAlignment.Left,
            Tag = path,
        }, FluentButtonStyle.Subtle);
        AutomationProperties.SetAutomationId(button, string.IsNullOrWhiteSpace(path) ? "BrowseFolder_All" : $"BrowseFolder_{path.Replace("\\", "_").Replace("/", "_")}");
        button.Click += async (_, _) =>
        {
            _activeFolderPath = path;
            await LoadMoviesAsync();
        };
        return button;
    }

    private async void OnLibraryChanged(object sender, SelectionChangedEventArgs args)
    {
        if (_suppressLibrarySelectionChanged)
        {
            return;
        }

        _activeMediaRoot = (_libraryBox.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "";
        _activeFolderPath = "";
        _searchBox.Text = "";
        await LoadFoldersAsync();
        await LoadMoviesAsync();
    }

    private async void OnSortChanged(object sender, SelectionChangedEventArgs args)
    {
        if (IsLoaded)
        {
            await LoadMoviesAsync();
        }
    }

    private async void OnSearchKeyDown(object sender, KeyRoutedEventArgs args)
    {
        if (args.Key == global::Windows.System.VirtualKey.Enter)
        {
            await LoadMoviesAsync();
        }
    }

    private void ShowStatus(string message, bool isError)
    {
        _statusText.Text = message;
        _statusText.Foreground = isError ? FluentTheme.Error : FluentTheme.TextSecondary;
        _statusText.Visibility = Visibility.Visible;
    }

    private IEnumerable<FolderNodeDto> SortFolders(IEnumerable<FolderNodeDto> folders)
    {
        var sort = (_sortBox.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "created_desc";
        return sort switch
        {
            "name" => folders.OrderBy(folder => folder.Name, StringComparer.CurrentCultureIgnoreCase),
            "release_date_desc" => folders.OrderByDescending(folder => folder.ReleaseDateMax ?? ""),
            "release_date_asc" => folders.OrderBy(folder => folder.ReleaseDateMax ?? ""),
            "created_asc" => folders.OrderBy(folder => folder.CreatedMax ?? ""),
            "random" => folders.OrderBy(_ => Guid.NewGuid()),
            _ => folders.OrderByDescending(folder => folder.CreatedMax ?? ""),
        };
    }

    internal static void AddSortOptions(ComboBox sortBox, bool browseLabels)
    {
        sortBox.Items.Add(new ComboBoxItem { Content = "最近添加", Tag = "created_desc" });
        sortBox.Items.Add(new ComboBoxItem { Content = "最早添加", Tag = "created_asc" });
        sortBox.Items.Add(new ComboBoxItem { Content = browseLabels ? "文件夹名称" : "名称", Tag = "name" });
        if (browseLabels)
        {
            sortBox.Items.Add(new ComboBoxItem { Content = "发行日期新到旧", Tag = "release_date_desc" });
            sortBox.Items.Add(new ComboBoxItem { Content = "发行日期旧到新", Tag = "release_date_asc" });
        }

        sortBox.Items.Add(new ComboBoxItem { Content = "随机", Tag = "random" });
    }

    internal static Button CreateMovieCard(MovieCardItem item)
    {
        var imageHost = new Grid
        {
            Height = 252,
            Background = FluentTheme.LayerAlt,
        };
        try
        {
            if (Uri.TryCreate(item.CoverUrl, UriKind.Absolute, out var coverUri))
            {
                var image = new Image
                {
                    Source = new BitmapImage(coverUri),
                    Stretch = Stretch.UniformToFill,
                };
                image.ImageFailed += (_, _) =>
                {
                    imageHost.Children.Clear();
                    AddCoverFallback(imageHost);
                };
                imageHost.Children.Add(image);
            }
            else
            {
                AddCoverFallback(imageHost);
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Failed to create native browse cover image for movie {item.Id}.");
            AddCoverFallback(imageHost);
        }

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
            Text = item.Subtitle,
            FontSize = 12,
            Foreground = FluentTheme.TextSecondary,
            TextTrimming = TextTrimming.CharacterEllipsis,
        });
        if (!string.IsNullOrWhiteSpace(item.ProgressText))
        {
            textStack.Children.Add(new TextBlock
            {
                Text = item.ProgressText,
                FontSize = 12,
                Foreground = FluentTheme.Accent,
            });
        }

        var stack = new StackPanel();
        stack.Children.Add(imageHost);
        stack.Children.Add(textStack);

        var card = new Button
        {
            Width = 178,
            Margin = new Thickness(6),
            CornerRadius = new CornerRadius(14),
            Background = FluentTheme.Layer,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(1),
            Content = stack,
            Padding = new Thickness(0),
            HorizontalContentAlignment = HorizontalAlignment.Stretch,
            VerticalContentAlignment = VerticalAlignment.Stretch,
            Tag = item,
        };
        AutomationProperties.SetAutomationId(card, $"BrowseMovieCard_{item.Id}");
        card.Click += (_, _) => ShellPage.Current?.NavigateToMovie(item.Id);
        return card;
    }

    private static void AddCoverFallback(Grid imageHost)
    {
        imageHost.Children.Add(new TextBlock
        {
            Text = "无封面",
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Foreground = FluentTheme.TextTertiary,
        });
    }
}
