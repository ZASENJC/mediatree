using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using MediaTree.Windows.Models;

namespace MediaTree.Windows.Services;

public interface IMediaApiClient : IDisposable
{
    Uri BackendUri { get; }

    void SetBackendUri(Uri backendUri);

    void SetBearerToken(string token);

    Task<AuthStatusDto> GetAuthStatusAsync(CancellationToken cancellationToken = default);

    Task<AuthResponseDto> LoginAsync(string username, string password, CancellationToken cancellationToken = default);

    Task<AuthResponseDto> SetupAuthAsync(string username, string password, CancellationToken cancellationToken = default);

    Task ChangePasswordAsync(string oldUsername, string oldPassword, string newUsername, string newPassword, CancellationToken cancellationToken = default);

    Task<SetupStatusDto> GetSetupStatusAsync(CancellationToken cancellationToken = default);

    Task<MediaRootsResponseDto> GetMediaRootsAsync(CancellationToken cancellationToken = default);

    Task<List<LibrarySettingDto>> GetLibrarySettingsAsync(CancellationToken cancellationToken = default);

    Task<FoldersResponseDto> GetFoldersAsync(string mediaRoot = "", CancellationToken cancellationToken = default);

    Task SaveLibrarySettingAsync(LibrarySettingDto setting, CancellationToken cancellationToken = default);

    Task SetLibraryPasswordAsync(string mediaRoot, string password, CancellationToken cancellationToken = default);

    Task ScanAsync(string mediaRoot, CancellationToken cancellationToken = default);

    Task ClearLibraryAsync(string mediaRoot, CancellationToken cancellationToken = default);

    Task<ScanStatusDto> GetScanStatusAsync(string mediaRoot, CancellationToken cancellationToken = default);

    Task<ScanLogDto> GetScanLogAsync(string mediaRoot, int lines = 80, CancellationToken cancellationToken = default);

    Task<ConfigDto> GetConfigAsync(CancellationToken cancellationToken = default);

    Task SaveConfigAsync(IEnumerable<string> extraMediaRoots, CancellationToken cancellationToken = default);

    Task SaveTmdbConfigAsync(string accessToken, CancellationToken cancellationToken = default);

    Task SaveGlobalConfigAsync(ConfigDto config, CancellationToken cancellationToken = default);

    Uri BuildBackupUri(string backupType);

    Task<byte[]> DownloadBackupAsync(string backupType, CancellationToken cancellationToken = default);

    Task RestoreBackupAsync(string filePath, CancellationToken cancellationToken = default);

    Task<MoviesResponseDto> GetMoviesAsync(string mediaRoot, string folder, string search, string sort, int limit, int offset, CancellationToken cancellationToken = default);

    Task<MoviesResponseDto> GetRecentWatchedAsync(string mediaRoot, int limit, int offset, CancellationToken cancellationToken = default);

    Task<MoviesResponseDto> GetFavoritesAsync(string mediaRoot, string sort, int limit, int offset, CancellationToken cancellationToken = default);

    Task<FolderSpecialsResponseDto> GetFolderSpecialsAsync(string folder, string mediaRoot, bool includeMovies = false, CancellationToken cancellationToken = default);

    Task<FolderSpecialsResponseDto> SetFolderSpecialsAsync(string folder, string mediaRoot, bool showSpecials, CancellationToken cancellationToken = default);

    Task<SearchScrapeResponseDto> SearchScrapeAsync(string query, string scraper, string mediaRoot, CancellationToken cancellationToken = default);

    Task<ManualScrapeResultDto> ManualScrapeMovieAsync(int movieId, string query, string sourceId, string mediaType, string scraper, CancellationToken cancellationToken = default);

    Task<BasicActionResultDto> RescrapeMovieAsync(int movieId, CancellationToken cancellationToken = default);

    Task<BasicActionResultDto> RescrapeFolderAsync(string folder, string mediaRoot, CancellationToken cancellationToken = default);

    Task<BasicActionResultDto> ApplyFolderScrapeAsync(string folder, string mediaRoot, string sourceId, string source, string mediaType, CancellationToken cancellationToken = default);

    Task<AlternativeCoversResponseDto> GetAlternativeCoversAsync(int movieId, CancellationToken cancellationToken = default);

    Task<BasicActionResultDto> ChangeMovieCoverAsync(int movieId, string url, CancellationToken cancellationToken = default);

    Task<BasicActionResultDto> UploadMovieCoverAsync(int movieId, string filePath, CancellationToken cancellationToken = default);

    Task<BasicActionResultDto> ChangeFolderCoverAsync(string folder, string mediaRoot, string url, CancellationToken cancellationToken = default);

    Task<BasicActionResultDto> EditMovieAsync(int movieId, string title, string code, string actress, string releaseDate, int? duration, CancellationToken cancellationToken = default);

    Task<BasicActionResultDto> EditFolderAsync(string folder, string mediaRoot, string title, string code, string actress, string releaseDate, int? duration, CancellationToken cancellationToken = default);

    Task<BasicActionResultDto> DeleteMovieAsync(int movieId, CancellationToken cancellationToken = default);

    Task<BasicActionResultDto> DeleteFolderAsync(string folder, string mediaRoot, CancellationToken cancellationToken = default);

    Task AddTagAsync(int movieId, string tag, CancellationToken cancellationToken = default);

    Task RemoveTagAsync(int movieId, string tag, CancellationToken cancellationToken = default);

    Task<MovieDto> GetMovieDetailAsync(int movieId, CancellationToken cancellationToken = default);

    Task<ProgressDto> GetProgressAsync(int movieId, CancellationToken cancellationToken = default);

    Task<ProgressDto> SaveProgressAsync(int movieId, double position, double? duration, bool stopped, CancellationToken cancellationToken = default);

    Task<string> EnsureMediaTokenAsync(CancellationToken cancellationToken = default);

    Task<string> BuildCoverUrlAsync(int movieId, CancellationToken cancellationToken = default);

    Task<string> BuildEpisodeStillUrlAsync(int movieId, CancellationToken cancellationToken = default);

    Task<string> BuildMediaAssetUrlAsync(string source, CancellationToken cancellationToken = default);

    Task<string> BuildStreamUrlAsync(int movieId, CancellationToken cancellationToken = default);

    Task<MediaPlaybackSource> BuildPlaybackSourceAsync(int movieId, CancellationToken cancellationToken = default);

    Task<VersionInfoDto> GetVersionAsync(CancellationToken cancellationToken = default);

    Task<UpdateCheckResultDto> CheckForUpdatesAsync(CancellationToken cancellationToken = default);

    Task<UpdateStatusDto> GetUpdateStatusAsync(CancellationToken cancellationToken = default);

    Task<UpdateActionResultDto> PerformUpdateAsync(string version, string mode = "app-package", CancellationToken cancellationToken = default);

    Task<UpdateActionResultDto> RollbackUpdateAsync(CancellationToken cancellationToken = default);

    Task<ChangelogDto> GetChangelogAsync(string version, CancellationToken cancellationToken = default);
}
