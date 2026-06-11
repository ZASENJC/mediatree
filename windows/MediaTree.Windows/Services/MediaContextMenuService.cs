using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MediaTree.Windows.Models;
using MediaTree.Windows.Styles;
using MediaTree.Windows.ViewModels;
using MediaTree.Windows.Views;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;
using Windows.Storage.Pickers;
using WinRT.Interop;

namespace MediaTree.Windows.Services;

public sealed class MediaContextMenuHost
{
    public required XamlRoot XamlRoot { get; init; }
    public required Action<string, bool> ShowStatus { get; init; }
    public required Func<Task> RefreshAsync { get; init; }
}

public static class MediaContextMenuService
{
    public static MenuFlyout CreateMovieFlyout(MovieCardItem item, MediaContextMenuHost host)
    {
        var flyout = FluentTheme.ApplyMenuFlyout(new MenuFlyout());
        if (!item.IsSpecial)
        {
            flyout.Items.Add(CreateItem("重新刮削", async () => await RunMovieActionAsync(item, host, "重新刮削", () => AppServices.MediaTree.Movie.RescrapeMovieAsync(item.Id))));
            flyout.Items.Add(CreateItem("手动刮削", async () => await ShowManualScrapeDialogAsync(item.Movie, host)));
        }

        flyout.Items.Add(CreateItem("更换封面", async () => await ShowMovieCoverDialogAsync(item.Movie, host)));
        flyout.Items.Add(CreateItem("编辑信息", async () => await ShowEditMovieDialogAsync(item.Movie, host)));
        flyout.Items.Add(CreateItem("删除", async () => await DeleteMovieAsync(item.Movie, host), destructive: true));
        return flyout;
    }

    public static MenuFlyout CreateFolderFlyout(FolderCardItem item, MediaContextMenuHost host)
    {
        var flyout = FluentTheme.ApplyMenuFlyout(new MenuFlyout());
        flyout.Items.Add(CreateItem("重新刮削", async () => await RunFolderActionAsync(item, host, "重新刮削", () => AppServices.MediaTree.Movie.RescrapeFolderAsync(item.Path, item.MediaRoot))));
        flyout.Items.Add(CreateItem("手动刮削", async () => await ShowFolderScrapeDialogAsync(item, host)));
        flyout.Items.Add(CreateItem("更换封面", async () => await ShowFolderCoverDialogAsync(item, host)));
        flyout.Items.Add(CreateItem("编辑信息", async () => await ShowEditFolderDialogAsync(item, host)));
        if (item.Folder.SpecialCount > 0)
        {
            flyout.Items.Add(CreateItem(item.Folder.ShowSpecials ? $"隐藏花絮 ({item.Folder.SpecialCount})" : $"显示花絮 ({item.Folder.SpecialCount})", async () => await ToggleFolderSpecialsAsync(item, host)));
        }

        flyout.Items.Add(CreateItem("删除", async () => await DeleteFolderAsync(item, host), destructive: true));
        return flyout;
    }

    private static MenuFlyoutItem CreateItem(string text, Func<Task> action, bool destructive = false)
    {
        var item = new MenuFlyoutItem
        {
            Text = text,
            Foreground = destructive ? FluentTheme.Error : FluentTheme.TextPrimary,
        };
        item.Click += async (_, _) => await action();
        return item;
    }

    private static async Task RunMovieActionAsync(MovieCardItem item, MediaContextMenuHost host, string label, Func<Task<BasicActionResultDto>> action)
    {
        try
        {
            host.ShowStatus($"正在{label}：{item.Title}", false);
            await action();
            host.ShowStatus($"{label}已完成", false);
            await host.RefreshAsync();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Native movie context action failed: {label} movie={item.Id}.");
            host.ShowStatus($"{label}失败：{ex.Message}", true);
        }
    }

    private static async Task RunFolderActionAsync(FolderCardItem item, MediaContextMenuHost host, string label, Func<Task<BasicActionResultDto>> action)
    {
        try
        {
            host.ShowStatus($"正在{label}：{item.Title}", false);
            await action();
            host.ShowStatus($"{label}已完成", false);
            await host.RefreshAsync();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Native folder context action failed: {label} folder={item.Path}.");
            host.ShowStatus($"{label}失败：{ex.Message}", true);
        }
    }

