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

public sealed partial class LibraryPage : Page
{
    public const double HeaderInputWidth = 220;
    private const double CompactSortMinWidth = 108;
    private const double ScanProgressRowHeight = 20;
    private const double ScanProgressWidth = 220;

    private readonly ComboBox _libraryBox;
    private readonly Button _folderTabButton;
    private readonly GridView _folderGrid;
    private readonly Button _addButton;
    private readonly Grid _headerGrid;
    private readonly TextBlock _headerSubtitleText;
    private readonly TextBlock _headerTitleText;
    private readonly TextBlock _loadingText;
    private readonly Button _moviesBackButton;
    private readonly GridView _moviesGrid;
    private readonly Button _recentTabButton;
    private readonly Grid _rootGrid;
    private readonly Button _scanButton;
    private readonly TextBox _searchBox;
    private readonly TextBlock _scanInfoText;
    private readonly Border _scanProgressFill;
    private readonly Border _scanProgressTrack;
    private readonly ComboBox _sortBox;
    private readonly StackPanel _tabs;
    private readonly Grid _toolbar;
    private readonly DispatcherTimer _scanTimer = new() { Interval = TimeSpan.FromSeconds(1) };
    private string _activeMediaRoot = "";
    private string _activeFolderPath = "";
    private string _activeView = "folders";
    private string _activeScanMediaRoot = "";
    private int _movieLoadGeneration;
    private int _scanProgressGeneration;
    private bool _hideHomeTitleText;
    private bool _showSourceName;
    private bool _scanHasObservedActiveStatus;
    private IReadOnlyList<string> _excludedFolderPaths = [];
    private bool _suppressLibrarySelectionChanged;

    public LibraryPage()
    {
        (_rootGrid, _headerGrid, _tabs, _toolbar, _libraryBox, _searchBox, _sortBox, _scanButton, _addButton, _scanInfoText, _scanProgressTrack, _scanProgressFill, _loadingText, _folderGrid, _moviesGrid, _headerTitleText, _headerSubtitleText, _folderTabButton, _recentTabButton, _moviesBackButton) = BuildContent();
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
        _scanTimer.Tick += OnScanTimerTick;
    }

