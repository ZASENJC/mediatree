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
    private const int BrowsePageSize = 48;
    private const double FolderTreePreferredWidth = 260;
    private const double FolderTreeCompactWidth = 220;

    private sealed record FolderSelection(string Path, string MediaRoot);

    private readonly ComboBox _libraryBox;
    private readonly ListView _folderList;
    private readonly GridView _moviesGrid;
    private readonly TextBlock _statusText;
    private readonly TextBox _searchBox;
    private readonly ComboBox _sortBox;
    private readonly TextBlock _subtitleText;
    private readonly TextBlock _titleText;
    private readonly StackPanel _paginationBar;
    private readonly Button _previousPageButton;
    private readonly Button _nextPageButton;
    private readonly TextBlock _pageText;
    private IReadOnlyList<MediaRootDto> _activeMediaRoots = [];
    private readonly HashSet<string> _excludedFolderPaths = new(StringComparer.OrdinalIgnoreCase);
    private readonly HashSet<string> _expandedFolderKeys = new(StringComparer.OrdinalIgnoreCase);
    private readonly HashSet<string> _collapsedFolderKeys = new(StringComparer.OrdinalIgnoreCase);
    private string _activeFolderPath = "";
    private string _activeFolderMediaRoot = "";
    private string _activeMediaRoot = "";
    private int _pageIndex;
    private int _loadGeneration;
    private bool _hasLoadedLibraries;
    private bool _suppressLibrarySelectionChanged;

    public BrowsePage()
    {
        NavigationCacheMode = Microsoft.UI.Xaml.Navigation.NavigationCacheMode.Enabled;
        (_libraryBox, _folderList, _moviesGrid, _statusText, _searchBox, _sortBox, _titleText, _subtitleText, _paginationBar, _previousPageButton, _nextPageButton, _pageText) = BuildContent();
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
    }

    private (ComboBox libraryBox, ListView folderList, GridView moviesGrid, TextBlock statusText, TextBox searchBox, ComboBox sortBox, TextBlock titleText, TextBlock subtitleText, StackPanel paginationBar, Button previousPageButton, Button nextPageButton, TextBlock pageText) BuildContent()
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

        var headerStack = new StackPanel { Spacing = 14 };
        var header = new Grid { ColumnSpacing = 16, RowSpacing = 12 };
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        header.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

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
        headerStack.Children.Add(header);

        var toolbar = new Grid
        {
            ColumnSpacing = 12,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            VerticalAlignment = VerticalAlignment.Bottom,
        };
        toolbar.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        toolbar.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        toolbar.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        toolbar.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        toolbar.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        toolbar.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        var libraryBox = FluentTheme.ApplyComboBox(new ComboBox
        {
            Header = "媒体库",
            Width = LibraryPage.HeaderInputWidth,
            HorizontalAlignment = HorizontalAlignment.Left,
        });
        AutomationProperties.SetAutomationId(libraryBox, "BrowseLibrarySelector");
        libraryBox.SelectionChanged += OnLibraryChanged;
        toolbar.Children.Add(libraryBox);

        var searchBox = FluentTheme.ApplyTextInput(new TextBox
        {
            Header = "搜索",
            PlaceholderText = "标题或关键字",
            Width = LibraryPage.HeaderInputWidth,
            HorizontalAlignment = HorizontalAlignment.Left,
        });
        AutomationProperties.SetAutomationId(searchBox, "BrowseSearchBox");
        searchBox.KeyDown += OnSearchKeyDown;
        Grid.SetColumn(searchBox, 1);
        toolbar.Children.Add(searchBox);

        var sortBox = FluentTheme.ApplyComboBox(new ComboBox
        {
            Header = "排序",
        });
        AutomationProperties.SetAutomationId(sortBox, "BrowseSort");
        AddSortOptions(sortBox, browseLabels: true);
        sortBox.SelectedIndex = 0;
        sortBox.SelectionChanged += OnSortChanged;
        Grid.SetColumn(sortBox, 3);
        toolbar.Children.Add(sortBox);

        var searchButton = FluentTheme.ApplyButton(new Button
        {
            Content = "搜索",
            VerticalAlignment = VerticalAlignment.Bottom,
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(searchButton, "BrowseSearchButton");
        searchButton.Click += async (_, _) => await ReloadFirstPageAsync();
        Grid.SetColumn(searchButton, 4);
        toolbar.Children.Add(searchButton);

        headerStack.Children.Add(toolbar);
        root.Children.Add(FluentTheme.Card(headerStack, new Thickness(16)));

        var content = new Grid { ColumnSpacing = 16 };
        content.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(260) });
        content.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        content.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        content.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });
        Grid.SetRow(content, 1);

        var folderStack = new Grid { RowSpacing = 10 };
        folderStack.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        folderStack.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        var folderTitle = new TextBlock
        {
            Text = "文件夹",
            FontSize = 13,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextSecondary,
        };
        Grid.SetRow(folderTitle, 0);
        folderStack.Children.Add(folderTitle);
        var folderList = FluentTheme.ApplyListView(new ListView
        {
            SelectionMode = ListViewSelectionMode.None,
            Padding = new Thickness(0),
            VerticalAlignment = VerticalAlignment.Stretch,
        });
        AutomationProperties.SetAutomationId(folderList, "BrowseFoldersList");
        Grid.SetRow(folderList, 1);
        folderStack.Children.Add(folderList);
        var folderHost = FluentTheme.Card(folderStack, new Thickness(14));
        content.Children.Add(folderHost);

        var moviesHost = new Grid { RowSpacing = 12 };
        moviesHost.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        moviesHost.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        Grid.SetColumn(moviesHost, 1);
        var moviesGrid = FluentTheme.ApplyGridView(new GridView
        {
            IsItemClickEnabled = false,
            SelectionMode = ListViewSelectionMode.None,
        });
        AutomationProperties.SetAutomationId(moviesGrid, "BrowseMoviesGrid");
        Grid.SetRow(moviesGrid, 0);
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
        Grid.SetRow(statusText, 0);
        moviesHost.Children.Add(statusText);

        var previousPageButton = FluentTheme.ApplyButton(new Button
        {
            Content = "上一页",
            MinWidth = 84,
        });
        AutomationProperties.SetAutomationId(previousPageButton, "BrowsePreviousPage");
        previousPageButton.Click += async (_, _) => await ChangePageAsync(_pageIndex - 1);

        var pageText = new TextBlock
        {
            Text = "",
            MinWidth = 96,
            TextAlignment = TextAlignment.Center,
            Foreground = FluentTheme.TextSecondary,
            VerticalAlignment = VerticalAlignment.Center,
        };
        AutomationProperties.SetAutomationId(pageText, "BrowsePageText");

        var nextPageButton = FluentTheme.ApplyButton(new Button
        {
            Content = "下一页",
            MinWidth = 84,
        });
        AutomationProperties.SetAutomationId(nextPageButton, "BrowseNextPage");
        nextPageButton.Click += async (_, _) => await ChangePageAsync(_pageIndex + 1);

        var paginationBar = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Center,
            Spacing = 8,
            Visibility = Visibility.Collapsed,
        };
        paginationBar.Children.Add(previousPageButton);
        paginationBar.Children.Add(pageText);
        paginationBar.Children.Add(nextPageButton);
        Grid.SetRow(paginationBar, 1);
        moviesHost.Children.Add(paginationBar);
        content.Children.Add(moviesHost);

        root.SizeChanged += (_, args) => ApplyBrowseResponsiveLayout(
            args.NewSize.Width,
            root,
            toolbar,
            content,
            folderHost,
            moviesHost,
            libraryBox,
            searchBox,
            sortBox,
            searchButton);

        root.Children.Add(content);
        Content = root;
        return (libraryBox, folderList, moviesGrid, statusText, searchBox, sortBox, titleText, subtitleText, paginationBar, previousPageButton, nextPageButton, pageText);
    }

    private static void ApplyBrowseResponsiveLayout(
        double width,
        Grid root,
        Grid toolbar,
        Grid content,
        Border folderHost,
        Grid moviesHost,
        ComboBox libraryBox,
        TextBox searchBox,
        ComboBox sortBox,
        Button searchButton)
    {
        var compact = width < FluentTheme.MediumBreakpoint;
        root.Padding = FluentTheme.PagePadding(width);

        toolbar.ColumnDefinitions[0].Width = compact ? new GridLength(1, GridUnitType.Star) : GridLength.Auto;
        toolbar.ColumnDefinitions[1].Width = compact ? new GridLength(1.25, GridUnitType.Star) : GridLength.Auto;
        toolbar.ColumnDefinitions[2].Width = new GridLength(1, GridUnitType.Star);
        toolbar.ColumnDefinitions[3].Width = GridLength.Auto;
        toolbar.ColumnDefinitions[4].Width = GridLength.Auto;

        libraryBox.Width = compact ? double.NaN : LibraryPage.HeaderInputWidth;
        searchBox.Width = compact ? double.NaN : LibraryPage.HeaderInputWidth;
        sortBox.Width = double.NaN;
        libraryBox.MinWidth = 0;
        searchBox.MinWidth = 0;
        sortBox.MinWidth = compact ? 108 : 160;
        libraryBox.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Left;
        searchBox.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Left;
        sortBox.HorizontalAlignment = compact ? HorizontalAlignment.Stretch : HorizontalAlignment.Left;
        searchButton.HorizontalAlignment = HorizontalAlignment.Left;

        var availableContentWidth = Math.Max(0, width - root.Padding.Left - root.Padding.Right);
        var folderTreeWidth = availableContentWidth < 840 ? FolderTreeCompactWidth : FolderTreePreferredWidth;
        content.RowSpacing = 0;
        content.ColumnDefinitions[0].Width = new GridLength(folderTreeWidth);
        content.ColumnDefinitions[1].Width = new GridLength(1, GridUnitType.Star);
        content.RowDefinitions[0].Height = new GridLength(1, GridUnitType.Star);
        content.RowDefinitions[1].Height = new GridLength(0);
        Grid.SetColumn(folderHost, 0);
        Grid.SetRow(folderHost, 0);
        Grid.SetColumn(moviesHost, 1);
        Grid.SetRow(moviesHost, 0);
    }

    private async Task LoadLibrariesAsync(bool forceRefresh = false)
    {
        if (_hasLoadedLibraries && !forceRefresh)
        {
            return;
        }

        var previousMediaRoot = _activeMediaRoot;
        var previousFolderMediaRoot = _activeFolderMediaRoot;
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
            if (!string.Equals(previousMediaRoot, selectedRoot, StringComparison.OrdinalIgnoreCase)
                || (!string.IsNullOrWhiteSpace(previousFolderMediaRoot) && !_activeMediaRoots.Any(root => LibraryService.RootsMatch(root.Path, previousFolderMediaRoot))))
            {
                _activeFolderPath = "";
                _activeFolderMediaRoot = "";
            }
        }
        finally
        {
            _suppressLibrarySelectionChanged = false;
        }

        await LoadFoldersAsync();
        await LoadMoviesAsync();
        _hasLoadedLibraries = true;
    }

    private async Task LoadFoldersAsync()
    {
        _folderList.Items.Clear();
        var allButton = CreateFolderButton("全部影片", "", "", 0);
        _folderList.Items.Add(allButton);

        try
        {
            foreach (var root in GetSelectedMediaRoots())
            {
                var response = await AppServices.Media.Library.GetFoldersAsync(root.Path);
                foreach (var state in BrowseFolderTreePresenter.VisibleNodeStatesForMediaRoot(
                    root.Path,
                    response.Tree,
                    _excludedFolderPaths,
                    _expandedFolderKeys,
                    _collapsedFolderKeys,
                    SortFolders))
                {
                    _folderList.Items.Add(CreateFolderRow(state));
                }
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
            var response = await LoadActiveMoviesAsync(sort, BrowsePageSize, _pageIndex * BrowsePageSize);
            if (generation != _loadGeneration)
            {
                return;
            }

            var totalPages = PageCount(response.Total);
            if (response.Total > 0 && _pageIndex >= totalPages)
            {
                _pageIndex = totalPages - 1;
                await LoadMoviesAsync();
                return;
            }

            foreach (var movie in response.Movies)
            {
                var item = new MovieCardItem(movie, "");
                _moviesGrid.Items.Add(CreateMovieCard(
                    item,
                    CreateContextMenuHost(async () => await LoadMoviesAsync())));
                _ = LoadMovieCardCoverAsync(item, generation, "browse");
            }

            _titleText.Text = string.IsNullOrWhiteSpace(_activeFolderPath) ? "全部影片" : $"浏览: {_activeFolderPath}";
            _subtitleText.Text = BuildBrowseSubtitle(response.Total, response.Movies.Count);
            UpdatePagination(response.Total);
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

    private async Task<MoviesResponseDto> LoadActiveMoviesAsync(string sort, int limit, int offset)
    {
        var search = _searchBox.Text.Trim();
        if (!string.IsNullOrWhiteSpace(_activeMediaRoot))
        {
            var response = await AppServices.Media.Movie.GetMoviesAsync(_activeMediaRoot, _activeFolderPath, search, sort, limit, offset);
            return BrowseLibraryPresenter.FilterExcludedMovies(response, _excludedFolderPaths, preserveTotal: true);
        }

        if (!string.IsNullOrWhiteSpace(_activeFolderPath) && !string.IsNullOrWhiteSpace(_activeFolderMediaRoot))
        {
            var response = await AppServices.Media.Movie.GetMoviesAsync(_activeFolderMediaRoot, _activeFolderPath, search, sort, limit, offset);
            return BrowseLibraryPresenter.FilterExcludedMovies(response, _excludedFolderPaths, preserveTotal: true);
        }

        var roots = _activeMediaRoots.ToList();
        if (roots.Count == 0)
        {
            return new MoviesResponseDto();
        }

        var fetchLimit = Math.Max(0, limit + offset);
        var responses = await Task.WhenAll(roots.Select(root => AppServices.Media.Movie.GetMoviesAsync(root.Path, "", search, sort, fetchLimit, 0)));
        return BrowseLibraryPresenter.FilterExcludedMovies(BrowseLibraryPresenter.MergeMovieResponses(responses, sort, limit, offset), _excludedFolderPaths, preserveTotal: true);
    }

    private static int PageCount(int total)
        => total <= 0 ? 0 : (int)Math.Ceiling(total / (double)BrowsePageSize);

    private string BuildBrowseSubtitle(int total, int currentCount)
    {
        if (total <= 0 || currentCount <= 0)
        {
            return $"共 {total} 部";
        }

        var start = _pageIndex * BrowsePageSize + 1;
        var end = Math.Min(total, start + currentCount - 1);
        return total > BrowsePageSize ? $"共 {total} 部，显示 {start}-{end}" : $"共 {total} 部";
    }

    private void UpdatePagination(int total)
    {
        var pageCount = PageCount(total);
        _paginationBar.Visibility = pageCount > 1 ? Visibility.Visible : Visibility.Collapsed;
        _pageText.Text = pageCount > 0 ? $"{_pageIndex + 1} / {pageCount}" : "";
        _previousPageButton.IsEnabled = _pageIndex > 0;
        _nextPageButton.IsEnabled = pageCount > 0 && _pageIndex < pageCount - 1;
    }

    private async Task ReloadFirstPageAsync()
    {
        _pageIndex = 0;
        await LoadMoviesAsync();
    }

    private async Task ChangePageAsync(int pageIndex)
    {
        var nextPage = Math.Max(0, pageIndex);
        if (nextPage == _pageIndex)
        {
            return;
        }

        _pageIndex = nextPage;
        await LoadMoviesAsync();
    }

    private IEnumerable<MediaRootDto> GetSelectedMediaRoots()
    {
        if (string.IsNullOrWhiteSpace(_activeMediaRoot))
        {
            return _activeMediaRoots;
        }

        return _activeMediaRoots.Where(root => LibraryService.RootsMatch(root.Path, _activeMediaRoot));
    }

    private Button CreateFolderButton(string label, string path, string mediaRoot, int depth)
    {
        var text = new TextBlock
        {
            Text = label,
            Margin = new Thickness(Math.Min(depth, 4) * 14, 0, 0, 0),
            TextTrimming = TextTrimming.CharacterEllipsis,
            Foreground = FluentTheme.TextPrimary,
        };
        var button = FluentTheme.ApplyButton(new Button
        {
            Content = text,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            HorizontalContentAlignment = HorizontalAlignment.Left,
            Tag = new FolderSelection(path, mediaRoot),
        }, FluentButtonStyle.Subtle);
        var automationKey = string.IsNullOrWhiteSpace(mediaRoot) ? path : $"{mediaRoot}_{path}";
        AutomationProperties.SetAutomationId(button, string.IsNullOrWhiteSpace(path) ? "BrowseFolder_All" : $"BrowseFolder_{SanitizeAutomationId(automationKey)}");
        button.Click += async (_, _) =>
        {
            if (button.Tag is not FolderSelection selection)
            {
                return;
            }

            _activeFolderPath = selection.Path;
            _activeFolderMediaRoot = selection.MediaRoot;
            await ReloadFirstPageAsync();
        };
        return button;
    }

    private UIElement CreateFolderRow(BrowseFolderTreeNodeState state)
    {
        var folder = state.Folder;
        var hasChildren = BrowseFolderTreePresenter.HasChildren(folder);
        var root = new Grid
        {
            ColumnSpacing = 6,
            MinHeight = 34,
            Padding = new Thickness(Math.Min(state.Depth, 6) * 16 + 6, 2, 6, 2),
            Opacity = state.IsIncluded ? 1 : 0.45,
        };
        root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(28) });
        root.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        root.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        if (hasChildren)
        {
            var expandIcon = new FontIcon
            {
                Glyph = state.IsExpanded ? "\uE70D" : "\uE76C",
                FontFamily = new FontFamily("Segoe MDL2 Assets"),
                FontSize = 11,
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center,
            };
            var expandButton = FluentTheme.ApplyButton(new Button
            {
                Content = expandIcon,
                Width = 28,
                MinWidth = 28,
                Height = 28,
                MinHeight = 28,
                HorizontalAlignment = HorizontalAlignment.Left,
                VerticalAlignment = VerticalAlignment.Center,
                HorizontalContentAlignment = HorizontalAlignment.Center,
                VerticalContentAlignment = VerticalAlignment.Center,
            }, FluentButtonStyle.Subtle);
            expandButton.Padding = new Thickness(0);
            ApplyFolderToggleTheme(expandButton, expandIcon);
            AutomationProperties.SetAutomationId(expandButton, $"BrowseFolderToggle_{SanitizeAutomationId(BrowseFolderTreePresenter.FolderKey(folder))}");
            ToolTipService.SetToolTip(expandButton, state.IsExpanded ? "收起" : "展开");
            expandButton.Click += async (_, _) =>
            {
                BrowseFolderTreePresenter.ToggleExpanded(_expandedFolderKeys, _collapsedFolderKeys, folder, state.Depth);
                await LoadFoldersAsync();
            };
            root.Children.Add(expandButton);
        }
        else
        {
            root.Children.Add(new Border
            {
                Width = 28,
                Height = 28,
                Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent),
            });
        }

        var includeBox = FluentTheme.ApplyCheckBox(new CheckBox
        {
            MinWidth = 28,
            MinHeight = 28,
            Padding = new Thickness(0),
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
        });
        includeBox.IsChecked = state.IsIncluded;
        AutomationProperties.SetAutomationId(includeBox, $"BrowseFolderInclude_{SanitizeAutomationId(BrowseFolderTreePresenter.FolderKey(folder))}");
        ToolTipService.SetToolTip(includeBox, state.IsIncluded ? "包含此文件夹" : "排除此文件夹");
        includeBox.Checked += async (_, _) => await SetFolderIncludedAsync(folder.Path, true);
        includeBox.Unchecked += async (_, _) => await SetFolderIncludedAsync(folder.Path, false);
        Grid.SetColumn(includeBox, 1);
        root.Children.Add(includeBox);

        var labelButton = FluentTheme.ApplyButton(new Button
        {
            Content = new TextBlock
            {
                Text = folder.Name,
                TextTrimming = TextTrimming.CharacterEllipsis,
                Foreground = state.IsIncluded ? FluentTheme.TextPrimary : FluentTheme.TextTertiary,
            },
            HorizontalAlignment = HorizontalAlignment.Stretch,
            HorizontalContentAlignment = HorizontalAlignment.Left,
            MinHeight = 30,
            Padding = new Thickness(6, 4, 8, 4),
            Tag = new FolderSelection(folder.Path, folder.MediaRoot),
        }, IsFolderSelected(folder) ? FluentButtonStyle.Accent : FluentButtonStyle.Subtle);
        AutomationProperties.SetAutomationId(labelButton, $"BrowseFolder_{SanitizeAutomationId(BrowseFolderTreePresenter.FolderKey(folder))}");
        labelButton.Click += async (_, _) =>
        {
            if (labelButton.Tag is not FolderSelection selection)
            {
                return;
            }

            _activeFolderPath = selection.Path;
            _activeFolderMediaRoot = selection.MediaRoot;
            await ReloadFirstPageAsync();
        };
        Grid.SetColumn(labelButton, 2);
        root.Children.Add(labelButton);

        if (folder.MovieCount > 0)
        {
            var countBadge = new Border
            {
                Padding = new Thickness(7, 2, 7, 3),
                CornerRadius = new CornerRadius(10),
                Background = FluentTheme.ControlAlt,
                VerticalAlignment = VerticalAlignment.Center,
                Child = new TextBlock
                {
                    Text = folder.MovieCount.ToString(),
                    FontSize = 11,
                    Foreground = FluentTheme.TextTertiary,
                },
            };
            Grid.SetColumn(countBadge, 3);
            root.Children.Add(countBadge);
        }

        return root;
    }

    private static void ApplyFolderToggleTheme(Button button, FontIcon icon)
    {
        void Refresh()
        {
            var foreground = button.ActualTheme == ElementTheme.Dark
                ? FluentTheme.Brush(0xD6, 0xDA, 0xE0)
                : FluentTheme.Brush(0x3B, 0x42, 0x4C);
            button.Foreground = foreground;
            icon.Foreground = foreground;
            button.Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent);
            button.BorderBrush = new SolidColorBrush(Microsoft.UI.Colors.Transparent);
        }

        button.Loaded += (_, _) => Refresh();
        button.ActualThemeChanged += (_, _) => Refresh();
        Refresh();
    }

    private bool IsFolderSelected(FolderNodeDto folder)
        => string.Equals(_activeFolderPath, folder.Path, StringComparison.OrdinalIgnoreCase)
            && (string.IsNullOrWhiteSpace(_activeMediaRoot)
                ? LibraryService.RootsMatch(_activeFolderMediaRoot, folder.MediaRoot)
                : LibraryService.RootsMatch(_activeMediaRoot, folder.MediaRoot));

    private async Task SetFolderIncludedAsync(string path, bool included)
    {
        BrowseFolderTreePresenter.SetIncluded(_excludedFolderPaths, path, included);
        SaveExcludedFolders();
        if (BrowseLibraryPresenter.IsFolderPathExcluded(_activeFolderPath, _excludedFolderPaths))
        {
            _activeFolderPath = "";
            _activeFolderMediaRoot = "";
        }

        await LoadFoldersAsync();
        await ReloadFirstPageAsync();
    }

    private void LoadExcludedFolders()
    {
        _excludedFolderPaths.Clear();
        foreach (var path in UiPreferenceStore.Load().ExcludedFolders)
        {
            if (!string.IsNullOrWhiteSpace(path))
            {
                _excludedFolderPaths.Add(path);
            }
        }
    }

    private void SaveExcludedFolders()
    {
        var preferences = UiPreferenceStore.Load();
        preferences.ExcludedFolders = _excludedFolderPaths.OrderBy(path => path, StringComparer.OrdinalIgnoreCase).ToList();
        UiPreferenceStore.Save(preferences);
    }

    private async void OnLibraryChanged(object sender, SelectionChangedEventArgs args)
    {
        if (_suppressLibrarySelectionChanged)
        {
            return;
        }

        _activeMediaRoot = (_libraryBox.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "";
        _activeFolderPath = "";
        _activeFolderMediaRoot = "";
        _searchBox.Text = "";
        await LoadFoldersAsync();
        await ReloadFirstPageAsync();
    }

    private async void OnLoaded(object sender, RoutedEventArgs args)
    {
        AppServices.Media.Library.LibrariesChanged -= OnLibrariesChanged;
        AppServices.Media.Library.LibrariesChanged += OnLibrariesChanged;
        LoadExcludedFolders();
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

    private async void OnSortChanged(object sender, SelectionChangedEventArgs args)
    {
        if (IsLoaded)
        {
            await ReloadFirstPageAsync();
        }
    }

    private async void OnSearchKeyDown(object sender, KeyRoutedEventArgs args)
    {
        if (args.Key == global::Windows.System.VirtualKey.Enter)
        {
            await ReloadFirstPageAsync();
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

    internal static Button CreateMovieCard(MovieCardItem item, MediaContextMenuHost? contextHost = null, Action? onClick = null)
    {
        onClick ??= () => ShellPage.Current?.NavigateToMovie(item.Id);

        var imageHost = new Grid
        {
            Height = item.HasEpisodeStill ? 100 : 252,
            Background = FluentTheme.LayerAlt,
        };

        var fallbackText = AddCoverFallback(imageHost);
        var image = new Image
        {
            Stretch = Stretch.UniformToFill,
            Visibility = Visibility.Collapsed,
        };
        imageHost.Children.Add(image);

        var triedFallback = false;
        void ApplyCoverUrl()
        {
            try
            {
                if (Uri.TryCreate(item.CoverUrl, UriKind.Absolute, out var coverUri))
                {
                    triedFallback = false;
                    image.Source = new BitmapImage(coverUri);
                    image.Visibility = Visibility.Visible;
                    fallbackText.Visibility = Visibility.Collapsed;
                    return;
                }

                image.Source = null;
                image.Visibility = Visibility.Collapsed;
                fallbackText.Visibility = Visibility.Visible;
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, $"Failed to create native browse cover image for movie {item.Id}.");
                image.Source = null;
                image.Visibility = Visibility.Collapsed;
                fallbackText.Visibility = Visibility.Visible;
            }
        }

        image.ImageFailed += (_, _) =>
        {
            if (item.HasEpisodeStill && !triedFallback && Uri.TryCreate(item.FallbackCoverUrl, UriKind.Absolute, out var fallbackUri))
            {
                triedFallback = true;
                image.Source = new BitmapImage(fallbackUri);
                image.Visibility = Visibility.Visible;
                fallbackText.Visibility = Visibility.Collapsed;
                return;
            }

            image.Visibility = Visibility.Collapsed;
            fallbackText.Visibility = Visibility.Visible;
        };
        item.PropertyChanged += (_, args) =>
        {
            if (args.PropertyName == nameof(MovieCardItem.CoverUrl))
            {
                if (imageHost.DispatcherQueue.HasThreadAccess)
                {
                    ApplyCoverUrl();
                    return;
                }

                _ = imageHost.DispatcherQueue.TryEnqueue(ApplyCoverUrl);
            }
        };
        ApplyCoverUrl();

        if (item.IsEpisode)
        {
            imageHost.Children.Add(new Border
            {
                Margin = new Thickness(8),
                Padding = new Thickness(8, 3, 8, 3),
                HorizontalAlignment = HorizontalAlignment.Left,
                VerticalAlignment = VerticalAlignment.Top,
                CornerRadius = FluentTheme.ControlCornerRadius,
                Background = FluentTheme.Accent,
                Child = new TextBlock
                {
                    Text = $"S{item.Movie.TmdbSeason?.ToString() ?? "-"}·E{item.Movie.TmdbEpisode?.ToString() ?? "-"}",
                    FontSize = 11,
                    FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
                    Foreground = new SolidColorBrush(Microsoft.UI.Colors.White),
                },
            });
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
            CornerRadius = FluentTheme.MediaCornerRadius,
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
        if (contextHost is not null)
        {
            card.ContextFlyout = MediaContextMenuService.CreateMovieFlyout(item, contextHost);
        }

        card.Click += (_, _) => onClick?.Invoke();
        return card;
    }

    private MediaContextMenuHost CreateContextMenuHost(Func<Task> refreshAsync)
        => new()
        {
            XamlRoot = XamlRoot,
            ShowStatus = ShowStatus,
            RefreshAsync = refreshAsync,
        };

    internal static async Task<MovieCardItem> CreateMovieCardItemAsync(MovieDto movie, string logContext)
    {
        var item = new MovieCardItem(movie, "");
        await PopulateMovieCardCoverAsync(item, logContext);
        return item;
    }

    private async Task LoadMovieCardCoverAsync(MovieCardItem item, int generation, string logContext)
    {
        await PopulateMovieCardCoverAsync(item, logContext);
        if (generation != _loadGeneration)
        {
            return;
        }
    }

    internal static async Task PopulateMovieCardCoverAsync(MovieCardItem item, string logContext)
    {
        try
        {
            var fallbackCover = await AppServices.Media.Api.BuildCoverUrlAsync(item.Id);
            item.FallbackCoverUrl = fallbackCover;
            item.CoverUrl = item.HasEpisodeStill
                ? await AppServices.Media.Api.BuildEpisodeStillUrlAsync(item.Id)
                : fallbackCover;
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Failed to build native {logContext} cover URL for movie {item.Id}.");
            item.CoverUrl = item.FallbackCoverUrl;
        }
    }

    private static TextBlock AddCoverFallback(Grid imageHost)
    {
        var existing = imageHost.Children.OfType<TextBlock>().FirstOrDefault(text => text.Text == "无封面");
        if (existing is not null)
        {
            return existing;
        }

        var fallback = new TextBlock
        {
            Text = "无封面",
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            Foreground = FluentTheme.TextTertiary,
        };
        imageHost.Children.Add(fallback);
        return fallback;
    }

    private static string SanitizeAutomationId(string value)
        => value.Replace("\\", "_").Replace("/", "_").Replace(":", "_");
}