    private static async Task ShowManualScrapeDialogAsync(MovieDto movie, MediaContextMenuHost host)
    {
        var queryBox = FluentTheme.ApplyTextInput(new TextBox
        {
            Header = "搜索关键词",
            Text = movie.BestTitle,
            PlaceholderText = "输入片名、原名或编号",
        });
        var scraperBox = CreateScraperBox("刮削器");
        var resultsList = FluentTheme.ApplyListView(new ListView
        {
            SelectionMode = ListViewSelectionMode.Single,
            MaxHeight = 360,
        });
        var status = StatusText("输入关键词后搜索，选择一个结果应用到当前影片。");
        var searchButton = FluentTheme.ApplyButton(new Button { Content = "搜索", HorizontalAlignment = HorizontalAlignment.Left }, FluentButtonStyle.Accent);
        searchButton.Click += async (_, _) => await SearchScrapeIntoListAsync(queryBox.Text, SelectedScraper(scraperBox), movie.MediaRoot, resultsList, status, searchButton);

        var stack = DialogStack(queryBox, scraperBox, searchButton, status, resultsList);
        var dialog = new WindowModalDialog("手动刮削", stack, "应用所选结果");
        dialog.PrimaryActionAsync = async () =>
        {
            if (resultsList.SelectedItem is not FrameworkElement { Tag: ScrapeSearchResultDto selected })
            {
                status.Foreground = FluentTheme.Error;
                status.Text = "请先选择一个候选结果。";
                return false;
            }

            try
            {
                status.Foreground = FluentTheme.TextSecondary;
                status.Text = "正在应用刮削结果...";
                await AppServices.MediaTree.Movie.ManualScrapeMovieAsync(movie.Id, selected.Title, selected.SourceId, selected.MediaType, string.IsNullOrWhiteSpace(selected.Scraper) ? SelectedScraper(scraperBox) : selected.Scraper);
                await host.RefreshAsync();
                return true;
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, $"Native manual movie scrape failed: movie={movie.Id}.");
                status.Foreground = FluentTheme.Error;
                status.Text = "应用失败：" + ex.Message;
                return false;
            }
        };