    private (Grid root, Grid header, StackPanel tabs, Grid toolbar, ComboBox libraryBox, TextBox searchBox, ComboBox sortBox, Button scanButton, Button addButton, TextBlock scanInfoText, Border scanProgressTrack, Border scanProgressFill, TextBlock loadingText, GridView folderGrid, GridView moviesGrid, TextBlock headerTitleText, TextBlock headerSubtitleText, Button folderTabButton, Button recentTabButton, Button moviesBackButton) BuildContent()
    {
        AutomationProperties.SetAutomationId(this, "LibraryPage");

        var root = new Grid
        {
            Padding = new Thickness(28),
            RowSpacing = 16,
            Background = FluentTheme.Canvas,
            RequestedTheme = ElementTheme.Light,
        };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(ScanProgressRowHeight) });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

        var headerStack = new StackPanel { Spacing = 14 };
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
        var headerTitleText = new TextBlock
        {
            Text = "我的媒体库",
            FontSize = 28,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
        };
        AutomationProperties.SetAutomationId(headerTitleText, "LibraryHeaderTitle");
        titleStack.Children.Add(headerTitleText);
        var headerSubtitleText = new TextBlock
        {
            Text = "",
            Foreground = FluentTheme.TextSecondary,
        };
        AutomationProperties.SetAutomationId(headerSubtitleText, "LibraryHeaderSubtitle");
        titleStack.Children.Add(headerSubtitleText);
        header.Children.Add(titleStack);

        var tabs = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 8,
            VerticalAlignment = VerticalAlignment.Center,
        };
        var folderTabButton = FluentTheme.ApplyButton(new Button { Content = "媒体库" }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(folderTabButton, "LibraryFolderTab");
        folderTabButton.Click += OnFolderTabClicked;
        tabs.Children.Add(folderTabButton);

        var recentTabButton = FluentTheme.ApplyButton(new Button { Content = "继续观看" });
        AutomationProperties.SetAutomationId(recentTabButton, "LibraryRecentTab");
        recentTabButton.Click += OnRecentTabClicked;
        tabs.Children.Add(recentTabButton);
        Grid.SetColumn(tabs, 1);
        header.Children.Add(tabs);
        headerStack.Children.Add(header);

        var toolbar = new Grid
        {
            ColumnSpacing = 12,
            HorizontalAlignment = HorizontalAlignment.Stretch,
        };
        toolbar.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        toolbar.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        toolbar.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        toolbar.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        toolbar.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        toolbar.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        toolbar.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        for (var i = 0; i < 6; i++)
        {
            toolbar.RowDefinitions.Add(new RowDefinition { Height = i == 0 ? GridLength.Auto : new GridLength(0) });
        }

        var moviesBackButton = FluentTheme.ApplyButton(new Button
        {
            Content = "返回媒体库",
            VerticalAlignment = VerticalAlignment.Bottom,
            Visibility = Visibility.Collapsed,
        });
        AutomationProperties.SetAutomationId(moviesBackButton, "LibraryBackToFolders");
        moviesBackButton.Click += OnBackToFoldersClicked;
        toolbar.Children.Add(moviesBackButton);

        var libraryBox = FluentTheme.ApplyComboBox(new ComboBox
        {
            Header = "文件夹",
            Width = HeaderInputWidth,
            HorizontalAlignment = HorizontalAlignment.Left,
        });
        AutomationProperties.SetAutomationId(libraryBox, "LibrarySelector");
        libraryBox.SelectionChanged += OnLibraryChanged;
        Grid.SetColumn(libraryBox, 1);
        toolbar.Children.Add(libraryBox);

        var searchBox = FluentTheme.ApplyTextInput(new TextBox
        {
            Header = "搜索影片",
            PlaceholderText = "输入标题或关键字",
            Width = HeaderInputWidth,
            HorizontalAlignment = HorizontalAlignment.Left,
        });
        AutomationProperties.SetAutomationId(searchBox, "LibrarySearchBox");
        searchBox.KeyDown += OnSearchKeyDown;
        Grid.SetColumn(searchBox, 2);
        toolbar.Children.Add(searchBox);

        var sortBox = FluentTheme.ApplyComboBox(new ComboBox
        {
            Header = "排序",
        });
        AutomationProperties.SetAutomationId(sortBox, "LibrarySort");
        sortBox.Items.Add(new ComboBoxItem { Content = "最近加入", Tag = "created_desc" });
        sortBox.Items.Add(new ComboBoxItem { Content = "名称", Tag = "name" });
        sortBox.Items.Add(new ComboBoxItem { Content = "发布日期", Tag = "release_date_desc" });
        sortBox.SelectedIndex = 0;
        sortBox.SelectionChanged += OnSortChanged;
        Grid.SetColumn(sortBox, 4);
        toolbar.Children.Add(sortBox);

        var scanButton = FluentTheme.ApplyButton(new Button
        {
            Content = "重新刮削",
            VerticalAlignment = VerticalAlignment.Bottom,
        });
        AutomationProperties.SetAutomationId(scanButton, "LibraryScanButton");
        scanButton.Click += OnScanClicked;
        Grid.SetColumn(scanButton, 5);
        toolbar.Children.Add(scanButton);

        var addButton = FluentTheme.ApplyButton(new Button
        {
            Content = "添加文件夹",
            VerticalAlignment = VerticalAlignment.Bottom,
        }, FluentButtonStyle.Accent);
        AutomationProperties.SetAutomationId(addButton, "LibraryAddFolderButton");
        addButton.Click += OnAddLibraryClicked;
        Grid.SetColumn(addButton, 6);
        toolbar.Children.Add(addButton);

        headerStack.Children.Add(toolbar);
        root.Children.Add(FluentTheme.Card(headerStack, new Thickness(16)));

        var scanInfoText = new TextBlock
        {
            Text = "",
            Visibility = Visibility.Collapsed,
            TextWrapping = TextWrapping.WrapWholeWords,
            Foreground = FluentTheme.TextSecondary,
            HorizontalAlignment = HorizontalAlignment.Right,
            VerticalAlignment = VerticalAlignment.Center,
            MaxWidth = 360,
            TextTrimming = TextTrimming.CharacterEllipsis,
        };
        AutomationProperties.SetAutomationId(scanInfoText, "LibraryScanInfoText");
        Grid.SetRow(scanInfoText, 1);
        root.Children.Add(scanInfoText);

        var scanProgressFill = new Border
        {
            Width = 0,
            Height = 4,
            CornerRadius = new CornerRadius(2),
            Background = FluentTheme.Accent,
            HorizontalAlignment = HorizontalAlignment.Left,
        };
        AutomationProperties.SetAutomationId(scanProgressFill, "LibraryScanProgressFill");
        var scanProgressTrack = new Border
        {
            Width = ScanProgressWidth,
            Height = 4,
            CornerRadius = new CornerRadius(2),
            Background = FluentTheme.AccentSoft,
            Child = scanProgressFill,
            Visibility = Visibility.Collapsed,
            HorizontalAlignment = HorizontalAlignment.Right,
            VerticalAlignment = VerticalAlignment.Center,
        };
        AutomationProperties.SetAutomationId(scanProgressTrack, "LibraryScanProgressTrack");
        Grid.SetRow(scanProgressTrack, 1);
        root.Children.Add(scanProgressTrack);

        var content = new Grid();
        Grid.SetRow(content, 2);

        var folderGrid = FluentTheme.ApplyGridView(new GridView
        {
            IsItemClickEnabled = true,
            SelectionMode = ListViewSelectionMode.None,
            Margin = new Thickness(-6, 0, -6, 0),
        });
        AutomationProperties.SetAutomationId(folderGrid, "FolderGrid");
        folderGrid.ItemClick += OnFolderItemClick;
        content.Children.Add(folderGrid);

        var moviesGrid = FluentTheme.ApplyGridView(new GridView
        {
            IsItemClickEnabled = true,
            SelectionMode = ListViewSelectionMode.None,
            Visibility = Visibility.Collapsed,
            Margin = new Thickness(-6, 0, -6, 0),
        });
        AutomationProperties.SetAutomationId(moviesGrid, "MoviesGrid");
        moviesGrid.ItemClick += OnMovieItemClick;
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
        AutomationProperties.SetAutomationId(loadingText, "LibraryLoadingText");
        content.Children.Add(loadingText);

        root.SizeChanged += (_, args) => ApplyLibraryResponsiveLayout(
            args.NewSize.Width,
            root,
            header,
            tabs,
            toolbar,
            moviesBackButton,
            libraryBox,
            searchBox,
            sortBox,
            scanButton,
            addButton);

        root.Children.Add(content);
        Content = root;
        return (root, header, tabs, toolbar, libraryBox, searchBox, sortBox, scanButton, addButton, scanInfoText, scanProgressTrack, scanProgressFill, loadingText, folderGrid, moviesGrid, headerTitleText, headerSubtitleText, folderTabButton, recentTabButton, moviesBackButton);
    }

    private void ApplyCurrentLayout()
    {
        if (_rootGrid.ActualWidth <= 0)
        {
            return;
        }

        ApplyLibraryResponsiveLayout(
            _rootGrid.ActualWidth,
            _rootGrid,
            _headerGrid,
            _tabs,
            _toolbar,
            _moviesBackButton,
            _libraryBox,
            _searchBox,
            _sortBox,
            _scanButton,
            _addButton);
    }

    private static void ApplyLibraryResponsiveLayout(
        double width,
        Grid root,
        Grid header,
        StackPanel tabs,
        Grid toolbar,
        Button moviesBackButton,
        ComboBox libraryBox,
        TextBox searchBox,
        ComboBox sortBox,
        Button scanButton,
        Button addButton)
    {
        var compactToolbar = width < FluentTheme.MediumBreakpoint;
        var backButtonVisible = moviesBackButton.Visibility == Visibility.Visible;
        root.Padding = FluentTheme.PagePadding(width);

        header.ColumnDefinitions[1].Width = GridLength.Auto;
        header.RowDefinitions[1].Height = new GridLength(0);
        Grid.SetColumn(tabs, 1);
        Grid.SetRow(tabs, 0);
        tabs.HorizontalAlignment = HorizontalAlignment.Right;

        toolbar.RowSpacing = 0;
        for (var i = 1; i < toolbar.RowDefinitions.Count; i++)
        {
            toolbar.RowDefinitions[i].Height = new GridLength(0);
        }

        var controls = new FrameworkElement[] { moviesBackButton, libraryBox, searchBox, sortBox, scanButton, addButton };
        if (compactToolbar)
        {
            ApplyCompressedToolbarLayout(toolbar, controls, backButtonVisible);
        }
        else
        {
            ApplyWideToolbarLayout(toolbar, controls, backButtonVisible);
        }

        libraryBox.Width = compactToolbar ? double.NaN : HeaderInputWidth;
        searchBox.Width = compactToolbar ? double.NaN : HeaderInputWidth;
        sortBox.Width = double.NaN;
        libraryBox.MinWidth = 0;
        searchBox.MinWidth = 0;
        sortBox.MinWidth = compactToolbar ? CompactSortMinWidth : 160;
    }

    private static void ApplyCompressedToolbarLayout(Grid toolbar, IReadOnlyList<FrameworkElement> controls, bool backButtonVisible)
    {
        if (backButtonVisible)
        {
            toolbar.ColumnDefinitions[0].Width = GridLength.Auto;
            toolbar.ColumnDefinitions[1].Width = new GridLength(1, GridUnitType.Star);
            toolbar.ColumnDefinitions[2].Width = new GridLength(1.25, GridUnitType.Star);
            toolbar.ColumnDefinitions[3].Width = new GridLength(1, GridUnitType.Star);
            toolbar.ColumnDefinitions[4].Width = GridLength.Auto;
            toolbar.ColumnDefinitions[5].Width = GridLength.Auto;
            toolbar.ColumnDefinitions[6].Width = GridLength.Auto;
            ApplyToolbarControlPositions(controls, [0, 1, 2, 4, 5, 6]);
        }
        else
        {
            toolbar.ColumnDefinitions[0].Width = new GridLength(1, GridUnitType.Star);
            toolbar.ColumnDefinitions[1].Width = new GridLength(1.25, GridUnitType.Star);
            toolbar.ColumnDefinitions[2].Width = new GridLength(1, GridUnitType.Star);
            toolbar.ColumnDefinitions[3].Width = GridLength.Auto;
            toolbar.ColumnDefinitions[4].Width = GridLength.Auto;
            toolbar.ColumnDefinitions[5].Width = GridLength.Auto;
            toolbar.ColumnDefinitions[6].Width = GridLength.Auto;
            ApplyToolbarControlPositions(controls, [0, 0, 1, 4, 5, 6]);
        }

        controls[0].HorizontalAlignment = HorizontalAlignment.Left;
        controls[1].HorizontalAlignment = HorizontalAlignment.Stretch;
        controls[2].HorizontalAlignment = HorizontalAlignment.Stretch;
        controls[3].HorizontalAlignment = HorizontalAlignment.Stretch;
        controls[4].HorizontalAlignment = HorizontalAlignment.Left;
        controls[5].HorizontalAlignment = HorizontalAlignment.Left;
    }

    private static void ApplyWideToolbarLayout(Grid toolbar, IReadOnlyList<FrameworkElement> controls, bool backButtonVisible)
    {
        toolbar.ColumnDefinitions[0].Width = GridLength.Auto;
        toolbar.ColumnDefinitions[1].Width = GridLength.Auto;
        toolbar.ColumnDefinitions[2].Width = GridLength.Auto;
        toolbar.ColumnDefinitions[3].Width = new GridLength(1, GridUnitType.Star);
        toolbar.ColumnDefinitions[4].Width = GridLength.Auto;
        toolbar.ColumnDefinitions[5].Width = GridLength.Auto;
        toolbar.ColumnDefinitions[6].Width = GridLength.Auto;
        ApplyToolbarControlPositions(controls, backButtonVisible ? [0, 1, 2, 4, 5, 6] : [0, 0, 1, 4, 5, 6]);

        foreach (var control in controls)
        {
            control.HorizontalAlignment = HorizontalAlignment.Left;
        }
    }

    private static void ApplyToolbarControlPositions(IReadOnlyList<FrameworkElement> controls, IReadOnlyList<int> columns)
    {
        for (var i = 0; i < controls.Count; i++)
        {
            Grid.SetColumn(controls[i], columns[i]);
            Grid.SetRow(controls[i], 0);
        }
    }

    private async void OnLoaded(object sender, RoutedEventArgs args)
    {
        try
        {
            AppServices.MediaTree.Library.LibrariesChanged -= OnLibrariesChanged;
            AppServices.MediaTree.Library.LibrariesChanged += OnLibrariesChanged;
            LoadUiPreferences();
            await LoadLibrariesAsync();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Unhandled native library page load failure.");
            ShowInfo($"加载媒体库失败：{ex.Message}", InfoBarSeverity.Error);
        }
    }

    private void OnUnloaded(object sender, RoutedEventArgs args)
    {
        AppServices.MediaTree.Library.LibrariesChanged -= OnLibrariesChanged;
        _scanTimer.Stop();
    }

    private void OnLibrariesChanged(object? sender, EventArgs args)
    {
        if (DispatcherQueue.HasThreadAccess)
        {
            _ = LoadLibrariesAsync();
            return;
        }

        _ = DispatcherQueue.TryEnqueue(() => _ = LoadLibrariesAsync());
    }

    private void LoadUiPreferences()
    {
        var preferences = UiPreferenceStore.Load();
        _hideHomeTitleText = preferences.HideHomeTitleText;
        _showSourceName = preferences.ShowSourceName;
        _excludedFolderPaths = preferences.ExcludedFolders;
    }

    private async Task LoadLibrariesAsync()
    {
        SetLoading(true);
        try
        {
            var setup = await AppServices.MediaTree.Library.GetSetupStatusAsync();
            if (setup.NeedsSetup)
            {
                ShellPage.Current?.NavigateToSetup();
                return;
            }

            var roots = await AppServices.MediaTree.Library.GetMediaRootsAsync();
            _suppressLibrarySelectionChanged = true;
            try
            {
                _libraryBox.Items.Clear();
                foreach (var root in roots.Items)
                {
                    _libraryBox.Items.Add(CreateLibraryItem(root));
                }

                _libraryBox.SelectedIndex = roots.Items.Count > 0 ? 0 : -1;
            }
            finally
            {
                _suppressLibrarySelectionChanged = false;
            }

            if (roots.Items.Count > 0)
            {
                _activeMediaRoot = roots.Items[0].Path;
                await LoadFoldersAsync();
                _scanTimer.Start();
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load native media roots.");
            ShowInfo($"加载媒体文件夹失败：{ex.Message}", InfoBarSeverity.Error);
        }
        finally
        {
            SetLoading(false);
        }
    }

    private async Task LoadFoldersAsync()
    {
        if (string.IsNullOrWhiteSpace(_activeMediaRoot))
        {
            return;
        }

        var mediaRoot = _activeMediaRoot;
        var generation = ++_movieLoadGeneration;
        try
        {
            SetLoading(true);
            _activeView = "folders";
            _activeFolderPath = "";
            ShowFoldersView();
            _folderGrid.Items.Clear();
            _moviesGrid.Items.Clear();

            var response = await AppServices.MediaTree.Library.GetFoldersAsync(mediaRoot);
            if (generation != _movieLoadGeneration || mediaRoot != _activeMediaRoot)
            {
                return;
            }

            var folders = SortFolders(BrowseLibraryPresenter.FilterExcludedFolders(response.Tree, _excludedFolderPaths))
                .Where(folder => folder.MovieCount > 0)
                .ToList();
            var cards = new List<Button>();
            foreach (var folder in folders)
            {
                if (string.IsNullOrWhiteSpace(folder.MediaRoot))
                {
                    folder.MediaRoot = mediaRoot;
                }

                var cover = await BuildFolderCoverUrlAsync(folder);
                cards.Add(CreateFolderCard(new FolderCardItem(folder, cover)));
            }

            if (generation != _movieLoadGeneration || mediaRoot != _activeMediaRoot)
            {
                return;
            }

            _folderGrid.Items.Clear();
            foreach (var card in cards)
            {
                _folderGrid.Items.Add(card);
            }

            _headerTitleText.Text = "我的媒体库";
            _headerSubtitleText.Text = $"共 {folders.Count} 个目录";
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load native library folders.");
            ShowInfo($"加载媒体库目录失败：{ex.Message}", InfoBarSeverity.Error);
        }
        finally
        {
            if (generation == _movieLoadGeneration)
            {
                SetLoading(false);
            }
        }
    }

    private async Task LoadMoviesAsync(string folderPath = "", bool recent = false)
    {
        if (string.IsNullOrWhiteSpace(_activeMediaRoot))
        {
            return;
        }

        var mediaRoot = _activeMediaRoot;
        var generation = ++_movieLoadGeneration;
        try
        {
            SetLoading(true);
            _activeView = recent ? "recent" : "movies";
            if (!recent)
            {
                _activeFolderPath = folderPath;
            }

            ShowMoviesView(recent);
            _moviesGrid.Items.Clear();
            _folderGrid.Items.Clear();
            var sort = (_sortBox.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "created_desc";
            var response = recent
                ? await AppServices.MediaTree.Movie.GetRecentWatchedAsync(mediaRoot, 80, 0)
                : await AppServices.MediaTree.Movie.GetMoviesAsync(mediaRoot, folderPath, _searchBox.Text.Trim(), sort, 80, 0);
            if (generation != _movieLoadGeneration || mediaRoot != _activeMediaRoot)
            {
                return;
            }

            var cards = new List<Button>();
            foreach (var movie in response.Movies)
            {
                var cover = "";
                try
                {
                    cover = await AppServices.MediaTree.Api.BuildCoverUrlAsync(movie.Id);
                }
                catch (Exception ex)
                {
                    ShellLogger.Error(ex, $"Failed to build native cover URL for movie {movie.Id}.");
                }

                cards.Add(CreateMovieCard(
                    new MovieCardItem(movie, cover),
                    CreateContextMenuHost(async () => await LoadMoviesAsync(folderPath, recent))));
            }

            if (generation != _movieLoadGeneration || mediaRoot != _activeMediaRoot)
            {
                return;
            }

            _moviesGrid.Items.Clear();
            foreach (var card in cards)
            {
                _moviesGrid.Items.Add(card);
            }

            _headerTitleText.Text = recent ? "继续观看" : (string.IsNullOrWhiteSpace(folderPath) ? "搜索结果" : FolderTitleFromPath(folderPath));
            _headerSubtitleText.Text = recent ? $"共 {response.Movies.Count} 部" : $"共 {response.Movies.Count} 部影片";
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to load native library movies.");
            ShowInfo($"加载媒体库失败：{ex.Message}", InfoBarSeverity.Error);
        }
        finally
        {
            if (generation == _movieLoadGeneration)
            {
                SetLoading(false);
            }
        }
    }

    private async void OnLibraryChanged(object sender, SelectionChangedEventArgs args)
    {
        if (_suppressLibrarySelectionChanged)
        {
            return;
        }

        if (_libraryBox.SelectedItem is not ComboBoxItem { Tag: MediaRootDto root })
        {
            return;
        }

        try
        {
            _activeMediaRoot = root.Path;
            _searchBox.Text = "";
            if (_activeView == "recent")
            {
                await LoadMoviesAsync("", true);
            }
            else
            {
                await LoadFoldersAsync();
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to change native library selection.");
            ShowInfo($"切换媒体文件夹失败：{ex.Message}", InfoBarSeverity.Error);
        }
    }

    private async void OnSortChanged(object sender, SelectionChangedEventArgs args)
    {
        try
        {
            if (IsLoaded)
            {
                if (_activeView == "folders")
                {
                    await LoadFoldersAsync();
                }
                else
                {
                    await LoadMoviesAsync(_activeFolderPath, _activeView == "recent");
                }
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to sort native library movies.");
            ShowInfo($"排序失败：{ex.Message}", InfoBarSeverity.Error);
        }
    }

    private async void OnSearchKeyDown(object sender, KeyRoutedEventArgs args)
    {
        try
        {
            if (args.Key == global::Windows.System.VirtualKey.Enter)
            {
                if (string.IsNullOrWhiteSpace(_searchBox.Text) && _activeView != "movies")
                {
                    await LoadFoldersAsync();
                    return;
                }

                await LoadMoviesAsync(_activeFolderPath, false);
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to search native library movies.");
            ShowInfo($"搜索失败：{ex.Message}", InfoBarSeverity.Error);
        }
    }

    private async void OnScanClicked(object sender, RoutedEventArgs args)
    {
        var mediaRoot = _activeMediaRoot;
        if (string.IsNullOrWhiteSpace(mediaRoot))
        {
            return;
        }

        _scanButton.IsEnabled = false;
        _activeScanMediaRoot = mediaRoot;
        _scanHasObservedActiveStatus = false;
        ShowScanProgress();
        _scanTimer.Start();
        _ = StartLibraryScanInBackgroundAsync(mediaRoot);
        await RefreshScanProgressAsync(mediaRoot);
    }

    private void OnAddLibraryClicked(object sender, RoutedEventArgs args)
    {
        ShellPage.Current?.NavigateToSetup();
    }

    private async void OnFolderTabClicked(object sender, RoutedEventArgs args)
    {
        try
        {
            _searchBox.Text = "";
            await LoadFoldersAsync();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to switch native library folder tab.");
            ShowInfo($"切换媒体库失败：{ex.Message}", InfoBarSeverity.Error);
        }
    }

    private async void OnRecentTabClicked(object sender, RoutedEventArgs args)
    {
        try
        {
            _searchBox.Text = "";
            await LoadMoviesAsync("", true);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to switch native library recent tab.");
            ShowInfo($"切换继续观看失败：{ex.Message}", InfoBarSeverity.Error);
        }
    }

    private async void OnBackToFoldersClicked(object sender, RoutedEventArgs args)
    {
        try
        {
            _searchBox.Text = "";
            await LoadFoldersAsync();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to return native library folder grid.");
            ShowInfo($"返回媒体库失败：{ex.Message}", InfoBarSeverity.Error);
        }
    }

    private void OnFolderItemClick(object sender, ItemClickEventArgs args)
    {
        if (args.ClickedItem is not FrameworkElement { Tag: FolderCardItem item })
        {
            return;
        }

        OpenFolderItem(item);
    }

    private void OnMovieItemClick(object sender, ItemClickEventArgs args)
    {
        if (args.ClickedItem is FrameworkElement { Tag: MovieCardItem item })
        {
            ShellPage.Current?.NavigateToMovie(item.Id);
        }
    }

    private void OpenFolderItem(FolderCardItem item)
    {
        try
        {
            if (!string.IsNullOrWhiteSpace(item.MediaRoot))
            {
                _activeMediaRoot = item.MediaRoot;
            }

            _searchBox.Text = "";
            ShellPage.Current?.NavigateToFolder(item.Path, _activeMediaRoot, item.Title);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to open native library folder.");
            ShowInfo($"打开目录失败：{ex.Message}", InfoBarSeverity.Error);
        }
    }

    private async void OnScanTimerTick(object? sender, object args)
        => await RefreshActiveScanProgressAsync();

    private async Task RefreshActiveScanProgressAsync()
    {
        var mediaRoot = string.IsNullOrWhiteSpace(_activeScanMediaRoot) ? _activeMediaRoot : _activeScanMediaRoot;
        if (string.IsNullOrWhiteSpace(mediaRoot))
        {
            return;
        }

        try
        {
            await RefreshScanProgressAsync(mediaRoot);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to poll native library scan status.");
            _scanButton.IsEnabled = true;
            _scanTimer.Stop();
        }
    }

    private async Task RefreshScanProgressAsync(string mediaRoot)
    {
        try
        {
            var status = await AppServices.MediaTree.Library.GetScanStatusAsync(mediaRoot);
            if (string.IsNullOrWhiteSpace(status.Status) || status.Status == "idle")
            {
                return;
            }

            if (IsActiveScanStatus(status.Status))
            {
                _scanHasObservedActiveStatus = true;
            }

            var terminalStatus = IsTerminalScanStatus(status.Status);
            if (terminalStatus && mediaRoot == _activeScanMediaRoot && !_scanHasObservedActiveStatus)
            {
                return;
            }

            if (terminalStatus)
            {
                ShowCompletedScanProgress(status);
                _scanTimer.Stop();
                _scanButton.IsEnabled = true;
                _activeScanMediaRoot = "";
                _scanHasObservedActiveStatus = false;
                if (mediaRoot != _activeMediaRoot)
                {
                    return;
                }

                if (_activeView == "folders")
                {
                    await LoadFoldersAsync();
                }
                else
                {
                    await LoadMoviesAsync(_activeFolderPath, _activeView == "recent");
                }

                return;
            }

            UpdateScanProgress(status);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to poll native library scan status.");
            _scanButton.IsEnabled = true;
            _scanTimer.Stop();
        }
    }

    private async Task StartLibraryScanInBackgroundAsync(string mediaRoot)
    {
        try
        {
            await AppServices.MediaTree.Library.ScanAsync(mediaRoot);
            if (mediaRoot == _activeScanMediaRoot)
            {
                _scanHasObservedActiveStatus = true;
                await RefreshScanProgressAsync(mediaRoot);
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Failed to start native library scan.");
            if (mediaRoot == _activeScanMediaRoot)
            {
                _scanButton.IsEnabled = true;
                _activeScanMediaRoot = "";
                _scanHasObservedActiveStatus = false;
                _scanTimer.Stop();
                if (mediaRoot == _activeMediaRoot)
                {
                    ShowInfo($"刮削启动失败：{ex.Message}", InfoBarSeverity.Error);
                }
            }
        }
    }

    private void ShowInfo(string message, InfoBarSeverity severity)
    {
        _scanProgressGeneration++;
        _scanInfoText.Text = message;
        _scanInfoText.Foreground = severity == InfoBarSeverity.Error ? FluentTheme.Error : FluentTheme.TextSecondary;
        _scanInfoText.Visibility = Visibility.Visible;
        _scanProgressTrack.Visibility = Visibility.Collapsed;
    }

    private void ShowScanProgress()
    {
        _scanProgressGeneration++;
        _scanInfoText.Visibility = Visibility.Collapsed;
        _scanInfoText.Text = "";
        UpdateScanProgressFill(0, 0);
        _scanProgressTrack.Visibility = Visibility.Visible;
    }

    private void UpdateScanProgress(ScanStatusDto status)
    {
        if (status.Status is "done" or "disabled" or "cancelled")
        {
            _scanProgressTrack.Visibility = Visibility.Collapsed;
            return;
        }

        _scanInfoText.Visibility = Visibility.Collapsed;
        _scanProgressTrack.Visibility = Visibility.Visible;
        UpdateScanProgressFill(status.Done, status.Total);
    }

    private void ShowCompletedScanProgress(ScanStatusDto status)
    {
        _scanInfoText.Visibility = Visibility.Collapsed;
        _scanProgressTrack.Visibility = Visibility.Visible;
        if (status.Status == "done" && status.Total > 0)
        {
            UpdateScanProgressFill(status.Total, status.Total);
        }
        else
        {
            UpdateScanProgressFill(status.Done, status.Total);
        }

        _ = HideScanProgressAfterCompletionAsync(_scanProgressGeneration);
    }

    private async Task HideScanProgressAfterCompletionAsync(int generation)
    {
        await Task.Delay(1200);
        if (generation == _scanProgressGeneration)
        {
            _scanProgressTrack.Visibility = Visibility.Collapsed;
        }
    }

    private void UpdateScanProgressFill(int done, int total)
    {
        var ratio = total > 0 ? Math.Clamp(done / (double)total, 0, 1) : 0;
        _scanProgressFill.Width = _scanProgressTrack.Width * ratio;
    }

    private void SetLoading(bool isLoading)
    {
        _loadingText.Visibility = isLoading ? Visibility.Visible : Visibility.Collapsed;
    }

    private async Task<string> BuildFolderCoverUrlAsync(FolderNodeDto folder)
    {
        var cover = string.IsNullOrWhiteSpace(folder.RandomCover) ? folder.Cover : folder.RandomCover;
        if (string.IsNullOrWhiteSpace(cover))
        {
            return "";
        }

        try
        {
            return await AppServices.MediaTree.Api.BuildMediaAssetUrlAsync(cover);
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Failed to build native folder cover URL for {folder.Path}.");
            return "";
        }
    }

    private IEnumerable<FolderNodeDto> SortFolders(IEnumerable<FolderNodeDto> folders)
    {
        var sort = (_sortBox.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "created_desc";
        return sort switch
        {
            "name" => folders.OrderBy(folder => folder.BestTitle, StringComparer.CurrentCultureIgnoreCase),
            "release_date_desc" => folders.OrderByDescending(folder => folder.ReleaseDateMax ?? ""),
            _ => folders.OrderByDescending(folder => folder.CreatedMax ?? ""),
        };
    }

    private void ShowFoldersView()
    {
        _folderGrid.Visibility = Visibility.Visible;
        _moviesGrid.Visibility = Visibility.Collapsed;
        _moviesBackButton.Visibility = Visibility.Collapsed;
        _activeView = "folders";
        ApplyTabStyles();
        ApplyCurrentLayout();
    }

    private void ShowMoviesView(bool recent)
    {
        _folderGrid.Visibility = Visibility.Collapsed;
        _moviesGrid.Visibility = Visibility.Visible;
        _moviesBackButton.Visibility = recent ? Visibility.Collapsed : Visibility.Visible;
        _activeView = recent ? "recent" : "movies";
        ApplyTabStyles();
        ApplyCurrentLayout();
    }

    private void ApplyTabStyles()
    {
        FluentTheme.ApplyButton(_folderTabButton, _activeView == "recent" ? FluentButtonStyle.Standard : FluentButtonStyle.Accent);
        FluentTheme.ApplyButton(_recentTabButton, _activeView == "recent" ? FluentButtonStyle.Accent : FluentButtonStyle.Standard);
    }

    private Button CreateFolderCard(FolderCardItem item)
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
            ShellLogger.Error(ex, $"Failed to create native folder cover image for {item.Path}.");
            AddCoverFallback(imageHost);
        }

        var textStack = new StackPanel
        {
            Padding = new Thickness(12),
            Spacing = 4,
        };
        if (!_hideHomeTitleText)
        {
            textStack.Children.Add(new TextBlock
            {
                Text = _showSourceName ? item.SourceName : item.Title,
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
        }

        var stack = new StackPanel();
        stack.Children.Add(imageHost);
        if (!_hideHomeTitleText)
        {
            stack.Children.Add(textStack);
        }

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
        AutomationProperties.SetAutomationId(card, $"FolderCard_{SanitizeAutomationId(item.Path)}");
        card.ContextFlyout = MediaContextMenuService.CreateFolderFlyout(
            item,
            CreateContextMenuHost(async () => await LoadFoldersAsync()));
        card.Click += (_, _) => OpenFolderItem(item);
        return card;
    }

    private Button CreateMovieCard(MovieCardItem item, MediaContextMenuHost? contextHost = null)
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
            ShellLogger.Error(ex, $"Failed to create native cover image for movie {item.Id}.");
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
        textStack.Children.Add(new TextBlock
        {
            Text = item.ProgressText,
            FontSize = 12,
            Foreground = FluentTheme.Accent,
        });

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
        AutomationProperties.SetAutomationId(card, $"MovieCard_{item.Id}");
        if (contextHost is not null)
        {
            card.ContextFlyout = MediaContextMenuService.CreateMovieFlyout(item, contextHost);
        }

        card.Click += (_, _) => ShellPage.Current?.NavigateToMovie(item.Id);
        return card;
    }

    private MediaContextMenuHost CreateContextMenuHost(Func<Task> refreshAsync)
        => new()
        {
            XamlRoot = XamlRoot,
            ShowStatus = (message, isError) => ShowInfo(message, isError ? InfoBarSeverity.Error : InfoBarSeverity.Informational),
            RefreshAsync = refreshAsync,
        };

    private static ComboBoxItem CreateLibraryItem(MediaRootDto root)
    {
        var label = string.IsNullOrWhiteSpace(root.Label) ? root.Path : root.Label;
        var count = root.MovieCount > 0 ? $" · {root.MovieCount}" : "";
        return new ComboBoxItem
        {
            Content = $"{label}{count}",
            Tag = root,
        };
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

    private static string SanitizeAutomationId(string value)
        => value.Replace("\\", "_").Replace("/", "_").Replace(":", "_");

    private static bool IsActiveScanStatus(string status)
        => status is "running" or "scanning" or "scanned" or "scraping";

    private static bool IsTerminalScanStatus(string status)
        => status is "done" or "disabled" or "cancelled";

    private static string FolderTitleFromPath(string folderPath)
    {
        if (string.IsNullOrWhiteSpace(folderPath))
        {
            return "影片";
        }

        var normalized = folderPath.Replace("\\", "/").TrimEnd('/');
        var index = normalized.LastIndexOf("/", StringComparison.Ordinal);
        return index >= 0 ? normalized[(index + 1)..] : normalized;
    }
}