        await dialog.ShowAsync();
    }

    private static async Task ShowFolderScrapeDialogAsync(FolderCardItem folder, MediaContextMenuHost host)
    {
        var queryBox = FluentTheme.ApplyTextInput(new TextBox
        {
            Header = "搜索关键词",
            Text = folder.Title,
            PlaceholderText = "输入目录对应的片名或合集名",
        });
        var scraperBox = CreateScraperBox("刮削器");
        var resultsList = FluentTheme.ApplyListView(new ListView
        {
            SelectionMode = ListViewSelectionMode.Single,
            MaxHeight = 360,
        });
        var status = StatusText("搜索后选择一个结果，应用到当前目录下的影片。");
        var searchButton = FluentTheme.ApplyButton(new Button { Content = "搜索", HorizontalAlignment = HorizontalAlignment.Left }, FluentButtonStyle.Accent);
        searchButton.Click += async (_, _) => await SearchScrapeIntoListAsync(queryBox.Text, SelectedScraper(scraperBox), folder.MediaRoot, resultsList, status, searchButton);

        var stack = DialogStack(queryBox, scraperBox, searchButton, status, resultsList);
        var dialog = new WindowModalDialog("手动刮削目录", stack, "应用所选结果");
        dialog.PrimaryActionAsync = async () =>
        {
            if (resultsList.SelectedItem is not FrameworkElement { Tag: ScrapeSearchResultDto selected })
            {
                status.Foreground = FluentTheme.Error;
                status.Text = "请先选择一个候选结果。";
                return false;
            }

            try
            {
                status.Foreground = FluentTheme.TextSecondary;
                status.Text = "正在应用刮削结果...";
                await AppServices.MediaTree.Movie.ApplyFolderScrapeAsync(folder.Path, folder.MediaRoot, selected.SourceId, selected.Source, selected.MediaType);
                await host.RefreshAsync();
                return true;
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, $"Native manual folder scrape failed: folder={folder.Path}.");
                status.Foreground = FluentTheme.Error;
                status.Text = "应用失败：" + ex.Message;
                return false;
            }
        };

        await dialog.ShowAsync();
    }

    private static async Task SearchScrapeIntoListAsync(string query, string scraper, string mediaRoot, ListView resultsList, TextBlock status, Button searchButton)
    {
        var trimmed = query.Trim();
        if (string.IsNullOrWhiteSpace(trimmed))
        {
            status.Foreground = FluentTheme.Error;
            status.Text = "请先输入搜索关键词。";
            return;
        }

        try
        {
            searchButton.IsEnabled = false;
            status.Foreground = FluentTheme.TextSecondary;
            status.Text = "正在搜索候选结果...";
            resultsList.Items.Clear();
            var response = await AppServices.MediaTree.Movie.SearchScrapeAsync(trimmed, scraper, mediaRoot);
            foreach (var result in response.Results)
            {
                resultsList.Items.Add(await CreateScrapeResultRowAsync(ScrapeResultPresenter.NormalizeScraper(result, scraper)));
            }

            status.Text = response.Results.Count == 0 ? "没有找到匹配结果。" : $"找到 {response.Results.Count} 个候选结果。";
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, "Native context scrape search failed.");
            status.Foreground = FluentTheme.Error;
            status.Text = "搜索失败：" + ex.Message;
        }
        finally
        {
            searchButton.IsEnabled = true;
        }
    }

    private static async Task ShowMovieCoverDialogAsync(MovieDto movie, MediaContextMenuHost host)
    {
        try
        {
            var response = await AppServices.MediaTree.Movie.GetAlternativeCoversAsync(movie.Id);
            await ShowCoverDialogAsync(host, response.Covers, async cover =>
            {
                await AppServices.MediaTree.Movie.ChangeMovieCoverAsync(movie.Id, cover.Url);
                await host.RefreshAsync();
            }, async () => await UploadMovieCoverAsync(movie, host));
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Native movie cover picker failed: movie={movie.Id}.");
            host.ShowStatus("封面加载失败：" + ex.Message, true);
        }
    }

    private static async Task ShowFolderCoverDialogAsync(FolderCardItem folder, MediaContextMenuHost host)
    {
        try
        {
            var first = await AppServices.MediaTree.Movie.GetMoviesAsync(folder.MediaRoot, folder.Path, "", "created_desc", 1, 0);
            var movie = first.Movies.FirstOrDefault();
            if (movie is null)
            {
                host.ShowStatus("目录下无影片", true);
                return;
            }

            var response = await AppServices.MediaTree.Movie.GetAlternativeCoversAsync(movie.Id);
            await ShowCoverDialogAsync(host, response.Covers, async cover =>
            {
                await AppServices.MediaTree.Movie.ChangeFolderCoverAsync(folder.Path, folder.MediaRoot, cover.Url);
                await host.RefreshAsync();
            });
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Native folder cover picker failed: folder={folder.Path}.");
            host.ShowStatus("封面加载失败：" + ex.Message, true);
        }
    }

    private static async Task ShowCoverDialogAsync(
        MediaContextMenuHost host,
        List<CoverChoiceDto> covers,
        Func<CoverChoiceDto, Task> applyAsync,
        Func<Task>? uploadAsync = null)
    {
        if (covers.Count == 0 && uploadAsync is null)
        {
            host.ShowStatus("没有找到备用封面", true);
            return;
        }

        var grid = FluentTheme.ApplyGridView(new GridView
        {
            SelectionMode = ListViewSelectionMode.Single,
            MaxHeight = 520,
        });
        foreach (var cover in covers)
        {
            grid.Items.Add(await CreateCoverChoiceCardAsync(cover));
        }

        var content = DialogStack();
        if (covers.Count > 0)
        {
            content.Children.Add(grid);
        }
        else
        {
            content.Children.Add(StatusText("没有找到备用封面，可以上传本地图片。"));
        }

        ContentDialog? dialog = null;
        if (uploadAsync is not null)
        {
            var uploadButton = FluentTheme.ApplyButton(new Button
            {
                Content = "上传本地图片",
                HorizontalAlignment = HorizontalAlignment.Left,
            });
            uploadButton.Click += async (_, _) =>
            {
                try
                {
                    uploadButton.IsEnabled = false;
                    await uploadAsync();
                    dialog?.Hide();
                }
                finally
                {
                    uploadButton.IsEnabled = true;
                }
            };
            content.Children.Add(uploadButton);
        }

        dialog = CreateDialog(host.XamlRoot, "更换封面", content, "应用所选封面");
        dialog.IsPrimaryButtonEnabled = covers.Count > 0;
        dialog.PrimaryButtonClick += async (_, args) =>
        {
            if (grid.SelectedItem is not FrameworkElement { Tag: CoverChoiceDto selected })
            {
                args.Cancel = true;
                return;
            }

            args.Cancel = true;
            try
            {
                dialog.IsPrimaryButtonEnabled = false;
                await applyAsync(selected);
                dialog.Hide();
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, "Native cover apply failed.");
                host.ShowStatus("封面应用失败：" + ex.Message, true);
                dialog.IsPrimaryButtonEnabled = true;
            }
        };

        await dialog.ShowAsync();
    }

    private static async Task UploadMovieCoverAsync(MovieDto movie, MediaContextMenuHost host)
    {
        try
        {
            var picker = new FileOpenPicker
            {
                SuggestedStartLocation = PickerLocationId.PicturesLibrary,
            };
            picker.FileTypeFilter.Add(".jpg");
            picker.FileTypeFilter.Add(".jpeg");
            picker.FileTypeFilter.Add(".png");
            picker.FileTypeFilter.Add(".webp");
            picker.FileTypeFilter.Add(".bmp");
            if (AppServices.MainWindow is not null)
            {
                InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(AppServices.MainWindow));
            }

            var file = await picker.PickSingleFileAsync();
            if (file is null)
            {
                return;
            }

            await AppServices.MediaTree.Movie.UploadMovieCoverAsync(movie.Id, file.Path);
            host.ShowStatus("封面已更新", false);
            await host.RefreshAsync();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Native movie cover upload failed: movie={movie.Id}.");
            host.ShowStatus("上传封面失败：" + ex.Message, true);
        }
    }

    private static async Task<FrameworkElement> CreateCoverChoiceCardAsync(CoverChoiceDto cover)
    {
        var stack = new StackPanel
        {
            Width = 132,
            Margin = new Thickness(5),
            Spacing = 6,
        };
        var host = new Grid
        {
            Height = 196,
            Background = FluentTheme.LayerAlt,
        };
        try
        {
            var url = await AppServices.MediaTree.Api.BuildMediaAssetUrlAsync(cover.Url);
            if (Uri.TryCreate(url, UriKind.Absolute, out var uri))
            {
                host.Children.Add(new Image
                {
                    Source = new Microsoft.UI.Xaml.Media.Imaging.BitmapImage(uri),
                    Stretch = Stretch.UniformToFill,
                });
            }
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Failed to render native cover choice: {cover.Url}.");
        }

        if (host.Children.Count == 0)
        {
            host.Children.Add(new TextBlock
            {
                Text = "无预览",
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center,
                Foreground = FluentTheme.TextTertiary,
            });
        }

        stack.Children.Add(host);
        stack.Children.Add(new TextBlock
        {
            Text = string.IsNullOrWhiteSpace(cover.Source) ? "封面" : cover.Source,
            FontSize = 12,
            Foreground = FluentTheme.TextSecondary,
            TextTrimming = TextTrimming.CharacterEllipsis,
        });
        return new Border
        {
            CornerRadius = FluentTheme.MediaCornerRadius,
            Background = FluentTheme.Layer,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(1),
            Child = stack,
            Tag = cover,
        };
    }

    private static async Task ShowEditMovieDialogAsync(MovieDto movie, MediaContextMenuHost host)
    {
        await ShowEditDialogAsync(
            host,
            "编辑影片信息",
            movie.BestTitle,
            movie.Code,
            movie.Actress,
            movie.ReleaseDate,
            DurationMinutesOrNull(movie.Duration),
            async fields =>
            {
                await AppServices.MediaTree.Movie.EditMovieAsync(movie.Id, fields.Title, fields.Code, fields.Actress, fields.ReleaseDate, fields.Duration);
                await host.RefreshAsync();
            });
    }

    private static async Task ShowEditFolderDialogAsync(FolderCardItem folder, MediaContextMenuHost host)
    {
        MovieDto? firstMovie = null;
        try
        {
            var response = await AppServices.MediaTree.Movie.GetMoviesAsync(folder.MediaRoot, folder.Path, "", "created_desc", 1, 0);
            firstMovie = response.Movies.FirstOrDefault();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Failed to load native folder edit seed: folder={folder.Path}.");
        }

        await ShowEditDialogAsync(
            host,
            "编辑目录信息",
            firstMovie?.BestTitle ?? folder.Title,
            firstMovie?.Code ?? "",
            firstMovie?.Actress ?? "",
            firstMovie?.ReleaseDate ?? "",
            DurationMinutesOrNull(firstMovie?.Duration ?? 0),
            async fields =>
            {
                await AppServices.MediaTree.Movie.EditFolderAsync(folder.Path, folder.MediaRoot, fields.Title, fields.Code, fields.Actress, fields.ReleaseDate, fields.Duration);
                await host.RefreshAsync();
            });
    }

    private sealed record EditFields(string Title, string Code, string Actress, string ReleaseDate, int? Duration);

    private static async Task ShowEditDialogAsync(
        MediaContextMenuHost host,
        string title,
        string initialTitle,
        string initialCode,
        string initialActress,
        string initialReleaseDate,
        int? initialDuration,
        Func<EditFields, Task> saveAsync)
    {
        var titleBox = FluentTheme.ApplyTextInput(new TextBox { Header = "标题", Text = initialTitle });
        var codeBox = FluentTheme.ApplyTextInput(new TextBox { Header = "番号/标识", Text = initialCode });
        var actressBox = FluentTheme.ApplyTextInput(new TextBox { Header = "演员", Text = initialActress });
        var releaseDateBox = FluentTheme.ApplyTextInput(new TextBox { Header = "发行日", PlaceholderText = "YYYY-MM-DD", Text = initialReleaseDate });
        var durationBox = FluentTheme.ApplyNumberInput(new NumberBox
        {
            Header = "时长(分钟)",
            Value = initialDuration ?? double.NaN,
            Minimum = 0,
            SpinButtonPlacementMode = NumberBoxSpinButtonPlacementMode.Compact,
        });
        var status = StatusText("");
        status.Visibility = Visibility.Collapsed;
        var form = DialogStack(titleBox, codeBox, actressBox, releaseDateBox, durationBox, status);
        var dialog = CreateDialog(host.XamlRoot, title, form, "保存");
        dialog.PrimaryButtonClick += async (_, args) =>
        {
            args.Cancel = true;
            try
            {
                dialog.IsPrimaryButtonEnabled = false;
                await saveAsync(new EditFields(
                    titleBox.Text,
                    codeBox.Text,
                    actressBox.Text,
                    releaseDateBox.Text,
                    double.IsNaN(durationBox.Value) ? null : Math.Max(0, (int)durationBox.Value)));
                dialog.Hide();
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, "Native edit dialog save failed.");
                status.Visibility = Visibility.Visible;
                status.Foreground = FluentTheme.Error;
                status.Text = "保存失败：" + ex.Message;
                dialog.IsPrimaryButtonEnabled = true;
            }
        };

        await dialog.ShowAsync();
    }

    private static int? DurationMinutesOrNull(double duration)
        => duration > 0 ? Math.Max(0, (int)Math.Round(duration)) : null;

    private static async Task DeleteMovieAsync(MovieDto movie, MediaContextMenuHost host)
    {
        var confirmed = await ConfirmAsync(host.XamlRoot, "删除影片", $"确定要删除 \"{movie.BestTitle}\"？此操作不可撤销。");
        if (!confirmed)
        {
            return;
        }

        try
        {
            await AppServices.MediaTree.Movie.DeleteMovieAsync(movie.Id);
            host.ShowStatus("已删除", false);
            await host.RefreshAsync();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Native movie delete failed: movie={movie.Id}.");
            host.ShowStatus("删除失败：" + ex.Message, true);
        }
    }

    private static async Task DeleteFolderAsync(FolderCardItem folder, MediaContextMenuHost host)
    {
        var confirmed = await ConfirmAsync(host.XamlRoot, "删除目录", $"确定要删除目录 \"{folder.Title}\" 下的所有影片？此操作不可撤销。");
        if (!confirmed)
        {
            return;
        }

        try
        {
            await AppServices.MediaTree.Movie.DeleteFolderAsync(folder.Path, folder.MediaRoot);
            host.ShowStatus("已删除", false);
            await host.RefreshAsync();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Native folder delete failed: folder={folder.Path}.");
            host.ShowStatus("删除失败：" + ex.Message, true);
        }
    }

    private static async Task ToggleFolderSpecialsAsync(FolderCardItem folder, MediaContextMenuHost host)
    {
        try
        {
            await AppServices.MediaTree.Movie.SetFolderSpecialsAsync(folder.Path, folder.MediaRoot, !folder.Folder.ShowSpecials);
            host.ShowStatus(folder.Folder.ShowSpecials ? "已隐藏花絮" : "已显示花絮", false);
            await host.RefreshAsync();
        }
        catch (Exception ex)
        {
            ShellLogger.Error(ex, $"Native folder specials toggle failed: folder={folder.Path}.");
            host.ShowStatus("花絮显示设置失败：" + ex.Message, true);
        }
    }

    private static async Task<bool> ConfirmAsync(XamlRoot xamlRoot, string title, string message)
    {
        var dialog = FluentTheme.ApplyContentDialog(new ContentDialog
        {
            Title = title,
            Content = new TextBlock
            {
                Text = message,
                TextWrapping = TextWrapping.WrapWholeWords,
            },
            PrimaryButtonText = "确定",
            CloseButtonText = "取消",
            DefaultButton = ContentDialogButton.Close,
            XamlRoot = ResolveDialogXamlRoot(xamlRoot),
        });
        var result = await dialog.ShowAsync();
        return result == ContentDialogResult.Primary;
    }

    private static ComboBox CreateScraperBox(string header)
    {
        var scraperBox = FluentTheme.ApplyComboBox(new ComboBox { Header = header, MinWidth = 0 });
        AddScraperOption(scraperBox, "auto", "自动");
        AddScraperOption(scraperBox, "tmdb_movie", "TMDB 电影");
        AddScraperOption(scraperBox, "tmdb_tv", "TMDB 剧集/番剧");
        AddScraperOption(scraperBox, "tmdb_collection", "TMDB 合集");
        AddScraperOption(scraperBox, "bangumi", "Bangumi");
        AddScraperOption(scraperBox, "javdatabase", "Javdatabase");
        scraperBox.SelectedIndex = 0;
        return scraperBox;
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

    private static TextBlock StatusText(string text)
        => new()
        {
            Text = text,
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
        };

    private static StackPanel DialogStack(params UIElement[] children)
    {
        var stack = new StackPanel
        {
            Spacing = 12,
            MaxWidth = 720,
        };
        foreach (var child in children)
        {
            stack.Children.Add(child);
        }

        return stack;
    }

    private static ContentDialog CreateDialog(XamlRoot xamlRoot, string title, UIElement content, string primaryText)
        => FluentTheme.ApplyContentDialog(new ContentDialog
        {
            Title = title,
            Content = new ScrollViewer
            {
                Content = content,
                MaxWidth = 720,
                MaxHeight = 560,
                VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            },
            MaxWidth = 760,
            PrimaryButtonText = primaryText,
            CloseButtonText = "取消",
            DefaultButton = ContentDialogButton.Primary,
            XamlRoot = ResolveDialogXamlRoot(xamlRoot),
        });

    private static XamlRoot ResolveDialogXamlRoot(XamlRoot fallback)
        => AppServices.MainWindow?.Content?.XamlRoot ?? fallback;

    public static async Task<FrameworkElement> CreateScrapeResultRowAsync(ScrapeSearchResultDto result, string automationPrefix = "ContextScrapeResult")
    {
        var poster = await CreateScrapePosterAsync(result);
        var textStack = new StackPanel
        {
            Spacing = 5,
            VerticalAlignment = VerticalAlignment.Center,
        };
        textStack.Children.Add(new TextBlock
        {
            Text = ScrapeResultPresenter.DisplayTitle(result),
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = FluentTheme.TextPrimary,
            TextWrapping = TextWrapping.WrapWholeWords,
            MaxLines = 2,
        });

        var meta = ScrapeResultPresenter.MetadataParts(result);
        textStack.Children.Add(new TextBlock
        {
            Text = string.Join(" · ", meta),
            Foreground = FluentTheme.TextSecondary,
            TextWrapping = TextWrapping.WrapWholeWords,
            MaxLines = 2,
        });

        if (!string.IsNullOrWhiteSpace(result.Overview))
        {
            textStack.Children.Add(new TextBlock
            {
                Text = result.Overview,
                MaxLines = 3,
                Foreground = FluentTheme.TextTertiary,
                TextWrapping = TextWrapping.WrapWholeWords,
            });
        }

        var grid = new Grid
        {
            Padding = new Thickness(10),
            ColumnSpacing = 12,
            MinHeight = 132,
        };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.Children.Add(poster);
        Grid.SetColumn(textStack, 1);
        grid.Children.Add(textStack);

        var border = new Border
        {
            CornerRadius = FluentTheme.CardCornerRadius,
            Background = FluentTheme.LayerAlt,
            BorderBrush = FluentTheme.Border,
            BorderThickness = new Thickness(1),
            Margin = new Thickness(0, 0, 0, 8),
            MaxWidth = 700,
            Child = grid,
            Tag = result,
        };
        AutomationProperties.SetAutomationId(border, $"{automationPrefix}_{ScrapeResultPresenter.SanitizeAutomationId(result.SourceId)}");
        return border;
    }

    private static async Task<FrameworkElement> CreateScrapePosterAsync(ScrapeSearchResultDto result)
    {
        var placeholder = new TextBlock
        {
            Text = "无封面",
            FontSize = 12,
            Foreground = FluentTheme.TextTertiary,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
            TextAlignment = TextAlignment.Center,
        };
        var host = new Grid
        {
            Width = 76,
            Height = 112,
            Background = FluentTheme.ControlAlt,
            Children = { placeholder },
        };

        if (ScrapeResultPresenter.HasPoster(result))
        {
            try
            {
                var posterUrl = await AppServices.MediaTree.Api.BuildMediaAssetUrlAsync(result.PosterUrl);
                if (Uri.TryCreate(posterUrl, UriKind.Absolute, out var posterUri))
                {
                    var image = new Image
                    {
                        Source = new BitmapImage(posterUri),
                        Stretch = Stretch.UniformToFill,
                    };
                    image.ImageFailed += (_, _) => image.Visibility = Visibility.Collapsed;
                    host.Children.Add(image);
                }
            }
            catch (Exception ex)
            {
                ShellLogger.Error(ex, $"Failed to render native scrape poster: {result.PosterUrl}.");
            }
        }

        return new Border
        {
            Width = 76,
            Height = 112,
            CornerRadius = FluentTheme.MediaCornerRadius,
            Clip = new Microsoft.UI.Xaml.Media.RectangleGeometry
            {
                Rect = new global::Windows.Foundation.Rect(0, 0, 76, 112),
            },
            Background = FluentTheme.ControlAlt,
            Child = host,
        };
    }
}
